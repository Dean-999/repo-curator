import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from repo_curator.bundle import _validate_source_governance, build_skill_bundle
from repo_curator import __version__


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class SkillBundleTest(unittest.TestCase):
    def test_source_governance_rejects_duplicate_json_keys(self):
        from repo_curator.bundle import _validate_source_governance

        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory)
            (source / "third_party").mkdir()
            (source / "third_party" / "sources.lock.yaml").write_text(
                '{"schema_version":"repo-curator.third-party-sources-lock.v1",'
                '"schema_version":"repo-curator.third-party-sources-lock.v1"}',
                encoding="utf-8",
            )
            (source / "THIRD_PARTY_NOTICES.md").write_text("notice\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "not valid UTF-8 JSON"):
                _validate_source_governance(source)

    def test_bundle_is_self_contained_hash_bound_and_runs_without_checkout_imports(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            bundle = temporary_path / "repo-curator"

            result = subprocess.run(
                [
                    sys.executable,
                    str(REPOSITORY_ROOT / "tools" / "build_skill_bundle.py"),
                    "--output",
                    str(bundle),
                ],
                cwd=temporary_path,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)

            manifest = json.loads(
                (bundle / "manifest.json").read_text(encoding="utf-8")
            )
            self.assertEqual(
                manifest["schema_version"], "repo-curator.skill-bundle.v4"
            )
            self.assertEqual(manifest["skill_name"], "repo-curator")
            self.assertEqual(manifest["repo_curator_version"], __version__)
            source_git = manifest["source_git"]
            expected_head = subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD^{commit}"],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            expected_tree = subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD^{tree}"],
                cwd=REPOSITORY_ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.strip()
            self.assertEqual(source_git["head_commit"], expected_head)
            self.assertEqual(source_git["head_tree"], expected_tree)
            self.assertIn(
                source_git["distributed_inputs_state"],
                {"MATCHES_HEAD", "DIFFERS_FROM_HEAD"},
            )
            self.assertRegex(
                source_git["distributed_inputs_sha256"], r"^[0-9a-f]{64}$"
            )
            self.assertIn("scripts/run_audit.py", manifest["files"])
            self.assertIn("scripts/repo_curator/cli.py", manifest["files"])
            self.assertIn("third_party/sources.lock.yaml", manifest["files"])
            self.assertIn("THIRD_PARTY_NOTICES.md", manifest["files"])
            self.assertIn("third_party/licenses/Apache-2.0.txt", manifest["files"])
            self.assertIn("third_party/licenses/BSD-3-Clause-repo2docker.txt", manifest["files"])
            self.assertIn("third_party/licenses/BSD-3-Clause-signac.txt", manifest["files"])
            self.assertIn("third_party/licenses/MIT-gitleaks.txt", manifest["files"])
            self.assertIn("third_party/licenses/MIT-frictionless-py.txt", manifest["files"])
            self.assertIn("third_party/licenses/MIT-git-sizer.txt", manifest["files"])
            self.assertIn("third_party/licenses/MIT-pre-commit-hooks.txt", manifest["files"])
            self.assertIn("schemas/registry.json", manifest["files"])
            self.assertIn("schemas/README.md", manifest["files"])
            self.assertIn(
                "schemas/ro-crate-evidence-profile.shacl.ttl", manifest["files"]
            )
            self.assertIn(
                "scripts/repo_curator/ro_crate_validation.py", manifest["files"]
            )
            governance = manifest["governance"]
            self.assertEqual(
                governance["source_lock_sha256"],
                hashlib.sha256((bundle / governance["source_lock_path"]).read_bytes()).hexdigest(),
            )
            self.assertEqual(
                governance["third_party_notices_sha256"],
                hashlib.sha256((bundle / governance["third_party_notices_path"]).read_bytes()).hexdigest(),
            )
            self.assertEqual(
                governance["schema_registry_sha256"],
                hashlib.sha256((bundle / governance["schema_registry_path"]).read_bytes()).hexdigest(),
            )
            self.assertEqual(
                governance["schema_guidance_sha256"],
                hashlib.sha256((bundle / governance["schema_guidance_path"]).read_bytes()).hexdigest(),
            )
            self.assertEqual(
                governance["ro_crate_shape_sha256"],
                hashlib.sha256(
                    (bundle / governance["ro_crate_shape_path"]).read_bytes()
                ).hexdigest(),
            )
            schema_registry = json.loads(
                (bundle / governance["schema_registry_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(
                schema_registry["schema_version"], "repo-curator.schema-registry.v1"
            )
            self.assertTrue(schema_registry["schemas"])
            self.assertEqual(schema_registry["defaults"]["unknown_version_policy"], "REJECT")
            source_lock = json.loads(
                (bundle / governance["source_lock_path"]).read_text(encoding="utf-8")
            )
            self.assertEqual(
                source_lock["schema_version"], "repo-curator.third-party-sources-lock.v1"
            )
            self.assertTrue(source_lock["review_policy"]["upstream_changes_enter_shadow_first"])
            self.assertTrue(source_lock["entries"])
            distributed = [item for item in source_lock["entries"] if item["distributed_code"]]
            self.assertEqual(
                {item["id"]: item["distributed_files"] for item in distributed},
                {
                    "frictionless-py": ["repo_curator/data_package.py"],
                    "gitleaks": ["repo_curator/secret_redaction.py"],
                    "git-sizer": ["repo_curator/git_repository_size.py"],
                    "pre-commit-hooks": ["repo_curator/repository_hygiene.py"],
                    "nbformat": ["repo_curator/notebook_envelope.py"],
                    "nf-prov": ["repo_curator/workflow_run_crate.py"],
                    "repo2docker": ["repo_curator/environment_declarations.py"],
                    "ro-crate-py": ["repo_curator/ro_crate_graph.py"],
                    "signac": ["repo_curator/research_metadata.py"],
                    "workflow-run-ro-crate": [
                        "repo_curator/workflow_run_crate.py"
                    ],
                },
            )
            self.assertTrue(
                all(item["license"]["text_path"] in manifest["files"] for item in distributed)
            )
            self.assertTrue(
                all(
                    item["distributed_code"] is False
                    for item in source_lock["entries"]
                    if item["id"] not in {
                        "frictionless-py", "gitleaks", "git-sizer", "nbformat",
                        "nf-prov", "pre-commit-hooks", "repo2docker",
                        "ro-crate-py", "signac", "workflow-run-ro-crate"
                    }
                )
            )
            self.assertTrue(all(item["modification_summary"] for item in source_lock["entries"]))
            self.assertFalse(any("__pycache__" in path for path in manifest["files"]))
            mutation_modules = {
                "approval.py",
                "archive_apply.py",
                "quarantine_apply.py",
                "recovery.py",
                "transactions.py",
            }
            packaged_modules = {
                Path(path).name
                for path in manifest["files"]
                if path.startswith("scripts/repo_curator/")
            }
            self.assertTrue(mutation_modules.isdisjoint(packaged_modules))
            for module in mutation_modules:
                self.assertFalse((bundle / "scripts" / "repo_curator" / module).exists())
            help_result = subprocess.run(
                [
                    sys.executable,
                    str(bundle / "scripts" / "run_audit.py"),
                    "--help",
                ],
                cwd=temporary_path,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(help_result.returncode, 0, help_result.stderr)
            self.assertIn("audit", help_result.stdout)
            self.assertIn("export-ro-crate", help_result.stdout)
            self.assertIn("validate-ro-crate", help_result.stdout)
            self.assertNotIn("corpus-manifest", help_result.stdout)
            self.assertNotIn("materialize-wave3", help_result.stdout)
            for relative_path, expected_hash in manifest["files"].items():
                self.assertEqual(
                    hashlib.sha256((bundle / relative_path).read_bytes()).hexdigest(),
                    expected_hash,
                )

            target = temporary_path / "research-repository"
            target.mkdir()
            marker = target / "target-code-executed"
            (target / "danger.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('executed')\n",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(bundle / "scripts" / "run_audit.py"),
                    "audit",
                    "--root",
                    str(target),
                    "--run-id",
                    "bundle-run",
                    "--created-at",
                    "2026-07-27T12:00:00Z",
                ],
                cwd=temporary_path,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(marker.exists())
            self.assertTrue(
                (
                    target
                    / ".repo-curator"
                    / "plans"
                    / "bundle-run"
                    / "curation-brief.md"
                ).is_file()
            )
            export_path = temporary_path / "ro-crate-metadata.json"
            export_result = subprocess.run(
                [
                    sys.executable,
                    str(bundle / "scripts" / "run_audit.py"),
                    "export-ro-crate",
                    "--run-directory",
                    str(target / ".repo-curator" / "runs" / "bundle-run"),
                    "--output",
                    str(export_path),
                ],
                cwd=temporary_path,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(export_result.returncode, 0, export_result.stderr)
            export = json.loads(export_path.read_text(encoding="utf-8"))
            self.assertFalse(
                next(item for item in export["@graph"] if item["@id"] == "./")[
                    "repo-curator:executionAuthorized"
                ]
            )
            validation_path = temporary_path / "ro-crate-validation.json"
            validation_result = subprocess.run(
                [
                    sys.executable,
                    str(bundle / "scripts" / "run_audit.py"),
                    "validate-ro-crate",
                    "--input",
                    str(export_path),
                    "--output",
                    str(validation_path),
                ],
                cwd=temporary_path,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(validation_result.returncode, 0, validation_result.stderr)
            self.assertEqual(
                json.loads(validation_path.read_text(encoding="utf-8"))["status"],
                "BOUNDED_PROFILE_CONFORMANT",
            )

    def test_bundle_refuses_to_overwrite_an_existing_path(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "existing"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep\n", encoding="utf-8")

            with self.assertRaises(FileExistsError):
                build_skill_bundle(REPOSITORY_ROOT, output)

            self.assertEqual(marker.read_text(encoding="utf-8"), "keep\n")

    def test_bundle_rejects_a_linked_source_root_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            linked_source = temporary_path / "linked-source"
            linked_source.symlink_to(REPOSITORY_ROOT, target_is_directory=True)
            output = temporary_path / "bundle"

            with self.assertRaisesRegex(ValueError, "source root must not be a symbolic link"):
                build_skill_bundle(linked_source, output)

            self.assertFalse(output.exists())

    def test_bundle_rejects_a_linked_distributed_input_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "bundle"
            skill_path = REPOSITORY_ROOT / ".agents" / "skills" / "repo-curator" / "SKILL.md"
            original_is_symlink = Path.is_symlink

            def report_skill_as_link(path):
                return path == skill_path or original_is_symlink(path)

            with mock.patch.object(Path, "is_symlink", autospec=True, side_effect=report_skill_as_link):
                with self.assertRaisesRegex(ValueError, "bundle source input is linked"):
                    build_skill_bundle(REPOSITORY_ROOT, output)

            self.assertFalse(output.exists())

    def test_bundle_refuses_invalid_source_governance_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "bundle"

            with mock.patch(
                "repo_curator.bundle._validate_source_governance",
                side_effect=ValueError("invalid source governance"),
            ):
                with self.assertRaisesRegex(ValueError, "invalid source governance"):
                    build_skill_bundle(REPOSITORY_ROOT, output)

            self.assertFalse(output.exists())

    def test_bundle_refuses_invalid_schema_registry_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "bundle"

            with mock.patch(
                "repo_curator.bundle._validate_schema_registry",
                side_effect=ValueError("invalid schema registry"),
            ):
                with self.assertRaisesRegex(ValueError, "invalid schema registry"):
                    build_skill_bundle(REPOSITORY_ROOT, output)

            self.assertFalse(output.exists())

    def test_source_governance_rejects_unbound_distributed_code(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory)
            (source / "third_party").mkdir()
            (source / "fixture.txt").write_text("fixture\n", encoding="utf-8")
            (source / "THIRD_PARTY_NOTICES.md").write_text(
                "## attributed-port\n", encoding="utf-8"
            )
            lock = {
                "entries": [
                    {
                        "adopted_boundary": "bounded port",
                        "commit": "a" * 40,
                        "distributed_code": True,
                        "distributed_files": ["missing.py"],
                        "excluded_authority": ["execution"],
                        "fixtures": ["fixture.txt"],
                        "id": "attributed-port",
                        "integration_mode": "ATTRIBUTED_BOUNDED_PORT",
                        "license": {"spdx": "Apache-2.0"},
                        "modification_summary": "bounded adaptation",
                        "name": "Attributed Port",
                        "repository": "https://example.invalid/upstream",
                        "upstream_material": ["source.py"],
                    }
                ],
                "review_policy": {
                    "cadence": "BEFORE_EACH_RELEASE",
                    "upstream_changes_enter_shadow_first": True,
                },
                "schema_version": "repo-curator.third-party-sources-lock.v1",
                "serialization": "JSON_SUBSET_OF_YAML_1_2",
            }
            (source / "third_party" / "sources.lock.yaml").write_text(
                json.dumps(lock), encoding="utf-8"
            )

            with self.assertRaisesRegex(
                ValueError, "distributed third-party source file is invalid"
            ):
                _validate_source_governance(source)

    def test_source_governance_rejects_missing_distributed_license_text(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory)
            (source / "third_party").mkdir()
            (source / "port.py").write_text("# attributed port\n", encoding="utf-8")
            (source / "fixture.txt").write_text("fixture\n", encoding="utf-8")
            (source / "THIRD_PARTY_NOTICES.md").write_text(
                "## attributed-port\n", encoding="utf-8"
            )
            lock = {
                "entries": [
                    {
                        "adopted_boundary": "bounded port",
                        "commit": "a" * 40,
                        "distributed_code": True,
                        "distributed_files": ["port.py"],
                        "excluded_authority": ["execution"],
                        "fixtures": ["fixture.txt"],
                        "id": "attributed-port",
                        "integration_mode": "ATTRIBUTED_BOUNDED_PORT",
                        "license": {
                            "spdx": "Apache-2.0",
                            "text_path": "third_party/licenses/Apache-2.0.txt",
                        },
                        "modification_summary": "bounded adaptation",
                        "name": "Attributed Port",
                        "repository": "https://example.invalid/upstream",
                        "upstream_material": ["source.py"],
                    }
                ],
                "review_policy": {
                    "cadence": "BEFORE_EACH_RELEASE",
                    "upstream_changes_enter_shadow_first": True,
                },
                "schema_version": "repo-curator.third-party-sources-lock.v1",
                "serialization": "JSON_SUBSET_OF_YAML_1_2",
            }
            (source / "third_party" / "sources.lock.yaml").write_text(
                json.dumps(lock), encoding="utf-8"
            )

            with self.assertRaisesRegex(
                ValueError, "distributed third-party license text is missing"
            ):
                _validate_source_governance(source)

    def test_source_governance_rejects_error_text_as_a_license(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            source = Path(temporary_directory)
            (source / "third_party" / "licenses").mkdir(parents=True)
            (source / "third_party" / "licenses" / "Apache-2.0.txt").write_text(
                "GitHub API: unexpected EOF\n", encoding="utf-8"
            )
            (source / "port.py").write_text("# attributed port\n", encoding="utf-8")
            (source / "fixture.txt").write_text("fixture\n", encoding="utf-8")
            (source / "THIRD_PARTY_NOTICES.md").write_text(
                "## attributed-port\n", encoding="utf-8"
            )
            lock = {
                "entries": [
                    {
                        "adopted_boundary": "bounded port",
                        "commit": "a" * 40,
                        "distributed_code": True,
                        "distributed_files": ["port.py"],
                        "excluded_authority": ["execution"],
                        "fixtures": ["fixture.txt"],
                        "id": "attributed-port",
                        "integration_mode": "ATTRIBUTED_BOUNDED_PORT",
                        "license": {
                            "spdx": "Apache-2.0",
                            "text_path": "third_party/licenses/Apache-2.0.txt",
                        },
                        "modification_summary": "bounded adaptation",
                        "name": "Attributed Port",
                        "repository": "https://example.invalid/upstream",
                        "upstream_material": ["source.py"],
                    }
                ],
                "review_policy": {
                    "cadence": "BEFORE_EACH_RELEASE",
                    "upstream_changes_enter_shadow_first": True,
                },
                "schema_version": "repo-curator.third-party-sources-lock.v1",
                "serialization": "JSON_SUBSET_OF_YAML_1_2",
            }
            (source / "third_party" / "sources.lock.yaml").write_text(
                json.dumps(lock), encoding="utf-8"
            )

            with self.assertRaisesRegex(
                ValueError, "distributed third-party license text is invalid"
            ):
                _validate_source_governance(source)


if __name__ == "__main__":
    unittest.main()
