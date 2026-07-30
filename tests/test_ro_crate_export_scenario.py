import json
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from repo_curator import interchange
from repo_curator.interchange import export_ro_crate
from repo_curator.inventory import audit_repository


class RoCrateExportScenarioTest(unittest.TestCase):
    def test_verified_audit_exports_non_executable_evidence_with_provenance(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            (repository / "README.md").write_text("mainline: analysis.py\n", encoding="utf-8")
            (repository / "analysis.py").write_text("print('not executed')\n", encoding="utf-8")
            audit_repository(repository, "ro-crate-run", "2026-07-27T00:00:00Z")
            run_directory = repository / ".repo-curator" / "runs" / "ro-crate-run"
            output = workspace / "export" / "ro-crate-metadata.json"

            export_ro_crate(run_directory, output)

            document = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(document["@context"][1]["repo-curator"], "https://github.com/Dean-999/repo-curator#")
            root = next(item for item in document["@graph"] if item["@id"] == "./")
            self.assertFalse(root["repo-curator:executionAuthorized"])
            evidence = next(
                item for item in document["@graph"] if item["@id"].startswith("#evidence/")
            )
            self.assertIn(evidence["repo-curator:assertionOrigin"], {"DECLARED", "DETERMINISTIC", "OBSERVED"})
            self.assertEqual(evidence["repo-curator:confidence"], "NOT_ASSIGNED")
            self.assertIn("repo-curator:counterEvidence", evidence)
            self.assertIn("repo-curator:limitations", evidence)
            mainline = next(
                item
                for item in document["@graph"]
                if item["@id"].startswith("#mainline/")
                and item["repo-curator:claimStatus"] == "ACTIVE_MAINLINE"
            )
            self.assertEqual(mainline["repo-curator:claimStatus"], "ACTIVE_MAINLINE")
            self.assertIn("repo-curator:supportingEvidence", mainline)
            self.assertFalse((repository / "target-executed").exists())

    def test_tampered_or_existing_output_is_rejected_without_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            audit_repository(repository, "ro-crate-run", "2026-07-27T00:00:00Z")
            run_directory = repository / ".repo-curator" / "runs" / "ro-crate-run"
            output = workspace / "export.json"
            evidence_path = run_directory / "evidence.jsonl"
            evidence_path.write_bytes(evidence_path.read_bytes() + b"{}\n")

            with self.assertRaisesRegex(ValueError, "output hash mismatch"):
                export_ro_crate(run_directory, output)
            self.assertFalse(output.exists())

            evidence_path.write_bytes(evidence_path.read_bytes()[:-3])
            output.write_text("preserve", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                export_ro_crate(run_directory, output)
            self.assertEqual(output.read_text(encoding="utf-8"), "preserve")

    def test_total_verified_input_limit_creates_no_export(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            audit_repository(repository, "ro-crate-run", "2026-07-27T00:00:00Z")
            run_directory = repository / ".repo-curator" / "runs" / "ro-crate-run"
            output = workspace / "export.json"

            with mock.patch.object(interchange, "_MAX_TOTAL_INPUT_BYTES", 1):
                with self.assertRaisesRegex(
                    ValueError, "audit run outputs exceed total byte limit"
                ):
                    export_ro_crate(run_directory, output)

            self.assertFalse(output.exists())

    def test_entity_limit_creates_no_export(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            audit_repository(repository, "ro-crate-run", "2026-07-27T00:00:00Z")
            run_directory = repository / ".repo-curator" / "runs" / "ro-crate-run"
            output = workspace / "export.json"

            with mock.patch.object(interchange, "_MAX_JSONL_RECORDS", 0):
                with self.assertRaisesRegex(ValueError, "evidence exceeds entity limit"):
                    export_ro_crate(run_directory, output)

            self.assertFalse(output.exists())

    def test_output_declaration_limit_creates_no_export(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            audit_repository(repository, "ro-crate-run", "2026-07-27T00:00:00Z")
            run_directory = repository / ".repo-curator" / "runs" / "ro-crate-run"
            output = workspace / "export.json"

            with mock.patch.object(interchange, "_MAX_OUTPUT_FILES", 0):
                with self.assertRaisesRegex(
                    ValueError, "audit run output declaration limit"
                ):
                    export_ro_crate(run_directory, output)

            self.assertFalse(output.exists())

    def test_single_verified_output_limit_creates_no_export(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            audit_repository(repository, "ro-crate-run", "2026-07-27T00:00:00Z")
            run_directory = repository / ".repo-curator" / "runs" / "ro-crate-run"
            output = workspace / "export.json"

            with mock.patch.object(interchange, "_MAX_OUTPUT_FILE_BYTES", 1):
                with self.assertRaisesRegex(
                    ValueError, "audit run output exceeds file byte limit"
                ):
                    export_ro_crate(run_directory, output)

            self.assertFalse(output.exists())

    def test_export_retries_short_writes_until_json_is_complete(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            audit_repository(repository, "ro-crate-run", "2026-07-27T00:00:00Z")
            run_directory = repository / ".repo-curator" / "runs" / "ro-crate-run"
            output = workspace / "export.json"
            original_write = interchange.os.write
            write_calls = 0

            def short_write(descriptor, content):
                nonlocal write_calls
                write_calls += 1
                maximum = max(1, len(content) // 2)
                return original_write(descriptor, content[:maximum])

            with mock.patch.object(interchange.os, "write", side_effect=short_write):
                export_ro_crate(run_directory, output)

            self.assertGreater(write_calls, 1)
            document = json.loads(output.read_text(encoding="utf-8"))
            self.assertTrue(document["@graph"])

    def test_export_creates_relative_to_open_parent_and_fsyncs_file_and_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            audit_repository(repository, "ro-crate-run", "2026-07-27T00:00:00Z")
            run_directory = repository / ".repo-curator" / "runs" / "ro-crate-run"
            output = workspace / "export" / "ro-crate-metadata.json"
            original_open = interchange.os.open
            original_fsync = interchange.os.fsync
            create_calls = []
            synced_types = []

            def observe_open(path, flags, *args, **kwargs):
                if flags & os.O_CREAT:
                    create_calls.append((path, kwargs.get("dir_fd")))
                return original_open(path, flags, *args, **kwargs)

            def observe_fsync(descriptor):
                mode = os.fstat(descriptor).st_mode
                synced_types.append(
                    "directory" if stat.S_ISDIR(mode) else "regular-file"
                )
                return original_fsync(descriptor)

            with mock.patch.object(interchange.os, "open", side_effect=observe_open):
                with mock.patch.object(interchange.os, "fsync", side_effect=observe_fsync):
                    export_ro_crate(run_directory, output)

            self.assertEqual(create_calls, [("ro-crate-metadata.json", mock.ANY)])
            self.assertIsInstance(create_calls[0][1], int)
            self.assertEqual(synced_types[-2:], ["regular-file", "directory"])

    def test_export_binds_a_preexisting_symlinked_ancestor_to_its_real_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            audit_repository(repository, "ro-crate-run", "2026-07-27T00:00:00Z")
            run_directory = repository / ".repo-curator" / "runs" / "ro-crate-run"
            external = workspace / "external"
            external.mkdir()
            linked = workspace / "linked"
            linked.symlink_to(external, target_is_directory=True)
            output = linked / "nested" / "ro-crate-metadata.json"

            export_ro_crate(run_directory, output)

            self.assertTrue((external / "nested" / "ro-crate-metadata.json").is_file())
