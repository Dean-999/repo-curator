import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


FIXED_RUN_ID = "boundary-run"
FIXED_CREATED_AT = "2026-07-19T00:00:00Z"


class BoundaryScenarioTest(unittest.TestCase):
    def test_links_are_recorded_without_following_targets(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "research-repository"
            repository.mkdir()
            internal_target = repository / "inside-π.txt"
            internal_target.write_text("inside\n", encoding="utf-8")
            external_marker = temporary_path / "outside-marker.txt"
            external_marker.write_text("outside\n", encoding="utf-8")
            (repository / "internal-link").symlink_to("inside-π.txt")
            (repository / "external-link").symlink_to(external_marker)
            (repository / "broken-link").symlink_to("missing.txt")
            external_directory = temporary_path / "external-directory"
            external_directory.mkdir()
            external_secret = external_directory / "secret"
            external_secret.write_text("outside secret\n", encoding="utf-8")
            (repository / "bridge").symlink_to(external_directory, target_is_directory=True)
            (repository / "through-bridge").symlink_to("bridge/secret")
            (repository / "bridge-parent").symlink_to("bridge/..")

            result = self._run_audit(repository)

            self.assertEqual(result.returncode, 0, result.stderr)
            records = self._inventory_records(repository)
            by_path = {record["repository_relative_path"]: record for record in records}
            self.assertEqual(by_path["internal-link"]["object_type"], "SYMLINK")
            self.assertEqual(by_path["internal-link"]["symlink_target_text"], "inside-π.txt")
            self.assertEqual(
                by_path["internal-link"]["fingerprint_scheme"],
                "sha256-symlink-target-v1",
            )
            self.assertEqual(
                by_path["internal-link"]["fingerprint"],
                hashlib.sha256(os.fsencode("inside-π.txt")).hexdigest(),
            )
            self.assertIn(
                "SYMLINK_TARGET_OUTSIDE_ROOT", by_path["external-link"]["warnings"]
            )
            self.assertIn(
                "SYMLINK_TARGET_MISSING", by_path["broken-link"]["warnings"]
            )
            self.assertIn(
                "SYMLINK_TARGET_OUTSIDE_ROOT", by_path["through-bridge"]["warnings"]
            )
            self.assertIn(
                "SYMLINK_TARGET_OUTSIDE_ROOT", by_path["bridge-parent"]["warnings"]
            )
            self.assertEqual(external_marker.read_text(encoding="utf-8"), "outside\n")
            self.assertEqual(external_secret.read_text(encoding="utf-8"), "outside secret\n")

    def test_special_and_nested_repository_objects_are_bounded(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            fifo_path = repository / "events.fifo"
            os.mkfifo(fifo_path)
            socket_path = repository / "events.sock"
            server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                server.bind(str(socket_path))
                (repository / ".git").mkdir()
                (repository / ".git" / "config").write_text("ignored", encoding="utf-8")
                (repository / "nested" / ".git").mkdir(parents=True)
                (repository / "nested" / ".git" / "config").write_text(
                    "ignored", encoding="utf-8"
                )
                (repository / "nested" / "ordinary.txt").write_text(
                    "do not inventory", encoding="utf-8"
                )

                result = self._run_audit(repository)
            finally:
                server.close()

            self.assertEqual(result.returncode, 0, result.stderr)
            records = self._inventory_records(repository)
            by_path = {record["repository_relative_path"]: record for record in records}
            self.assertEqual(by_path["events.fifo"]["object_type"], "SPECIAL_FILE")
            self.assertIn("SPECIAL_FILE_NOT_READ", by_path["events.fifo"]["warnings"])
            self.assertIsNone(by_path["events.fifo"]["content_id"])
            self.assertIsNone(by_path["events.fifo"]["fingerprint_scheme"])
            self.assertIsNone(by_path["events.fifo"]["fingerprint"])
            self.assertEqual(by_path["events.sock"]["object_type"], "SPECIAL_FILE")
            self.assertIn("SPECIAL_FILE_NOT_READ", by_path["events.sock"]["warnings"])
            self.assertIn("PROTECTED_GIT_CONTROL", by_path[".git"]["warnings"])
            self.assertIn("NESTED_REPOSITORY_BOUNDARY", by_path["nested"]["warnings"])
            self.assertIn(
                "NESTED_REPOSITORY_BOUNDARY", by_path["nested/.git"]["warnings"]
            )
            self.assertNotIn(".git/config", by_path)
            self.assertNotIn("nested/.git/config", by_path)
            self.assertNotIn("nested/ordinary.txt", by_path)

    def test_git_administration_files_are_protected_without_hashing_or_following(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            regular_repository = temporary_path / "regular-git-repository"
            regular_repository.mkdir()
            (regular_repository / ".git").write_text(
                "gitdir: /elsewhere\n", encoding="utf-8"
            )

            regular_result = self._run_audit(regular_repository)

            self.assertEqual(regular_result.returncode, 0, regular_result.stderr)
            regular_record = self._inventory_by_path(regular_repository)[".git"]
            self.assertEqual(regular_record["object_type"], "REGULAR_FILE")
            self.assertIn("PROTECTED_GIT_CONTROL", regular_record["warnings"])
            self.assertIsNone(regular_record["content_id"])
            self.assertIsNone(regular_record["fingerprint"])

            symlink_repository = temporary_path / "symlink-git-repository"
            symlink_repository.mkdir()
            external_git = temporary_path / "external-git-admin"
            external_git.write_text("outside git\n", encoding="utf-8")
            (symlink_repository / ".git").symlink_to(external_git)

            symlink_result = self._run_audit(symlink_repository)

            self.assertEqual(symlink_result.returncode, 0, symlink_result.stderr)
            symlink_record = self._inventory_by_path(symlink_repository)[".git"]
            self.assertEqual(symlink_record["object_type"], "SYMLINK")
            self.assertIn("PROTECTED_GIT_CONTROL", symlink_record["warnings"])
            self.assertIsNone(symlink_record["content_id"])
            self.assertIsNone(symlink_record["fingerprint"])
            self.assertEqual(external_git.read_text(encoding="utf-8"), "outside git\n")

    def test_boundary_inventory_is_deterministic_for_fixed_inputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "content.txt").write_text("content\n", encoding="utf-8")
            (repository / "content-link").symlink_to("content.txt")
            os.mkfifo(repository / "events.fifo")

            first_result = self._run_audit(repository)

            self.assertEqual(first_result.returncode, 0, first_result.stderr)
            run_directory = repository / ".repo-curator" / "runs" / FIXED_RUN_ID
            first_inventory_bytes = (run_directory / "inventory.jsonl").read_bytes()
            first_run_bytes = (run_directory / "run.json").read_bytes()

            shutil.rmtree(repository / ".repo-curator")
            second_result = self._run_audit(repository)

            self.assertEqual(second_result.returncode, 0, second_result.stderr)
            self.assertEqual(
                (run_directory / "inventory.jsonl").read_bytes(), first_inventory_bytes
            )
            self.assertEqual((run_directory / "run.json").read_bytes(), first_run_bytes)

    def test_python_virtual_environment_is_retained_as_one_non_recursive_boundary(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            environment = repository / "operation" / "venv"
            (environment / "lib" / "site-packages").mkdir(parents=True)
            (environment / "pyvenv.cfg").write_text("home = /python\n", encoding="utf-8")
            (environment / "lib" / "site-packages" / "dependency.py").write_text(
                "not project evidence\n", encoding="utf-8"
            )
            ordinary = repository / "venv"
            ordinary.mkdir()
            (ordinary / "research-note.txt").write_text("retain me\n", encoding="utf-8")

            result = self._run_audit(repository)

            self.assertEqual(result.returncode, 0, result.stderr)
            records = self._inventory_by_path(repository)
            self.assertIn(
                "PYTHON_VIRTUAL_ENVIRONMENT_BOUNDARY_NOT_RECURSED",
                records["operation/venv"]["warnings"],
            )
            self.assertNotIn("operation/venv/pyvenv.cfg", records)
            self.assertNotIn("operation/venv/lib/site-packages/dependency.py", records)
            self.assertIn("venv/research-note.txt", records)

    def _run_audit(self, repository: Path) -> subprocess.CompletedProcess[str]:
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
            ],
            cwd=Path(__file__).resolve().parents[1],
            capture_output=True,
            text=True,
            check=False,
        )

    def _inventory_records(self, repository: Path) -> list[dict]:
        inventory_path = (
            repository
            / ".repo-curator"
            / "runs"
            / FIXED_RUN_ID
            / "inventory.jsonl"
        )
        return [
            json.loads(line)
            for line in inventory_path.read_text(encoding="utf-8").splitlines()
        ]

    def _inventory_by_path(self, repository: Path) -> dict[str, dict]:
        return {
            record["repository_relative_path"]: record
            for record in self._inventory_records(repository)
        }


if __name__ == "__main__":
    unittest.main()
