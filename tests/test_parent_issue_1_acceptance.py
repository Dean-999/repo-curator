"""Cross-platform black-box acceptance coverage for parent Issue #1."""

import errno
import hashlib
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
import unicodedata
from pathlib import Path
from typing import Optional

FIXED_RUN_ID = "parent-issue-one-fixture"
FIXED_CREATED_AT = "2026-07-19T00:00:00Z"
UNSUPPORTED_FILENAME_ERRNOS = {
    errno.EILSEQ,
    errno.ENOSYS,
    getattr(errno, "ENOTSUP", errno.EOPNOTSUPP),
    errno.EOPNOTSUPP,
}
UNSUPPORTED_FIFO_ERRNOS = {
    errno.ENOSYS,
    getattr(errno, "ENOTSUP", errno.EOPNOTSUPP),
    errno.EOPNOTSUPP,
}
UNSUPPORTED_UNIX_SOCKET_ERRNOS = UNSUPPORTED_FIFO_ERRNOS | {
    getattr(errno, "EAFNOSUPPORT", errno.EPROTONOSUPPORT),
    getattr(errno, "EPFNOSUPPORT", errno.EPROTONOSUPPORT),
    errno.EPROTONOSUPPORT,
}
EXPECTED_DECLARATION_FAMILIES = {
    "DVC",
    "DATALAD",
    "MLFLOW",
    "SACRED",
    "RO_CRATE",
    "BAGIT",
}


