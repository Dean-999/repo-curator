import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from repo_curator.interchange import export_ro_crate
from repo_curator.inventory import audit_repository


class SchemaMigrationScenarioTest(unittest.TestCase):
    def test_prior_v1_curation_brief_remains_unchanged_when_current_audit_emits_v3(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()
            (repository / "notes.txt").write_text("notes\n", encoding="utf-8")
            audit_repository(repository, "prior", "2026-07-28T00:00:00Z")
            prior_brief_path = (
                repository
                / ".repo-curator"
                / "plans"
                / "prior"
                / "curation-brief.json"
            )
            prior_brief = json.loads(prior_brief_path.read_text(encoding="utf-8"))
            prior_brief["schema_version"] = "repo-curator.curation-brief.v1"
            prior_brief.pop("declared_experiment_chains")
            prior_brief.pop("canonical_result_review")
            prior_brief.pop("reproducibility_gap_review")
            prior_v1_bytes = (
                json.dumps(
                    prior_brief,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
            prior_brief_path.write_bytes(prior_v1_bytes)
            prior_plan_path = prior_brief_path.parent / "plan.json"
            prior_plan = json.loads(prior_plan_path.read_text(encoding="utf-8"))
            prior_plan["curation_brief"]["json_sha256"] = hashlib.sha256(
                prior_v1_bytes
            ).hexdigest()
            prior_plan_bytes = (
                json.dumps(
                    prior_plan,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
            prior_plan_path.write_bytes(prior_plan_bytes)

            audit_repository(
                repository,
                "current",
                "2026-07-28T00:01:00Z",
                compare_to_run_id="prior",
            )

            self.assertEqual(prior_brief_path.read_bytes(), prior_v1_bytes)
            self.assertEqual(prior_plan_path.read_bytes(), prior_plan_bytes)
            self.assertEqual(
                json.loads(prior_plan_path.read_text(encoding="utf-8"))[
                    "curation_brief"
                ]["json_sha256"],
                hashlib.sha256(prior_brief_path.read_bytes()).hexdigest(),
            )
            current_brief = json.loads(
                (
                    repository
                    / ".repo-curator"
                    / "plans"
                    / "current"
                    / "curation-brief.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                current_brief["schema_version"],
                "repo-curator.curation-brief.v3",
            )

    def test_prior_v2_curation_brief_remains_unchanged_when_current_audit_emits_v3(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()
            (repository / "notes.txt").write_text("notes\n", encoding="utf-8")
            audit_repository(repository, "prior", "2026-07-28T00:00:00Z")
            prior_brief_path = (
                repository
                / ".repo-curator"
                / "plans"
                / "prior"
                / "curation-brief.json"
            )
            prior_brief = json.loads(prior_brief_path.read_text(encoding="utf-8"))
            prior_brief["schema_version"] = "repo-curator.curation-brief.v2"
            prior_brief.pop("canonical_result_review")
            prior_brief.pop("reproducibility_gap_review")
            prior_v2_bytes = (
                json.dumps(
                    prior_brief,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
            prior_brief_path.write_bytes(prior_v2_bytes)
            prior_plan_path = prior_brief_path.parent / "plan.json"
            prior_plan = json.loads(prior_plan_path.read_text(encoding="utf-8"))
            prior_plan["curation_brief"]["json_sha256"] = hashlib.sha256(
                prior_v2_bytes
            ).hexdigest()
            prior_plan_bytes = (
                json.dumps(
                    prior_plan,
                    ensure_ascii=True,
                    separators=(",", ":"),
                    sort_keys=True,
                )
                + "\n"
            ).encode("utf-8")
            prior_plan_path.write_bytes(prior_plan_bytes)

            audit_repository(
                repository,
                "current",
                "2026-07-28T00:01:00Z",
                compare_to_run_id="prior",
            )

            self.assertEqual(prior_brief_path.read_bytes(), prior_v2_bytes)
            self.assertEqual(prior_plan_path.read_bytes(), prior_plan_bytes)
            self.assertEqual(
                json.loads(prior_plan_path.read_text(encoding="utf-8"))[
                    "curation_brief"
                ]["json_sha256"],
                hashlib.sha256(prior_brief_path.read_bytes()).hexdigest(),
            )
            current_brief = json.loads(
                (
                    repository
                    / ".repo-curator"
                    / "plans"
                    / "current"
                    / "curation-brief.json"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(
                current_brief["schema_version"],
                "repo-curator.curation-brief.v3",
            )

    def test_prior_v1_classifications_remain_unchanged_during_comparison(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()
            (repository / "notes.txt").write_text("notes\n", encoding="utf-8")
            audit_repository(repository, "prior", "2026-07-28T00:00:00Z")
            run_directory = repository / ".repo-curator" / "runs" / "prior"
            classifications_path = run_directory / "classifications.jsonl"
            classifications = [
                json.loads(line)
                for line in classifications_path.read_text(encoding="utf-8").splitlines()
            ]
            for classification in classifications:
                classification["schema_version"] = "repo-curator.classification.v1"
            v1_bytes = (
                "".join(
                    json.dumps(item, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
                    + "\n"
                    for item in classifications
                )
            ).encode("utf-8")
            classifications_path.write_bytes(v1_bytes)
            run_path = run_directory / "run.json"
            run = json.loads(run_path.read_text(encoding="utf-8"))
            run["output_file_hashes"]["classifications.jsonl"] = hashlib.sha256(
                v1_bytes
            ).hexdigest()
            run_path.write_text(
                json.dumps(run, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
                + "\n",
                encoding="utf-8",
            )

            audit_repository(
                repository,
                "current",
                "2026-07-28T00:01:00Z",
                compare_to_run_id="prior",
            )

            self.assertEqual(classifications_path.read_bytes(), v1_bytes)
            current = repository / ".repo-curator" / "runs" / "current"
            current_classification = json.loads(
                (current / "classifications.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()[0]
            )
            self.assertEqual(
                current_classification["schema_version"],
                "repo-curator.classification.v2",
            )

    def test_future_supplied_export_manifest_is_preserved_and_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            payload = workspace / "payload.json"
            payload.write_text("{}", encoding="utf-8")
            manifest = workspace / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "repo-curator.supplied-adapter-export-manifest.v999",
                        "adapter_family": "REPROZIP",
                        "source_tool": "reprozip",
                        "source_version": "future",
                        "snapshot_scope": "PROJECT_DIRECTORY",
                        "payload_type": "REPROZIP_METADATA_JSON",
                        "payload": {
                            "path": payload.name,
                            "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
                        },
                    }
                ),
                encoding="utf-8",
            )
            original_bytes = manifest.read_bytes()

            with self.assertRaisesRegex(ValueError, "manifest schema version is unsupported"):
                audit_repository(
                    repository,
                    "future-manifest",
                    "2026-07-28T00:00:00Z",
                    adapter_export_manifests=(manifest,),
                )

            self.assertEqual(manifest.read_bytes(), original_bytes)
            self.assertFalse((repository / ".repo-curator").exists())

    def test_future_prior_run_schema_is_preserved_and_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "repository"
            repository.mkdir()
            audit_repository(repository, "prior", "2026-07-28T00:00:00Z")
            run_path = repository / ".repo-curator" / "runs" / "prior" / "run.json"
            future_run = json.loads(run_path.read_text(encoding="utf-8"))
            future_run["schema_version"] = "repo-curator.run.v999"
            run_path.write_text(json.dumps(future_run), encoding="utf-8")
            original_bytes = run_path.read_bytes()

            with self.assertRaisesRegex(ValueError, "prior run schema version is unsupported"):
                audit_repository(
                    repository,
                    "current",
                    "2026-07-28T00:01:00Z",
                    compare_to_run_id="prior",
                )

            self.assertEqual(run_path.read_bytes(), original_bytes)
            self.assertFalse((repository / ".repo-curator" / "runs" / "current").exists())

    def test_future_run_schema_is_preserved_and_refused_by_interchange_export(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            audit_repository(repository, "future-run", "2026-07-28T00:00:00Z")
            run_directory = repository / ".repo-curator" / "runs" / "future-run"
            run_path = run_directory / "run.json"
            future_run = json.loads(run_path.read_text(encoding="utf-8"))
            future_run["schema_version"] = "repo-curator.run.v999"
            run_path.write_text(json.dumps(future_run), encoding="utf-8")
            original_bytes = run_path.read_bytes()
            output = workspace / "ro-crate-metadata.json"

            with self.assertRaisesRegex(ValueError, "audit run schema version is unsupported"):
                export_ro_crate(run_directory, output)

            self.assertEqual(run_path.read_bytes(), original_bytes)
            self.assertFalse(output.exists())
