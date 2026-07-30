import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from repo_curator import inventory
from repo_curator.repository_hygiene import (
    ADDED_LARGE_FILE_KIB,
    HYGIENE_FINDING_LIMIT,
    parse_hygiene_status,
    staged_large_files,
)


RUN_ID = "repository-hygiene-run"
CREATED_AT = "2026-07-28T18:00:00Z"


@unittest.skipUnless(shutil.which("git"), "system Git is required for Git fixtures")
@unittest.skipUnless(hasattr(os, "symlink"), "symbolic links are required")
class RepositoryHygieneTest(unittest.TestCase):
    def test_staged_large_files_use_strict_boundary_and_bounded_byte_order(self):
        records = [
            self._record("exact.bin", ADDED_LARGE_FILE_KIB * 1024),
            self._record("over.bin", ADDED_LARGE_FILE_KIB * 1024 + 1),
        ]
        records.extend(
            self._record(f"z-{index:03d}.bin", ADDED_LARGE_FILE_KIB * 1024 + 1)
            for index in range(HYGIENE_FINDING_LIMIT)
        )
        staged_paths = {
            record["repository_relative_path"] for record in records
        }

        findings, count, limitations = staged_large_files(records, staged_paths)

        self.assertEqual(count, HYGIENE_FINDING_LIMIT + 1)
        self.assertEqual(len(findings), HYGIENE_FINDING_LIMIT)
        self.assertNotIn("exact.bin", [item["repository_relative_path"] for item in findings])
        self.assertIn("over.bin", [item["repository_relative_path"] for item in findings])
        self.assertNotIn("z-255.bin", [item["repository_relative_path"] for item in findings])
        self.assertEqual(
            limitations, ("GIT_REPOSITORY_HYGIENE_FINDING_LIMIT",)
        )

    def test_porcelain_parser_preserves_paths_and_candidate_language(self):
        equal_hash = b"a" * 40
        other_hash = b"b" * 40
        raw_path = b"space and-\xff.bin"
        payload = (
            self._ordinary_entry(
                b"A.",
                b"000000",
                b"100644",
                equal_hash,
                equal_hash,
                b"added file.bin",
            )
            + b"\0"
            + self._ordinary_entry(b"M.", b"120000", b"100644", equal_hash, equal_hash, raw_path)
            + b"\0"
            + self._ordinary_entry(
                b"M.",
                b"120000",
                b"100755",
                equal_hash,
                other_hash,
                b"candidate",
            )
            + b"\0"
        )

        staged, findings, count, limitations = parse_hygiene_status(payload)

        self.assertEqual(staged, {"added file.bin"})
        self.assertEqual(count, 2)
        self.assertEqual(findings[0]["match_status"], "MODE_CHANGE_CANDIDATE")
        self.assertEqual(
            findings[1]["repository_relative_path"].encode(
                "utf-8", errors="surrogateescape"
            ),
            raw_path,
        )
        self.assertEqual(findings[1]["match_status"], "CONTENT_ID_EQUAL")
        self.assertEqual(
            limitations, ("GIT_DESTROYED_SYMLINK_CONTENT_NOT_COMPARED",)
        )

    def test_porcelain_parser_fails_closed_on_truncation_duplicates_and_garbage(self):
        object_id = b"a" * 40
        entry = self._ordinary_entry(
            b"M.", b"120000", b"100644", object_id, object_id, b"same"
        )
        duplicate_with_other_mode = self._ordinary_entry(
            b"M.", b"120000", b"100755", object_id, object_id, b"same"
        )
        malformed = ("GIT_REPOSITORY_HYGIENE_STATUS_MALFORMED",)

        self.assertEqual(parse_hygiene_status(entry)[3], malformed)
        self.assertEqual(parse_hygiene_status(b"garbage\0")[3], malformed)
        self.assertEqual(
            parse_hygiene_status(entry + b"\0" + duplicate_with_other_mode + b"\0")[3],
            malformed,
        )

    def test_nonordinary_records_are_explicitly_partial(self):
        object_id = b"a" * 40
        unmerged = (
            b"u UU N... 100644 100644 100644 100644 "
            + object_id
            + b" "
            + object_id
            + b" "
            + object_id
            + b" conflict path\0"
        )
        from repo_curator.git_evidence import _repository_hygiene_summary

        completed = subprocess.CompletedProcess(["git"], 0, unmerged, b"")
        with mock.patch("repo_curator.git_evidence._run_git", return_value=completed):
            summary, warnings = _repository_hygiene_summary(
                "/usr/bin/git", Path("/fixture"), []
            )

        limitation = "GIT_REPOSITORY_HYGIENE_NONORDINARY_RECORD_NOT_EVALUATED"
        self.assertEqual(summary["status"], "PARTIAL")
        self.assertIn(limitation, summary["limitations"])
        self.assertEqual(warnings, [limitation])

    def test_command_output_limit_and_unavailable_are_partial(self):
        from repo_curator.git_evidence import (
            GIT_OUTPUT_LIMIT_RETURN_CODE,
            _repository_hygiene_summary,
        )

        limited = subprocess.CompletedProcess(
            ["git"], GIT_OUTPUT_LIMIT_RETURN_CODE, b"", b""
        )
        for result, expected in (
            (limited, "GIT_REPOSITORY_HYGIENE_STATUS_OUTPUT_LIMIT"),
            (None, "GIT_REPOSITORY_HYGIENE_STATUS_UNAVAILABLE"),
        ):
            with self.subTest(expected=expected), mock.patch(
                "repo_curator.git_evidence._run_git", return_value=result
            ):
                summary, warnings = _repository_hygiene_summary(
                    "/usr/bin/git", Path("/fixture"), []
                )
            self.assertEqual(summary["status"], "PARTIAL")
            self.assertEqual(summary["staged_large_file_count"], 0)
            self.assertIn(expected, summary["limitations"])
            self.assertEqual(warnings, [expected])

    def test_audit_observes_staged_large_file_broken_and_destroyed_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()
            self._git(repository, "init")
            self._git(repository, "config", "user.email", "fixture@example.test")
            self._git(repository, "config", "user.name", "Fixture")
            (repository / "target.txt").write_text("target\n", encoding="utf-8")
            (repository / "preserved-link").symlink_to("target.txt")
            self._git(repository, "add", "target.txt", "preserved-link")
            self._git(repository, "commit", "-m", "symlink fixture")

            (repository / "preserved-link").unlink()
            (repository / "preserved-link").write_text("target.txt\n", encoding="utf-8")
            (repository / "large-result.bin").write_bytes(b"x" * (500 * 1024 + 1))
            (repository / "broken-link").symlink_to("missing-target")
            self._git(repository, "add", "preserved-link", "large-result.bin")

            inventory.audit_repository(repository, RUN_ID, CREATED_AT)

            run_directory = repository / ".repo-curator" / "runs" / RUN_ID
            observations = [
                json.loads(line)
                for line in (run_directory / "git-observations.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            summary = next(
                item
                for item in observations
                if item["observation_type"] == "GIT_REPOSITORY_HYGIENE_SUMMARY"
            )
            self.assertEqual(
                [item["observation_id"] for item in observations],
                [
                    f"gitobs_{RUN_ID}_{index:08d}"
                    for index in range(1, len(observations) + 1)
                ],
            )
            self.assertEqual(summary["status"], "OBSERVED")
            self.assertEqual(summary["staged_large_file_count"], 1)
            self.assertEqual(
                summary["staged_large_files"][0]["repository_relative_path"],
                "large-result.bin",
            )
            self.assertEqual(summary["destroyed_symlink_count"], 1)
            self.assertEqual(
                summary["destroyed_symlinks"][0]["repository_relative_path"],
                "preserved-link",
            )
            self.assertIn(
                "GIT_REPOSITORY_HYGIENE_NOT_CLEANUP_AUTHORITY",
                summary["limitations"],
            )

            inventory_records = {
                json.loads(line)["repository_relative_path"]: json.loads(line)
                for line in (run_directory / "inventory.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            }
            self.assertIn(
                "SYMLINK_TARGET_MISSING", inventory_records["broken-link"]["warnings"]
            )

    def _record(self, path: str, size_bytes: int):
        return {
            "artifact_id": f"artifact-{path}",
            "object_type": "REGULAR_FILE",
            "repository_relative_path": path,
            "size_bytes": size_bytes,
        }

    def _ordinary_entry(
        self,
        xy: bytes,
        head_mode: bytes,
        index_mode: bytes,
        head_hash: bytes,
        index_hash: bytes,
        path: bytes,
    ) -> bytes:
        return b" ".join(
            (
                b"1",
                xy,
                b"N...",
                head_mode,
                index_mode,
                index_mode,
                head_hash,
                index_hash,
                path,
            )
        )

    def _git(self, repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *arguments],
            cwd=repository,
            check=True,
            capture_output=True,
            text=True,
        )


if __name__ == "__main__":
    unittest.main()
