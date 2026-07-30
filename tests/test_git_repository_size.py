import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from repo_curator import inventory


RUN_ID = "git-size-run"
CREATED_AT = "2026-07-28T16:00:00Z"


@unittest.skipUnless(shutil.which("git"), "system Git is required for Git fixtures")
class GitRepositorySizeTest(unittest.TestCase):
    def test_audit_emits_bounded_repository_size_summary_without_ref_names(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()
            self._git(repository, "init")
            self._git(repository, "config", "user.email", "fixture@example.test")
            self._git(repository, "config", "user.name", "Fixture")
            (repository / "result.bin").write_bytes(b"x" * 4096)
            self._git(repository, "add", "result.bin")
            self._git(repository, "commit", "-m", "fixture")
            self._git(repository, "tag", "private-experiment-name")

            inventory.audit_repository(repository, RUN_ID, CREATED_AT)

            observations = [
                json.loads(line)
                for line in (
                    repository
                    / ".repo-curator"
                    / "runs"
                    / RUN_ID
                    / "git-observations.jsonl"
                )
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            summary = next(
                item
                for item in observations
                if item["observation_type"] == "GIT_REPOSITORY_SIZE_SUMMARY"
            )
            self.assertEqual(
                [item["observation_id"] for item in observations],
                [f"gitobs_{RUN_ID}_{index:08d}" for index in range(1, len(observations) + 1)],
            )
            self.assertEqual(summary["status"], "OBSERVED")
            self.assertEqual(summary["reachable_commit_count"], 1)
            self.assertEqual(summary["reference_count"], 2)
            self.assertEqual(summary["reference_scales"]["reference_count"], 25_000)
            self.assertEqual(
                summary["concern_ratios"]["reference_count"], 0.00008
            )
            self.assertGreaterEqual(summary["object_database"]["in_pack"], 0)
            self.assertEqual(
                summary["current_checkout"]["max_regular_file_size_bytes"], 4096
            )
            self.assertEqual(
                summary["current_checkout"]["max_regular_file_path"], "result.bin"
            )
            self.assertIn(
                "GIT_SIZE_METRICS_NOT_CLEANUP_AUTHORITY", summary["limitations"]
            )
            self.assertNotIn(
                b"private-experiment-name",
                (
                    repository
                    / ".repo-curator"
                    / "runs"
                    / RUN_ID
                    / "git-observations.jsonl"
                ).read_bytes(),
            )

    def test_parsers_fail_closed_on_unknown_or_malformed_output(self):
        from repo_curator.git_repository_size import (
            parse_count,
            parse_count_objects,
        )

        self.assertIsNone(parse_count(b"12 trailing\n"))
        self.assertIsNone(parse_count(b"-1\n"))
        self.assertIsNone(parse_count(b"9" * 21 + b"\n"))
        self.assertIsNone(parse_count(b"18446744073709551616\n"))
        self.assertIsNone(
            parse_count_objects(
                b"count: 1\nsize: 2\nin-pack: 3\npacks: 1\n"
                b"size-pack: 4\nprune-packable: 0\ngarbage: 0\n"
                b"size-garbage: 0\nunknown: 5\n"
            )
        )

    def test_command_failures_produce_partial_null_metrics(self):
        from repo_curator.git_evidence import (
            GIT_OUTPUT_LIMIT_RETURN_CODE,
            _repository_size_summary,
        )

        limited = subprocess.CompletedProcess(
            ["git", "count-objects"], GIT_OUTPUT_LIMIT_RETURN_CODE, b"", b""
        )
        malformed = subprocess.CompletedProcess(
            ["git", "rev-list"], 0, b"not-a-count\n", b""
        )
        with mock.patch(
            "repo_curator.git_evidence._run_git",
            side_effect=[limited, None, malformed],
        ):
            summary, warnings = _repository_size_summary(
                "/usr/bin/git", Path("/fixture"), []
            )

        self.assertEqual(summary["status"], "PARTIAL")
        self.assertIsNone(summary["object_database"])
        self.assertIsNone(summary["reference_count"])
        self.assertIsNone(summary["reachable_commit_count"])
        self.assertIsNone(summary["concern_ratios"])
        self.assertEqual(
            warnings,
            [
                "GIT_SIZE_OBJECT_DATABASE_OUTPUT_LIMIT",
                "GIT_SIZE_REFERENCES_UNAVAILABLE",
                "GIT_SIZE_COMMITS_MALFORMED",
            ],
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
