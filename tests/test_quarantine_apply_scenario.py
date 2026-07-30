import hashlib
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from repo_curator.archive_apply import ArchiveApplyError, observe_apply_context
from repo_curator.quarantine_apply import (
    apply_quarantine_batch,
    quarantine_destination,
)


class QuarantineApplyScenarioTest(unittest.TestCase):
    def test_approved_complete_batch_moves_all_bundle_members_to_plan_scope(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "obsolete-a.txt").write_text("obsolete a\n", encoding="utf-8")
            (root / "obsolete-b.txt").write_text("obsolete b\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, ["obsolete-a.txt", "obsolete-b.txt"])

            result = apply_quarantine_batch(root, plan_bytes, approval, "2026-07-24T00:00:00Z")

            self.assertEqual(result, {
                "completed_action_ids": ["quarantine-1", "quarantine-2"],
                "failed_action_id": None,
                "skipped_action_ids": [],
                "status": "APPLIED",
            })
            for source_path in ("obsolete-a.txt", "obsolete-b.txt"):
                destination = root / quarantine_destination("plan-quarantine", source_path)
                self.assertFalse((root / source_path).exists())
                self.assertEqual(destination.read_text(encoding="utf-8"), "obsolete " + source_path[9] + "\n")
                self.assertEqual(
                    json.loads(destination.with_name(destination.name + ".provenance.json").read_text(encoding="utf-8"))["original_path"],
                    source_path,
                )
            journal = root / ".repo-curator" / "applies" / "plan-quarantine" / "apply-journal.jsonl"
            events = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(
                [event["event_type"] for event in events],
                [
                    "ACTION_VALIDATION_STARTED", "MOVE_STARTED", "DESTINATION_OBSERVED",
                    "SOURCE_REMOVAL_OBSERVED", "ACTION_VERIFIED",
                    "ACTION_VALIDATION_STARTED", "MOVE_STARTED", "DESTINATION_OBSERVED",
                    "SOURCE_REMOVAL_OBSERVED", "ACTION_VERIFIED",
                    "TRANSACTION_COMMITTED",
                ],
            )

            repeated = apply_quarantine_batch(root, plan_bytes, approval, "2026-07-24T00:00:01Z")
            self.assertEqual(repeated, {
                "completed_action_ids": ["quarantine-1", "quarantine-2"],
                "failed_action_id": None,
                "skipped_action_ids": [],
                "status": "ALREADY_VERIFIED",
            })

    def test_repeat_rejects_a_journal_that_does_not_prove_every_completed_action(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "obsolete-a.txt").write_text("obsolete a\n", encoding="utf-8")
            (root / "obsolete-b.txt").write_text("obsolete b\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, ["obsolete-a.txt", "obsolete-b.txt"])
            apply_quarantine_batch(root, plan_bytes, approval, "2026-07-24T00:00:00Z")
            journal = root / ".repo-curator" / "applies" / "plan-quarantine" / "apply-journal.jsonl"
            lines = journal.read_text(encoding="utf-8").splitlines()
            journal.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(ArchiveApplyError, "MANUAL_RECOVERY_REQUIRED"):
                apply_quarantine_batch(root, plan_bytes, approval, "2026-07-24T00:00:01Z")

    def test_repeat_rejects_scalar_provenance_with_a_stable_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "obsolete-a.txt").write_text("obsolete a\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, ["obsolete-a.txt"])
            apply_quarantine_batch(root, plan_bytes, approval, "2026-07-24T00:00:00Z")
            destination = root / quarantine_destination("plan-quarantine", "obsolete-a.txt")
            destination.with_name(destination.name + ".provenance.json").write_text("42\n", encoding="utf-8")

            with self.assertRaisesRegex(ArchiveApplyError, "MANUAL_RECOVERY_REQUIRED"):
                apply_quarantine_batch(root, plan_bytes, approval, "2026-07-24T00:00:01Z")

    def test_existing_apply_scope_without_a_journal_requires_recovery(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "obsolete-a.txt").write_text("obsolete a\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, ["obsolete-a.txt"])
            (root / ".repo-curator" / "applies" / "plan-quarantine").mkdir(parents=True)

            with self.assertRaisesRegex(ArchiveApplyError, "MANUAL_RECOVERY_REQUIRED"):
                apply_quarantine_batch(root, plan_bytes, approval, "2026-07-24T00:00:00Z")
            self.assertTrue((root / "obsolete-a.txt").is_file())

    def test_non_journaled_state_drift_between_actions_stops_the_batch(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "obsolete-a.txt").write_text("obsolete a\n", encoding="utf-8")
            (root / "obsolete-b.txt").write_text("obsolete b\n", encoding="utf-8")
            independent = root / "unrelated.txt"
            independent.write_text("before\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, ["obsolete-a.txt", "obsolete-b.txt"])
            from repo_curator.quarantine_apply import _execute_action

            def drift_after_first(*args, **kwargs):
                _execute_action(*args, **kwargs)
                if args[4]["action_id"] == "quarantine-1":
                    independent.write_text("changed outside batch\n", encoding="utf-8")

            with mock.patch("repo_curator.quarantine_apply._execute_action", side_effect=drift_after_first):
                result = apply_quarantine_batch(root, plan_bytes, approval, "2026-07-24T00:00:00Z")

            self.assertEqual(result["status"], "PARTIAL_FAILURE")
            self.assertEqual(result["completed_action_ids"], ["quarantine-1"])
            self.assertEqual(result["failed_action_id"], "quarantine-2")
            self.assertTrue((root / "obsolete-b.txt").is_file())
            journal = root / ".repo-curator" / "applies" / "plan-quarantine" / "apply-journal.jsonl"
            self.assertIn("DRIFT_REPOSITORY_STATE", journal.read_text(encoding="utf-8"))

    def test_postcondition_detects_source_recreated_after_verified_event(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            source = root / "obsolete-a.txt"
            source.write_text("obsolete a\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, ["obsolete-a.txt"])
            from repo_curator.quarantine_apply import _event

            def recreate_after_verified(*args, **kwargs):
                _event(*args, **kwargs)
                if args[5] == "ACTION_VERIFIED":
                    source.write_text("newer content\n", encoding="utf-8")

            with mock.patch("repo_curator.quarantine_apply._event", side_effect=recreate_after_verified):
                result = apply_quarantine_batch(root, plan_bytes, approval, "2026-07-24T00:00:00Z")

            self.assertEqual(result["status"], "PARTIAL_FAILURE")
            self.assertEqual(result["failed_action_id"], "quarantine-1")
            self.assertEqual(source.read_text(encoding="utf-8"), "newer content\n")
            destination = root / quarantine_destination("plan-quarantine", "obsolete-a.txt")
            self.assertTrue(destination.is_file())
            journal = root / ".repo-curator" / "applies" / "plan-quarantine" / "apply-journal.jsonl"
            self.assertIn("VERIFY_POSTCONDITION", journal.read_text(encoding="utf-8"))

    def test_complete_prevalidation_blocks_every_move_when_any_action_is_unsafe(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "obsolete-a.txt").write_text("obsolete a\n", encoding="utf-8")
            (root / "obsolete-b.txt").write_text("obsolete b\n", encoding="utf-8")
            existing = root / quarantine_destination("plan-quarantine", "obsolete-b.txt")
            existing.parent.mkdir(parents=True)
            existing.write_text("occupied\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, ["obsolete-a.txt", "obsolete-b.txt"])

            with self.assertRaisesRegex(ArchiveApplyError, "PATH_DESTINATION_EXISTS"):
                apply_quarantine_batch(root, plan_bytes, approval, "2026-07-24T00:00:00Z")

            self.assertTrue((root / "obsolete-a.txt").is_file())
            self.assertTrue((root / "obsolete-b.txt").is_file())
            self.assertEqual(existing.read_text(encoding="utf-8"), "occupied\n")
            self.assertFalse((root / ".repo-curator" / "applies" / "plan-quarantine").exists())

    def test_failure_records_partial_state_and_skips_remaining_actions_without_rollback(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            for name in ("obsolete-a.txt", "obsolete-b.txt", "obsolete-c.txt"):
                (root / name).write_text(name + "\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(
                root, ["obsolete-a.txt", "obsolete-b.txt", "obsolete-c.txt"]
            )

            from repo_curator.quarantine_apply import _provenance

            def fail_second_provenance(parent_fd, name, *args):
                if name.endswith("obsolete-b.txt"):
                    raise OSError("injected failure")
                return _provenance(parent_fd, name, *args)

            with mock.patch("repo_curator.quarantine_apply._provenance", side_effect=fail_second_provenance):
                result = apply_quarantine_batch(root, plan_bytes, approval, "2026-07-24T00:00:00Z")

            self.assertEqual(result, {
                "completed_action_ids": ["quarantine-1"],
                "failed_action_id": "quarantine-2",
                "skipped_action_ids": ["quarantine-3"],
                "status": "PARTIAL_FAILURE",
            })
            self.assertFalse((root / "obsolete-a.txt").exists())
            self.assertTrue((root / "obsolete-b.txt").is_file())
            self.assertTrue((root / "obsolete-c.txt").is_file())
            self.assertTrue((root / quarantine_destination("plan-quarantine", "obsolete-a.txt")).is_file())
            self.assertTrue((root / quarantine_destination("plan-quarantine", "obsolete-b.txt")).is_file())
            self.assertFalse((root / quarantine_destination("plan-quarantine", "obsolete-c.txt")).exists())
            journal = root / ".repo-curator" / "applies" / "plan-quarantine" / "apply-journal.jsonl"
            events = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
            self.assertIn(("quarantine-2", "ACTION_FAILED"), {(event["action_id"], event["event_type"]) for event in events})
            self.assertIn(("quarantine-3", "ACTION_SKIPPED"), {(event["action_id"], event["event_type"]) for event in events})

    def test_rejects_redirected_quarantine_destination_and_incomplete_bundle_before_writing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "obsolete-a.txt").write_text("obsolete a\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, ["obsolete-a.txt"])
            plan = json.loads(plan_bytes)
            plan["action_candidates"][0]["destination_path"] = ".repo-curator/quarantine/plan-quarantine/redirect"
            redirected, approval = self._reapprove(plan)

            with self.assertRaisesRegex(ArchiveApplyError, "PLAN_QUARANTINE_DESTINATION_INVALID"):
                apply_quarantine_batch(root, redirected, approval, "2026-07-24T00:00:00Z")
            self.assertTrue((root / "obsolete-a.txt").is_file())

            plan = json.loads(plan_bytes)
            plan["action_candidates"][0]["destination_path"] = ".repo-curator/quarantine/other-plan/redirect"
            other_plan, approval = self._reapprove(plan)
            with self.assertRaisesRegex(ArchiveApplyError, "PATH_PROTECTED"):
                apply_quarantine_batch(root, other_plan, approval, "2026-07-24T00:00:00Z")
            self.assertTrue((root / "obsolete-a.txt").is_file())

            plan = json.loads(plan_bytes)
            plan["action_candidates"][0]["bundle_member_action_ids"] = ["missing"]
            incomplete, approval = self._reapprove(plan)
            with self.assertRaisesRegex(ArchiveApplyError, "BUNDLE_PARTIAL_MOVEMENT"):
                apply_quarantine_batch(root, incomplete, approval, "2026-07-24T00:00:00Z")
            self.assertTrue((root / "obsolete-a.txt").is_file())

            plan = json.loads(plan_bytes)
            plan["action_candidates"][0]["resolution_status"] = "UNRESOLVED"
            unresolved, approval = self._reapprove(plan)
            with self.assertRaisesRegex(ArchiveApplyError, "ACTION_UNRESOLVED"):
                apply_quarantine_batch(root, unresolved, approval, "2026-07-24T00:00:00Z")

    def _git_repository(self, temporary_path: Path) -> Path:
        root = temporary_path / "repository"
        root.mkdir()
        self._git(root, "init", "-q")
        return root

    def _git(self, root: Path, *arguments: str) -> None:
        result = subprocess.run(["git", *arguments], cwd=root, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def _plan_and_approval(self, root: Path, source_paths):
        context = observe_apply_context(root)
        action_ids = ["quarantine-{}".format(index) for index in range(1, len(source_paths) + 1)]
        actions = []
        for index, source_path in enumerate(source_paths, 1):
            payload = (root / source_path).read_bytes()
            actions.append({
                "action_id": action_ids[index - 1],
                "affected_artifact_ids": ["art-{}".format(index)],
                "affected_bytes": len(payload),
                "approval_required": True,
                "bundle_complete": True,
                "bundle_id": "bundle-obsolete",
                "bundle_member_action_ids": action_ids,
                "bundle_member_artifact_ids": ["art-{}".format(index)],
                "case_collision": False,
                "destination_exists": False,
                "destination_path": quarantine_destination("plan-quarantine", source_path),
                "executable_in_supported_scope": True,
                "repository_mode": "GIT_WORKTREE",
                "retention_closure_satisfied": True,
                "retention_evidence_ids": ["retention-quarantine"],
                "resolution_status": "RESOLVED",
                "same_filesystem": True,
                "source_external_symlink": False,
                "source_fingerprint": hashlib.sha256(payload).hexdigest(),
                "source_path": source_path,
                "type": "QUARANTINE",
            })
        plan = {
            "action_candidates": actions,
            "decision_set_hash": context["decision_set_hash"],
            "effective_policy_hash": context["effective_policy_hash"],
            "execution_mode": "APPLY_READY",
            "mutation_budget": {
                "max_actions": len(actions),
                "max_affected_bytes": sum(action["affected_bytes"] for action in actions),
                "max_blast_radius": len(actions),
            },
            "plan_id": "plan-quarantine",
            "planner": "repo_curator.quarantine_batch.v1",
            "recommendation_ids": ["recommendation-{}".format(index) for index in range(1, len(actions) + 1)],
            "repository_state_hash": context["repository_state_hash"],
            "schema_version": "repo-curator.quarantine-plan.v1",
        }
        return self._reapprove(plan)

    def _reapprove(self, plan):
        plan_bytes = json.dumps(plan, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
        approval = {
            "approval_id": "approval-quarantine",
            "approval_created_at": "2026-07-24T00:00:00Z",
            "approval_schema_version": "repo-curator.approval.v1",
            "approved_action_ids": [action["action_id"] for action in plan["action_candidates"]],
            "approved_plan_id": plan["plan_id"],
            "approved_plan_sha256": "sha256:" + hashlib.sha256(plan_bytes).hexdigest(),
            "approved_recommendation_ids": plan["recommendation_ids"],
            "approving_actor": "reviewer",
            "decision_set_hash": plan["decision_set_hash"],
            "effective_policy_hash": plan["effective_policy_hash"],
            "mutation_budget": plan["mutation_budget"],
            "repository_state_hash": plan["repository_state_hash"],
        }
        return plan_bytes, approval


if __name__ == "__main__":
    unittest.main()
