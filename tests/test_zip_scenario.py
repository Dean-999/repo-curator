import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from repo_curator.archives import _zip_observation


class ZipScenarioTest(unittest.TestCase):
    def test_central_directory_budget_is_checked_before_zipfile_parsing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with zipfile.ZipFile(root / "many.zip", "w") as archive:
                for index in range(20):
                    archive.writestr("member-{:03d}.txt".format(index), "x")
            root_fd = os.open(root, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                with mock.patch("repo_curator.archives.ZIP_CENTRAL_DIRECTORY_LIMIT", 64):
                    status, _, limitations = _zip_observation(root_fd, "many.zip")
            finally:
                os.close(root_fd)

            self.assertEqual(status, "LIMITED")
            self.assertIn("RESOURCE_LIMIT_REACHED", limitations)
    def test_zip_inspection_is_bounded_and_other_archives_are_opaque(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            with zipfile.ZipFile(root / "safe.zip", "w") as archive:
                archive.writestr("results/value.txt", "one\n")
            with zipfile.ZipFile(root / "unsafe.zip", "w") as archive:
                archive.writestr("../escape.txt", "no\n")
            with tarfile.open(root / "data.tar", "w") as archive:
                info = tarfile.TarInfo("data.txt"); info.size = 3
                archive.addfile(info, io.BytesIO(b"one"))
            (root / "broken.zip").write_bytes(b"PK\x03\x04broken")

            result = subprocess.run(
                [sys.executable, "-m", "repo_curator", "audit", "--root", str(root),
                 "--run-id", "zip-run", "--created-at", "2026-07-24T00:00:00Z"],
                cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            output = root / ".repo-curator" / "runs" / "zip-run"
            observations = {item["repository_relative_path"]: item for item in
                            (json.loads(line) for line in (output / "archive-observations.jsonl").read_text().splitlines())}
            self.assertEqual(observations["safe.zip"]["status"], "INSPECTED")
            self.assertIn("ARCHIVE_PATH_UNSAFE", observations["unsafe.zip"]["limitations"])
            self.assertIn("UNSUPPORTED_FORMAT", observations["data.tar"]["limitations"])
            self.assertIn("ARCHIVE_MALFORMED", observations["broken.zip"]["limitations"])
            self.assertFalse((root / "results").exists())


if __name__ == "__main__":
    unittest.main()