def _collision_key(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()


class ParentIssueOneAcceptanceTest(unittest.TestCase):
    def test_parent_issue_one_fixture_matrix(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "research-repository"
            repository.mkdir()
            capability_skips, socket_server = self._build_fixture(repository)
            markers, environment = self._fake_external_environment(temporary_path)
            original_contents = self._snapshot_target_contents(repository)
            original_hard_link_topology = self._hard_link_topology(repository)

            try:
                first_result = self._run_audit(repository, environment)
                self.assertEqual(first_result.returncode, 0, first_result.stderr)

                run_directory = self._run_directory(repository)
                first_outputs = {
                    name: (run_directory / name).read_bytes()
                    for name in (
                        "inventory.jsonl",
                        "adapter-observations.jsonl",
                        "run.json",
                    )
                }
                records = self._json_lines(first_outputs["inventory.jsonl"])
                observations = self._json_lines(
                    first_outputs["adapter-observations.jsonl"]
                )
                run = json.loads(first_outputs["run.json"])
                records_by_path = {
                    record["repository_relative_path"]: record for record in records
                }

                self._assert_inventory_contract(
                    records_by_path,
                    observations,
                    run,
                    first_outputs,
                    capability_skips,
                )
                self.assertFalse(any(marker.exists() for marker in markers))
                self.assertEqual(
                    self._snapshot_target_contents(repository), original_contents
                )
                self.assertEqual(
                    self._hard_link_topology(repository), original_hard_link_topology
                )

                shutil.rmtree(repository / ".repo-curator")
                second_result = self._run_audit(repository, environment)
                self.assertEqual(second_result.returncode, 0, second_result.stderr)
                for name, first_bytes in first_outputs.items():
                    with self.subTest(output=name):
                        self.assertEqual(
                            (self._run_directory(repository) / name).read_bytes(),
                            first_bytes,
                        )
                self.assertFalse(any(marker.exists() for marker in markers))
                self.assertEqual(
                    self._snapshot_target_contents(repository), original_contents
                )
                self.assertEqual(
                    self._hard_link_topology(repository), original_hard_link_topology
                )
            finally:
                if socket_server is not None:
                    socket_server.close()

    def _build_fixture(
        self, repository: Path
    ) -> tuple[set[str], Optional[socket.socket]]:
        """Create optional filesystem objects before the audit begins."""
        capability_skips: set[str] = set()
        (repository / "README.md").write_text("ordinary\n", encoding="utf-8")
        (repository / ".hidden-note").write_text("hidden\n", encoding="utf-8")
        (repository / ".gitignore").write_text("*.ignored\n", encoding="utf-8")
        (repository / "ignored-pattern.ignored").write_text("kept\n", encoding="utf-8")
        (repository / "inside.txt").write_text("inside\n", encoding="utf-8")
        (repository / "large.bin").write_bytes(b"123456789")

        hard_link_source = repository / "hard-link-source.txt"
        hard_link_source.write_bytes(b"linked\n")
        os.link(hard_link_source, repository / "hard-link-peer.txt")

        case_a = repository / "Caf\u00e9.txt"
        case_b = repository / "Cafe\u0301.TXT"
        case_a.write_text("nfc\n", encoding="utf-8")
        try:
            case_b.write_text("nfd\n", encoding="utf-8")
        except OSError as error:
            if error.errno not in UNSUPPORTED_FILENAME_ERRNOS:
                raise
            capability_skips.add("unicode_case_collision")
        else:
            colliding = [
                name
                for name in os.listdir(repository)
                if _collision_key(name) == _collision_key(case_a.name)
            ]
            if len(colliding) != 2:
                capability_skips.add("unicode_case_collision")

        external_directory = repository.parent / "external"
        external_directory.mkdir()
        external_secret = external_directory / "secret.txt"
        external_secret.write_text("outside\n", encoding="utf-8")
        (repository / "internal-link").symlink_to("inside.txt")
        (repository / "external-link").symlink_to(external_secret)
        (repository / "broken-link").symlink_to("missing.txt")
        (repository / "bridge").symlink_to(external_directory, target_is_directory=True)
        (repository / "through-intermediate-link").symlink_to("bridge/secret.txt")

        if not hasattr(os, "mkfifo"):
            capability_skips.add("fifo")
        else:
            try:
                os.mkfifo(repository / "events.fifo")
            except OSError as error:
                if error.errno not in UNSUPPORTED_FIFO_ERRNOS:
                    raise
                capability_skips.add("fifo")

        socket_server = None
        if hasattr(socket, "AF_UNIX"):
            try:
                socket_server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                socket_server.bind(str(repository / "events.sock"))
            except OSError as error:
                if socket_server is not None:
                    socket_server.close()
                socket_server = None
                if error.errno not in UNSUPPORTED_UNIX_SOCKET_ERRNOS:
                    raise
                capability_skips.add("unix_socket")
        else:
            capability_skips.add("unix_socket")

        # These are boundaries only; no Git command is needed or permitted.
        (repository / ".git" / "hooks").mkdir(parents=True)
        (repository / ".git" / "config").write_text("untrusted\n", encoding="utf-8")
        self._write_marker_command(
            repository / ".git" / "hooks" / "post-checkout",
            repository / "hook-was-executed",
        )
        nested = repository / "nested-repository"
        (nested / ".git").mkdir(parents=True)
        (nested / ".git" / "config").write_text("untrusted\n", encoding="utf-8")
        (nested / "target.py").write_text("raise SystemExit('must not run')\n", encoding="utf-8")

        (repository / "dvc.yaml").write_text("stages: {}\n", encoding="utf-8")
        (repository / ".datalad").mkdir()
        (repository / ".datalad" / "config").write_text("[datalad]\n", encoding="utf-8")
        (repository / "MLproject").write_text("name: fixture\n", encoding="utf-8")
        sacred = repository / "sacred-complete"
        sacred.mkdir()
        (sacred / "config.json").write_text("{}", encoding="utf-8")
        (sacred / "run.json").write_text("{}", encoding="utf-8")
        partial_sacred = repository / "sacred-partial"
        partial_sacred.mkdir()
        (partial_sacred / "config.json").write_text("{}", encoding="utf-8")
        oversized_sacred = repository / "sacred-over-budget"
        oversized_sacred.mkdir()
        (oversized_sacred / "config.json").write_bytes(b"123456789")
        (oversized_sacred / "run.json").write_text("{}", encoding="utf-8")
        # ``NaN`` is short enough for the 8-byte audit budget but invalid under
        # the strict JSON parser used for declaration validation.
        (repository / "ro-crate-metadata.json").write_text("NaN", encoding="utf-8")
        (repository / "bagit.txt").write_text("BagIt-Version: 1.0\n", encoding="utf-8")
        self._write_marker_command(
            repository / "target-command", repository / "target-command-was-executed"
        )
        return capability_skips, socket_server

    def _assert_inventory_contract(
        self,
        records: dict[str, dict],
        observations: list[dict],
        run: dict,
        outputs: dict[str, bytes],
        capability_skips: set[str],
    ) -> None:
        for path in ("README.md", ".hidden-note", ".gitignore", "ignored-pattern.ignored"):
            self.assertIn(path, records)
        self.assertEqual(run["repository_mode"], "FILESYSTEM")
        self.assertIsNone(run["git_head"])
        self.assertEqual(records["ignored-pattern.ignored"]["git_state"]["tracked"], None)

        self.assertEqual(
            records["hard-link-source.txt"]["content_id"],
            records["hard-link-peer.txt"]["content_id"],
        )
        self.assertEqual(
            records["hard-link-source.txt"]["content_id"],
            "sha256-file-v1:" + hashlib.sha256(b"linked\n").hexdigest(),
        )
        self.assertNotEqual(
            records["hard-link-source.txt"]["artifact_id"],
            records["hard-link-peer.txt"]["artifact_id"],
        )
        self.assertNotEqual(
            records["hard-link-source.txt"]["location_id"],
            records["hard-link-peer.txt"]["location_id"],
        )
        for path in ("hard-link-source.txt", "hard-link-peer.txt"):
            self.assertIsNone(records[path]["lineage_id"])
            self.assertEqual(records[path]["lineage_status"], "UNRESOLVED")
        if "unicode_case_collision" not in capability_skips:
            for path in ("Caf\u00e9.txt", "Cafe\u0301.TXT"):
                self.assertIn("CASE_COLLISION", records[path]["warnings"])

        self.assertEqual(records["internal-link"]["object_type"], "SYMLINK")
        self.assertEqual(records["internal-link"]["symlink_target_text"], "inside.txt")
        self.assertIn("SYMLINK_TARGET_OUTSIDE_ROOT", records["external-link"]["warnings"])
        self.assertIn("SYMLINK_TARGET_MISSING", records["broken-link"]["warnings"])
        self.assertIn(
            "SYMLINK_TARGET_OUTSIDE_ROOT",
            records["through-intermediate-link"]["warnings"],
        )

        self.assertIsNone(records["large.bin"]["content_id"])
        self.assertIn("CONTENT_HASH_SKIPPED_SIZE_LIMIT", records["large.bin"]["warnings"])
        self.assertIsNone(records["."]["content_id"])
        self.assertIn("CONTENT_HASH_SKIPPED_SIZE_LIMIT", records["."]["warnings"])
        self.assertIsNone(records["sacred-over-budget"]["content_id"])
        self.assertIn(
            "CONTENT_HASH_SKIPPED_SIZE_LIMIT",
            records["sacred-over-budget"]["warnings"],
        )
        if "fifo" not in capability_skips:
            self.assertEqual(records["events.fifo"]["object_type"], "SPECIAL_FILE")
            self.assertIsNone(records["events.fifo"]["content_id"])
            self.assertIn("SPECIAL_FILE_NOT_READ", records["events.fifo"]["warnings"])
        if "unix_socket" not in capability_skips:
            self.assertEqual(records["events.sock"]["object_type"], "SPECIAL_FILE")
            self.assertIsNone(records["events.sock"]["content_id"])
            self.assertIn("SPECIAL_FILE_NOT_READ", records["events.sock"]["warnings"])

        self.assertIn("PROTECTED_GIT_CONTROL", records[".git"]["warnings"])
        self.assertIn(
            "NESTED_REPOSITORY_BOUNDARY", records["nested-repository"]["warnings"]
        )
        self.assertNotIn(".git/config", records)
        self.assertNotIn("nested-repository/target.py", records)

        self.assertEqual(
            {observation["declaration_family"] for observation in observations},
            EXPECTED_DECLARATION_FAMILIES,
        )
        self.assertEqual(
            [observation["observation_id"] for observation in observations],
            [
                f"obs_{FIXED_RUN_ID}_{sequence:08d}"
                for sequence in range(1, len(observations) + 1)
            ],
        )
        self.assertTrue(
            all(
                observation["coverage"] == "DECLARATION_PRESENCE_ONLY"
                for observation in observations
            )
        )
        self.assertTrue(
            all(
                "EXECUTED" not in observation["status"]
                and "EXECUTED" not in observation["validation_status"]
                and "REPRODUCED" not in observation["status"]
                and "REPRODUCED" not in observation["validation_status"]
                for observation in observations
            )
        )
        records_by_artifact_id = {
            record["artifact_id"]: record for record in records.values()
        }
        self.assertEqual(len(records_by_artifact_id), len(records))
        for observation in observations:
            source = records_by_artifact_id[observation["source_artifact_id"]]
            self.assertEqual(
                source["location_id"], observation["source_location_id"]
            )
        for family in ("DVC", "DATALAD", "MLFLOW", "BAGIT"):
            observation = next(
                item for item in observations if item["declaration_family"] == family
            )
            self.assertEqual(observation["status"], "PRESENT")
            self.assertEqual(observation["validation_status"], "NOT_APPLICABLE")
            self.assertEqual(observation["coverage"], "DECLARATION_PRESENCE_ONLY")
        sacred_observations = [
            observation
            for observation in observations
            if observation["declaration_family"] == "SACRED"
        ]
        self.assertTrue(
            any("DECLARATION_PARTIAL" in item["limitations"] for item in sacred_observations)
        )
        self.assertTrue(
            any(
                item["status"] == "PRESENT_UNVALIDATED"
                and "DECLARATION_VALIDATION_UNAVAILABLE" in item["limitations"]
                for item in sacred_observations
            )
        )
        sacred_by_source_path = {
            records_by_artifact_id[item["source_artifact_id"]][
                "repository_relative_path"
            ]: item
            for item in sacred_observations
        }
        self.assertEqual(
            sacred_by_source_path["sacred-complete/run.json"]["status"], "PRESENT"
        )
        self.assertEqual(
            sacred_by_source_path["sacred-complete/run.json"]["validation_status"],
            "SYNTAX_VALIDATED",
        )
        self.assertEqual(
            sacred_by_source_path["sacred-partial/config.json"]["status"], "PARTIAL"
        )
        self.assertEqual(
            sacred_by_source_path["sacred-over-budget/run.json"]["status"],
            "PRESENT_UNVALIDATED",
        )
        self.assertIn(
            "DECLARATION_VALIDATION_UNAVAILABLE",
            sacred_by_source_path["sacred-over-budget/run.json"]["limitations"],
        )
        crate = next(
            observation
            for observation in observations
            if observation["declaration_family"] == "RO_CRATE"
        )
        self.assertEqual(crate["status"], "MALFORMED")
        self.assertIn("DECLARATION_MALFORMED", crate["limitations"])
        self.assertEqual(run["final_status"], "COMPLETED_WITH_LIMITATIONS")
        for warning in (
            "CONTENT_HASH_SKIPPED_SIZE_LIMIT",
            "DECLARATION_MALFORMED",
            "PROTECTED_GIT_CONTROL",
        ):
            self.assertIn(warning, run["warnings"])
        self.assertEqual(
            run["component_states"]["inventory"]["status"],
            "COMPLETED_WITH_LIMITATIONS",
        )
        self.assertEqual(
            run["component_states"]["declarations"]["status"],
            "COMPLETED_WITH_LIMITATIONS",
        )
        for record in records.values():
            self.assertIsNone(record["lineage_id"])
            self.assertEqual(record["lineage_status"], "UNRESOLVED")
        for name in ("inventory.jsonl", "adapter-observations.jsonl"):
            self.assertEqual(
                run["output_file_hashes"][name],
                hashlib.sha256(outputs[name]).hexdigest(),
            )

    def _fake_external_environment(self, temporary_path: Path) -> tuple[list[Path], dict[str, str]]:
        fake_bin = temporary_path / "fake-bin"
        fake_bin.mkdir()
        markers = []
        for executable in (
            "git",
            "dvc",
            "datalad",
            "mlflow",
            "sacred",
            "bagit",
            "pip",
            "npm",
            "conda",
            "make",
        ):
            marker = temporary_path / f"{executable}-was-called"
            self._write_marker_command(fake_bin / executable, marker)
            markers.append(marker)
        environment = os.environ.copy()
        environment["PATH"] = f"{fake_bin}{os.pathsep}{environment.get('PATH', '')}"
        return markers, environment

    def _write_marker_command(self, command: Path, marker: Path) -> None:
        command.write_text("#!/bin/sh\ntouch " + str(marker) + "\n", encoding="utf-8")
        command.chmod(0o700)

    def _run_audit(self, repository: Path, environment: dict[str, str]) -> subprocess.CompletedProcess[str]:
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
                "--max-file-bytes",
                "8",
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def _run_directory(self, repository: Path) -> Path:
        return repository / ".repo-curator" / "runs" / FIXED_RUN_ID

    def _snapshot_target_contents(
        self, repository: Path
    ) -> dict[str, tuple[str, int, int, int, Optional[bytes]]]:
        snapshot = {}
        for path in [repository, *sorted(repository.rglob("*"))]:
            if ".repo-curator" in path.parts:
                continue
            metadata = path.lstat()
            mode = metadata.st_mode
            relative_path = (
                "." if path == repository else path.relative_to(repository).as_posix()
            )
            content = None
            if stat.S_ISREG(mode):
                object_type = "REGULAR_FILE"
                content = path.read_bytes()
            elif stat.S_ISLNK(mode):
                object_type = "SYMLINK"
                content = os.fsencode(os.readlink(path))
            elif stat.S_ISDIR(mode):
                object_type = "DIRECTORY"
            elif stat.S_ISFIFO(mode):
                object_type = "FIFO"
            elif stat.S_ISSOCK(mode):
                object_type = "SOCKET"
            elif stat.S_ISCHR(mode):
                object_type = "CHARACTER_DEVICE"
            elif stat.S_ISBLK(mode):
                object_type = "BLOCK_DEVICE"
            else:
                object_type = "UNKNOWN"
            snapshot[relative_path] = (
                object_type,
                mode & 0o7777,
                metadata.st_dev,
                metadata.st_ino,
                content,
            )
        return snapshot

    def _json_lines(self, payload: bytes) -> list[dict]:
        return [json.loads(line) for line in payload.decode("utf-8").splitlines()]

    def _hard_link_topology(self, repository: Path) -> tuple[int, int, int]:
        source = (repository / "hard-link-source.txt").lstat()
        peer = (repository / "hard-link-peer.txt").lstat()
        self.assertEqual((source.st_dev, source.st_ino), (peer.st_dev, peer.st_ino))
        self.assertGreaterEqual(source.st_nlink, 2)
        return source.st_dev, source.st_ino, source.st_nlink


if __name__ == "__main__":
    unittest.main()
