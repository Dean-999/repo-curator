import json
import tempfile
import unittest
from pathlib import Path

from repo_curator import inventory
from repo_curator.research_metadata import (
    SIGNAC_MARKER_LIMIT,
    is_sensitive_research_metadata_path,
    signac_candidate,
)


RUN_ID = "research-metadata-run"
CREATED_AT = "2026-07-28T12:00:00Z"


class ResearchMetadataObserverTest(unittest.TestCase):
    def test_cff_and_codemeta_profile_suppression_matches_exact_root_contract(self):
        self.assertTrue(is_sensitive_research_metadata_path("CITATION.cff"))
        self.assertTrue(is_sensitive_research_metadata_path("codemeta.json"))
        self.assertFalse(is_sensitive_research_metadata_path("docs/CITATION.cff"))
        self.assertFalse(is_sensitive_research_metadata_path("CODEMETA.JSON"))

    def test_audit_observes_cff_codemeta_and_signac_without_persisting_values(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            private_values = [
                "private-author@example.test",
                "private-project-title",
                "private-statepoint-value",
                "private-job-document-value",
            ]
            (repository / "CITATION.cff").write_text(
                "cff-version: 1.2.0\n"
                f"title: {private_values[1]}\n"
                "authors:\n"
                f"  - email: {private_values[0]}\n",
                encoding="utf-8",
            )
            (repository / "codemeta.json").write_text(
                json.dumps(
                    {
                        "@context": "https://w3id.org/codemeta/3.0",
                        "@type": "SoftwareSourceCode",
                        "name": private_values[1],
                        "author": [{"email": private_values[0]}],
                        "codeRepository": "https://user:password@example.test/repo",
                        "programmingLanguage": ["Python", "C++"],
                        "softwareVersion": "1.2.3",
                        "supportingData": {"name": private_values[2]},
                        private_values[0]: "unknown-field-name-must-not-persist",
                    }
                ),
                encoding="utf-8",
            )
            signac = repository / ".signac"
            signac.mkdir()
            (signac / "config").write_text(
                f"schema_version = 2\nsecret = {private_values[2]}\n",
                encoding="utf-8",
            )
            (signac / "statepoint_cache.json.gz").write_bytes(
                private_values[2].encode("utf-8")
            )
            (repository / "signac_project_document.json").write_text(
                json.dumps({"private": private_values[3]}), encoding="utf-8"
            )
            workspace = repository / "workspace" / "job-a"
            workspace.mkdir(parents=True)
            (workspace / "signac_statepoint.json").write_text(
                json.dumps({"parameter": private_values[2]}), encoding="utf-8"
            )
            (workspace / "signac_job_document.json").write_text(
                json.dumps({"result": private_values[3]}), encoding="utf-8"
            )

            inventory.audit_repository(repository, RUN_ID, CREATED_AT)

            run_directory = repository / ".repo-curator" / "runs" / RUN_ID
            observations = [
                json.loads(line)
                for line in (run_directory / "adapter-observations.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            by_family = {item["declaration_family"]: item for item in observations}
            self.assertTrue({"CITATION_CFF", "CODEMETA", "SIGNAC"}.issubset(by_family))

            codemeta = by_family["CODEMETA"]
            self.assertEqual(codemeta["validation_status"], "SYNTAX_VALIDATED")
            self.assertEqual(
                codemeta["codemeta"]["declared_fields"],
                [
                    "@context",
                    "@type",
                    "author",
                    "codeRepository",
                    "name",
                    "programmingLanguage",
                    "softwareVersion",
                    "supportingData",
                ],
            )
            self.assertEqual(codemeta["codemeta"]["author_count_declared"], 1)
            self.assertEqual(
                codemeta["codemeta"]["programming_language_count_declared"], 2
            )

            signac_observation = by_family["SIGNAC"]
            self.assertEqual(signac_observation["signac"]["statepoint_count"], 1)
            self.assertEqual(signac_observation["signac"]["job_document_count"], 1)
            self.assertTrue(signac_observation["signac"]["project_config_present"])
            self.assertTrue(signac_observation["signac"]["statepoint_cache_present"])
            self.assertEqual(signac_observation["signac"]["project_document_count"], 1)
            self.assertIn(
                "SIGNAC_METADATA_CONTENT_NOT_PARSED", signac_observation["limitations"]
            )

            profiles = [
                json.loads(line)
                for line in (run_directory / "profiles.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            metadata_profiles = [
                item
                for item in profiles
                if item["repository_relative_path"]
                in {
                    "CITATION.cff",
                    "codemeta.json",
                    ".signac/config",
                    ".signac/statepoint_cache.json.gz",
                    "signac_project_document.json",
                    "workspace/job-a/signac_statepoint.json",
                    "workspace/job-a/signac_job_document.json",
                }
            ]
            self.assertEqual(len(metadata_profiles), 7)
            self.assertTrue(
                all(item["sample"] == "" and item["metadata"] == {} for item in metadata_profiles)
            )
            for path in run_directory.iterdir():
                if path.is_file():
                    payload = path.read_bytes()
                    for value in private_values:
                        self.assertNotIn(value.encode("utf-8"), payload, path.name)

    def test_malformed_codemeta_is_retained_without_signac_false_positive(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "codemeta.json").write_text("{bad", encoding="utf-8")
            (repository / "signac_statepoint.json.backup").write_text(
                "not a marker", encoding="utf-8"
            )

            inventory.audit_repository(repository, RUN_ID, CREATED_AT)

            run_directory = repository / ".repo-curator" / "runs" / RUN_ID
            observations = [
                json.loads(line)
                for line in (run_directory / "adapter-observations.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            self.assertEqual(len(observations), 1)
            self.assertEqual(observations[0]["declaration_family"], "CODEMETA")
            self.assertEqual(observations[0]["status"], "MALFORMED")
            self.assertNotIn("CODEMETA_ROOT_NOT_OBJECT", observations[0]["limitations"])

    def test_codemeta_size_boundary_is_explicit(self):
        for extra_byte, expected_status, expected_validation in (
            (False, "PRESENT", "SYNTAX_VALIDATED"),
            (True, "PRESENT_UNVALIDATED", "SIZE_LIMIT"),
        ):
            with self.subTest(extra_byte=extra_byte), tempfile.TemporaryDirectory() as temporary_directory:
                repository = Path(temporary_directory) / "research-repository"
                repository.mkdir()
                size = 1024 * 1024 + int(extra_byte)
                (repository / "codemeta.json").write_bytes(b"{}" + b" " * (size - 2))

                inventory.audit_repository(repository, RUN_ID, CREATED_AT)

                observation = json.loads(
                    (repository / ".repo-curator" / "runs" / RUN_ID / "adapter-observations.jsonl")
                    .read_text(encoding="utf-8")
                    .strip()
                )
                self.assertEqual(observation["status"], expected_status)
                self.assertEqual(observation["validation_status"], expected_validation)
                self.assertNotIn("CODEMETA_ROOT_NOT_OBJECT", observation["limitations"])

    def test_signac_marker_retention_is_bounded_and_deterministic(self):
        records = {
            f"workspace/{index:04d}/signac_statepoint.json": {
                "artifact_id": f"artifact-{index:04d}",
                "object_type": "REGULAR_FILE",
                "repository_relative_path": f"workspace/{index:04d}/signac_statepoint.json",
            }
            for index in reversed(range(SIGNAC_MARKER_LIMIT + 44))
        }

        candidate = signac_candidate(records)

        self.assertIsNotNone(candidate)
        source, markers, limitations, details = candidate
        self.assertEqual(len(markers), SIGNAC_MARKER_LIMIT)
        self.assertEqual(source["repository_relative_path"], "workspace/0000/signac_statepoint.json")
        self.assertEqual(
            [item["repository_relative_path"] for item in markers],
            sorted(item["repository_relative_path"] for item in markers),
        )
        self.assertEqual(details["signac"]["statepoint_count"], SIGNAC_MARKER_LIMIT + 44)
        self.assertIn("SIGNAC_MARKER_LIMIT", limitations)


if __name__ == "__main__":
    unittest.main()
