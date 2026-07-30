import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class ReleaseCheckTest(unittest.TestCase):
    def test_release_checklist_requires_one_exact_checked_line(self):
        from tools.check_release import _verify_release_checklist

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            checklist = root / "docs" / "release-checklist.md"
            checklist.parent.mkdir()
            source = (REPOSITORY_ROOT / "docs" / "release-checklist.md").read_text(
                encoding="utf-8"
            )
            checklist.write_text(
                source.replace(
                    "- [x] Current Skill release mode: READ_ONLY",
                    "- [ ] Current Skill release mode: READ_ONLY",
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "checklist is incomplete"):
                _verify_release_checklist(root)

    def test_release_check_builds_and_smoke_tests_a_portable_bundle(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            output = temporary_path / "release-check.json"
            upstream_review = temporary_path / "upstream-review.json"
            self._write_upstream_review(upstream_review)
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPOSITORY_ROOT / "tools" / "check_release.py"),
                    "--output",
                    str(output),
                    "--upstream-review",
                    str(upstream_review),
                    "--release-at",
                    "2026-07-28T21:00:00Z",
                ],
                cwd=temporary_directory,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(report["schema_version"], "repo-curator.release-check.v2")
            self.assertEqual(report["status"], "PASSED")
            self.assertTrue(report["bundle_manifest_sha256"])
            self.assertEqual(
                report["bundle_schema_version"], "repo-curator.skill-bundle.v4"
            )
            self.assertRegex(
                report["bundle_source_git"]["distributed_inputs_sha256"],
                r"^[0-9a-f]{64}$",
            )
            self.assertTrue(report["data_package_observer_verified"])
            self.assertTrue(report["adapter_adversarial_matrix_verified"])
            self.assertTrue(report["audit_output_hashes_verified"])
            self.assertTrue(report["calibration_contract_verified"])
            self.assertTrue(report["corpus_card_contract_verified"])
            self.assertTrue(report["environment_declaration_verified"])
            self.assertTrue(report["git_history_secret_scan_verified"])
            self.assertTrue(report["notebook_profile_verified"])
            self.assertTrue(report["repository_hygiene_verified"])
            self.assertTrue(report["release_checklist_markers_verified"])
            self.assertTrue(report["release_provenance_tooling_verified"])
            self.assertEqual(
                report["upstream_review"]["status"], "COMPLETED"
            )
            self.assertEqual(len(report["upstream_review"]["receipt_sha256"]), 64)
            self.assertTrue(report["ro_crate_export_verified"])
            self.assertTrue(report["ro_crate_validation_verified"])
            self.assertTrue(report["secret_redaction_verified"])
            self.assertTrue(report["target_execution_prevented"])
            self.assertEqual(report["human_admission_status"], "NOT_ADMITTED")
            self.assertEqual(report["mutation_workflow_status"], "NOT_EXPOSED")

    def test_release_gate_rejects_missing_hardening_artifact(self):
        from tools.check_release import _verify_hardening_artifacts

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaisesRegex(ValueError, "hardening artifact"):
                _verify_hardening_artifacts(root)

    def test_release_check_never_overwrites_a_report(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_path = Path(temporary_directory)
            output = temporary_path / "release-check.json"
            upstream_review = temporary_path / "upstream-review.json"
            self._write_upstream_review(upstream_review)
            output.write_text("preserve", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPOSITORY_ROOT / "tools" / "check_release.py"),
                    "--output",
                    str(output),
                    "--upstream-review",
                    str(upstream_review),
                    "--release-at",
                    "2026-07-28T21:00:00Z",
                ],
                cwd=temporary_directory,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 2)
            self.assertEqual(output.read_text(encoding="utf-8"), "preserve")

    def test_release_check_rejects_stale_or_wrong_lock_upstream_review(self):
        from tools.check_release import _verify_upstream_review

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "upstream-review.json"
            self._write_upstream_review(
                path,
                checked_at="2026-01-01T00:00:00Z",
                source_lock_sha256="f" * 64,
            )

            with self.assertRaisesRegex(ValueError, "upstream review"):
                _verify_upstream_review(
                    REPOSITORY_ROOT,
                    path,
                    "2026-07-28T21:00:00Z",
                )

    def test_release_check_rejects_upstream_review_below_source_coverage_floor(self):
        from tools.check_release import _verify_upstream_review

        with tempfile.TemporaryDirectory() as temporary_directory:
            path = Path(temporary_directory) / "upstream-review.json"
            self._write_upstream_review(path)
            review = json.loads(path.read_text(encoding="utf-8"))
            unavailable_count = len(review["entries"]) // 5 + 1
            for entry in review["entries"][:unavailable_count]:
                entry.update(
                    {
                        "adoption_effect": "NO_CHANGE_REVIEW_REQUIRED",
                        "license_status": "UNAVAILABLE",
                        "limitations": ["UPSTREAM_METADATA_UNAVAILABLE"],
                        "observed_default_branch": None,
                        "observed_head_commit": None,
                        "observed_license_spdx": None,
                        "review_required": False,
                        "source_status": "UNAVAILABLE",
                    }
                )
            review["status"] = "COMPLETED_WITH_LIMITATIONS"
            review["summary"] = {
                "entry_count": len(review["entries"]),
                "license_review_count": 0,
                "limitation_count": unavailable_count,
                "review_required_count": 0,
                "source_drift_count": 0,
            }
            path.write_text(json.dumps(review), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "source coverage"):
                _verify_upstream_review(
                    REPOSITORY_ROOT,
                    path,
                    "2026-07-28T21:00:00Z",
                )

    def test_release_check_rejects_an_empty_source_lock_without_dividing_by_zero(self):
        from tools.check_release import _verify_upstream_review

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            lock_path = root / "third_party" / "sources.lock.yaml"
            lock_path.parent.mkdir()
            lock = {
                "entries": [],
                "review_policy": {
                    "cadence": "BEFORE_EACH_RELEASE",
                    "upstream_changes_enter_shadow_first": True,
                },
                "schema_version": "repo-curator.third-party-sources-lock.v1",
            }
            lock_bytes = json.dumps(lock).encode("utf-8")
            lock_path.write_bytes(lock_bytes)
            review_path = root / "upstream-review.json"
            review_path.write_text(
                json.dumps(
                    {
                        "checked_at": "2026-07-28T20:00:00Z",
                        "entries": [],
                        "review_policy": {
                            "adoption": "MANUAL_REVIEW_ONLY",
                            "cadence": "BEFORE_EACH_RELEASE",
                            "upstream_changes_enter_shadow_first": True,
                        },
                        "schema_version": "repo-curator.upstream-review.v1",
                        "source_lock_sha256": hashlib.sha256(lock_bytes).hexdigest(),
                        "status": "COMPLETED",
                        "summary": {
                            "entry_count": 0,
                            "license_review_count": 0,
                            "limitation_count": 0,
                            "review_required_count": 0,
                            "source_drift_count": 0,
                        },
                    }
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "source lock entries"):
                _verify_upstream_review(
                    root, review_path, "2026-07-28T21:00:00Z"
                )

    def _write_upstream_review(
        self,
        path: Path,
        checked_at: str = "2026-07-28T20:00:00Z",
        source_lock_sha256: str = "",
    ) -> None:
        lock_bytes = (REPOSITORY_ROOT / "third_party" / "sources.lock.yaml").read_bytes()
        lock = json.loads(lock_bytes)
        if not source_lock_sha256:
            source_lock_sha256 = hashlib.sha256(lock_bytes).hexdigest()
        entries = []
        for entry in lock["entries"]:
            locked_license = entry["license"]["spdx"]
            entries.append(
                {
                    "adoption_effect": "NO_CHANGE",
                    "distributed_code": entry["distributed_code"],
                    "integration_mode": entry["integration_mode"],
                    "license_status": (
                        "NOT_COMPARABLE"
                        if locked_license == "NOASSERTION"
                        else "MATCH"
                    ),
                    "limitations": [],
                    "locked_commit": entry["commit"],
                    "locked_license_spdx": locked_license,
                    "observed_default_branch": "main",
                    "observed_head_commit": entry["commit"],
                    "observed_license_spdx": locked_license,
                    "repository": entry["repository"],
                    "review_required": False,
                    "source_id": entry["id"],
                    "source_status": "LOCKED_COMMIT_IS_DEFAULT_HEAD",
                }
            )
        path.write_text(
            json.dumps(
                {
                    "checked_at": checked_at,
                    "entries": entries,
                    "review_policy": {
                        "adoption": "MANUAL_REVIEW_ONLY",
                        "cadence": lock["review_policy"]["cadence"],
                        "upstream_changes_enter_shadow_first": True,
                    },
                    "schema_version": "repo-curator.upstream-review.v1",
                    "source_lock_sha256": source_lock_sha256,
                    "status": "COMPLETED",
                    "summary": {
                        "entry_count": len(entries),
                        "license_review_count": 0,
                        "limitation_count": 0,
                        "review_required_count": 0,
                        "source_drift_count": 0,
                    },
                }
            ),
            encoding="utf-8",
        )
