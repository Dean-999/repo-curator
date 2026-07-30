import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from repo_curator import inventory


RUN_ID = "data-package-run"
CREATED_AT = "2026-07-28T00:00:00Z"


class DataPackageObserverTest(unittest.TestCase):
    def test_observer_reports_bounded_resource_structure_without_payload_values(self):
        from repo_curator.data_package import observe_data_package

        remote = "https://fixture-user:fixture-password@example.test/data.csv"
        inline_secret = "inline-secret-must-not-persist"
        parsed = {
            "name": "climate-data",
            "profile": "https://datapackage.org/profiles/2.0/datapackage.json",
            "resources": [
                {
                    "name": "measurements",
                    "path": "data.csv",
                    "format": "csv",
                    "mediatype": "text/csv",
                    "schema": {"fields": [{"name": "temperature"}]},
                },
                {"name": "missing", "path": "missing.csv"},
                {"name": "remote", "path": remote},
                {"name": "inline", "data": [["value"], [inline_secret]]},
                {"name": "escape", "path": "../../outside.csv"},
                {"name": "windows", "path": "C:/outside.csv"},
            ],
        }
        inventory_records = {
            "dataset/data.csv": {"object_type": "REGULAR_FILE"},
        }

        details, limitations = observe_data_package(
            parsed, "dataset/datapackage.json", inventory_records
        )

        package = details["data_package"]
        self.assertEqual(package["declared_name"], "climate-data")
        self.assertTrue(package["profile_declared"])
        self.assertEqual(package["resource_count_declared"], 6)
        self.assertEqual(
            package["resources"][0],
            {
                "declared_format": "csv",
                "declared_mediatype": "text/csv",
                "index": 0,
                "local_paths": [
                    {
                        "inventory_status": "PRESENT",
                        "repository_relative_path": "dataset/data.csv",
                    }
                ],
                "name": "measurements",
                "schema_kind": "INLINE_OBJECT",
                "source_kind": "LOCAL_PATH",
            },
        )
        self.assertEqual(package["resources"][1]["local_paths"][0]["inventory_status"], "MISSING")
        self.assertEqual(package["resources"][2]["source_kind"], "REMOTE_PATH")
        self.assertNotIn("local_paths", package["resources"][2])
        self.assertEqual(package["resources"][3]["source_kind"], "INLINE_DATA")
        self.assertEqual(package["resources"][4]["source_kind"], "UNSAFE_PATH")
        self.assertEqual(package["resources"][5]["source_kind"], "UNSAFE_PATH")
        encoded = json.dumps(details, sort_keys=True)
        self.assertNotIn(remote, encoded)
        self.assertNotIn(inline_secret, encoded)
        self.assertIn("DATA_PACKAGE_REMOTE_RESOURCES_NOT_ACCESSED", limitations)
        self.assertIn("DATA_PACKAGE_INLINE_DATA_NOT_PERSISTED", limitations)
        self.assertIn("DATA_PACKAGE_LOCAL_RESOURCE_MISSING", limitations)
        self.assertIn("DATA_PACKAGE_RESOURCE_PATH_UNSAFE", limitations)

    def test_observer_bounds_resources_and_paths(self):
        from repo_curator.data_package import observe_data_package

        parsed = {
            "resources": [
                {
                    "name": "multipart",
                    "path": "part-0.csv",
                    "extrapaths": ["part-1.csv", "part-2.csv"],
                },
                {"name": "second", "path": "second.csv"},
            ]
        }
        with mock.patch("repo_curator.data_package.RESOURCE_LIMIT", 1), mock.patch(
            "repo_curator.data_package.PATHS_PER_RESOURCE_LIMIT", 2
        ):
            details, limitations = observe_data_package(parsed, "datapackage.json", {})

        self.assertEqual(len(details["data_package"]["resources"]), 1)
        self.assertEqual(
            len(details["data_package"]["resources"][0]["local_paths"]), 2
        )
        self.assertIn("DATA_PACKAGE_RESOURCE_LIMIT", limitations)
        self.assertIn("DATA_PACKAGE_RESOURCE_PATH_LIMIT", limitations)

    def test_observer_distinguishes_non_regular_local_resource_from_missing(self):
        from repo_curator.data_package import observe_data_package

        details, limitations = observe_data_package(
            {"resources": [{"name": "directory", "path": "data"}]},
            "datapackage.json",
            {"data": {"object_type": "DIRECTORY"}},
        )

        self.assertEqual(
            details["data_package"]["resources"][0]["local_paths"][0][
                "inventory_status"
            ],
            "PRESENT_NON_REGULAR",
        )
        self.assertIn("DATA_PACKAGE_LOCAL_RESOURCE_NON_REGULAR", limitations)
        self.assertNotIn("DATA_PACKAGE_LOCAL_RESOURCE_MISSING", limitations)

    def test_audit_emits_one_observation_per_descriptor_and_retains_malformed_json(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            repository = Path(temporary_directory) / "research-repository"
            repository.mkdir()
            (repository / "datapackage.json").write_text("{bad", encoding="utf-8")
            nested = repository / "dataset"
            nested.mkdir()
            (nested / "data.csv").write_text("value\n1\n", encoding="utf-8")
            uri_secret = "nested-uri-password"
            inline_value = "nested-inline-value"
            (nested / "datapackage.json").write_text(
                json.dumps(
                    {
                        "name": "nested-data",
                        "resources": [
                            {"name": "data", "path": "data.csv"},
                            {
                                "name": "remote",
                                "path": (
                                    "https://fixture-user:"
                                    + uri_secret
                                    + "@example.test/data.csv"
                                ),
                            },
                            {"name": "inline", "data": [[inline_value]]},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            inventory.audit_repository(repository, RUN_ID, CREATED_AT)

            run_directory = repository / ".repo-curator" / "runs" / RUN_ID
            observations = [
                json.loads(line)
                for line in (run_directory / "adapter-observations.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]
            packages = [
                item for item in observations
                if item["declaration_family"] == "DATA_PACKAGE"
            ]
            self.assertEqual(len(packages), 2)
            by_path = {item["marker_paths"][0]: item for item in packages}
            self.assertEqual(by_path["datapackage.json"]["status"], "MALFORMED")
            nested_observation = by_path["dataset/datapackage.json"]
            self.assertEqual(nested_observation["validation_status"], "SYNTAX_VALIDATED")
            self.assertEqual(
                nested_observation["data_package"]["resources"][0]["local_paths"],
                [
                    {
                        "inventory_status": "PRESENT",
                        "repository_relative_path": "dataset/data.csv",
                    }
                ],
            )
            profile = next(
                item
                for item in (
                    json.loads(line)
                    for line in (run_directory / "profiles.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                )
                if item["repository_relative_path"] == "dataset/datapackage.json"
            )
            self.assertEqual(profile["format"], "DATA_PACKAGE")
            self.assertEqual(profile["sample"], "")
            for output in run_directory.iterdir():
                if output.is_file():
                    payload = output.read_bytes()
                    self.assertNotIn(uri_secret.encode("utf-8"), payload)
                    self.assertNotIn(inline_value.encode("utf-8"), payload)


if __name__ == "__main__":
    unittest.main()
