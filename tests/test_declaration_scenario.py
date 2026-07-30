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
from repo_curator import declarations


FIXED_RUN_ID = "declaration-fixture-run"
FIXED_CREATED_AT = "2026-07-19T00:00:00Z"
EXPECTED_FAMILIES = {"DVC", "DATALAD", "MLFLOW", "SACRED", "RO_CRATE", "BAGIT"}


class DeclarationScenarioTest(unittest.TestCase):
    def test_supported_declarations_emit_typed_presence_observations(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "research-repository"
            repository.mkdir()
            self._write_supported_declarations(repository)
            target_marker = repository / "target-command-was-executed"
            target_command = repository / "target-hook"
            target_command.write_text(
                "#!/bin/sh\n" f"touch {str(target_marker)!r}\n", encoding="utf-8"
            )
            target_command.chmod(0o700)
            execution_markers, environment = self._fake_tool_environment(temporary_path)

            result = self._run_audit(repository, environment)

            self.assertEqual(result.returncode, 0, result.stderr)
            observations_path = self._run_directory(repository) / "adapter-observations.jsonl"
            observations_bytes = observations_path.read_bytes()
            observations = [
                json.loads(line)
                for line in observations_bytes.decode("utf-8").splitlines()
            ]
            run_record = json.loads((self._run_directory(repository) / "run.json").read_bytes())

            self.assertEqual(
                {observation["declaration_family"] for observation in observations},
                EXPECTED_FAMILIES,
            )
            self.assertTrue(
                all(observation["status"] == "PRESENT" for observation in observations)
            )
            self.assertTrue(
                all(observation["validation_status"] != "EXECUTED" for observation in observations)
            )
            self.assertTrue(
                all(
                    observation["validation_status"] in {"NOT_APPLICABLE", "SYNTAX_VALIDATED"}
                    for observation in observations
                )
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
                    {
                        "schema_version",
                        "run_id",
                        "observation_id",
                        "declaration_family",
                        "source_artifact_id",
                        "source_location_id",
                        "status",
                        "validation_status",
                        "coverage",
                        "limitations",
                        "created_at",
                    }.issubset(observation)
                    for observation in observations
                )
            )
            self.assertEqual(
                run_record["output_file_hashes"]["adapter-observations.jsonl"],
                hashlib.sha256(observations_bytes).hexdigest(),
            )
            self.assertEqual(
                run_record["component_states"]["declarations"]["status"], "COMPLETED"
            )
            self.assertFalse(any(marker.exists() for marker in execution_markers))
            self.assertFalse(target_marker.exists())

            shutil.rmtree(repository / ".repo-curator")
            second_result = self._run_audit(repository, environment)

            self.assertEqual(second_result.returncode, 0, second_result.stderr)
            self.assertEqual(observations_path.read_bytes(), observations_bytes)

    def test_malformed_ro_crate_is_retained_with_a_limitation(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "ro-crate-metadata.json").write_text(
                '{"non_standard": NaN}', encoding="utf-8"
            )

            result = self._run_audit(repository, os.environ.copy())

            self.assertEqual(result.returncode, 0, result.stderr)
            observation = self._observation_by_family(repository, "RO_CRATE")
            self.assertEqual(observation["status"], "MALFORMED")
            self.assertEqual(observation["validation_status"], "MALFORMED")
            self.assertIn("DECLARATION_MALFORMED", observation["limitations"])

    def test_oversized_json_declaration_is_retained_without_parsing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "ro-crate-metadata.json").write_bytes(b" " * (1024 * 1024 + 1))

            result = self._run_audit(repository, os.environ.copy())

            self.assertEqual(result.returncode, 0, result.stderr)
            observation = self._observation_by_family(repository, "RO_CRATE")
            self.assertEqual(observation["status"], "PRESENT_UNVALIDATED")
            self.assertEqual(observation["validation_status"], "SIZE_LIMIT")
            self.assertIn("DECLARATION_VALIDATION_SIZE_LIMIT", observation["limitations"])

    def test_partial_sacred_declarations_are_retained_in_both_directions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            config_only = repository / "config-only"
            config_only.mkdir()
            (config_only / "config.json").write_text("{}", encoding="utf-8")
            run_only = repository / "run-only"
            run_only.mkdir()
            (run_only / "run.json").write_text("{}", encoding="utf-8")

            result = self._run_audit(repository, os.environ.copy())

            self.assertEqual(result.returncode, 0, result.stderr)
            observations = self._observations_by_family(repository, "SACRED")
            self.assertEqual(len(observations), 2)
            self.assertEqual({item["status"] for item in observations}, {"PARTIAL"})
            limitations = [item["limitations"] for item in observations]
            self.assertTrue(any("SACRED_RUN_JSON_MISSING" in item for item in limitations))
            self.assertTrue(any("SACRED_CONFIG_JSON_MISSING" in item for item in limitations))
            self.assertTrue(all("DECLARATION_PARTIAL" in item for item in limitations))

    def test_complete_sacred_observation_retains_both_marker_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            run_directory = repository / "sacred-run"
            run_directory.mkdir()
            (run_directory / "config.json").write_text("{}", encoding="utf-8")
            (run_directory / "run.json").write_text("{}", encoding="utf-8")

            result = self._run_audit(repository, os.environ.copy())

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                self._observation_by_family(repository, "SACRED")["marker_paths"],
                ["sacred-run/config.json", "sacred-run/run.json"],
            )

    def test_workflow_run_ro_crate_is_explicit_but_remains_declaration_only(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "ro-crate-metadata.json").write_text(
                json.dumps(
                    {
                        "@context": "https://w3id.org/ro/crate/1.1/context",
                        "@graph": [
                            {
                                "@id": "./",
                                "@type": ["Dataset", "WorkflowRunCrate"],
                                "conformsTo": {"@id": "https://w3id.org/workflowhub/workflow-ro-crate/1.0"},
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = self._run_audit(repository, os.environ.copy())

            self.assertEqual(result.returncode, 0, result.stderr)
            observations = self._observations_by_family(repository, "WORKFLOW_RUN_RO_CRATE")
            self.assertEqual(len(observations), 1)
            observation = observations[0]
            self.assertEqual(observation["status"], "PRESENT")
            self.assertEqual(observation["validation_status"], "SYNTAX_VALIDATED")
            self.assertTrue(observation["workflow_run_ro_crate_declared"])
            self.assertEqual(
                observation["declared_profile_uris"],
                ["https://w3id.org/workflowhub/workflow-ro-crate/1.0"],
            )
            self.assertIn("WorkflowRunCrate", observation["declared_type_tokens"])
            self.assertIn("WORKFLOW_RUN_RO_CRATE_DECLARATION_ONLY", observation["limitations"])
            self.assertEqual(
                self._observation_by_family(repository, "RO_CRATE")["observation_id"],
                observation["source_observation_id"],
            )

    def test_ro_crate_graph_import_is_bounded_local_and_reference_explicit(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            marker = repository / "target-code-executed"
            (repository / "ro-crate-metadata.json").write_text(
                json.dumps(
                    {
                        "@context": "https://w3id.org/ro/crate/1.2/context",
                        "@graph": [
                            {
                                "@id": "ro-crate-metadata.json",
                                "@type": "CreativeWork",
                                "about": {"@id": "./"},
                                "conformsTo": {"@id": "https://w3id.org/ro/crate/1.2"},
                            },
                            {
                                "@id": "./",
                                "@type": ["Dataset", "RepositoryCollection"],
                                "hasPart": [
                                    {"@id": "results/output.csv"},
                                    {"@id": "missing.csv"},
                                ],
                            },
                            {
                                "@id": "results/output.csv",
                                "@type": "File",
                                "encodingFormat": "text/csv",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = self._run_audit(repository, os.environ.copy())

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(marker.exists())
            observation = self._observation_by_family(repository, "RO_CRATE")
            graph = observation["ro_crate_graph"]
            self.assertEqual(graph["status"], "OBSERVED_WITH_LIMITATIONS")
            self.assertEqual(graph["metadata_descriptor_id"], "ro-crate-metadata.json")
            self.assertEqual(graph["root_entity_id"], "./")
            self.assertEqual(graph["entity_count_in_scope"], 3)
            self.assertEqual(
                graph["entities"],
                [
                    {"entity_id": "./", "types": ["Dataset", "RepositoryCollection"]},
                    {"entity_id": "results/output.csv", "types": ["File"]},
                    {"entity_id": "ro-crate-metadata.json", "types": ["CreativeWork"]},
                ],
            )
            self.assertIn(
                {
                    "property": "hasPart",
                    "source_entity_id": "./",
                    "target_entity_id": "results/output.csv",
                    "target_present": True,
                },
                graph["references"],
            )
            self.assertEqual(graph["unresolved_reference_ids"], ["missing.csv"])
            self.assertEqual(graph["external_reference_ids"], ["https://w3id.org/ro/crate/1.2"])
            self.assertIn("RO_CRATE_REFERENCE_UNRESOLVED", observation["limitations"])
            self.assertIn("RO_CRATE_EXTERNAL_REFERENCE_NOT_RETRIEVED", observation["limitations"])
            self.assertEqual(observation["coverage"], "DECLARATION_PRESENCE_ONLY")

    def test_ro_crate_graph_rejects_duplicate_ids_and_invalid_root_without_guessing(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "ro-crate-metadata.json").write_text(
                json.dumps(
                    {
                        "@context": {},
                        "@graph": [
                            {"@id": "ro-crate-metadata.json", "@type": "CreativeWork", "about": {"@id": "./"}},
                            {"@id": "./", "@type": "Thing"},
                            {"@id": "./", "@type": "Dataset"},
                            {"@type": "File"},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = self._run_audit(repository, os.environ.copy())

            self.assertEqual(result.returncode, 0, result.stderr)
            observation = self._observation_by_family(repository, "RO_CRATE")
            graph = observation["ro_crate_graph"]
            self.assertEqual(graph["status"], "OBSERVED_WITH_LIMITATIONS")
            self.assertIsNone(graph["root_entity_id"])
            self.assertIn("RO_CRATE_DUPLICATE_ENTITY_ID", observation["limitations"])
            self.assertIn("RO_CRATE_ENTITY_MALFORMED", observation["limitations"])
            self.assertIn("RO_CRATE_ROOT_INVALID", observation["limitations"])

    def test_dvc_lock_stage_summary_is_bounded_and_lexical(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "dvc.lock").write_text(
                "schema: '2.0'\nstages:\n  prepare:\n    cmd: python prepare.py\n  train:\n    cmd: python train.py\n",
                encoding="utf-8",
            )

            result = self._run_audit(repository, os.environ.copy())

            self.assertEqual(result.returncode, 0, result.stderr)
            observation = self._observation_by_family(repository, "DVC")
            self.assertEqual(observation["dvc_lock_scan_status"], "LEXICAL_OBSERVED")
            self.assertEqual(observation["dvc_lock_stage_key_count"], 2)
            self.assertIn("DVC_LOCK_STAGE_KEYS_LEXICAL_ONLY", observation["limitations"])

    def test_sacred_validation_aggregates_both_members_with_malformed_precedence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            for name, first, second in (
                ("size-then-malformed", b" " * (1024 * 1024 + 1), b"{bad"),
                ("malformed-then-size", b"{bad", b" " * (1024 * 1024 + 1)),
            ):
                directory = repository / name
                directory.mkdir()
                (directory / "config.json").write_bytes(first)
                (directory / "run.json").write_bytes(second)

            result = self._run_audit(repository, os.environ.copy())

            self.assertEqual(result.returncode, 0, result.stderr)
            observations = self._observations_by_family(repository, "SACRED")
            self.assertEqual(len(observations), 2)
            for observation in observations:
                self.assertEqual(observation["status"], "MALFORMED")
                self.assertEqual(observation["validation_status"], "MALFORMED")
                self.assertIn("DECLARATION_MALFORMED", observation["limitations"])
                self.assertIn("DECLARATION_VALIDATION_SIZE_LIMIT", observation["limitations"])

    def test_json_validation_failure_is_retained_without_aborting_audit(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            declaration = repository / "ro-crate-metadata.json"
            declaration.write_text("{}", encoding="utf-8")
            original_open = declarations._open_regular_file

            with mock.patch.object(
                declarations,
                "_open_regular_file",
                side_effect=FileNotFoundError("simulated disappearance"),
            ):
                inventory.audit_repository(repository, FIXED_RUN_ID, FIXED_CREATED_AT)

            observation = self._observation_by_family(repository, "RO_CRATE")
            self.assertEqual(observation["status"], "PRESENT_UNVALIDATED")
            self.assertIn("DECLARATION_VALIDATION_UNAVAILABLE", observation["limitations"])
            self.assertFalse(original_open is None)

    def test_changed_or_unsafe_json_declarations_are_retained_without_aborting(self):
        for error in (ValueError("type changed"), OSError("symlink swapped")):
            with self.subTest(error=type(error).__name__), tempfile.TemporaryDirectory() as temporary_directory:
                repository = Path(temporary_directory) / "research-repository"
                repository.mkdir()
                (repository / "ro-crate-metadata.json").write_text("{}", encoding="utf-8")
                with mock.patch.object(declarations, "_open_regular_file", side_effect=error):
                    inventory.audit_repository(repository, FIXED_RUN_ID, FIXED_CREATED_AT)
                observation = self._observation_by_family(repository, "RO_CRATE")
                self.assertEqual(observation["status"], "PRESENT_UNVALIDATED")
                self.assertIn("DECLARATION_CHANGED_DURING_VALIDATION", observation["limitations"])

    def test_json_validation_ceiling_accepts_exactly_one_mebibyte_and_detects_growth(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            payload = b'{"x":"' + b" " * (1024 * 1024 - 8) + b'"}'
            self.assertEqual(len(payload), 1024 * 1024)
            (repository / "ro-crate-metadata.json").write_bytes(payload)
            result = self._run_audit(repository, os.environ.copy())
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                self._observation_by_family(repository, "RO_CRATE")["validation_status"],
                "SYNTAX_VALIDATED",
            )

        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "ro-crate-metadata.json").write_text("{}", encoding="utf-8")
            with mock.patch.object(
                declarations,
                "_read_at_most",
                return_value=b" " * (1024 * 1024 + 1),
            ):
                inventory.audit_repository(repository, FIXED_RUN_ID, FIXED_CREATED_AT)
            observation = self._observation_by_family(repository, "RO_CRATE")
            self.assertEqual(observation["status"], "PRESENT_UNVALIDATED")
            self.assertIn("DECLARATION_VALIDATION_SIZE_LIMIT", observation["limitations"])

    def test_no_declaration_repository_emits_an_empty_observation_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "README.md").write_text("ordinary", encoding="utf-8")

            result = self._run_audit(repository, os.environ.copy())

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                (self._run_directory(repository) / "adapter-observations.jsonl").read_bytes(),
                b"",
            )

    def test_extended_workflow_markers_are_grouped_without_tool_execution(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "research-repository"
            repository.mkdir()
            (repository / ".dvc").mkdir()
            (repository / ".dvc" / "config").write_text("[core]\n", encoding="utf-8")
            (repository / "stages").mkdir()
            (repository / "stages" / "prepare.dvc").write_text("outs:\n", encoding="utf-8")
            (repository / "workflow").mkdir()
            (repository / "workflow" / "Snakefile").write_text("rule all:\n", encoding="utf-8")
            (repository / "nextflow.config").write_text("profiles {}\n", encoding="utf-8")
            (repository / "renku.yaml").write_text("not-a-renku-project: true\n", encoding="utf-8")
            (repository / ".renku").mkdir()
            (repository / "showyourwork.yml").write_text("paths: {}\n", encoding="utf-8")
            (repository / ".noworkflow").mkdir()
            markers, environment = self._fake_tool_environment(temporary_path)

            result = self._run_audit(repository, environment)

            self.assertEqual(result.returncode, 0, result.stderr)
            observations = {
                item["declaration_family"]: item
                for item in self._read_observations(repository)
            }
            self.assertTrue(
                {"DVC", "SNAKEMAKE", "NEXTFLOW", "RENKU", "SHOWYOURWORK", "NOWORKFLOW"}
                .issubset(observations)
            )
            self.assertEqual(
                observations["DVC"]["marker_paths"],
                [".dvc/config", "stages/prepare.dvc"],
            )
            self.assertEqual(
                observations["SNAKEMAKE"]["marker_paths"], ["workflow/Snakefile"]
            )
            self.assertEqual(observations["NOWORKFLOW"]["marker_paths"], [".noworkflow"])
            self.assertEqual(observations["RENKU"]["marker_paths"], [".renku"])
            self.assertTrue(
                all(item["coverage"] == "DECLARATION_PRESENCE_ONLY" for item in observations.values())
            )
            self.assertFalse(any(marker.exists() for marker in markers))

    def test_renku_yaml_alone_is_not_misidentified_as_a_renku_project(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "renku.yaml").write_text("application: unrelated\n", encoding="utf-8")

            result = self._run_audit(repository, os.environ.copy())

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(
                any(
                    item["declaration_family"] == "RENKU"
                    for item in self._read_observations(repository)
                )
            )

    def test_mlflow_project_marker_is_case_insensitive_at_repository_root(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "mlproject").write_text("name: fixture\n", encoding="utf-8")

            result = self._run_audit(repository, os.environ.copy())

            self.assertEqual(result.returncode, 0, result.stderr)
            observation = self._observation_by_family(repository, "MLFLOW")
            self.assertEqual(observation["marker_paths"], ["mlproject"])

    def test_repo2docker_environment_scope_is_observed_without_executing_build_instructions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            repository = temporary_path / "research-repository"
            repository.mkdir()
            (repository / "requirements.txt").write_text("root-only-package\n", encoding="utf-8")
            binder = repository / "binder"
            binder.mkdir()
            (binder / "environment.yml").write_text("name: research\n", encoding="utf-8")
            executed = temporary_path / "post-build-was-executed"
            (binder / "postBuild").write_text(
                "#!/bin/sh\n" f"touch {str(executed)!r}\n",
                encoding="utf-8",
            )

            result = self._run_audit(repository, os.environ.copy())

            self.assertEqual(result.returncode, 0, result.stderr)
            observation = self._observation_by_family(repository, "COMPUTATIONAL_ENVIRONMENT")
            self.assertEqual(observation["environment_scope"], "BINDER")
            self.assertEqual(
                observation["active_environment_marker_paths"],
                ["binder/environment.yml", "binder/postBuild"],
            )
            self.assertEqual(
                observation["shadowed_environment_marker_paths"],
                ["requirements.txt"],
            )
            self.assertEqual(
                observation["environment_declarations"],
                [
                    {"kind": "CONDA", "path": "binder/environment.yml", "scope_status": "ACTIVE"},
                    {"kind": "POST_BUILD_SCRIPT", "path": "binder/postBuild", "scope_status": "ACTIVE"},
                    {"kind": "PIP", "path": "requirements.txt", "scope_status": "SHADOWED"},
                ],
            )
            self.assertIn("ENVIRONMENT_ROOT_MARKERS_SHADOWED", observation["limitations"])
            self.assertIn("ENVIRONMENT_BUILD_INSTRUCTIONS_NOT_EXECUTED", observation["limitations"])
            self.assertEqual(observation["coverage"], "DECLARATION_PRESENCE_ONLY")
            self.assertFalse(executed.exists())

    def test_repo2docker_conflicting_binder_directories_are_preserved_as_unresolved(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            for directory, marker in (("binder", "Dockerfile"), (".binder", "Project.toml")):
                path = repository / directory
                path.mkdir()
                (path / marker).write_text("declaration only\n", encoding="utf-8")

            result = self._run_audit(repository, os.environ.copy())

            self.assertEqual(result.returncode, 0, result.stderr)
            observation = self._observation_by_family(repository, "COMPUTATIONAL_ENVIRONMENT")
            self.assertEqual(observation["environment_scope"], "CONFLICT")
            self.assertEqual(observation["active_environment_marker_paths"], [])
            self.assertEqual(
                observation["shadowed_environment_marker_paths"],
                [".binder/Project.toml", "binder/Dockerfile"],
            )
            self.assertIn("ENVIRONMENT_BINDER_SCOPE_CONFLICT", observation["limitations"])
            self.assertEqual(observation["status"], "PRESENT")

    def _write_supported_declarations(self, repository: Path) -> None:
        (repository / "dvc.yaml").write_text("stages: {}\n", encoding="utf-8")
        (repository / ".datalad").mkdir()
        (repository / ".datalad" / "config").write_text("[datalad]\n", encoding="utf-8")
        (repository / "MLproject").write_text("name: fixture\n", encoding="utf-8")
        sacred_directory = repository / "sacred-run"
        sacred_directory.mkdir()
        (sacred_directory / "config.json").write_text("{}", encoding="utf-8")
        (sacred_directory / "run.json").write_text("{}", encoding="utf-8")
        (repository / "ro-crate-metadata.json").write_text(
            json.dumps(
                {
                    "@context": "https://w3id.org/ro/crate/1.2/context",
                    "@graph": [
                        {
                            "@id": "ro-crate-metadata.json",
                            "@type": "CreativeWork",
                            "about": {"@id": "./"},
                        },
                        {"@id": "./", "@type": "Dataset"},
                    ],
                }
            ),
            encoding="utf-8",
        )
        (repository / "bagit.txt").write_text("BagIt-Version: 1.0\n", encoding="utf-8")

    def _fake_tool_environment(self, temporary_path: Path) -> tuple[list[Path], dict[str, str]]:
        fake_bin = temporary_path / "fake-bin"
        fake_bin.mkdir()
        markers = []
        for executable in (
            "dvc", "datalad", "mlflow", "sacred", "bagit", "pip", "npm", "conda"
        ):
            marker = temporary_path / f"{executable}-was-called"
            executable_path = fake_bin / executable
            executable_path.write_text(
                "#!/bin/sh\n"
                f"touch {str(marker)!r}\n",
                encoding="utf-8",
            )
            executable_path.chmod(0o700)
            markers.append(marker)
        environment = os.environ.copy()
        environment["PATH"] = f"{fake_bin}{os.pathsep}{environment.get('PATH', '')}"
        return markers, environment

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
            ],
            cwd=Path(__file__).resolve().parents[1],
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )

    def _run_directory(self, repository: Path) -> Path:
        return repository / ".repo-curator" / "runs" / FIXED_RUN_ID

    def _observation_by_family(self, repository: Path, family: str) -> dict:
        return self._observations_by_family(repository, family)[0]

    def _observations_by_family(self, repository: Path, family: str) -> list[dict]:
        return [
            item for item in self._read_observations(repository)
            if item["declaration_family"] == family
        ]

    def _read_observations(self, repository: Path) -> list[dict]:
        observations_path = self._run_directory(repository) / "adapter-observations.jsonl"
        return [
            json.loads(line)
            for line in observations_path.read_text(encoding="utf-8").splitlines()
        ]


class AtomicDeclarationOutputTest(unittest.TestCase):
    def test_final_run_directory_appears_only_after_all_outputs_are_written(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "ro-crate-metadata.json").write_text("{}", encoding="utf-8")
            run_directory = repository / ".repo-curator" / "runs" / FIXED_RUN_ID
            original_write = inventory._write_bytes

            def write_and_require_staging(directory_fd: int, name: str, content: bytes) -> None:
                original_write(directory_fd, name, content)
                if name not in {
                    "plan.json",
                    "plan.md",
                    "curation-brief.json",
                    "curation-brief.md",
                }:
                    self.assertFalse(run_directory.exists())

            with mock.patch.object(
                inventory, "_write_bytes", side_effect=write_and_require_staging
            ):
                inventory.audit_repository(repository, FIXED_RUN_ID, FIXED_CREATED_AT)

            self.assertEqual(
                {path.name for path in run_directory.iterdir()},
                {
                    "inventory.jsonl",
                    "git-observations.jsonl",
                    "profiles.jsonl",
                    "structural-observations.jsonl",
                    "archive-observations.jsonl",
                    "evidence.jsonl",
                    "relationships.jsonl",
                    "project-intent.json",
                    "retention-policy.json",
                    "mainline-map.jsonl",
                    "intent-conflicts.jsonl",
                    "decision-questions.jsonl",
                    "user-decisions.jsonl",
                    "experiment-attempts.jsonl",
                    "experiment-bundles.jsonl",
                    "canonical-result-candidates.jsonl",
                    "reproducibility-gaps.jsonl",
                    "change-episodes.jsonl",
                    "capability-families.jsonl",
                    "implementation-roles.jsonl",
                    "document-comparisons.jsonl",
                    "canonical-entry-points.jsonl",
                    "classifications.jsonl",
                    "recommendations.jsonl",
                    "adapter-observations.jsonl",
                    "run.json",
                },
            )
            self.assertEqual(
                {path.name for path in (repository / ".repo-curator" / "plans" / FIXED_RUN_ID).iterdir()},
                {
                    "plan.json",
                    "plan.md",
                    "curation-brief.json",
                    "curation-brief.md",
                },
            )

    def test_curation_brief_write_failure_clears_the_incomplete_plan(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            original_write = inventory._write_bytes

            def fail_brief_markdown(
                directory_fd: int, name: str, content: bytes
            ) -> None:
                if name == "curation-brief.md":
                    raise OSError("simulated curation brief failure")
                original_write(directory_fd, name, content)

            with mock.patch.object(
                inventory, "_write_bytes", side_effect=fail_brief_markdown
            ):
                with self.assertRaisesRegex(
                    OSError, "simulated curation brief failure"
                ):
                    inventory.audit_repository(
                        repository, FIXED_RUN_ID, FIXED_CREATED_AT
                    )

            self._assert_no_tool_run(repository)
            plans_directory = repository / ".repo-curator" / "plans"
            tombstones = [
                path
                for path in plans_directory.iterdir()
                if path.name.startswith(f".{FIXED_RUN_ID}.")
            ]
            self.assertTrue(tombstones)
            self.assertTrue(
                all(path.is_dir() and not list(path.iterdir()) for path in tombstones)
            )

    def test_atomic_publish_refuses_an_existing_empty_run_directory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            runs_directory = Path(temporary_directory)
            staging_name = ".staged-run"
            final_name = "final-run"
            (runs_directory / staging_name).mkdir()
            (runs_directory / final_name).mkdir()
            directory_fd = os.open(
                runs_directory,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
            )
            try:
                with self.assertRaises(FileExistsError):
                    inventory._rename_directory_without_replacing(
                        directory_fd, staging_name, final_name
                    )
            finally:
                os.close(directory_fd)

            self.assertTrue((runs_directory / staging_name).is_dir())
            self.assertTrue((runs_directory / final_name).is_dir())

    def test_private_staging_retries_after_a_stale_collision(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            runs_directory = Path(temporary_directory)
            stale_name = ".fixture-run." + (b"a" * 16).hex() + ".tmp"
            (runs_directory / stale_name).mkdir()
            descriptor = os.open(runs_directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                with mock.patch.object(inventory.os, "urandom", side_effect=[b"a" * 16, b"b" * 16]):
                    staging_name, staging_fd = inventory._create_private_staging_directory(
                        descriptor,
                        os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
                        "fixture-run",
                    )
                os.close(staging_fd)
            finally:
                os.close(descriptor)
            self.assertNotEqual(staging_name, stale_name)
            self.assertTrue((runs_directory / stale_name).is_dir())
            self.assertTrue((runs_directory / staging_name).is_dir())

    def test_rename_swap_fails_closed_without_removing_the_replacement(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "README.md").write_text("ordinary", encoding="utf-8")
            original_rename = inventory._rename_directory_without_replacing

            def rename_then_swap(directory_fd: int, source: str, destination: str) -> None:
                original_rename(directory_fd, source, destination)
                os.rename(
                    destination,
                    "moved-original",
                    src_dir_fd=directory_fd,
                    dst_dir_fd=directory_fd,
                )
                os.mkdir(destination, dir_fd=directory_fd)

            with mock.patch.object(
                inventory,
                "_rename_directory_without_replacing",
                side_effect=rename_then_swap,
            ):
                with self.assertRaisesRegex(ValueError, "published run directory changed"):
                    inventory.audit_repository(repository, FIXED_RUN_ID, FIXED_CREATED_AT)

            run_directory = repository / ".repo-curator" / "runs" / FIXED_RUN_ID
            self.assertTrue(run_directory.is_dir())

    def test_write_and_publication_failures_leave_no_finalized_or_staging_run(self):
        for failed_name in ("inventory.jsonl", "adapter-observations.jsonl", "run.json"):
            with self.subTest(failed_name=failed_name), tempfile.TemporaryDirectory() as temporary_directory:
                repository = Path(temporary_directory) / "research-repository"
                repository.mkdir()
                original_write = inventory._write_bytes

                def fail_named_write(directory_fd: int, name: str, content: bytes) -> None:
                    if name == failed_name:
                        raise OSError("simulated output failure")
                    original_write(directory_fd, name, content)

                with mock.patch.object(inventory, "_write_bytes", side_effect=fail_named_write):
                    with self.assertRaisesRegex(OSError, "simulated output failure"):
                        inventory.audit_repository(repository, FIXED_RUN_ID, FIXED_CREATED_AT)
                self._assert_no_tool_run(repository)

        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            with mock.patch.object(
                inventory,
                "_rename_directory_without_replacing",
                side_effect=OSError("simulated publication failure"),
            ):
                with self.assertRaisesRegex(OSError, "simulated publication failure"):
                    inventory.audit_repository(repository, FIXED_RUN_ID, FIXED_CREATED_AT)
            self._assert_no_tool_run(repository)

    def test_run_publication_failure_clears_an_already_published_shadow_plan(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            original_rename = inventory._rename_directory_without_replacing
            rename_count = 0

            def fail_run_rename(directory_fd: int, source: str, destination: str) -> None:
                nonlocal rename_count
                rename_count += 1
                if rename_count == 2:
                    raise OSError("simulated run publication failure")
                original_rename(directory_fd, source, destination)

            with mock.patch.object(
                inventory,
                "_rename_directory_without_replacing",
                side_effect=fail_run_rename,
            ):
                with self.assertRaisesRegex(OSError, "simulated run publication failure"):
                    inventory.audit_repository(repository, FIXED_RUN_ID, FIXED_CREATED_AT)

            self._assert_no_tool_run(repository)
            plan_directory = repository / ".repo-curator" / "plans" / FIXED_RUN_ID
            self.assertEqual(list(plan_directory.iterdir()), [])

    def test_staging_path_replacement_is_detected_before_publication(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            runs_directory = Path(temporary_directory)
            (runs_directory / "staging").mkdir()
            runs_fd = os.open(runs_directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            staging_fd = os.open(
                "staging",
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0),
                dir_fd=runs_fd,
            )
            identity = os.fstat(staging_fd)
            os.rename("staging", "moved-tool-staging", src_dir_fd=runs_fd, dst_dir_fd=runs_fd)
            os.mkdir("staging", dir_fd=runs_fd)
            try:
                with self.assertRaisesRegex(ValueError, "staging directory changed"):
                    inventory._require_named_directory_identity(runs_fd, "staging", identity)
            finally:
                os.close(staging_fd)
                os.close(runs_fd)
            self.assertTrue((runs_directory / "staging").is_dir())

    def test_audit_rejects_a_staging_path_swap_before_rename(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            original_require = inventory._require_named_directory_identity
            swapped = []
            staging_checks = []

            def swap_then_require(directory_fd: int, name: str, identity: os.stat_result) -> None:
                if name.startswith(f".{FIXED_RUN_ID}."):
                    staging_checks.append(name)
                if name.startswith(f".{FIXED_RUN_ID}.") and len(staging_checks) == 2 and not swapped:
                    os.rename(name, "moved-tool-staging", src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
                    os.mkdir(name, dir_fd=directory_fd)
                    swapped.append(name)
                original_require(directory_fd, name, identity)

            with mock.patch.object(
                inventory,
                "_require_named_directory_identity",
                side_effect=swap_then_require,
            ):
                with self.assertRaisesRegex(ValueError, "cleanup directory identity mismatch"):
                    inventory.audit_repository(repository, FIXED_RUN_ID, FIXED_CREATED_AT)

            runs_directory = repository / ".repo-curator" / "runs"
            self.assertFalse((runs_directory / FIXED_RUN_ID).exists())
            self.assertTrue((runs_directory / swapped[0]).is_dir())

    def test_audit_rejects_a_shadow_plan_staging_path_swap_before_run_publication(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            original_require = inventory._require_named_directory_identity
            swapped = []

            def swap_plan_then_require(directory_fd: int, name: str, identity: os.stat_result) -> None:
                if name.startswith(f".{FIXED_RUN_ID}.") and not swapped:
                    os.rename(name, "moved-tool-plan", src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
                    os.mkdir(name, dir_fd=directory_fd)
                    swapped.append(name)
                original_require(directory_fd, name, identity)

            with mock.patch.object(
                inventory,
                "_require_named_directory_identity",
                side_effect=swap_plan_then_require,
            ):
                with self.assertRaisesRegex(ValueError, "staging directory changed"):
                    inventory.audit_repository(repository, FIXED_RUN_ID, FIXED_CREATED_AT)

            self.assertFalse((repository / ".repo-curator" / "runs" / FIXED_RUN_ID).exists())
            plans_directory = repository / ".repo-curator" / "plans"
            self.assertTrue((plans_directory / swapped[0]).is_dir())

    def test_cleanup_preserves_replacements_and_leaves_matching_tombstones(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            runs_directory = Path(temporary_directory)
            (runs_directory / "active").mkdir()
            runs_fd = os.open(runs_directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            active_fd = os.open("active", os.O_RDONLY | getattr(os, "O_DIRECTORY", 0), dir_fd=runs_fd)
            identity = os.fstat(active_fd)
            os.rename("active", "moved-tool-staging", src_dir_fd=runs_fd, dst_dir_fd=runs_fd)
            os.mkdir("active", dir_fd=runs_fd)
            with self.assertRaisesRegex(ValueError, "cleanup directory identity mismatch"):
                inventory._cleanup_incomplete_run(active_fd, runs_fd, "active", identity)
            self.assertTrue((runs_directory / "active").is_dir())

        with tempfile.TemporaryDirectory() as temporary_directory:
            runs_directory = Path(temporary_directory)
            (runs_directory / "active").mkdir()
            (runs_directory / "active" / "inventory.jsonl").write_text("partial")
            runs_fd = os.open(runs_directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            active_fd = os.open("active", os.O_RDONLY | getattr(os, "O_DIRECTORY", 0), dir_fd=runs_fd)
            inventory._cleanup_incomplete_run(active_fd, runs_fd, "active", os.fstat(active_fd))
            self.assertTrue((runs_directory / "active").is_dir())
            self.assertEqual(list((runs_directory / "active").iterdir()), [])

    def _assert_no_tool_run(self, repository: Path) -> None:
        runs_directory = repository / ".repo-curator" / "runs"
        self.assertFalse((runs_directory / FIXED_RUN_ID).exists())
        if runs_directory.exists():
            tombstones = [
                path
                for path in runs_directory.iterdir()
                if path.name.startswith(f".{FIXED_RUN_ID}.")
            ]
            self.assertTrue(tombstones)
            self.assertTrue(all(path.is_dir() and not list(path.iterdir()) for path in tombstones))


if __name__ == "__main__":
    unittest.main()
