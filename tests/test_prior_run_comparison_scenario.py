import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from repo_curator import prior_runs
from repo_curator.inventory import audit_repository


class PriorRunComparisonScenarioTest(unittest.TestCase):
    def test_verified_prior_run_yields_deterministic_artifact_and_evidence_changes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()
            (repository / "README.md").write_text("mainline: current.py\n", encoding="utf-8")
            (repository / "current.py").write_text("first\n", encoding="utf-8")
            (repository / "moved.py").write_text("same bytes\n", encoding="utf-8")
            (repository / "old.py").write_text("old\n", encoding="utf-8")
            audit_repository(repository, "first-run", "2026-07-27T00:00:00Z")

            (repository / "current.py").write_text("second\n", encoding="utf-8")
            (repository / "moved.py").rename(repository / "renamed.py")
            (repository / "old.py").unlink()
            (repository / "new.py").write_text("new\n", encoding="utf-8")
            audit_repository(
                repository,
                "second-run",
                "2026-07-27T00:01:00Z",
                compare_to_run_id="first-run",
            )

            output = repository / ".repo-curator" / "runs" / "second-run"
            comparison = json.loads((output / "prior-run-comparison.json").read_text(encoding="utf-8"))
            self.assertEqual(comparison["previous_run_id"], "first-run")
            self.assertEqual(comparison["schema_version"], "repo-curator.prior-run-comparison.v1")
            self.assertIn(
                {"from_path": "moved.py", "to_path": "renamed.py"},
                comparison["moved_artifacts"],
            )
            self.assertEqual(comparison["added_artifact_paths"], ["new.py"])
            self.assertEqual(comparison["removed_artifact_paths"], ["old.py"])
            self.assertEqual(comparison["changed_artifact_paths"], ["current.py"])
            self.assertEqual(comparison["still_unresolved_mainline_paths"], ["README.md"])
            run = json.loads((output / "run.json").read_text(encoding="utf-8"))
            self.assertIn("prior-run-comparison.json", run["output_file_hashes"])

    def test_prior_run_hash_failure_stops_before_new_run_is_published(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()
            (repository / "source.py").write_text("value = 1\n", encoding="utf-8")
            audit_repository(repository, "first-run", "2026-07-27T00:00:00Z")
            prior_inventory = repository / ".repo-curator" / "runs" / "first-run" / "inventory.jsonl"
            prior_inventory.write_bytes(prior_inventory.read_bytes() + b"tamper\n")

            with self.assertRaisesRegex(ValueError, "prior run output hash mismatch"):
                audit_repository(
                    repository,
                    "second-run",
                    "2026-07-27T00:01:00Z",
                    compare_to_run_id="first-run",
                )
            self.assertFalse((repository / ".repo-curator" / "runs" / "second-run").exists())

    def test_prior_run_total_input_limit_stops_before_new_run_is_published(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()
            (repository / "source.py").write_text("value = 1\n", encoding="utf-8")
            audit_repository(repository, "first-run", "2026-07-27T00:00:00Z")

            with mock.patch.object(prior_runs, "_MAX_TOTAL_INPUT_BYTES", 1):
                with self.assertRaisesRegex(
                    ValueError, "prior run outputs exceed total byte limit"
                ):
                    audit_repository(
                        repository,
                        "second-run",
                        "2026-07-27T00:01:00Z",
                        compare_to_run_id="first-run",
                    )

            self.assertFalse(
                (repository / ".repo-curator" / "runs" / "second-run").exists()
            )

    def test_prior_run_record_limit_stops_before_new_run_is_published(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()
            (repository / "source.py").write_text("value = 1\n", encoding="utf-8")
            audit_repository(repository, "first-run", "2026-07-27T00:00:00Z")

            with mock.patch.object(prior_runs, "_MAX_JSONL_RECORDS", 0):
                with self.assertRaisesRegex(
                    ValueError, "prior inventory exceeds record limit"
                ):
                    audit_repository(
                        repository,
                        "second-run",
                        "2026-07-27T00:01:00Z",
                        compare_to_run_id="first-run",
                    )

            self.assertFalse(
                (repository / ".repo-curator" / "runs" / "second-run").exists()
            )

    def test_prior_run_output_declaration_limit_stops_before_publication(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()
            audit_repository(repository, "first-run", "2026-07-27T00:00:00Z")

            with mock.patch.object(prior_runs, "_MAX_OUTPUT_FILES", 0):
                with self.assertRaisesRegex(
                    ValueError, "prior run output declaration limit"
                ):
                    audit_repository(
                        repository,
                        "second-run",
                        "2026-07-27T00:01:00Z",
                        compare_to_run_id="first-run",
                    )

            self.assertFalse(
                (repository / ".repo-curator" / "runs" / "second-run").exists()
            )

    def test_prior_run_single_output_limit_stops_before_publication(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()
            audit_repository(repository, "first-run", "2026-07-27T00:00:00Z")

            with mock.patch.object(prior_runs, "_MAX_OUTPUT_FILE_BYTES", 1):
                with self.assertRaisesRegex(
                    ValueError, "prior run output exceeds file byte limit"
                ):
                    audit_repository(
                        repository,
                        "second-run",
                        "2026-07-27T00:01:00Z",
                        compare_to_run_id="first-run",
                    )

            self.assertFalse(
                (repository / ".repo-curator" / "runs" / "second-run").exists()
            )
