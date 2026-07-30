import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from repo_curator.inventory import audit_repository
from repo_curator.supplied_exports import MAX_EXPORT_MANIFESTS


FIXED_RUN_ID = "supplied-export-fixture-run"
FIXED_CREATED_AT = "2026-07-27T00:00:00Z"


class SuppliedExportScenarioTest(unittest.TestCase):
    def test_bound_workflow_run_crate_imports_bounded_declared_actions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            exports = workspace / "exports"
            exports.mkdir()
            marker = repository / "target-code-executed"
            (repository / "danger.py").write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
                encoding="utf-8",
            )
            payload = exports / "ro-crate-metadata.json"
            payload.write_text(
                json.dumps(
                    {
                        "@context": [
                            "https://w3id.org/ro/crate/1.1/context",
                            "https://w3id.org/ro/terms/workflow-run/context",
                        ],
                        "@graph": [
                            {
                                "@id": "ro-crate-metadata.json",
                                "@type": "CreativeWork",
                                "about": {"@id": "./"},
                            },
                            {
                                "@id": "./",
                                "@type": "Dataset",
                                "conformsTo": [
                                    {
                                        "@id": "https://w3id.org/ro/wfrun/workflow/0.5"
                                    }
                                ],
                                "mentions": [
                                    {"@id": "#completed"},
                                    {"@id": "#failed"},
                                ],
                            },
                            {
                                "@id": "workflow.cwl",
                                "@type": ["File", "ComputationalWorkflow"],
                            },
                            {"@id": "input.csv", "@type": "File"},
                            {"@id": "output.csv", "@type": "File"},
                            {
                                "@id": "#completed",
                                "@type": "CreateAction",
                                "instrument": {"@id": "workflow.cwl"},
                                "object": [{"@id": "input.csv"}],
                                "result": [{"@id": "output.csv"}],
                                "actionStatus": "http://schema.org/CompletedActionStatus",
                            },
                            {
                                "@id": "#failed",
                                "@type": "CreateAction",
                                "instrument": {"@id": "workflow.cwl"},
                                "object": [{"@id": "missing-input.csv"}],
                                "actionStatus": "http://schema.org/FailedActionStatus",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest = exports / "workflow-run-export.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": (
                            "repo-curator.workflow-run-ro-crate-export-manifest.v1"
                        ),
                        "adapter_family": "WORKFLOW_RUN_RO_CRATE",
                        "source_tool": "nf-prov",
                        "source_version": "1.0",
                        "snapshot_scope": "WORKFLOW_RUN",
                        "payload_type": "WORKFLOW_RUN_RO_CRATE_JSON",
                        "payload": {
                            "path": payload.name,
                            "sha256": hashlib.sha256(
                                payload.read_bytes()
                            ).hexdigest(),
                        },
                    }
                ),
                encoding="utf-8",
            )

            audit_repository(
                repository,
                FIXED_RUN_ID,
                FIXED_CREATED_AT,
                adapter_export_manifests=(manifest,),
            )

            observation = json.loads(
                (
                    repository
                    / ".repo-curator"
                    / "runs"
                    / FIXED_RUN_ID
                    / "adapter-observations.jsonl"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(observation["adapter_family"], "WORKFLOW_RUN_RO_CRATE")
            self.assertEqual(
                observation["coverage"], "SUPPLIED_EXPORT_DECLARATION_GRAPH"
            )
            self.assertEqual(observation["source_tool"], "nf-prov")
            self.assertEqual(observation["workflow_run"]["action_count_in_scope"], 2)
            actions = {
                item["action_id"]: item
                for item in observation["workflow_run"]["actions"]
            }
            self.assertEqual(
                actions["#completed"]["status"], "COMPLETED_DECLARED"
            )
            self.assertEqual(actions["#completed"]["input_ids"], ["input.csv"])
            self.assertEqual(actions["#completed"]["output_ids"], ["output.csv"])
            self.assertEqual(actions["#failed"]["status"], "FAILED_DECLARED")
            self.assertEqual(
                actions["#failed"]["unresolved_input_ids"],
                ["missing-input.csv"],
            )
            self.assertIn(
                "SUPPLIED_ACTION_STATUS_NOT_EXECUTION_VERIFIED",
                observation["limitations"],
            )
            self.assertFalse(marker.exists())

    def test_supplied_payload_cannot_assign_local_declaration_classification(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            (repository / "notes.txt").write_text("notes\n", encoding="utf-8")
            exports = workspace / "exports"
            exports.mkdir()
            payload = exports / "reprozip-metadata.json"
            payload.write_text(
                json.dumps(
                    {
                        "marker_artifact_ids": [
                            f"art_{FIXED_RUN_ID}_00000002"
                        ],
                        "source_artifact_id": f"art_{FIXED_RUN_ID}_00000002",
                    }
                ),
                encoding="utf-8",
            )
            manifest = self._write_manifest(exports, payload)

            audit_repository(
                repository,
                FIXED_RUN_ID,
                FIXED_CREATED_AT,
                adapter_export_manifests=(manifest,),
            )

            classifications_path = (
                repository
                / ".repo-curator"
                / "runs"
                / FIXED_RUN_ID
                / "classifications.jsonl"
            )
            notes = next(
                item
                for item in (
                    json.loads(line)
                    for line in classifications_path.read_text(
                        encoding="utf-8"
                    ).splitlines()
                )
                if item["repository_relative_path"] == "notes.txt"
            )

            self.assertEqual(notes["state"], "UNRESOLVED")
            self.assertEqual(notes["supporting_evidence_ids"], [])

    def test_bound_reprozip_metadata_is_recorded_without_execution(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            exports = workspace / "exports"
            exports.mkdir()
            payload = exports / "reprozip-metadata.json"
            payload.write_text('{"format":"reprozip-metadata"}', encoding="utf-8")
            manifest = self._write_manifest(exports, payload)

            audit_repository(
                repository,
                FIXED_RUN_ID,
                FIXED_CREATED_AT,
                adapter_export_manifests=(manifest,),
            )

            run_directory = repository / ".repo-curator" / "runs" / FIXED_RUN_ID
            observations_bytes = (run_directory / "adapter-observations.jsonl").read_bytes()
            observations = [
                json.loads(line) for line in observations_bytes.decode("utf-8").splitlines()
            ]
            self.assertEqual(len(observations), 1)
            observation = observations[0]
            self.assertEqual(observation["declaration_family"], "REPROZIP")
            self.assertEqual(observation["coverage"], "SUPPLIED_EXPORT_METADATA_ONLY")
            self.assertEqual(observation["source_tool"], "reprozip")
            self.assertEqual(observation["source_version"], "1.2.2")
            self.assertEqual(observation["snapshot_scope"], "PROJECT_DIRECTORY")
            self.assertEqual(observation["payload_sha256"], hashlib.sha256(payload.read_bytes()).hexdigest())
            self.assertEqual(observation["validation_status"], "BOUND_MANIFEST_VALIDATED")
            self.assertIn("SUPPLIED_EXPORT_NOT_EXECUTED", observation["limitations"])
            self.assertEqual(
                json.loads((run_directory / "run.json").read_text(encoding="utf-8"))["output_file_hashes"]["adapter-observations.jsonl"],
                hashlib.sha256(observations_bytes).hexdigest(),
            )

    def test_unbound_or_unsafe_export_is_rejected_before_run_publication(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            exports = workspace / "exports"
            exports.mkdir()
            payload = exports / "payload.json"
            payload.write_text("{}", encoding="utf-8")
            manifest = self._write_manifest(exports, payload)
            document = json.loads(manifest.read_text(encoding="utf-8"))
            document["payload"]["sha256"] = "0" * 64
            manifest.write_text(json.dumps(document), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "payload SHA-256 does not match"):
                audit_repository(
                    repository,
                    FIXED_RUN_ID,
                    FIXED_CREATED_AT,
                    adapter_export_manifests=(manifest,),
                )
            self.assertFalse((repository / ".repo-curator").exists())

    def test_workflow_schema_family_mismatch_is_rejected_before_publication(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            exports = workspace / "exports"
            exports.mkdir()
            payload = exports / "ro-crate-metadata.json"
            payload.write_text("{}", encoding="utf-8")
            manifest = exports / "workflow-run-export.json"
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": (
                            "repo-curator.workflow-run-ro-crate-export-manifest.v1"
                        ),
                        "adapter_family": "REPROZIP",
                        "source_tool": "nf-prov",
                        "source_version": "1.0",
                        "snapshot_scope": "WORKFLOW_RUN",
                        "payload_type": "WORKFLOW_RUN_RO_CRATE_JSON",
                        "payload": {
                            "path": payload.name,
                            "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "adapter family is unsupported"):
                audit_repository(
                    repository,
                    FIXED_RUN_ID,
                    FIXED_CREATED_AT,
                    adapter_export_manifests=(manifest,),
                )

            self.assertFalse((repository / ".repo-curator").exists())

    def test_malformed_workflow_root_is_explicitly_unavailable(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            exports = workspace / "exports"
            exports.mkdir()
            payload = exports / "ro-crate-metadata.json"
            payload.write_text(
                json.dumps(
                    {
                        "@context": "https://w3id.org/ro/crate/1.1/context",
                        "@graph": [
                            {
                                "@id": "ro-crate-metadata.json",
                                "@type": "CreativeWork",
                                "about": {"@id": "./"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest = self._write_workflow_manifest(exports, payload)

            audit_repository(
                repository,
                FIXED_RUN_ID,
                FIXED_CREATED_AT,
                adapter_export_manifests=(manifest,),
            )

            observation = json.loads(
                (
                    repository
                    / ".repo-curator"
                    / "runs"
                    / FIXED_RUN_ID
                    / "adapter-observations.jsonl"
                ).read_text(encoding="utf-8")
            )
            self.assertEqual(observation["workflow_run"]["status"], "UNAVAILABLE")
            self.assertEqual(
                observation["validation_status"],
                "BOUND_MANIFEST_VALIDATED_DECLARATION_GRAPH_UNAVAILABLE",
            )
            self.assertIn("RO_CRATE_ROOT_MISSING", observation["limitations"])

    def test_supplied_export_count_is_bounded_before_publication(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            exports = workspace / "exports"
            exports.mkdir()
            payload = exports / "payload.json"
            payload.write_text("{}", encoding="utf-8")
            template = self._write_manifest(exports, payload).read_text(encoding="utf-8")
            manifests = []
            for index in range(MAX_EXPORT_MANIFESTS + 1):
                manifest = exports / f"export-{index:02d}.json"
                manifest.write_text(template, encoding="utf-8")
                manifests.append(manifest)

            with self.assertRaisesRegex(ValueError, "manifest count exceeds limit"):
                audit_repository(
                    repository,
                    FIXED_RUN_ID,
                    FIXED_CREATED_AT,
                    adapter_export_manifests=tuple(manifests),
                )

            self.assertFalse((repository / ".repo-curator").exists())

    def test_payload_path_escape_and_symbolic_link_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            workspace = Path(temporary_directory)
            repository = workspace / "repository"
            repository.mkdir()
            exports = workspace / "exports"
            exports.mkdir()
            outside = workspace / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            payload_link = exports / "payload.json"
            payload_link.symlink_to(outside)
            manifest = self._write_manifest(exports, payload_link)

            with self.assertRaisesRegex(ValueError, "payload is a symbolic link"):
                audit_repository(
                    repository,
                    FIXED_RUN_ID,
                    FIXED_CREATED_AT,
                    adapter_export_manifests=(manifest,),
                )
            self.assertFalse((repository / ".repo-curator").exists())

            escaped = json.loads(manifest.read_text(encoding="utf-8"))
            escaped["payload"]["path"] = "../outside.json"
            manifest.write_text(json.dumps(escaped), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "payload path must be a contained relative path"):
                audit_repository(
                    repository,
                    FIXED_RUN_ID,
                    FIXED_CREATED_AT,
                    adapter_export_manifests=(manifest,),
                )

    @staticmethod
    def _write_manifest(exports: Path, payload: Path) -> Path:
        manifest = exports / "reprozip-export.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": "repo-curator.supplied-adapter-export-manifest.v1",
                    "adapter_family": "REPROZIP",
                    "source_tool": "reprozip",
                    "source_version": "1.2.2",
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
        return manifest

    @staticmethod
    def _write_workflow_manifest(exports: Path, payload: Path) -> Path:
        manifest = exports / "workflow-run-export.json"
        manifest.write_text(
            json.dumps(
                {
                    "schema_version": (
                        "repo-curator.workflow-run-ro-crate-export-manifest.v1"
                    ),
                    "adapter_family": "WORKFLOW_RUN_RO_CRATE",
                    "source_tool": "nf-prov",
                    "source_version": "1.0",
                    "snapshot_scope": "WORKFLOW_RUN",
                    "payload_type": "WORKFLOW_RUN_RO_CRATE_JSON",
                    "payload": {
                        "path": payload.name,
                        "sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
                    },
                }
            ),
            encoding="utf-8",
        )
        return manifest
