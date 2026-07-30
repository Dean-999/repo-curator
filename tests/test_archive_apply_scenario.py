import hashlib
import json
import os
import fcntl
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from repo_curator.archive_apply import ArchiveApplyError, apply_archive, archive_destination, observe_apply_context


class ArchiveApplyScenarioTest(unittest.TestCase):
    def test_journal_is_hash_chained_and_committed_against_exact_approval(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "output.txt").write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, "output.txt")

            apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:00Z")

            journal = root / ".repo-curator" / "applies" / "plan-archive" / "apply-journal.jsonl"
            events = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(events[-1]["event_type"], "TRANSACTION_COMMITTED")
            previous = "sha256:" + "0" * 64
            approval_hash = "sha256:" + hashlib.sha256(
                json.dumps(approval, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
            ).hexdigest()
            for event in events:
                self.assertEqual(event["schema_version"], "repo-curator.apply-journal.v2")
                self.assertEqual(event["plan_sha256"], approval["approved_plan_sha256"])
                self.assertEqual(event["approval_sha256"], approval_hash)
                self.assertEqual(event["previous_event_hash"], previous)
                claimed = event.pop("event_hash")
                calculated = "sha256:" + hashlib.sha256(
                    json.dumps(event, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
                ).hexdigest()
                self.assertEqual(claimed, calculated)
                previous = claimed

    def test_repository_mutation_lock_rejects_a_second_owner(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / "output.txt").write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, "output.txt")
            control = root / ".repo-curator"
            control.mkdir()
            lock = os.open(control / "mutation.lock", os.O_RDWR | os.O_CREAT, 0o600)
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                with self.assertRaisesRegex(ArchiveApplyError, "MUTATION_LOCKED"):
                    apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:00Z")
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)
                os.close(lock)
    def test_approved_single_file_archive_moves_once_with_journal_and_provenance(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            source = root / "output.txt"
            source.write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, "output.txt")

            result = apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:00Z")

            destination = root / archive_destination("plan-archive", "output.txt")
            provenance = destination.with_name(destination.name + ".provenance.json")
            journal = root / ".repo-curator" / "applies" / "plan-archive" / "apply-journal.jsonl"
            self.assertEqual(result["status"], "APPLIED")
            self.assertFalse(source.exists())
            self.assertEqual(destination.read_text(encoding="utf-8"), "accepted output\n")
            self.assertEqual(json.loads(provenance.read_text(encoding="utf-8"))["original_path"], "output.txt")
            events = [json.loads(line)["event_type"] for line in journal.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(events, ["ACTION_VALIDATION_STARTED", "MOVE_STARTED", "DESTINATION_OBSERVED", "SOURCE_REMOVAL_OBSERVED", "ACTION_VERIFIED", "TRANSACTION_COMMITTED"])
            first_record = json.loads(journal.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(
                set(first_record),
                {
                    "action_id", "approval_id", "approval_sha256", "apply_run_id", "created_at",
                    "destination_observation", "error", "event_type",
                    "event_hash", "expected_state_hash", "journal_event_id", "observed_state_hash",
                    "operator_note", "plan_id", "plan_sha256", "previous_event_hash",
                    "rollback_action_id", "rollback_plan_id", "schema_version", "sequence",
                    "source_observation", "timestamp",
                },
            )

            repeated = apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:01Z")
            self.assertEqual(repeated["status"], "ALREADY_VERIFIED")
            self.assertEqual(destination.read_text(encoding="utf-8"), "accepted output\n")

    def test_apply_rejects_non_git_shadow_or_tampered_plan_before_moving(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            (root / "output.txt").write_text("output\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, "output.txt", repository_mode="FILESYSTEM")
            with self.assertRaisesRegex(ArchiveApplyError, "PREFLIGHT_REPOSITORY_MODE"):
                apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:00Z")
            self.assertTrue((root / "output.txt").exists())

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            source = root / "output.txt"
            source.write_text("output\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, "output.txt")
            tampered = plan_bytes.replace(b"output.txt", b"changed.txt", 1)
            with self.assertRaisesRegex(ArchiveApplyError, "APPROVAL_PLAN_HASH_MISMATCH"):
                apply_archive(root, tampered, approval, "2026-07-24T00:00:00Z")
            self.assertTrue(source.exists())

        with self.assertRaisesRegex(ArchiveApplyError, "PLAN_ARCHIVE_DESTINATION_INVALID"):
            archive_destination("plan-archive", "output\x00.txt")
        with self.assertRaisesRegex(ArchiveApplyError, "PLAN_ARCHIVE_DESTINATION_INVALID"):
            archive_destination("plan-archive\x00", "output.txt")

    def test_apply_accepts_a_linked_git_worktree_without_following_git_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            primary = temporary_path / "primary"
            linked = temporary_path / "linked"
            primary.mkdir()
            self._git(primary, "init")
            self._git(primary, "config", "user.email", "fixture@example.test")
            self._git(primary, "config", "user.name", "Fixture")
            (primary / "tracked.txt").write_text("fixture\n", encoding="utf-8")
            self._git(primary, "add", "tracked.txt")
            self._git(primary, "commit", "-m", "fixture")
            self._git(primary, "worktree", "add", "--detach", str(linked), "HEAD")
            (linked / "output.txt").write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(linked, "output.txt")

            result = apply_archive(linked, plan_bytes, approval, "2026-07-24T00:00:00Z")

            self.assertEqual(result["status"], "APPLIED")
            self.assertTrue((linked / archive_destination("plan-archive", "output.txt")).is_file())

    def test_apply_fails_closed_for_destination_drift_and_source_revalidation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            source = root / "output.txt"
            source.write_text("output\n", encoding="utf-8")
            destination = root / archive_destination("plan-archive", "output.txt")
            destination.parent.mkdir(parents=True)
            destination.write_text("existing\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, "output.txt")

            with self.assertRaisesRegex(ArchiveApplyError, "PATH_DESTINATION_EXISTS"):
                apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:00Z")
            self.assertTrue(source.exists())
            self.assertEqual(destination.read_text(encoding="utf-8"), "existing\n")

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            source = root / "output.txt"
            source.write_text("output\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, "output.txt")
            source.write_text("changed after approval\n", encoding="utf-8")

            with self.assertRaisesRegex(ArchiveApplyError, "DRIFT_REPOSITORY_STATE"):
                apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:00Z")
            self.assertTrue(source.exists())

    def test_apply_rejects_protected_and_external_symlink_sources(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            (root / ".git" / "config-copy").write_text("protected\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, ".git/config-copy")
            with self.assertRaisesRegex(ArchiveApplyError, "PATH_PROTECTED"):
                apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:00Z")

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            root = self._git_repository(temporary_path)
            outside = temporary_path / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            (root / "output.txt").symlink_to(outside)
            plan_bytes, approval = self._plan_and_approval(root, "output.txt", fingerprint=b"outside\n")
            with self.assertRaisesRegex(ArchiveApplyError, "PATH_EXTERNAL_SYMLINK"):
                apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:00Z")
            self.assertTrue(outside.exists())

    def test_state_observation_never_follows_an_external_symlink(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            root = self._git_repository(temporary_path)
            outside = temporary_path / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            (root / "link.txt").symlink_to(outside)

            context = observe_apply_context(root)

            self.assertTrue(context["repository_state_hash"].startswith("sha256:"))
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")

    def test_state_observation_rejects_a_directory_replaced_during_descriptor_open(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            root = self._git_repository(temporary_path)
            nested = root / "results"
            nested.mkdir()
            (nested / "output.txt").write_text("accepted output\n", encoding="utf-8")
            outside = temporary_path / "outside"
            outside.mkdir()
            (outside / "output.txt").write_text("outside\n", encoding="utf-8")
            actual_open = os.open
            swapped = False

            def swap_directory(name, flags, *args, **kwargs):
                nonlocal swapped
                if name == "results" and not swapped:
                    swapped = True
                    nested.rename(root / "results-old")
                    nested.symlink_to(outside, target_is_directory=True)
                return actual_open(name, flags, *args, **kwargs)

            with mock.patch("repo_curator.archive_apply.os.open", side_effect=swap_directory):
                with self.assertRaisesRegex(ArchiveApplyError, "DRIFT_REPOSITORY_STATE"):
                    observe_apply_context(root)
            self.assertEqual((outside / "output.txt").read_text(encoding="utf-8"), "outside\n")

    def test_state_observation_binds_git_head_even_when_worktree_content_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            self._git(root, "config", "user.email", "fixture@example.test")
            self._git(root, "config", "user.name", "Fixture")
            (root / "notes.txt").write_text("first\n", encoding="utf-8")
            self._git(root, "add", "notes.txt")
            self._git(root, "commit", "-m", "first")
            (root / "notes.txt").write_text("second\n", encoding="utf-8")
            self._git(root, "commit", "-am", "second")
            before = observe_apply_context(root)["repository_state_hash"]
            branch = subprocess.run(
                ["git", "symbolic-ref", "--short", "HEAD"], cwd=root, text=True,
                capture_output=True, check=True,
            ).stdout.strip()
            self._git(root, "update-ref", "refs/heads/" + branch, "HEAD^")

            after = observe_apply_context(root)["repository_state_hash"]

            self.assertNotEqual(before, after)

    def test_repeat_rejects_symlink_swapped_verified_destination(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            root = self._git_repository(temporary_path)
            (root / "output.txt").write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, "output.txt")
            apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:00Z")
            destination = root / archive_destination("plan-archive", "output.txt")
            outside = temporary_path / "outside.txt"
            outside.write_text("accepted output\n", encoding="utf-8")
            destination.unlink()
            destination.symlink_to(outside)

            with self.assertRaisesRegex(ArchiveApplyError, "MANUAL_RECOVERY_REQUIRED"):
                apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:01Z")
            self.assertEqual(outside.read_text(encoding="utf-8"), "accepted output\n")

    def test_repeat_rejects_symlink_swapped_journal(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            root = self._git_repository(temporary_path)
            (root / "output.txt").write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, "output.txt")
            apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:00Z")
            journal = root / ".repo-curator" / "applies" / "plan-archive" / "apply-journal.jsonl"
            outside = temporary_path / "outside-journal.jsonl"
            outside.write_text(journal.read_text(encoding="utf-8"), encoding="utf-8")
            journal.unlink()
            journal.symlink_to(outside)

            with self.assertRaisesRegex(ArchiveApplyError, "MANUAL_RECOVERY_REQUIRED"):
                apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:01Z")
            self.assertEqual(outside.read_text(encoding="utf-8"), outside.read_text(encoding="utf-8"))

    def test_provenance_failure_preserves_partial_state_and_blocks_repeat(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            source = root / "output.txt"
            source.write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, "output.txt")

            with mock.patch("repo_curator.archive_apply._provenance", side_effect=OSError("disk failure")):
                with self.assertRaisesRegex(ArchiveApplyError, "ACTION_FILESYSTEM_FAILURE"):
                    apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:00Z")

            destination = root / archive_destination("plan-archive", "output.txt")
            journal = root / ".repo-curator" / "applies" / "plan-archive" / "apply-journal.jsonl"
            self.assertTrue(source.is_file())
            self.assertTrue(destination.is_file())
            self.assertFalse(destination.with_name(destination.name + ".provenance.json").exists())
            self.assertIn("ACTION_FAILED", journal.read_text(encoding="utf-8"))

            with self.assertRaisesRegex(ArchiveApplyError, "MANUAL_RECOVERY_REQUIRED"):
                apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:01Z")
            self.assertTrue(source.is_file())
            self.assertTrue(destination.is_file())

    def test_symlink_swap_immediately_before_move_fails_closed_and_is_journaled(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            root = self._git_repository(temporary_path)
            source = root / "output.txt"
            source.write_text("accepted output\n", encoding="utf-8")
            outside = temporary_path / "outside.txt"
            outside.write_text("outside\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, "output.txt")
            actual_link = os.link

            def swap_then_link(source_name, destination_name, **kwargs):
                source.unlink()
                source.symlink_to(outside)
                return actual_link(source_name, destination_name, **kwargs)

            with mock.patch("repo_curator.archive_apply.os.link", side_effect=swap_then_link):
                with self.assertRaisesRegex(ArchiveApplyError, "ACTION_FILESYSTEM_FAILURE"):
                    apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:00Z")

            destination = root / archive_destination("plan-archive", "output.txt")
            journal = root / ".repo-curator" / "applies" / "plan-archive" / "apply-journal.jsonl"
            self.assertTrue(source.is_symlink())
            self.assertTrue(destination.is_symlink())
            self.assertEqual(outside.read_text(encoding="utf-8"), "outside\n")
            self.assertIn("ACTION_FAILED", journal.read_text(encoding="utf-8"))

            with self.assertRaisesRegex(ArchiveApplyError, "MANUAL_RECOVERY_REQUIRED"):
                apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:01Z")

    def test_postcondition_detects_source_recreated_after_verified_event(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            source = root / "output.txt"
            source.write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, "output.txt")
            from repo_curator.archive_apply import _event

            def recreate_after_verified(*args, **kwargs):
                _event(*args, **kwargs)
                if args[5] == "ACTION_VERIFIED":
                    source.write_text("newer content\n", encoding="utf-8")

            with mock.patch("repo_curator.archive_apply._event", side_effect=recreate_after_verified):
                with self.assertRaisesRegex(ArchiveApplyError, "VERIFY_POSTCONDITION"):
                    apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:00Z")

            destination = root / archive_destination("plan-archive", "output.txt")
            journal = root / ".repo-curator" / "applies" / "plan-archive" / "apply-journal.jsonl"
            self.assertEqual(source.read_text(encoding="utf-8"), "newer content\n")
            self.assertTrue(destination.is_file())
            self.assertIn("ACTION_FAILED", journal.read_text(encoding="utf-8"))

    def test_source_open_failure_is_recorded_after_validation_starts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = self._git_repository(Path(temporary_directory))
            source = root / "output.txt"
            source.write_text("accepted output\n", encoding="utf-8")
            plan_bytes, approval = self._plan_and_approval(root, "output.txt")
            actual_open_source = __import__("repo_curator.archive_apply", fromlist=["_open_source"])._open_source

            def remove_then_open(*args, **kwargs):
                source.unlink()
                return actual_open_source(*args, **kwargs)

            with mock.patch("repo_curator.archive_apply._open_source", side_effect=remove_then_open):
                with self.assertRaisesRegex(ArchiveApplyError, "DRIFT_SOURCE_MISSING"):
                    apply_archive(root, plan_bytes, approval, "2026-07-24T00:00:00Z")
            journal = root / ".repo-curator" / "applies" / "plan-archive" / "apply-journal.jsonl"
            events = [json.loads(line)["event_type"] for line in journal.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(events, ["ACTION_VALIDATION_STARTED", "ACTION_FAILED"])

    def _git_repository(self, temporary_path: Path) -> Path:
        root = temporary_path / "repository"
        root.mkdir()
        result = subprocess.run(["git", "init", "-q", str(root)], text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return root

    def _git(self, root: Path, *arguments: str) -> None:
        result = subprocess.run(["git", *arguments], cwd=root, text=True, capture_output=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)

    def _plan_and_approval(self, root: Path, source_path: str, repository_mode: str = "GIT_WORKTREE", fingerprint=None):
        context = observe_apply_context(root)
        payload = fingerprint if fingerprint is not None else (root / source_path).read_bytes()
        action = {
            "action_id": "archive-1", "affected_artifact_ids": ["art-output"],
            "affected_bytes": len(payload), "approval_required": True, "bundle_complete": True,
            "bundle_member_artifact_ids": ["art-output"], "case_collision": False,
            "destination_exists": False, "destination_path": archive_destination("plan-archive", source_path),
            "executable_in_supported_scope": True, "repository_mode": repository_mode,
            "same_filesystem": True, "source_external_symlink": False,
            "retention_closure_satisfied": True, "retention_evidence_ids": ["retention-archive"],
            "source_fingerprint": hashlib.sha256(payload).hexdigest(),
            "source_fingerprint_scheme": "sha256-file-v1", "source_path": source_path, "type": "ARCHIVE",
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
            "approval_id": "approval-archive", "approval_created_at": "2026-07-24T00:00:00Z",
            "approval_schema_version": "repo-curator.approval.v1", "approved_action_ids": ["archive-1"],
            "approved_plan_id": "plan-archive", "approved_plan_sha256": "sha256:" + hashlib.sha256(plan_bytes).hexdigest(),
            "approved_recommendation_ids": ["recommendation-archive"], "approving_actor": "reviewer",
            "decision_set_hash": context["decision_set_hash"], "effective_policy_hash": context["effective_policy_hash"],
            "mutation_budget": plan["mutation_budget"], "repository_state_hash": context["repository_state_hash"],
        }
        return plan_bytes, approval


if __name__ == "__main__":
    unittest.main()
