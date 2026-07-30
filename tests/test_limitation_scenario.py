import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from repo_curator import declarations, inventory, scanner
from repo_curator.budgets import AuditBudgets


FIXED_RUN_ID = "limitation-fixture-run"
FIXED_CREATED_AT = "2026-07-19T00:00:00Z"


class LimitationScenarioTest(unittest.TestCase):
    def test_large_file_is_retained_without_hashing_past_the_budget(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "README.md").write_text("small\n", encoding="utf-8")
            (repository / "large.bin").write_bytes(b"0123456789")

            result = self._run_audit(repository, "--max-file-bytes", "8")

            self.assertEqual(result.returncode, 0, result.stderr)
            records = self._records(repository)
            large_record = next(
                record for record in records if record["repository_relative_path"] == "large.bin"
            )
            run_record = self._run_record(repository)
            self.assertIsNone(large_record["content_id"])
            self.assertIsNone(large_record["fingerprint"])
            self.assertIn("CONTENT_HASH_SKIPPED_SIZE_LIMIT", large_record["warnings"])
            root_record = next(
                record for record in records if record["repository_relative_path"] == "."
            )
            self.assertIsNone(root_record["content_id"])
            self.assertIsNone(root_record["fingerprint"])
            self.assertIn("CONTENT_HASH_SKIPPED_SIZE_LIMIT", root_record["warnings"])
            self.assertEqual(
                run_record["resource_budgets"],
                {
                    "max_artifacts": 100_000,
                    "max_depth": 128,
                    "max_directory_entries": 50_000,
                    "max_file_bytes": 8,
                    "max_total_hash_bytes": 1_073_741_824,
                },
            )
            self.assertEqual(run_record["final_status"], "COMPLETED_WITH_LIMITATIONS")
            self.assertIn("CONTENT_HASH_SKIPPED_SIZE_LIMIT", run_record["warnings"])
            self.assertIn(
                "CONTENT_HASH_SKIPPED_SIZE_LIMIT",
                run_record["component_states"]["inventory"]["warnings"],
            )

    def test_one_unreadable_artifact_does_not_abort_other_records(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "README.md").write_text("kept\n", encoding="utf-8")
            (repository / "blocked.txt").write_text("not-read\n", encoding="utf-8")
            original_open = scanner.os.open

            def deny_blocked(name, flags, *args, **kwargs):
                if name == "blocked.txt":
                    raise PermissionError("deterministic denial")
                return original_open(name, flags, *args, **kwargs)

            with mock.patch.object(scanner.os, "open", side_effect=deny_blocked):
                inventory.audit_repository(
                    repository,
                    FIXED_RUN_ID,
                    FIXED_CREATED_AT,
                    AuditBudgets(),
                )

            records = self._records(repository)
            by_path = {record["repository_relative_path"]: record for record in records}
            self.assertIn("README.md", by_path)
            self.assertIn("ARTIFACT_UNREADABLE", by_path["blocked.txt"]["warnings"])
            self.assertIsNone(by_path["blocked.txt"]["content_id"])
            self.assertEqual(self._run_record(repository)["final_status"], "COMPLETED_WITH_LIMITATIONS")

    def test_fifo_swap_uses_nonblocking_open_and_is_changed_not_unreadable(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "README.md").write_text("kept\n", encoding="utf-8")
            (repository / "swapped.txt").write_text("state\n", encoding="utf-8")
            original_open = scanner.os.open
            read_descriptor, write_descriptor = os.pipe()
            observed_flags = []

            def simulate_fifo_swap(name, flags, *args, **kwargs):
                if name == "swapped.txt":
                    observed_flags.append(flags)
                    return os.dup(read_descriptor)
                return original_open(name, flags, *args, **kwargs)

            try:
                with mock.patch.object(scanner.os, "open", side_effect=simulate_fifo_swap):
                    inventory.audit_repository(
                        repository,
                        FIXED_RUN_ID,
                        FIXED_CREATED_AT,
                        AuditBudgets(),
                    )
            finally:
                os.close(read_descriptor)
                os.close(write_descriptor)

            by_path = {record["repository_relative_path"]: record for record in self._records(repository)}
            self.assertTrue(observed_flags)
            self.assertTrue(observed_flags[0] & getattr(os, "O_NONBLOCK", 0))
            self.assertIn("ARTIFACT_CHANGED_DURING_INVENTORY", by_path["swapped.txt"]["warnings"])
            self.assertNotIn("ARTIFACT_UNREADABLE", by_path["swapped.txt"]["warnings"])

    def test_hash_reader_never_requests_bytes_past_the_budget(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "artifact"
            path.write_bytes(b"0123456789")
            descriptor = os.open(path, os.O_RDONLY)
            original_read = scanner.os.read
            requests = []

            def observe_read(fd, requested):
                requests.append(requested)
                return original_read(fd, requested)

            try:
                with mock.patch.object(scanner.os, "read", side_effect=observe_read):
                    scanner._hash_file_descriptor(descriptor, 8)
            finally:
                os.close(descriptor)

            self.assertEqual(requests, [8])

    def test_disappearing_artifact_is_retained_and_siblings_continue(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "README.md").write_text("kept\n", encoding="utf-8")
            (repository / "gone.txt").write_text("gone\n", encoding="utf-8")
            original_open = scanner.os.open

            def remove_gone(name, flags, *args, **kwargs):
                if name == "gone.txt":
                    raise FileNotFoundError("deterministic disappearance")
                return original_open(name, flags, *args, **kwargs)

            with mock.patch.object(scanner.os, "open", side_effect=remove_gone):
                inventory.audit_repository(
                    repository,
                    FIXED_RUN_ID,
                    FIXED_CREATED_AT,
                    AuditBudgets(),
                )

            by_path = {record["repository_relative_path"]: record for record in self._records(repository)}
            self.assertIn("README.md", by_path)
            self.assertIn("ARTIFACT_DISAPPEARED", by_path["gone.txt"]["warnings"])
            self.assertIsNone(by_path["gone.txt"]["content_id"])

    def test_replaced_file_after_hash_is_retained_without_stale_content(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            artifact = repository / "replaced.txt"
            artifact.write_text("old evidence\n", encoding="utf-8")
            (repository / "sibling.txt").write_text("kept\n", encoding="utf-8")
            replacement = Path(temporary_directory) / "replacement.txt"
            replacement.write_text("new evidence\n", encoding="utf-8")
            original_hash = scanner._hash_file_descriptor
            swapped = False

            def hash_then_replace(file_descriptor, maximum_bytes):
                nonlocal swapped
                fingerprint = original_hash(file_descriptor, maximum_bytes)
                if not swapped:
                    os.replace(replacement, artifact)
                    swapped = True
                return fingerprint

            with mock.patch.object(
                scanner, "_hash_file_descriptor", side_effect=hash_then_replace
            ):
                inventory.audit_repository(
                    repository,
                    FIXED_RUN_ID,
                    FIXED_CREATED_AT,
                    AuditBudgets(),
                )

            by_path = {
                record["repository_relative_path"]: record
                for record in self._records(repository)
            }
            self.assertTrue(swapped)
            self.assertEqual(artifact.read_text(encoding="utf-8"), "new evidence\n")
            self.assertIn(
                "ARTIFACT_CHANGED_DURING_INVENTORY", by_path["replaced.txt"]["warnings"]
            )
            self.assertIsNone(by_path["replaced.txt"]["fingerprint"])
            self.assertIsNone(by_path["replaced.txt"]["content_id"])
            self.assertIsNotNone(by_path["sibling.txt"]["content_id"])
            self.assertEqual(
                self._run_record(repository)["final_status"], "COMPLETED_WITH_LIMITATIONS"
            )

    def test_replaced_directory_purges_stale_descendants_and_keeps_siblings(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "research-repository"
            repository.mkdir()
            stale_directory = repository / "stale-directory"
            stale_directory.mkdir()
            (stale_directory / "old-child.txt").write_text("old\n", encoding="utf-8")
            (repository / "sibling.txt").write_text("kept\n", encoding="utf-8")
            replacement = temporary_path / "replacement-directory"
            replacement.mkdir()
            (replacement / "new-child.txt").write_text("new\n", encoding="utf-8")
            retired = temporary_path / "retired-directory"
            original_scan = scanner._scan_directory
            swapped = False

            def scan_then_replace(*args, **kwargs):
                nonlocal swapped
                original_scan(*args, **kwargs)
                if args[2] == "stale-directory" and not swapped:
                    os.replace(stale_directory, retired)
                    os.replace(replacement, stale_directory)
                    swapped = True

            with mock.patch.object(scanner, "_scan_directory", side_effect=scan_then_replace):
                inventory.audit_repository(
                    repository,
                    FIXED_RUN_ID,
                    FIXED_CREATED_AT,
                    AuditBudgets(),
                )

            by_path = {
                record["repository_relative_path"]: record
                for record in self._records(repository)
            }
            self.assertTrue(swapped)
            self.assertIn(
                "ARTIFACT_CHANGED_DURING_INVENTORY",
                by_path["stale-directory"]["warnings"],
            )
            self.assertIsNone(by_path["stale-directory"]["fingerprint"])
            self.assertIsNone(by_path["stale-directory"]["content_id"])
            self.assertNotIn("stale-directory/old-child.txt", by_path)
            self.assertIsNotNone(by_path["sibling.txt"]["content_id"])
            self.assertEqual(
                self._run_record(repository)["final_status"], "COMPLETED_WITH_LIMITATIONS"
            )

    def test_unreadable_directory_remains_without_a_content_conclusion(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "README.md").write_text("kept\n", encoding="utf-8")
            (repository / "blocked-directory").mkdir()
            original_open = scanner.os.open

            def deny_directory(name, flags, *args, **kwargs):
                if name == "blocked-directory":
                    raise PermissionError("deterministic denial")
                return original_open(name, flags, *args, **kwargs)

            with mock.patch.object(scanner.os, "open", side_effect=deny_directory):
                inventory.audit_repository(
                    repository,
                    FIXED_RUN_ID,
                    FIXED_CREATED_AT,
                    AuditBudgets(),
                )

            by_path = {record["repository_relative_path"]: record for record in self._records(repository)}
            blocked = by_path["blocked-directory"]
            self.assertIn("ARTIFACT_UNREADABLE", blocked["warnings"])
            self.assertIsNone(blocked["fingerprint"])
            self.assertIsNone(blocked["content_id"])

    def test_nested_unreadable_warning_propagates_to_every_ancestor(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            blocked = repository / "outer" / "inner" / "blocked.txt"
            blocked.parent.mkdir(parents=True)
            blocked.write_text("not-read\n", encoding="utf-8")
            original_open = scanner.os.open

            def deny_blocked(name, flags, *args, **kwargs):
                if name == "blocked.txt":
                    raise PermissionError("deterministic denial")
                return original_open(name, flags, *args, **kwargs)

            with mock.patch.object(scanner.os, "open", side_effect=deny_blocked):
                inventory.audit_repository(
                    repository,
                    FIXED_RUN_ID,
                    FIXED_CREATED_AT,
                    AuditBudgets(),
                )

            by_path = {record["repository_relative_path"]: record for record in self._records(repository)}
            for path in ("outer/inner", "outer", "."):
                with self.subTest(path=path):
                    self.assertIsNone(by_path[path]["content_id"])
                    self.assertIn("ARTIFACT_UNREADABLE", by_path[path]["warnings"])

    def test_nested_git_probe_failure_is_local_and_siblings_continue(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            nested = repository / "nested"
            nested.mkdir(parents=True)
            (nested / ".git").mkdir()
            (nested / "sibling.txt").write_text("kept\n", encoding="utf-8")
            original_stat = scanner.os.stat

            def deny_git_probe(name, *args, **kwargs):
                if name == ".git":
                    raise PermissionError("deterministic .git probe denial")
                return original_stat(name, *args, **kwargs)

            with mock.patch.object(scanner.os, "stat", side_effect=deny_git_probe):
                inventory.audit_repository(
                    repository,
                    FIXED_RUN_ID,
                    FIXED_CREATED_AT,
                    AuditBudgets(),
                )

            by_path = {record["repository_relative_path"]: record for record in self._records(repository)}
            self.assertIn("nested/sibling.txt", by_path)
            self.assertIn("nested/.git", by_path)
            self.assertEqual(by_path["nested/.git"]["object_type"], "UNKNOWN")
            self.assertIn("ARTIFACT_UNREADABLE", by_path["nested/.git"]["warnings"])

    def test_unreadable_symlink_is_retained_without_aborting_siblings(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "README.md").write_text("kept\n", encoding="utf-8")
            (repository / "blocked-link").symlink_to("README.md")
            original_readlink = scanner.os.readlink

            def deny_link(name, *args, **kwargs):
                if name == "blocked-link":
                    raise PermissionError("deterministic denial")
                return original_readlink(name, *args, **kwargs)

            with mock.patch.object(scanner.os, "readlink", side_effect=deny_link):
                inventory.audit_repository(
                    repository,
                    FIXED_RUN_ID,
                    FIXED_CREATED_AT,
                    AuditBudgets(),
                )

            by_path = {record["repository_relative_path"]: record for record in self._records(repository)}
            self.assertIn("README.md", by_path)
            self.assertIn("ARTIFACT_UNREADABLE", by_path["blocked-link"]["warnings"])
            self.assertIsNone(by_path["blocked-link"]["content_id"])

    def test_skipped_declaration_is_not_reopened_for_validation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "ro-crate-metadata.json").write_text("{}", encoding="utf-8")

            inventory.audit_repository(
                repository,
                FIXED_RUN_ID,
                FIXED_CREATED_AT,
                AuditBudgets(max_file_bytes=1),
            )

            observations = [
                json.loads(line)
                for line in (self._run_directory(repository) / "adapter-observations.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            observation = next(item for item in observations if item["declaration_family"] == "RO_CRATE")
            self.assertEqual(observation["status"], "PRESENT_UNVALIDATED")
            self.assertIn("DECLARATION_VALIDATION_UNAVAILABLE", observation["limitations"])

    def test_declaration_local_failure_finishes_with_limitations(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "ro-crate-metadata.json").write_text("{}", encoding="utf-8")

            with mock.patch.object(
                declarations,
                "_open_regular_file",
                side_effect=PermissionError("deterministic denial"),
            ):
                inventory.audit_repository(
                    repository,
                    FIXED_RUN_ID,
                    FIXED_CREATED_AT,
                    AuditBudgets(),
                )

            run_record = self._run_record(repository)
            self.assertEqual(run_record["final_status"], "COMPLETED_WITH_LIMITATIONS")
            self.assertIn("DECLARATION_VALIDATION_UNAVAILABLE", run_record["warnings"])
            self.assertEqual(
                run_record["component_states"]["declarations"]["status"],
                "COMPLETED_WITH_LIMITATIONS",
            )

    def test_invalid_budget_has_a_stable_cli_error(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            for value in ("0", "268435457", "not-a-number"):
                with self.subTest(value=value):
                    result = self._run_audit(repository, "--max-file-bytes", value)
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("max file bytes must be between 1 and 268435456", result.stderr)
                    self.assertNotIn("Traceback", result.stderr)

    def test_audit_budgets_are_immutable_and_bounded(self):
        budgets = AuditBudgets()
        self.assertEqual(budgets.max_file_bytes, 33_554_432)
        self.assertEqual(budgets.max_artifacts, 100_000)
        self.assertEqual(budgets.max_depth, 128)
        self.assertEqual(budgets.max_directory_entries, 50_000)
        self.assertEqual(budgets.max_total_hash_bytes, 1_073_741_824)
        with self.assertRaises(ValueError):
            AuditBudgets(max_file_bytes=0)
        with self.assertRaises(ValueError):
            AuditBudgets(max_file_bytes=268_435_457)
        with self.assertRaises(ValueError):
            AuditBudgets(max_artifacts=1_000_001)
        with self.assertRaises(ValueError):
            AuditBudgets(max_depth=513)
        with self.assertRaises(ValueError):
            AuditBudgets(max_directory_entries=100_001)
        with self.assertRaises(ValueError):
            AuditBudgets(max_total_hash_bytes=68_719_476_737)
        with self.assertRaises(Exception):
            budgets.max_file_bytes = 1

    def test_directory_entry_limit_scans_none_of_an_overwide_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            for name in ("a.txt", "b.txt", "c.txt"):
                (repository / name).write_text(name, encoding="utf-8")

            records = self._scan(repository, AuditBudgets(max_directory_entries=2))

            self.assertEqual([record.path for record in records], ["."])
            self.assertIn("DIRECTORY_ENTRY_LIMIT", records[0].warnings)
            self.assertIsNone(records[0].fingerprint)

    def test_control_directory_does_not_consume_root_entry_budget(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            (repository / "a.txt").write_text("a", encoding="utf-8")
            (repository / "b.txt").write_text("b", encoding="utf-8")
            control = repository / ".repo-curator"
            control.mkdir()
            (control / "ignored.txt").write_text("ignored", encoding="utf-8")

            records = self._scan(repository, AuditBudgets(max_directory_entries=2))

            self.assertEqual([record.path for record in records], [".", "a.txt", "b.txt"])
            self.assertNotIn("DIRECTORY_ENTRY_LIMIT", records[0].warnings)

    def test_artifact_limit_stops_at_a_deterministic_sorted_prefix(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            for name in ("c.txt", "a.txt", "b.txt"):
                (repository / name).write_text(name, encoding="utf-8")

            records = self._scan(repository, AuditBudgets(max_artifacts=3))

            self.assertEqual([record.path for record in records], [".", "a.txt", "b.txt"])
            self.assertIn("INVENTORY_ARTIFACT_LIMIT", records[0].warnings)
            self.assertIsNone(records[0].fingerprint)

    def test_depth_limit_retains_boundary_directory_without_recursing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            nested = repository / "level-one"
            nested.mkdir()
            (nested / "hidden.txt").write_text("hidden", encoding="utf-8")

            records = self._scan(repository, AuditBudgets(max_depth=1))
            by_path = {record.path: record for record in records}

            self.assertEqual(set(by_path), {".", "level-one"})
            self.assertIn("INVENTORY_DEPTH_LIMIT", by_path["level-one"].warnings)
            self.assertIsNone(by_path["level-one"].fingerprint)

    def test_total_hash_budget_skips_content_but_keeps_file_metadata(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory)
            (repository / "a.txt").write_bytes(b"aaaa")
            (repository / "b.txt").write_bytes(b"bbbb")

            records = self._scan(repository, AuditBudgets(max_total_hash_bytes=5))
            by_path = {record.path: record for record in records}

            self.assertIsNotNone(by_path["a.txt"].fingerprint)
            self.assertIsNone(by_path["b.txt"].fingerprint)
            self.assertIn(
                "CONTENT_HASH_SKIPPED_TOTAL_BYTES_LIMIT", by_path["b.txt"].warnings
            )
            self.assertIsNone(by_path["."].fingerprint)

    def _scan(self, repository: Path, budgets: AuditBudgets):
        root_fd = os.open(repository, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            return scanner.scan_root(root_fd, budgets)
        finally:
            os.close(root_fd)

    def _run_audit(self, repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "repo_curator",
                "audit",
                "--root",
                str(repository),
                "--run-id",
                FIXED_RUN_ID,
                "--created-at",
                FIXED_CREATED_AT,
                *arguments,
            ],
            check=False,
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            capture_output=True,
        )

    def _run_directory(self, repository: Path) -> Path:
        return repository / ".repo-curator" / "runs" / FIXED_RUN_ID

    def _records(self, repository: Path) -> list[dict]:
        return [
            json.loads(line)
            for line in (self._run_directory(repository) / "inventory.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]

    def _run_record(self, repository: Path) -> dict:
        return json.loads((self._run_directory(repository) / "run.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
