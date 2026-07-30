import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from repo_curator import inventory


FIXED_RUN_ID = "fixture-run"
FIXED_CREATED_AT = "2026-07-19T00:00:00Z"


class AuditScenarioTest(unittest.TestCase):
    def test_audit_emits_deterministic_inventory_without_executing_target_content(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "README.md").write_text("# Study\n", encoding="utf-8")
            (repository / "data").mkdir()
            (repository / "data" / "results.csv").write_text(
                "metric,value\naccuracy,0.91\n", encoding="utf-8"
            )
            execution_marker = repository / "target-content-was-executed"
            (repository / "danger.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(execution_marker)!r}).write_text('executed')\n",
                encoding="utf-8",
            )
            original_files = self._snapshot_original_files(repository)

            first_run = self._run_audit(repository)
            self.assertEqual(first_run.returncode, 0, first_run.stderr)

            run_directory = repository / ".repo-curator" / "runs" / FIXED_RUN_ID
            first_run_bytes = (run_directory / "run.json").read_bytes()
            first_inventory_bytes = (run_directory / "inventory.jsonl").read_bytes()
            first_git_observations_bytes = (
                run_directory / "git-observations.jsonl"
            ).read_bytes()
            run_record = json.loads(first_run_bytes)
            inventory_records = [
                json.loads(line)
                for line in first_inventory_bytes.decode("utf-8").splitlines()
            ]

            self.assertEqual(run_record["schema_version"], "repo-curator.run.v1")
            required_run_fields = {
                "schema_version",
                "run_id",
                "repository_root_realpath",
                "repository_mode",
                "git_head",
                "repository_state_hash",
                "effective_config_hash",
                "tool_versions",
                "started_at",
                "ended_at",
                "execution_mode",
                "previous_run_id",
                "exclusions",
                "resource_budgets",
                "component_states",
                "warnings",
                "output_file_hashes",
                "final_status",
            }
            self.assertTrue(required_run_fields.issubset(run_record))
            self.assertEqual(run_record["final_status"], "COMPLETED_WITH_LIMITATIONS")
            self.assertEqual(run_record["repository_mode"], "FILESYSTEM")
            self.assertEqual(
                run_record["component_states"]["git"],
                {"status": "COMPLETED_WITH_LIMITATIONS", "warnings": ["GIT_NOT_REPOSITORY"]},
            )
            self.assertEqual(run_record["artifact_count"], len(inventory_records))
            self.assertEqual(
                run_record["output_file_hashes"]["inventory.jsonl"],
                hashlib.sha256(first_inventory_bytes).hexdigest(),
            )
            self.assertEqual(
                run_record["output_file_hashes"]["git-observations.jsonl"],
                hashlib.sha256(first_git_observations_bytes).hexdigest(),
            )
            self.assertEqual(first_git_observations_bytes, b"")
            self.assertEqual(
                [record["repository_relative_path"] for record in inventory_records],
                [".", "README.md", "danger.py", "data", "data/results.csv"],
            )
            required_inventory_fields = {
                "schema_version",
                "run_id",
                "artifact_id",
                "content_id",
                "location_id",
                "lineage_id",
                "repository_relative_path",
                "realpath",
                "object_type",
                "size_bytes",
                "mode",
                "executable",
                "mtime_ns",
                "symlink_target_text",
                "git_state",
                "lfs_pointer",
                "fingerprint_scheme",
                "fingerprint",
                "profile_eligibility",
                "warnings",
                "created_at",
            }
            self.assertTrue(
                all(
                    required_inventory_fields.issubset(record)
                    for record in inventory_records
                )
            )
            directory_records = [
                record
                for record in inventory_records
                if record["object_type"] == "DIRECTORY"
            ]
            self.assertTrue(directory_records)
            self.assertTrue(
                all(record["size_bytes"] is None for record in directory_records)
            )
            self.assertTrue(
                all(
                    record["content_id"].startswith("merkle-dir-v1:")
                    for record in directory_records
                )
            )

            for sequence, record in enumerate(inventory_records, start=1):
                self.assertEqual(
                    record["artifact_id"], f"art_{FIXED_RUN_ID}_{sequence:08d}"
                )
                self.assertIn("location_id", record)
                self.assertIn("content_id", record)
                self.assertIn("lineage_id", record)

            readme_record = next(
                record
                for record in inventory_records
                if record["repository_relative_path"] == "README.md"
            )
            expected_hash = hashlib.sha256(b"# Study\n").hexdigest()
            self.assertEqual(
                readme_record["content_id"], f"sha256-file-v1:{expected_hash}"
            )
            self.assertEqual(readme_record["fingerprint_scheme"], "sha256-file-v1")
            self.assertEqual(readme_record["fingerprint"], expected_hash)
            self.assertIsNone(readme_record["lineage_id"])
            self.assertEqual(readme_record["lineage_status"], "UNRESOLVED")

            self.assertFalse(execution_marker.exists())
            self.assertEqual(self._snapshot_original_files(repository), original_files)

            shutil.rmtree(repository / ".repo-curator")
            second_run = self._run_audit(repository)
            self.assertEqual(second_run.returncode, 0, second_run.stderr)
            second_run_directory = (
                repository / ".repo-curator" / "runs" / FIXED_RUN_ID
            )
            self.assertEqual(
                (second_run_directory / "run.json").read_bytes(), first_run_bytes
            )
            self.assertEqual(
                (second_run_directory / "inventory.jsonl").read_bytes(),
                first_inventory_bytes,
            )
            self.assertEqual(
                (second_run_directory / "git-observations.jsonl").read_bytes(),
                first_git_observations_bytes,
            )

    def test_audit_records_an_external_symbolic_link_without_reading_its_target(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "research-repository"
            repository.mkdir()
            external_file = temporary_path / "external-secret.txt"
            external_file.write_text("outside", encoding="utf-8")
            (repository / "external-link").symlink_to(external_file)

            result = self._run_audit(repository)

            self.assertEqual(result.returncode, 0, result.stderr)
            records = [
                json.loads(line)
                for line in (
                    repository
                    / ".repo-curator"
                    / "runs"
                    / FIXED_RUN_ID
                    / "inventory.jsonl"
                ).read_text(encoding="utf-8").splitlines()
            ]
            link_record = next(
                record
                for record in records
                if record["repository_relative_path"] == "external-link"
            )
            self.assertEqual(link_record["object_type"], "SYMLINK")
            self.assertIn("SYMLINK_TARGET_OUTSIDE_ROOT", link_record["warnings"])
            self.assertEqual(external_file.read_text(encoding="utf-8"), "outside")

    def test_audit_rejects_a_run_id_that_could_escape_the_run_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "README.md").write_text("# Study\n", encoding="utf-8")

            result = self._run_audit(repository, run_id="../escape")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid run ID", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse((repository / ".repo-curator").exists())

    def test_audit_rejects_a_control_directory_symbolic_link(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "research-repository"
            repository.mkdir()
            external_directory = temporary_path / "external"
            external_directory.mkdir()
            (repository / ".repo-curator").symlink_to(
                external_directory, target_is_directory=True
            )

            result = self._run_audit(repository)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsafe control directory", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertEqual(list(external_directory.iterdir()), [])

    def test_parent_directory_merkle_changes_with_nested_file_content(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            nested_file = repository / "data" / "results.csv"
            nested_file.parent.mkdir(parents=True)
            nested_file.write_text("value\n1\n", encoding="utf-8")

            first_result = self._run_audit(repository, run_id="first")
            self.assertEqual(first_result.returncode, 0, first_result.stderr)
            first_root_content_id = self._root_content_id(repository, "first")

            shutil.rmtree(repository / ".repo-curator")
            nested_file.write_text("value\n2\n", encoding="utf-8")
            second_result = self._run_audit(repository, run_id="second")
            self.assertEqual(second_result.returncode, 0, second_result.stderr)
            second_root_content_id = self._root_content_id(repository, "second")

            self.assertNotEqual(first_root_content_id, second_root_content_id)

    def test_repository_state_hash_does_not_depend_on_run_identity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "README.md").write_text("# Study\n", encoding="utf-8")

            first_result = self._run_audit(repository, run_id="first")
            self.assertEqual(first_result.returncode, 0, first_result.stderr)
            first_state_hash = self._run_record(repository, "first")[
                "repository_state_hash"
            ]

            shutil.rmtree(repository / ".repo-curator")
            second_result = self._run_audit(repository, run_id="second")
            self.assertEqual(second_result.returncode, 0, second_result.stderr)
            second_state_hash = self._run_record(repository, "second")[
                "repository_state_hash"
            ]

            self.assertEqual(first_state_hash, second_state_hash)

    def test_identical_directory_content_has_one_identity_at_two_locations(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            for directory_name in ("alpha", "beta"):
                directory = repository / directory_name
                directory.mkdir(parents=True)
                (directory / "result.txt").write_text("same\n", encoding="utf-8")

            result = self._run_audit(repository)

            self.assertEqual(result.returncode, 0, result.stderr)
            inventory_path = (
                repository
                / ".repo-curator"
                / "runs"
                / FIXED_RUN_ID
                / "inventory.jsonl"
            )
            records = [
                json.loads(line)
                for line in inventory_path.read_text(encoding="utf-8").splitlines()
            ]
            directory_content_ids = {
                record["repository_relative_path"]: record["content_id"]
                for record in records
                if record["repository_relative_path"] in {"alpha", "beta"}
            }
            self.assertEqual(
                directory_content_ids["alpha"], directory_content_ids["beta"]
            )

    def _run_audit(
        self, repository: Path, run_id: str = FIXED_RUN_ID
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                "-m",
                "repo_curator",
                "audit",
                "--root",
                str(repository),
                "--run-id",
                run_id,
                "--created-at",
                FIXED_CREATED_AT,
            ],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )

    def _snapshot_original_files(self, repository: Path) -> dict[str, bytes]:
        return {
            path.relative_to(repository).as_posix(): path.read_bytes()
            for path in sorted(repository.rglob("*"))
            if path.is_file() and ".repo-curator" not in path.parts
        }

    def _root_content_id(self, repository: Path, run_id: str) -> str:
        inventory_path = (
            repository / ".repo-curator" / "runs" / run_id / "inventory.jsonl"
        )
        records = [
            json.loads(line)
            for line in inventory_path.read_text(encoding="utf-8").splitlines()
        ]
        return next(
            record["content_id"]
            for record in records
            if record["repository_relative_path"] == "."
        )

    def _run_record(self, repository: Path, run_id: str) -> dict:
        run_path = repository / ".repo-curator" / "runs" / run_id / "run.json"
        return json.loads(run_path.read_text(encoding="utf-8"))


class AtomicOutputTest(unittest.TestCase):
    def test_failed_flush_does_not_leave_a_finalized_output_name(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0)
            directory_fd = os.open(directory, directory_flags)
            try:
                with mock.patch.object(
                    inventory.os,
                    "fsync",
                    side_effect=OSError("simulated flush failure"),
                ):
                    with self.assertRaisesRegex(OSError, "simulated flush failure"):
                        inventory._write_bytes(directory_fd, "run.json", b"partial")
            finally:
                os.close(directory_fd)

            self.assertFalse((directory / "run.json").exists())
            self.assertEqual(list(directory.iterdir()), [])

    def test_second_output_failure_removes_the_incomplete_run_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "README.md").write_text("# Study\n", encoding="utf-8")
            original_write = inventory._write_bytes

            def fail_run_record(
                directory_fd: int, name: str, content: bytes
            ) -> None:
                if name == "run.json":
                    raise OSError("simulated run-record failure")
                original_write(directory_fd, name, content)

            with mock.patch.object(
                inventory, "_write_bytes", side_effect=fail_run_record
            ):
                with self.assertRaisesRegex(OSError, "simulated run-record failure"):
                    inventory.audit_repository(
                        repository, FIXED_RUN_ID, FIXED_CREATED_AT
                    )

            run_directory = repository / ".repo-curator" / "runs" / FIXED_RUN_ID
            self.assertFalse(run_directory.exists())

    def test_replacing_root_after_inventory_does_not_redirect_outputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "research-repository"
            moved_repository = temporary_path / "moved-research-repository"
            repository.mkdir()
            (repository / "README.md").write_text("# Study\n", encoding="utf-8")
            original_inventory_records = inventory._inventory_records

            def replace_root_after_inventory(*args, **kwargs):
                records = original_inventory_records(*args, **kwargs)
                repository.rename(moved_repository)
                repository.mkdir()
                return records

            with mock.patch.object(
                inventory,
                "_inventory_records",
                side_effect=replace_root_after_inventory,
            ):
                with self.assertRaisesRegex(ValueError, "audit root changed"):
                    inventory.audit_repository(
                        repository, FIXED_RUN_ID, FIXED_CREATED_AT
                    )

            self.assertFalse((repository / ".repo-curator").exists())
            self.assertFalse((moved_repository / ".repo-curator").exists())


if __name__ == "__main__":
    unittest.main()
