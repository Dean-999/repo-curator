import errno
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from repo_curator.identity import collision_key, location_identity

FIXED_RUN_ID = "identity-run"
FIXED_CREATED_AT = "2026-07-19T00:00:00Z"


class IdentityScenarioTest(unittest.TestCase):
    def test_equal_bytes_share_content_but_not_artifact_or_location_identity(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "left.txt").write_bytes(b"same bytes\n")
            (repository / "right.txt").write_bytes(b"same bytes\n")

            result = self._run_audit(repository)

            self.assertEqual(result.returncode, 0, result.stderr)
            by_path = self._records_by_path(repository)
            left = by_path["left.txt"]
            right = by_path["right.txt"]
            self.assertEqual(left["content_id"], right["content_id"])
            self.assertNotEqual(left["artifact_id"], right["artifact_id"])
            self.assertNotEqual(left["location_id"], right["location_id"])
            self.assertIsNone(left["lineage_id"])
            self.assertEqual(left["lineage_status"], "UNRESOLVED")

    def test_hard_links_and_unicode_case_collisions_remain_independent(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            hard_a = repository / "hard-a.txt"
            hard_a.write_bytes(b"hard link bytes\n")
            os.link(hard_a, repository / "hard-b.txt")
            case_a = repository / "Caf\u00e9.txt"
            case_b = repository / "Cafe\u0301.TXT"
            case_a.write_bytes(b"first\n")
            case_b.write_bytes(b"second\n")
            fixture_entries = [
                entry
                for entry in os.listdir(repository)
                if collision_key(entry) == collision_key(case_a.name)
            ]
            if len(fixture_entries) != 2:
                self.skipTest("filesystem folds the collision fixture into one entry")
            result = self._run_audit(repository)

            self.assertEqual(result.returncode, 0, result.stderr)
            by_path = self._records_by_path(repository)
            hard_a_record = by_path["hard-a.txt"]
            hard_b_record = by_path["hard-b.txt"]
            self.assertEqual(hard_a_record["content_id"], hard_b_record["content_id"])
            self.assertNotEqual(hard_a_record["artifact_id"], hard_b_record["artifact_id"])
            self.assertNotEqual(hard_a_record["location_id"], hard_b_record["location_id"])
            for record in (hard_a_record, hard_b_record):
                self.assertIsNone(record["lineage_id"])
                self.assertEqual(record["lineage_status"], "UNRESOLVED")
            colliding_records = [
                record
                for record in self._records(repository)
                if collision_key(record["repository_relative_path"])
                == collision_key(case_a.name)
            ]
            self.assertEqual(len(colliding_records), 2)
            self.assertTrue(
                all("CASE_COLLISION" in record["warnings"] for record in colliding_records)
            )

    def test_undecodable_raw_filename_bytes_round_trip_when_supported(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            root_fd = os.open(repository, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                try:
                    raw_fd = os.open(
                        b"raw-\xff", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600, dir_fd=root_fd
                    )
                except OSError as error:
                    if error.errno != errno.EILSEQ:
                        raise
                    self.skipTest(
                        f"filesystem rejects undecodable filename bytes: {error}"
                    )
                else:
                    os.close(raw_fd)
            finally:
                os.close(root_fd)

            result = self._run_audit(repository)

            self.assertEqual(result.returncode, 0, result.stderr)
            by_path = self._records_by_path(repository)
            raw_record = next(
                record
                for record in by_path.values()
                if os.fsencode(record["repository_relative_path"]) == b"raw-\xff"
            )
            self.assertEqual(os.fsencode(raw_record["repository_relative_path"]), b"raw-\xff")

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

    def _records_by_path(self, repository: Path) -> dict[str, dict]:
        return {
            record["repository_relative_path"]: record
            for record in self._records(repository)
        }

    def _records(self, repository: Path) -> list[dict]:
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


class LocationIdentityTest(unittest.TestCase):
    def test_location_identity_uses_root_realpath_object_type_and_raw_path(self):
        root_a = "/repositories/a"
        root_b = "/repositories/b"
        raw_path_a = b"raw-\xff"
        raw_path_b = b"other-\xff"

        baseline = location_identity(root_a, "REGULAR_FILE", raw_path_a)

        self.assertNotEqual(
            baseline, location_identity(root_b, "REGULAR_FILE", raw_path_a)
        )
        self.assertNotEqual(
            baseline, location_identity(root_a, "DIRECTORY", raw_path_a)
        )
        self.assertNotEqual(
            baseline, location_identity(root_a, "REGULAR_FILE", raw_path_b)
        )


if __name__ == "__main__":
    unittest.main()
