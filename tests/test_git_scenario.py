import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from repo_curator import inventory


FIXED_RUN_ID = "git-fixture-run"
FIXED_CREATED_AT = "2026-07-24T00:00:00Z"


@unittest.skipUnless(shutil.which("git"), "system Git is required for Git fixtures")
class GitScenarioTest(unittest.TestCase):
    def test_git_runner_terminates_output_that_exceeds_its_byte_budget(self):
        from repo_curator.git_evidence import (
            GIT_OUTPUT_LIMIT_RETURN_CODE,
            _run_git,
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            executable = temporary_path / "oversized-git-fixture"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "import sys\n"
                "sys.stdout.buffer.write(b'x' * 4096)\n",
                encoding="utf-8",
            )
            executable.chmod(0o700)

            result = _run_git(
                str(executable), temporary_path, ["ignored"], output_limit=1024
            )

            self.assertIsNotNone(result)
            self.assertEqual(result.returncode, GIT_OUTPUT_LIMIT_RETURN_CODE)
            self.assertLessEqual(len(result.stdout), 1024)

    def test_git_runner_timeout_applies_when_child_does_not_read_input(self):
        from repo_curator.git_evidence import GIT_COMMAND_INPUT_BYTES, _run_git

        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            executable = temporary_path / "blocked-input-git-fixture"
            executable.write_text(
                "#!/usr/bin/env python3\n"
                "import time\n"
                "time.sleep(5)\n",
                encoding="utf-8",
            )
            executable.chmod(0o700)

            with mock.patch(
                "repo_curator.git_evidence.GIT_COMMAND_TIMEOUT_SECONDS", 0.05
            ):
                result = _run_git(
                    str(executable),
                    temporary_path,
                    ["ignored"],
                    input_bytes=b"x" * GIT_COMMAND_INPUT_BYTES,
                )

            self.assertIsNone(result)

    def test_history_secret_tree_output_limit_is_an_explicit_partial_result(self):
        from repo_curator.git_evidence import (
            GIT_OUTPUT_LIMIT_RETURN_CODE,
            _secret_history,
        )

        limited = subprocess.CompletedProcess(
            ["git"], GIT_OUTPUT_LIMIT_RETURN_CODE, b"", b""
        )
        commit_id = "a" * 40
        with mock.patch("repo_curator.git_evidence._run_git", return_value=limited):
            summary, warnings = _secret_history(
                "/usr/bin/git",
                Path("/fixture"),
                [(commit_id, [], 1_700_000_000)],
                {commit_id: ["result.txt"]},
                change_history_available=True,
            )

        self.assertEqual(summary["status"], "PARTIAL")
        self.assertIn("GIT_SECRET_HISTORY_TREE_OUTPUT_LIMIT", summary["limitations"])
        self.assertEqual(warnings, ["GIT_SECRET_HISTORY_TREE_OUTPUT_LIMIT"])

    def test_git_runner_disables_lazy_object_fetch_and_pathspec_expansion(self):
        from repo_curator.git_evidence import _git_environment

        environment = _git_environment()
        self.assertEqual(environment["GIT_ALLOW_PROTOCOL"], "")
        self.assertEqual(environment["GIT_NO_LAZY_FETCH"], "1")
        self.assertEqual(environment["GIT_LITERAL_PATHSPECS"], "1")
        self.assertEqual(environment["GIT_NO_REPLACE_OBJECTS"], "1")
        self.assertEqual(environment["GIT_PROTOCOL_FROM_USER"], "0")

    def test_audit_reports_history_only_secret_category_without_persisting_value(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            self._git(repository, "init")
            self._git(repository, "config", "user.email", "fixture@example.test")
            self._git(repository, "config", "user.name", "Fixture")
            secret = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            secret_path = repository / "retired-credentials.txt"
            secret_path.write_text(secret + "\n", encoding="utf-8")
            self._git(repository, "add", "retired-credentials.txt")
            self._git(repository, "commit", "-m", "add retired credential fixture")
            secret_commit = self._git(repository, "rev-parse", "HEAD").stdout.strip()
            secret_path.unlink()
            self._git(repository, "add", "retired-credentials.txt")
            self._git(repository, "commit", "-m", "remove retired credential fixture")

            result = self._run_audit(repository)

            self.assertEqual(result.returncode, 0, result.stderr)
            _, _, observations = self._outputs(repository)
            summary = next(
                item
                for item in observations
                if item["observation_type"] == "GIT_SECRET_HISTORY_SUMMARY"
            )
            self.assertEqual(summary["status"], "OBSERVED")
            self.assertEqual(summary["coverage"], "RECENT_CHANGED_BLOBS_ONLY")
            self.assertEqual(summary["credential_validation"], "NOT_PERFORMED")
            self.assertEqual(
                summary["findings"],
                [
                    {
                        "category": "GITHUB_TOKEN",
                        "commit_id": secret_commit,
                        "repository_relative_path": "retired-credentials.txt",
                    }
                ],
            )
            self.assertIn(
                "GIT_SECRET_CREDENTIAL_VALIDATION_NOT_PERFORMED",
                summary["limitations"],
            )
            self.assertIn(
                "GIT_SECRET_PATTERN_MATCH_NOT_CREDENTIAL_VALIDITY",
                summary["limitations"],
            )
            for output in self._run_directory(repository).iterdir():
                if output.is_file():
                    self.assertNotIn(secret.encode("ascii"), output.read_bytes())

    def test_history_secret_blob_size_budget_reduces_coverage_without_aborting(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            self._git(repository, "init")
            self._git(repository, "config", "user.email", "fixture@example.test")
            self._git(repository, "config", "user.name", "Fixture")
            (repository / "large.txt").write_text("12345", encoding="ascii")
            self._git(repository, "add", "large.txt")
            self._git(repository, "commit", "-m", "oversized history fixture")

            with mock.patch(
                "repo_curator.git_evidence.HISTORY_SECRET_BLOB_BYTES", 4
            ):
                result = self._run_audit_in_process(repository)

            self.assertEqual(result.name, FIXED_RUN_ID)
            run, _, observations = self._outputs(repository)
            summary = next(
                item
                for item in observations
                if item["observation_type"] == "GIT_SECRET_HISTORY_SUMMARY"
            )
            self.assertEqual(summary["status"], "PARTIAL")
            self.assertEqual(summary["blob_count_scanned"], 0)
            self.assertIn("GIT_SECRET_HISTORY_BLOB_SIZE_LIMIT", summary["limitations"])
            self.assertIn(
                "GIT_SECRET_HISTORY_BLOB_SIZE_LIMIT",
                run["component_states"]["git"]["warnings"],
            )

    def test_shallow_repository_is_explicitly_limited_across_history_outputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            source = temporary_path / "source"
            repository = temporary_path / "shallow-repository"
            source.mkdir()
            self._git(source, "init")
            self._git(source, "config", "user.email", "fixture@example.test")
            self._git(source, "config", "user.name", "Fixture")
            (source / "first.txt").write_text("first\n", encoding="utf-8")
            self._git(source, "add", "first.txt")
            self._git(source, "commit", "-m", "first fixture commit")
            (source / "second.txt").write_text("second\n", encoding="utf-8")
            self._git(source, "add", "second.txt")
            self._git(source, "commit", "-m", "second fixture commit")
            subprocess.run(
                [
                    shutil.which("git"),
                    "clone",
                    "--depth=1",
                    source.as_uri(),
                    str(repository),
                ],
                text=True,
                capture_output=True,
                check=True,
            )

            result = self._run_audit(repository)

            self.assertEqual(result.returncode, 0, result.stderr)
            run, _, observations = self._outputs(repository)
            limitation = "GIT_SHALLOW_REPOSITORY_HISTORY_INCOMPLETE"
            self.assertIn(limitation, run["component_states"]["git"]["warnings"])
            worktree = next(
                item
                for item in observations
                if item["observation_type"] == "GIT_WORKTREE"
            )
            self.assertIn(limitation, worktree["limitations"])
            secret_summary = next(
                item
                for item in observations
                if item["observation_type"] == "GIT_SECRET_HISTORY_SUMMARY"
            )
            self.assertEqual(secret_summary["status"], "PARTIAL")
            self.assertIn(limitation, secret_summary["limitations"])
            self.assertIn(
                limitation,
                run["relationship_coverage"]["change_episode"]["limitations"],
            )

    def test_history_tree_parser_rejects_unrequested_and_malformed_entries(self):
        from repo_curator.git_evidence import _parse_history_tree

        object_id = b"a" * 40
        valid = b"100644 blob " + object_id + b" 12\trequested.txt\x00"
        entries, warnings = _parse_history_tree(valid, {"requested.txt"})
        self.assertEqual(entries, [("requested.txt", "a" * 40, 12)])
        self.assertEqual(warnings, [])

        entries, warnings = _parse_history_tree(valid, {":(glob)*"})
        self.assertEqual(entries, [])
        self.assertEqual(warnings, ["GIT_SECRET_HISTORY_TREE_MALFORMED"])

        malformed = b"100644 commit " + object_id + b" 12\trequested.txt\x00"
        entries, warnings = _parse_history_tree(malformed, {"requested.txt"})
        self.assertEqual(entries, [])
        self.assertEqual(warnings, ["GIT_SECRET_HISTORY_TREE_MALFORMED"])

    def test_audit_collects_sanitized_state_history_and_metadata(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            self._git(repository, "init")
            self._git(repository, "config", "user.email", "fixture@example.test")
            self._git(repository, "config", "user.name", "Fixture")
            (repository / ".gitignore").write_text("ignored/\n", encoding="utf-8")
            (repository / "tracked.txt").write_text("first\n", encoding="utf-8")
            (repository / "lfs.dat").write_text(
                "version https://git-lfs.github.com/spec/v1\n"
                "oid sha256:"
                + "a" * 64
                + "\nsize 42\n",
                encoding="ascii",
            )
            self._git(repository, "add", ".gitignore", "tracked.txt", "lfs.dat")
            self._git(repository, "commit", "-m", "fixture commit")
            (repository / "tracked.txt").write_text("second\n", encoding="utf-8")
            self._git(repository, "add", "tracked.txt")
            self._git(repository, "commit", "-m", "second fixture commit")
            self._git(
                repository,
                "update-index",
                "--add",
                "--cacheinfo",
                "160000," + "b" * 40 + ",submodules/example",
            )
            (repository / ".git" / "annex").mkdir()
            (repository / "tracked.txt").write_text("changed\n", encoding="utf-8")
            (repository / "untracked.txt").write_text("new\n", encoding="utf-8")
            (repository / "ignored").mkdir()
            (repository / "ignored" / "result.txt").write_text("ignored\n", encoding="utf-8")

            result = self._run_audit(repository)

            self.assertEqual(result.returncode, 0, result.stderr)
            run, records, observations = self._outputs(repository)
            self.assertEqual(run["repository_mode"], "GIT_WORKTREE")
            self.assertEqual(run["git_head"], self._git(repository, "rev-parse", "HEAD").stdout.strip())
            self.assertEqual(
                run["component_states"]["git"]["status"],
                "COMPLETED",
                run["component_states"]["git"]["warnings"],
            )
            self.assertEqual(
                run["output_file_hashes"]["git-observations.jsonl"],
                hashlib.sha256(
                    (self._run_directory(repository) / "git-observations.jsonl").read_bytes()
                ).hexdigest(),
            )

            self.assertTrue(records["tracked.txt"]["git_state"]["tracked"])
            self.assertTrue(records["tracked.txt"]["git_state"]["modified"])
            self.assertEqual(records["tracked.txt"]["git_state"]["index_status"], " M")
            self.assertTrue(records["untracked.txt"]["git_state"]["untracked"])
            self.assertTrue(records["ignored/result.txt"]["git_state"]["ignored_included"])
            self.assertEqual(
                records["lfs.dat"]["lfs_pointer"],
                {"oid": "sha256:" + "a" * 64, "size_bytes": 42},
            )
            self.assertIn("LFS_CONTENT_NOT_DOWNLOADED", records["lfs.dat"]["warnings"])
            self.assertEqual(records[".git"]["git_state"]["tracked"], None)

            self.assertTrue(
                any(
                    observation["observation_type"] == "GIT_COMMIT"
                    and observation["commit_id"] == run["git_head"]
                    for observation in observations
                )
            )
            self.assertTrue(
                any(
                    observation["observation_type"] == "GIT_SUBMODULE"
                    and observation["repository_relative_path"] == "submodules/example"
                    and observation["limitations"] == ["SUBMODULE_NOT_RECURSED"]
                    for observation in observations
                )
            )
            self.assertTrue(
                any(
                    observation["observation_type"] == "GIT_ANNEX_METADATA"
                    and observation["status"] == "PRESENT"
                    and observation["limitations"] == ["GIT_ANNEX_METADATA_NOT_RECURSED"]
                    for observation in observations
                )
            )
            self.assertTrue(
                all(
                    observation["origin"] == "DETERMINISTIC"
                    and observation["assertion_class"] == "OBSERVED"
                    for observation in observations
                )
            )

    def test_malicious_git_configuration_cannot_launch_a_program(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            self._git(repository, "init")
            self._git(repository, "config", "user.email", "fixture@example.test")
            self._git(repository, "config", "user.name", "Fixture")
            marker = repository / "configured-program-was-executed"
            command = repository / "configured-program"
            command.write_text("#!/bin/sh\ntouch " + str(marker) + "\n", encoding="utf-8")
            command.chmod(0o700)
            (repository / "tracked.txt").write_text("fixture\n", encoding="utf-8")
            self._git(repository, "add", "tracked.txt")
            self._git(repository, "commit", "-m", "fixture")
            for key, value in (
                ("core.hooksPath", str(repository / "hooks")),
                ("alias.status", "!" + str(command)),
                ("core.pager", str(command)),
                ("pager.status", str(command)),
                ("diff.external", str(command)),
                ("diff.poison.textconv", str(command)),
                ("filter.poison.clean", str(command)),
                ("core.fsmonitor", str(command)),
                ("credential.helper", str(command)),
                ("filter.lfs.process", str(command)),
            ):
                self._git(repository, "config", key, value)

            result = self._run_audit(repository)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(marker.exists())
            run, _, _ = self._outputs(repository)
            self.assertEqual(run["repository_mode"], "GIT_WORKTREE")

    def test_linked_worktree_is_observed_without_recursing_into_its_administration(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "primary"
            worktree = temporary_path / "linked"
            repository.mkdir()
            self._git(repository, "init")
            self._git(repository, "config", "user.email", "fixture@example.test")
            self._git(repository, "config", "user.name", "Fixture")
            (repository / "tracked.txt").write_text("fixture\n", encoding="utf-8")
            self._git(repository, "add", "tracked.txt")
            self._git(repository, "commit", "-m", "fixture")
            self._git(repository, "worktree", "add", "--detach", str(worktree), "HEAD")

            result = self._run_audit(worktree)

            self.assertEqual(result.returncode, 0, result.stderr)
            _, records, observations = self._outputs(worktree)
            self.assertIn("PROTECTED_GIT_CONTROL", records[".git"]["warnings"])
            self.assertTrue(
                any(
                    observation["observation_type"] == "GIT_WORKTREE"
                    and observation["kind"] == "LINKED_WORKTREE"
                    and observation["limitations"]
                    == ["LINKED_WORKTREE_ADMINISTRATION_NOT_RECURSED"]
                    for observation in observations
                )
            )
            self.assertFalse(any(path.startswith(".git/") for path in records))

    def test_missing_git_and_malformed_history_reduce_coverage_without_aborting(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "README.md").write_text("fixture\n", encoding="utf-8")

            with mock.patch("repo_curator.git_evidence._git_executable", return_value=None):
                result = self._run_audit_in_process(repository)

            self.assertEqual(result.name, FIXED_RUN_ID)
            run, _, observations = self._outputs(repository)
            self.assertEqual(run["repository_mode"], "FILESYSTEM")
            self.assertIn("GIT_UNAVAILABLE", run["component_states"]["git"]["warnings"])
            self.assertEqual(observations, [])

        from repo_curator.git_evidence import _parse_history

        self.assertEqual(_parse_history(b"broken\x00record\x00"), ([], ["GIT_HISTORY_MALFORMED"]))

    def test_history_parser_accepts_multiple_nul_terminated_records(self):
        from repo_curator.git_evidence import _parse_history

        first_commit = "a" * 40
        second_commit = "b" * 40
        history, warnings = _parse_history(
            (
                first_commit.encode("ascii")
                + b"\x00\x00"
                + b"1700000000\x00"
                + second_commit.encode("ascii")
                + b"\x00"
                + first_commit.encode("ascii")
                + b"\x00"
                + b"1700000100\x00"
            )
        )

        self.assertEqual(warnings, [])
        self.assertEqual(
            history,
            [
                (first_commit, [], 1_700_000_000),
                (second_commit, [first_commit], 1_700_000_100),
            ],
        )

    def test_file_level_cochange_creates_only_a_limited_episode_candidate(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            self._git(repository, "init")
            self._git(repository, "config", "user.email", "fixture@example.test")
            self._git(repository, "config", "user.name", "Fixture")
            (repository / "relationship-manifest.json").write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {"path": "analysis.py", "episode": "declared-event"},
                            {"path": "config.yaml", "episode": "declared-event"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            self._git(repository, "add", "relationship-manifest.json")
            self._git(repository, "commit", "-m", "add relationship declaration")
            (repository / "analysis.py").write_text("def analyze(): pass\n", encoding="utf-8")
            (repository / "config.yaml").write_text("model: baseline\n", encoding="utf-8")
            self._git(repository, "add", "analysis.py", "config.yaml")
            self._git(repository, "commit", "-m", "add analysis fixture")

            result = self._run_audit(repository)

            self.assertEqual(result.returncode, 0, result.stderr)
            run, _, observations = self._outputs(repository)
            head = next(
                item
                for item in observations
                if item["observation_type"] == "GIT_COMMIT"
                and item["commit_id"] == run["git_head"]
            )
            self.assertEqual(head["changed_paths"], ["analysis.py", "config.yaml"])
            episodes = self._json_lines(self._run_directory(repository) / "change-episodes.jsonl")
            self.assertEqual(len(episodes), 2)
            self.assertEqual(
                {episode["event_evidence"] for episode in episodes},
                {"declared-event", run["git_head"]},
            )
            git_episode = next(
                episode for episode in episodes
                if episode["event_evidence"] == run["git_head"]
            )
            self.assertEqual(git_episode["member_paths"], ["analysis.py", "config.yaml"])
            self.assertEqual(
                git_episode["limitations"], ["GIT_COCHANGE_NOT_COMMON_PURPOSE"]
            )
            self.assertTrue(
                git_episode["supporting_evidence_ids"][0].startswith("evidence_"),
                git_episode["supporting_evidence_ids"],
            )
            self.assertEqual(len({episode["episode_id"] for episode in episodes}), 2)
            self.assertEqual(
                run["relationship_coverage"]["change_episode"]["status"],
                "AVAILABLE_MIXED_EVIDENCE",
            )

    def test_diff_tree_parser_is_stateful_for_control_looking_paths(self):
        from repo_curator.git_evidence import _parse_changed_paths

        commit = "a" * 40
        hash_path = "b" * 40
        payload = (
            commit.encode("ascii")
            + b"\x00"
            + b":100644 100644 "
            + b"c" * 40
            + b" "
            + b"d" * 40
            + b" M\x00"
            + hash_path.encode("ascii")
            + b"\x00"
            + b":100644 100644 "
            + b"e" * 40
            + b" "
            + b"f" * 40
            + b" M\x00"
            + b":looks-like-metadata.py\x00"
        )

        changed, warnings = _parse_changed_paths(payload, [commit])

        self.assertEqual(
            changed,
            {commit: [":looks-like-metadata.py", hash_path]},
        )
        self.assertEqual(warnings, [])
        self.assertEqual(
            _parse_changed_paths(b"malformed\x00", [commit]),
            ({}, ["GIT_CHANGE_HISTORY_MALFORMED"]),
        )

    def test_large_git_cochange_is_retained_but_not_grouped_as_an_episode(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            self._git(repository, "init")
            self._git(repository, "config", "user.email", "fixture@example.test")
            self._git(repository, "config", "user.name", "Fixture")
            paths = []
            for index in range(65):
                path = f"bulk-{index:03d}.txt"
                (repository / path).write_text("fixture\n", encoding="utf-8")
                paths.append(path)
            self._git(repository, "add", *paths)
            self._git(repository, "commit", "-m", "bulk import fixture")
            (repository / "small-a.txt").write_text("fixture\n", encoding="utf-8")
            (repository / "small-b.txt").write_text("fixture\n", encoding="utf-8")
            self._git(repository, "add", "small-a.txt", "small-b.txt")
            self._git(repository, "commit", "-m", "small change fixture")

            result = self._run_audit(repository)

            self.assertEqual(result.returncode, 0, result.stderr)
            run, _, _ = self._outputs(repository)
            episodes = self._json_lines(self._run_directory(repository) / "change-episodes.jsonl")
            self.assertEqual(len(episodes), 1)
            self.assertEqual(episodes[0]["member_paths"], ["small-a.txt", "small-b.txt"])
            self.assertEqual(
                run["relationship_coverage"]["change_episode"],
                {
                    "candidate_count": 1,
                    "limitations": [
                        "GIT_COCHANGE_MEMBER_LIMIT",
                        "GIT_COCHANGE_NOT_COMMON_PURPOSE",
                    ],
                    "status": "AVAILABLE_GIT_COCHANGE_ONLY",
                },
            )

    def _git(self, repository: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [shutil.which("git"), *arguments],
            cwd=repository,
            text=True,
            capture_output=True,
            check=True,
        )

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
            text=True,
            capture_output=True,
            check=False,
        )

    def _run_audit_in_process(self, repository: Path) -> Path:
        return inventory.audit_repository(repository, FIXED_RUN_ID, FIXED_CREATED_AT)

    def _outputs(self, repository: Path) -> tuple[dict, dict[str, dict], list[dict]]:
        run_directory = self._run_directory(repository)
        run = json.loads((run_directory / "run.json").read_text(encoding="utf-8"))
        records = {
            record["repository_relative_path"]: record
            for record in self._json_lines(run_directory / "inventory.jsonl")
        }
        return run, records, self._json_lines(run_directory / "git-observations.jsonl")

    def _run_directory(self, repository: Path) -> Path:
        return repository / ".repo-curator" / "runs" / FIXED_RUN_ID

    def _json_lines(self, path: Path) -> list[dict]:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
        ]


if __name__ == "__main__":
    unittest.main()
