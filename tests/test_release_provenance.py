import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from repo_curator.release_provenance import (
    ReleaseProvenanceError,
    build_release_provenance,
    verify_release_provenance,
)


class ReleaseProvenanceTest(unittest.TestCase):
    def test_hosted_attestation_is_explicitly_availability_gated(self):
        workflow = (
            Path(__file__).resolve().parents[1]
            / ".github"
            / "workflows"
            / "attest-release.yml"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "HOSTED_ATTESTATION_UNAVAILABLE_PRIVATE_REPOSITORY", workflow
        )
        self.assertIn("if: ${{ github.event.repository.private }}", workflow)
        self.assertIn("if: ${{ ! github.event.repository.private }}", workflow)

    def test_statement_binds_artifact_source_builder_and_receipts(self):
        statement = self._statement()

        self.assertEqual(statement["_type"], "https://in-toto.io/Statement/v1")
        self.assertEqual(
            statement["predicateType"], "https://slsa.dev/provenance/v1"
        )
        self.assertEqual(
            statement["subject"],
            [{"digest": {"sha256": "a" * 64}, "name": "repo-curator.tar.gz"}],
        )
        dependencies = statement["predicate"]["buildDefinition"][
            "resolvedDependencies"
        ]
        self.assertEqual(
            dependencies,
            [
                {
                    "digest": {"gitCommit": "1" * 40},
                    "uri": "git+https://github.com/Dean-999/repo-curator@"
                    + "1" * 40,
                },
                {
                    "digest": {"sha256": "b" * 64},
                    "uri": "repo-curator:bundle-manifest",
                },
                {
                    "digest": {"sha256": "c" * 64},
                    "uri": "repo-curator:release-check",
                },
            ],
        )
        summary = verify_release_provenance(
            statement,
            expected_artifact_name="repo-curator.tar.gz",
            expected_artifact_sha256="a" * 64,
            expected_builder_id="https://github.com/Dean-999/repo-curator/actions/workflows/attest-release.yml",
            expected_source_commit="1" * 40,
            expected_source_tree="2" * 40,
        )
        self.assertTrue(summary["verified"])

    def test_tampering_or_unknown_predicate_fails_closed(self):
        statement = self._statement()
        tampered = copy.deepcopy(statement)
        tampered["subject"][0]["digest"]["sha256"] = "f" * 64
        with self.assertRaisesRegex(ReleaseProvenanceError, "artifact"):
            verify_release_provenance(
                tampered,
                "repo-curator.tar.gz",
                "a" * 64,
                "https://github.com/Dean-999/repo-curator/actions/workflows/attest-release.yml",
                "1" * 40,
                "2" * 40,
            )

        future = copy.deepcopy(statement)
        future["predicateType"] = "https://slsa.dev/provenance/v2"
        with self.assertRaisesRegex(ReleaseProvenanceError, "predicate"):
            verify_release_provenance(
                future,
                "repo-curator.tar.gz",
                "a" * 64,
                "https://github.com/Dean-999/repo-curator/actions/workflows/attest-release.yml",
                "1" * 40,
                "2" * 40,
            )

        extra_dependency = copy.deepcopy(statement)
        extra_dependency["predicate"]["buildDefinition"]["resolvedDependencies"].append(
            {"digest": {"sha256": "d" * 64}, "uri": "unexpected:input"}
        )
        with self.assertRaisesRegex(ReleaseProvenanceError, "dependencies"):
            verify_release_provenance(
                extra_dependency,
                "repo-curator.tar.gz",
                "a" * 64,
                "https://github.com/Dean-999/repo-curator/actions/workflows/attest-release.yml",
                "1" * 40,
                "2" * 40,
            )

    def test_tools_build_create_once_and_verify_offline(self):
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            artifact = directory / "repo-curator.tar.gz"
            manifest = directory / "bundle-manifest.json"
            release_check = directory / "release-check.json"
            statement = directory / "provenance.json"
            artifact.write_bytes(b"release bytes")
            manifest.write_text(
                json.dumps(
                    {
                        "schema_version": "repo-curator.skill-bundle.v4",
                        "source_git": {
                            "head_commit": "1" * 40,
                            "head_tree": "2" * 40,
                        },
                    }
                ),
                encoding="utf-8",
            )
            release_check.write_text(
                json.dumps(
                    {
                        "schema_version": "repo-curator.release-check.v2",
                        "status": "PASSED",
                    }
                ),
                encoding="utf-8",
            )
            build = [
                sys.executable,
                str(root / "tools" / "build_release_provenance.py"),
                "--artifact",
                str(artifact),
                "--bundle-manifest",
                str(manifest),
                "--release-check",
                str(release_check),
                "--builder-id",
                "https://github.com/Dean-999/repo-curator/actions/workflows/attest-release.yml",
                "--invocation-id",
                "https://github.com/Dean-999/repo-curator/actions/runs/1",
                "--output",
                str(statement),
            ]
            subprocess.run(build, cwd=root, check=True)
            repeated = subprocess.run(build, cwd=root, capture_output=True, text=True)
            self.assertNotEqual(repeated.returncode, 0)

            subprocess.run(
                [
                    sys.executable,
                    str(root / "tools" / "verify_release_provenance.py"),
                    "--statement",
                    str(statement),
                    "--artifact",
                    str(artifact),
                    "--builder-id",
                    "https://github.com/Dean-999/repo-curator/actions/workflows/attest-release.yml",
                    "--source-commit",
                    "1" * 40,
                    "--source-tree",
                    "2" * 40,
                ],
                cwd=root,
                check=True,
            )
            artifact.write_bytes(b"tampered")
            rejected = subprocess.run(
                [
                    sys.executable,
                    str(root / "tools" / "verify_release_provenance.py"),
                    "--statement",
                    str(statement),
                    "--artifact",
                    str(artifact),
                    "--builder-id",
                    "https://github.com/Dean-999/repo-curator/actions/workflows/attest-release.yml",
                    "--source-commit",
                    "1" * 40,
                    "--source-tree",
                    "2" * 40,
                ],
                cwd=root,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(rejected.returncode, 0)

    @staticmethod
    def _statement():
        return build_release_provenance(
            artifact_name="repo-curator.tar.gz",
            artifact_sha256="a" * 64,
            builder_id="https://github.com/Dean-999/repo-curator/actions/workflows/attest-release.yml",
            invocation_id="https://github.com/Dean-999/repo-curator/actions/runs/1",
            source_commit="1" * 40,
            source_tree="2" * 40,
            bundle_manifest_sha256="b" * 64,
            release_check_sha256="c" * 64,
        )
