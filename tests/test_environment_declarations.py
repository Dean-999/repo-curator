import unittest

from repo_curator.environment_declarations import environment_declaration_candidate


def _record(path, object_type="REGULAR_FILE"):
    return {
        "artifact_id": f"artifact:{path}",
        "location_id": f"location:{path}",
        "object_type": object_type,
        "repository_relative_path": path,
    }


class EnvironmentDeclarationsTest(unittest.TestCase):
    def test_returns_none_without_a_root_or_binder_marker(self):
        records = {
            "nested/requirements.txt": _record("nested/requirements.txt"),
            "README.md": _record("README.md"),
        }

        self.assertIsNone(environment_declaration_candidate(records))

    def test_root_scope_records_deprecated_and_executable_declarations(self):
        records = {
            "REQUIRE": _record("REQUIRE"),
            "start": _record("start"),
        }

        _, marker_records, limitations, details = environment_declaration_candidate(records)

        self.assertEqual(
            [record["repository_relative_path"] for record in marker_records],
            ["REQUIRE", "start"],
        )
        self.assertEqual(details["environment_scope"], "ROOT")
        self.assertEqual(details["active_environment_marker_paths"], ["REQUIRE", "start"])
        self.assertIn("ENVIRONMENT_DECLARATION_DEPRECATED_UPSTREAM", limitations)
        self.assertIn("ENVIRONMENT_BUILD_INSTRUCTIONS_NOT_EXECUTED", limitations)

    def test_dot_binder_scope_shadows_root_and_ignores_root_only_marker_inside_scope(self):
        records = {
            ".binder": _record(".binder", "DIRECTORY"),
            ".binder/environment.yaml": _record(".binder/environment.yaml"),
            ".binder/pyproject.toml": _record(".binder/pyproject.toml"),
            "pyproject.toml": _record("pyproject.toml"),
        }

        _, marker_records, limitations, details = environment_declaration_candidate(records)

        self.assertEqual(
            [record["repository_relative_path"] for record in marker_records],
            [".binder/environment.yaml", "pyproject.toml"],
        )
        self.assertEqual(details["environment_scope"], "DOT_BINDER")
        self.assertEqual(
            details["active_environment_marker_paths"], [".binder/environment.yaml"]
        )
        self.assertEqual(details["shadowed_environment_marker_paths"], ["pyproject.toml"])
        self.assertIn("ENVIRONMENT_ROOT_MARKERS_SHADOWED", limitations)

    def test_empty_active_binder_scope_retains_shadowed_root_evidence(self):
        records = {
            "binder": _record("binder", "DIRECTORY"),
            "requirements.txt": _record("requirements.txt"),
        }

        _, _, limitations, details = environment_declaration_candidate(records)

        self.assertEqual(details["environment_scope"], "BINDER")
        self.assertEqual(details["active_environment_marker_paths"], [])
        self.assertEqual(details["shadowed_environment_marker_paths"], ["requirements.txt"])
        self.assertIn("ENVIRONMENT_ACTIVE_SCOPE_HAS_NO_RECOGNIZED_MARKER", limitations)

    def test_conflicting_binder_scopes_mark_every_declaration_unresolved(self):
        records = {
            "binder": _record("binder", "DIRECTORY"),
            ".binder": _record(".binder", "DIRECTORY"),
            "binder/Dockerfile": _record("binder/Dockerfile"),
            ".binder/Project.toml": _record(".binder/Project.toml"),
        }

        _, _, limitations, details = environment_declaration_candidate(records)

        self.assertEqual(details["environment_scope"], "CONFLICT")
        self.assertTrue(
            all(
                declaration["scope_status"] == "UNRESOLVED"
                for declaration in details["environment_declarations"]
            )
        )
        self.assertIn("ENVIRONMENT_BINDER_SCOPE_CONFLICT", limitations)


if __name__ == "__main__":
    unittest.main()
