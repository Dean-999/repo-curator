import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from repo_curator.archive_apply import apply_archive, archive_destination, observe_apply_context
from repo_curator.quarantine_apply import apply_quarantine_batch, quarantine_destination
from repo_curator.recovery import RecoveryError, apply_rollback, reconcile_apply


class RecoveryScenarioTest(unittest.TestCase):
    def test_verified_archive_reconciles_to_a_separately_approved_rollback(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            source = root / "output.txt"
            source.write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._archive_plan(root)
            apply_archive(root, plan_bytes, approval, "2026-07-25T00:00:00Z")

            recovery = reconcile_apply(root, plan_bytes, approval, "2026-07-25T00:01:00Z")

            self.assertEqual(recovery["status"], "SAFE_ROLLBACK_ELIGIBLE")
            self.assertEqual(recovery["actions"], [{"action_id": "archive-1", "status": "VERIFIED"}])
            rollback = json.loads(recovery["rollback_plan_bytes"])
            self.assertEqual(rollback["action_candidates"][0]["source_path"], archive_destination("plan-archive", "output.txt"))
            self.assertEqual(rollback["action_candidates"][0]["destination_path"], "output.txt")
            rollback_approval = self._rollback_approval(recovery["rollback_plan_bytes"])

            result = apply_rollback(root, recovery["rollback_plan_bytes"], rollback_approval, "2026-07-25T00:02:00Z", plan_bytes, approval)

            self.assertEqual(result, {"restored_action_ids": ["rollback-archive-1"], "status": "ROLLED_BACK"})
            self.assertEqual(source.read_text(encoding="utf-8"), "accepted output\n")
            self.assertFalse((root / archive_destination("plan-archive", "output.txt")).exists())
            journal = root / ".repo-curator" / "applies" / "plan-archive" / "apply-journal.jsonl"
            self.assertEqual(
                [json.loads(line)["event_type"] for line in journal.read_text(encoding="utf-8").splitlines()][-2:],
                ["ROLLBACK_ACTION_VERIFIED", "ROLLBACK_COMPLETED"],
            )
            receipt = root / ".repo-curator" / "applies" / "plan-archive" / "rollback-receipts" / "rollback-archive-1.json"
            self.assertTrue(receipt.is_file())
            self.assertIn("provenance_sha256", json.loads(receipt.read_text(encoding="utf-8")))

            repeated = apply_rollback(root, recovery["rollback_plan_bytes"], rollback_approval, "2026-07-25T00:03:00Z", plan_bytes, approval)
            self.assertEqual(repeated, {"restored_action_ids": ["rollback-archive-1"], "status": "ALREADY_ROLLED_BACK"})

    def test_rollback_requires_original_plan_and_approval_bytes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "output.txt").write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._archive_plan(root)
            apply_archive(root, plan_bytes, approval, "2026-07-25T00:00:00Z")
            recovery = reconcile_apply(root, plan_bytes, approval, "2026-07-25T00:01:00Z")

            with self.assertRaisesRegex(RecoveryError, "ROLLBACK_ORIGINAL_EVIDENCE_REQUIRED"):
                apply_rollback(
                    root, recovery["rollback_plan_bytes"], self._rollback_approval(recovery["rollback_plan_bytes"]),
                    "2026-07-25T00:02:00Z",
                )

    def test_rollback_refuses_to_overwrite_newer_source_content(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "output.txt").write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._archive_plan(root)
            apply_archive(root, plan_bytes, approval, "2026-07-25T00:00:00Z")
            recovery = reconcile_apply(root, plan_bytes, approval, "2026-07-25T00:01:00Z")
            rollback_approval = self._rollback_approval(recovery["rollback_plan_bytes"])
            (root / "output.txt").write_text("newer content\n", encoding="utf-8")

            with self.assertRaisesRegex(RecoveryError, "ROLLBACK_DESTINATION_EXISTS"):
                apply_rollback(root, recovery["rollback_plan_bytes"], rollback_approval, "2026-07-25T00:02:00Z", plan_bytes, approval)

            self.assertEqual((root / "output.txt").read_text(encoding="utf-8"), "newer content\n")
            self.assertTrue((root / archive_destination("plan-archive", "output.txt")).is_file())

    def test_rollback_refuses_when_provenance_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "output.txt").write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._archive_plan(root)
            apply_archive(root, plan_bytes, approval, "2026-07-25T00:00:00Z")
            recovery = reconcile_apply(root, plan_bytes, approval, "2026-07-25T00:01:00Z")
            rollback_approval = self._rollback_approval(recovery["rollback_plan_bytes"])
            destination = root / archive_destination("plan-archive", "output.txt")
            destination.with_name(destination.name + ".provenance.json").unlink()

            with self.assertRaisesRegex(RecoveryError, "ROLLBACK_PROVENANCE_MISSING"):
                apply_rollback(root, recovery["rollback_plan_bytes"], rollback_approval, "2026-07-25T00:02:00Z", plan_bytes, approval)
            self.assertFalse((root / "output.txt").exists())
            self.assertTrue(destination.is_file())

    def test_scalar_provenance_requires_manual_recovery_without_crashing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "output.txt").write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._archive_plan(root)
            apply_archive(root, plan_bytes, approval, "2026-07-25T00:00:00Z")
            destination = root / archive_destination("plan-archive", "output.txt")
            destination.with_name(destination.name + ".provenance.json").write_text("42\n", encoding="utf-8")

            recovery = reconcile_apply(root, plan_bytes, approval, "2026-07-25T00:01:00Z")

            self.assertEqual(recovery["status"], "MANUAL_RECOVERY_REQUIRED")
            self.assertEqual(recovery["actions"], [{"action_id": "archive-1", "status": "AMBIGUOUS"}])

    def test_rollback_refuses_when_the_original_journal_changed_after_reconciliation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "output.txt").write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._archive_plan(root)
            apply_archive(root, plan_bytes, approval, "2026-07-25T00:00:00Z")
            recovery = reconcile_apply(root, plan_bytes, approval, "2026-07-25T00:01:00Z")
            rollback_approval = self._rollback_approval(recovery["rollback_plan_bytes"])
            journal = root / ".repo-curator" / "applies" / "plan-archive" / "apply-journal.jsonl"
            journal.write_text(journal.read_text(encoding="utf-8") + "{}\n", encoding="utf-8")

            with self.assertRaisesRegex(RecoveryError, "ROLLBACK_JOURNAL_DRIFT"):
                apply_rollback(root, recovery["rollback_plan_bytes"], rollback_approval, "2026-07-25T00:02:00Z", plan_bytes, approval)

            self.assertFalse((root / "output.txt").exists())
            self.assertTrue((root / archive_destination("plan-archive", "output.txt")).is_file())

    def test_rollback_requires_the_exact_separately_approved_action_set(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "output.txt").write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._archive_plan(root)
            apply_archive(root, plan_bytes, approval, "2026-07-25T00:00:00Z")
            recovery = reconcile_apply(root, plan_bytes, approval, "2026-07-25T00:01:00Z")
            rollback_approval = self._rollback_approval(recovery["rollback_plan_bytes"])
            rollback_approval["approved_action_ids"] = []

            with self.assertRaisesRegex(RecoveryError, "ROLLBACK_APPROVAL_SCOPE_EXPANSION"):
                apply_rollback(root, recovery["rollback_plan_bytes"], rollback_approval, "2026-07-25T00:02:00Z", plan_bytes, approval)

            self.assertFalse((root / "output.txt").exists())
            self.assertTrue((root / archive_destination("plan-archive", "output.txt")).is_file())

    def test_rollback_filesystem_failure_is_journaled_without_hiding_partial_state(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "output.txt").write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._archive_plan(root)
            apply_archive(root, plan_bytes, approval, "2026-07-25T00:00:00Z")
            recovery = reconcile_apply(root, plan_bytes, approval, "2026-07-25T00:01:00Z")
            rollback_approval = self._rollback_approval(recovery["rollback_plan_bytes"])
            payload = root / archive_destination("plan-archive", "output.txt")
            original_unlink = os.unlink

            def reject_payload_removal(name, *args, **kwargs):
                if name == payload.name:
                    raise OSError("injected rollback payload removal failure")
                return original_unlink(name, *args, **kwargs)

            with mock.patch("repo_curator.recovery.os.unlink", side_effect=reject_payload_removal):
                with self.assertRaisesRegex(RecoveryError, "ROLLBACK_FILESYSTEM_FAILURE"):
                    apply_rollback(root, recovery["rollback_plan_bytes"], rollback_approval, "2026-07-25T00:02:00Z", plan_bytes, approval)

            self.assertEqual((root / "output.txt").read_text(encoding="utf-8"), "accepted output\n")
            self.assertTrue(payload.is_file())
            journal = root / ".repo-curator" / "applies" / "plan-archive" / "apply-journal.jsonl"
            self.assertEqual(json.loads(journal.read_text(encoding="utf-8").splitlines()[-1])["event_type"], "ROLLBACK_FAILED")

    def test_partial_move_is_manual_recovery_and_never_generates_rollback(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "output.txt").write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._archive_plan(root)
            with mock.patch("repo_curator.archive_apply._provenance", side_effect=OSError("injected")):
                with self.assertRaises(Exception):
                    apply_archive(root, plan_bytes, approval, "2026-07-25T00:00:00Z")

            recovery = reconcile_apply(root, plan_bytes, approval, "2026-07-25T00:01:00Z")

            self.assertEqual(recovery["status"], "MANUAL_RECOVERY_REQUIRED")
            self.assertEqual(recovery["actions"], [{"action_id": "archive-1", "status": "MOVED"}])
            self.assertNotIn("rollback_plan_bytes", recovery)

    def test_scalar_json_journal_requires_manual_recovery_without_crashing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "output.txt").write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._archive_plan(root)
            journal = root / ".repo-curator" / "applies" / "plan-archive" / "apply-journal.jsonl"
            journal.parent.mkdir(parents=True)
            journal.write_text("42\n", encoding="utf-8")

            recovery = reconcile_apply(root, plan_bytes, approval, "2026-07-25T00:01:00Z")

            self.assertEqual(recovery["status"], "MANUAL_RECOVERY_REQUIRED")
            self.assertEqual(recovery["actions"], [{"action_id": "archive-1", "status": "AMBIGUOUS"}])

    def test_verified_quarantine_is_restored_only_from_its_plan_scoped_payload(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "obsolete.txt").write_text("obsolete\n", encoding="utf-8")
            plan_bytes, approval = self._quarantine_plan(root)
            apply_quarantine_batch(root, plan_bytes, approval, "2026-07-25T00:00:00Z")

            recovery = reconcile_apply(root, plan_bytes, approval, "2026-07-25T00:01:00Z")
            result = apply_rollback(root, recovery["rollback_plan_bytes"], self._rollback_approval(recovery["rollback_plan_bytes"]), "2026-07-25T00:02:00Z", plan_bytes, approval)

            self.assertEqual(result["status"], "ROLLED_BACK")
            self.assertEqual((root / "obsolete.txt").read_text(encoding="utf-8"), "obsolete\n")
            self.assertFalse((root / quarantine_destination("plan-quarantine", "obsolete.txt")).exists())

    def _git_repository(self, temporary_path: Path) -> Path:
        root = temporary_path / "repository"
        root.mkdir()
        result = subprocess.run(["git", "init", "-q", str(root)], text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return root

    def _archive_plan(self, root: Path):
        context = observe_apply_context(root)
        payload = (root / "output.txt").read_bytes()
        action = {
            "action_id": "archive-1", "affected_artifact_ids": ["art-output"], "affected_bytes": len(payload),
            "approval_required": True, "bundle_complete": True, "bundle_member_artifact_ids": ["art-output"],
            "case_collision": False, "destination_exists": False,
            "destination_path": archive_destination("plan-archive", "output.txt"), "executable_in_supported_scope": True,
            "repository_mode": "GIT_WORKTREE", "retention_closure_satisfied": True,
            "retention_evidence_ids": ["retention-archive"], "same_filesystem": True, "source_external_symlink": False,
            "source_fingerprint": hashlib.sha256(payload).hexdigest(), "source_path": "output.txt", "type": "ARCHIVE",
        }
        plan = {
            "action_candidates": [action], "decision_set_hash": context["decision_set_hash"],
            "effective_policy_hash": context["effective_policy_hash"], "execution_mode": "APPLY_READY",
            "mutation_budget": {"max_actions": 1, "max_affected_bytes": len(payload), "max_blast_radius": 1},
            "plan_id": "plan-archive", "planner": "repo_curator.archive_tracer.v1",
            "recommendation_ids": ["recommendation-archive"], "repository_state_hash": context["repository_state_hash"],
            "schema_version": "repo-curator.archive-plan.v1",
        }
        plan_bytes = json.dumps(plan, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
        approval = {
            "approval_id": "approval-archive", "approval_created_at": "2026-07-25T00:00:00Z",
            "approval_schema_version": "repo-curator.approval.v1", "approved_action_ids": ["archive-1"],
            "approved_plan_id": "plan-archive", "approved_plan_sha256": "sha256:" + hashlib.sha256(plan_bytes).hexdigest(),
            "approved_recommendation_ids": ["recommendation-archive"], "approving_actor": "reviewer",
            "decision_set_hash": context["decision_set_hash"], "effective_policy_hash": context["effective_policy_hash"],
            "mutation_budget": plan["mutation_budget"], "repository_state_hash": context["repository_state_hash"],
        }
        return plan_bytes, approval

    def _rollback_approval(self, payload: bytes):
        plan = json.loads(payload)
        return {
            "approval_id": "approval-rollback", "approved_plan_id": plan["plan_id"],
            "approved_plan_sha256": "sha256:" + hashlib.sha256(payload).hexdigest(),
            "approved_action_ids": [action["action_id"] for action in plan["action_candidates"]],
        }

    def _quarantine_plan(self, root: Path):
        context = observe_apply_context(root)
        payload = (root / "obsolete.txt").read_bytes()
        action = {
            "action_id": "quarantine-1", "affected_artifact_ids": ["art-obsolete"], "affected_bytes": len(payload),
            "approval_required": True, "bundle_complete": True, "bundle_id": "bundle-obsolete",
            "bundle_member_action_ids": ["quarantine-1"], "bundle_member_artifact_ids": ["art-obsolete"],
            "case_collision": False, "destination_exists": False,
            "destination_path": quarantine_destination("plan-quarantine", "obsolete.txt"), "executable_in_supported_scope": True,
            "repository_mode": "GIT_WORKTREE", "resolution_status": "RESOLVED",
            "retention_closure_satisfied": True, "retention_evidence_ids": ["retention-quarantine"], "same_filesystem": True,
            "source_external_symlink": False, "source_fingerprint": hashlib.sha256(payload).hexdigest(),
            "source_path": "obsolete.txt", "type": "QUARANTINE",
        }
        plan = {
            "action_candidates": [action], "decision_set_hash": context["decision_set_hash"],
            "effective_policy_hash": context["effective_policy_hash"], "execution_mode": "APPLY_READY",
            "mutation_budget": {"max_actions": 1, "max_affected_bytes": len(payload), "max_blast_radius": 1},
            "plan_id": "plan-quarantine", "planner": "repo_curator.quarantine_batch.v1",
            "recommendation_ids": ["recommendation-quarantine"], "repository_state_hash": context["repository_state_hash"],
            "schema_version": "repo-curator.quarantine-plan.v1",
        }
        plan_bytes = json.dumps(plan, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
        approval = {
            "approval_id": "approval-quarantine", "approval_created_at": "2026-07-25T00:00:00Z",
            "approval_schema_version": "repo-curator.approval.v1", "approved_action_ids": ["quarantine-1"],
            "approved_plan_id": "plan-quarantine", "approved_plan_sha256": "sha256:" + hashlib.sha256(plan_bytes).hexdigest(),
            "approved_recommendation_ids": ["recommendation-quarantine"], "approving_actor": "reviewer",
            "decision_set_hash": context["decision_set_hash"], "effective_policy_hash": context["effective_policy_hash"],
            "mutation_budget": plan["mutation_budget"], "repository_state_hash": context["repository_state_hash"],
        }
        return plan_bytes, approval


if __name__ == "__main__":
    unittest.main()
