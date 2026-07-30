import contextlib
import hashlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from repo_curator.cli import main


class EvaluationCliScenarioTest(unittest.TestCase):
    def test_manifest_and_evaluation_commands_create_bound_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases_path = root / "cases.json"
            risk_cases_path = root / "risk-cases.json"
            reviewers_path = root / "reviewers.json"
            manifest_path = root / "manifest.json"
            report_path = root / "report.json"
            cases_path.write_text(json.dumps([self._case()]), encoding="utf-8")
            risk_cases_path.write_text("[]", encoding="utf-8")
            reviewers_path.write_text(json.dumps({
                "reviewer-1": self._hash("reviewer-1 provenance"),
                "reviewer-2": self._hash("reviewer-2 provenance"),
            }), encoding="utf-8")

            self.assertEqual(main([
                "corpus-manifest",
                "--cases", str(cases_path),
                "--risk-cases", str(risk_cases_path),
                "--reviewer-registry", str(reviewers_path),
                "--corpus-id", "pilot-corpus-1",
                "--evaluator-version", "repo-curator-evaluator/1",
                "--output", str(manifest_path),
            ]), 0)

            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["schema_version"], "repo-curator.evaluation-corpus-manifest.v1")
            self.assertEqual(manifest["case_records_sha256"], self._digest([self._case()]))
            self.assertEqual(manifest["reviewer_registry"]["reviewer-1"], self._hash("reviewer-1 provenance"))

            artifact_root = root / "artifacts"
            artifact_root.mkdir()
            artifacts = {
                "expected-label.json": "expected label",
                "prediction.json": "prediction",
                "reviewer-1.json": "reviewer-1 provenance",
                "reviewer-2.json": "reviewer-2 provenance",
                "label-1.json": "label 1",
                "label-2.json": "label 2",
                "snapshot.json": "snapshot",
            }
            for relative_path, content in artifacts.items():
                (artifact_root / relative_path).write_text(content, encoding="utf-8")
            ledger_path = root / "artifact-ledger.json"
            ledger_path.write_text(json.dumps({
                "schema_version": "repo-curator.corpus-artifact-ledger.v1",
                "artifacts": [
                    {"artifact_hash": self._hash(content), "path": relative_path}
                    for relative_path, content in artifacts.items()
                ],
            }), encoding="utf-8")
            missing_verification_path = root / "missing-verification-report.json"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main([
                    "evaluate",
                    "--cases", str(cases_path),
                    "--risk-cases", str(risk_cases_path),
                    "--manifest", str(manifest_path),
                    "--created-at", "2026-07-25T00:00:00Z",
                    "--output", str(missing_verification_path),
                ])
            self.assertEqual(result, 2)
            self.assertFalse(missing_verification_path.exists())
            self.assertIn("artifact verification is required", stderr.getvalue())

            self.assertEqual(main([
                "evaluate",
                "--cases", str(cases_path),
                "--risk-cases", str(risk_cases_path),
                "--manifest", str(manifest_path),
                "--artifact-ledger", str(ledger_path),
                "--artifact-root", str(artifact_root),
                "--created-at", "2026-07-25T00:00:00Z",
                "--output", str(report_path),
            ]), 0)

            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertEqual(report["corpus_manifest_id"], "pilot-corpus-1")
            self.assertEqual(report["verdict"], "SHADOW_ONLY")
            self.assertEqual(report["conforms_to"], [
                "https://github.com/Dean-999/repo-curator/tree/main/docs/profiles/evaluation-v1"
            ])
            self.assertEqual(report["artifact_verification"]["artifact_ledger_sha256"], self._digest(json.loads(ledger_path.read_text(encoding="utf-8"))))

    def test_commands_fail_closed_for_invalid_input_and_existing_outputs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            invalid_cases_path = root / "invalid-cases.json"
            risk_cases_path = root / "risk-cases.json"
            reviewers_path = root / "reviewers.json"
            output_path = root / "manifest.json"
            invalid_cases_path.write_text("{}", encoding="utf-8")
            risk_cases_path.write_text("[]", encoding="utf-8")
            reviewers_path.write_text("{}", encoding="utf-8")
            output_path.write_text("existing evidence\n", encoding="utf-8")

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main([
                    "corpus-manifest",
                    "--cases", str(invalid_cases_path),
                    "--risk-cases", str(risk_cases_path),
                    "--reviewer-registry", str(reviewers_path),
                    "--corpus-id", "pilot-corpus-1",
                    "--evaluator-version", "repo-curator-evaluator/1",
                    "--output", str(output_path),
                ])

            self.assertEqual(result, 2)
            self.assertIn("cases must contain a JSON array", stderr.getvalue())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "existing evidence\n")

            valid_cases_path = root / "valid-cases.json"
            valid_cases_path.write_text(json.dumps([self._case()]), encoding="utf-8")
            reviewers_path.write_text(json.dumps({
                "reviewer-1": self._hash("reviewer-1 provenance"),
                "reviewer-2": self._hash("reviewer-2 provenance"),
            }), encoding="utf-8")
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main([
                    "corpus-manifest",
                    "--cases", str(valid_cases_path),
                    "--risk-cases", str(risk_cases_path),
                    "--reviewer-registry", str(reviewers_path),
                    "--corpus-id", "pilot-corpus-1",
                    "--evaluator-version", "repo-curator-evaluator/1",
                    "--output", str(output_path),
                ])

            self.assertEqual(result, 2)
            self.assertIn("output already exists", stderr.getvalue())
            self.assertEqual(output_path.read_text(encoding="utf-8"), "existing evidence\n")

    def test_manifest_command_rejects_symbolic_linked_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases_path = root / "cases.json"
            linked_cases_path = root / "linked-cases.json"
            risk_cases_path = root / "risk-cases.json"
            reviewers_path = root / "reviewers.json"
            output_path = root / "manifest.json"
            cases_path.write_text(json.dumps([self._case()]), encoding="utf-8")
            linked_cases_path.symlink_to(cases_path)
            risk_cases_path.write_text("[]", encoding="utf-8")
            reviewers_path.write_text(json.dumps({
                "reviewer-1": self._hash("reviewer-1 provenance"),
                "reviewer-2": self._hash("reviewer-2 provenance"),
            }), encoding="utf-8")

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main([
                    "corpus-manifest",
                    "--cases", str(linked_cases_path),
                    "--risk-cases", str(risk_cases_path),
                    "--reviewer-registry", str(reviewers_path),
                    "--corpus-id", "pilot-corpus-1",
                    "--evaluator-version", "repo-curator-evaluator/1",
                    "--output", str(output_path),
                ])

            self.assertEqual(result, 2)
            self.assertFalse(output_path.exists())
            self.assertIn("corpus manifest failed", stderr.getvalue())

    def test_corpus_verify_closes_every_v2_artifact_reference_before_writing_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases_path = root / "cases.json"
            risk_cases_path = root / "risk-cases.json"
            reviewers_path = root / "reviewers.json"
            ledger_path = root / "artifact-ledger.json"
            artifact_root = root / "artifacts"
            receipt_path = root / "verification-receipt.json"
            artifact_root.mkdir()
            case = self._case()
            cases_path.write_text(json.dumps([case]), encoding="utf-8")
            risk_cases_path.write_text("[]", encoding="utf-8")
            reviewers = {
                "reviewer-1": self._hash("reviewer-1 provenance"),
                "reviewer-2": self._hash("reviewer-2 provenance"),
            }
            reviewers_path.write_text(json.dumps(reviewers), encoding="utf-8")
            artifacts = {
                "expected-label.json": "expected label",
                "prediction.json": "prediction",
                "reviewer-1.json": "reviewer-1 provenance",
                "reviewer-2.json": "reviewer-2 provenance",
                "label-1.json": "label 1",
                "label-2.json": "label 2",
                "snapshot.json": "snapshot",
            }
            for relative_path, content in artifacts.items():
                (artifact_root / relative_path).write_text(content, encoding="utf-8")
            ledger = {
                "schema_version": "repo-curator.corpus-artifact-ledger.v1",
                "artifacts": [
                    {"artifact_hash": self._hash(content), "path": relative_path}
                    for relative_path, content in artifacts.items()
                ],
            }
            ledger_path.write_text(json.dumps(ledger), encoding="utf-8")

            self.assertEqual(main([
                "corpus-verify",
                "--cases", str(cases_path),
                "--risk-cases", str(risk_cases_path),
                "--reviewer-registry", str(reviewers_path),
                "--artifact-ledger", str(ledger_path),
                "--artifact-root", str(artifact_root),
                "--output", str(receipt_path),
            ]), 0)

            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            self.assertEqual(receipt["schema_version"], "repo-curator.corpus-artifact-verification.v1")
            self.assertEqual(receipt["referenced_artifact_count"], 7)
            self.assertEqual(set(receipt["verified_artifact_hashes"]), set(reviewers.values()) | {
                case["expected_label_artifact_hash"],
                case["prediction_artifact_hash"],
                case["repository_snapshot_hash"],
                *(label["label_artifact_hash"] for label in case["review_labels"]),
            })

            (artifact_root / "expected-label.json").write_text("tampered", encoding="utf-8")
            second_receipt_path = root / "second-verification-receipt.json"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main([
                    "corpus-verify",
                    "--cases", str(cases_path),
                    "--risk-cases", str(risk_cases_path),
                    "--reviewer-registry", str(reviewers_path),
                    "--artifact-ledger", str(ledger_path),
                    "--artifact-root", str(artifact_root),
                    "--output", str(second_receipt_path),
                ])
            self.assertEqual(result, 2)
            self.assertFalse(second_receipt_path.exists())
            self.assertIn("artifact hash mismatch", stderr.getvalue())

            (artifact_root / "expected-label.json").write_text("expected label", encoding="utf-8")
            (artifact_root / "prediction.json").unlink()
            (artifact_root / "prediction.json").symlink_to("expected-label.json")
            third_receipt_path = root / "third-verification-receipt.json"
            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main([
                    "corpus-verify",
                    "--cases", str(cases_path),
                    "--risk-cases", str(risk_cases_path),
                    "--reviewer-registry", str(reviewers_path),
                    "--artifact-ledger", str(ledger_path),
                    "--artifact-root", str(artifact_root),
                    "--output", str(third_receipt_path),
                ])
            self.assertEqual(result, 2)
            self.assertFalse(third_receipt_path.exists())

    def test_corpus_verify_rejects_ledger_paths_that_escape_or_link_outside_artifact_root(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases_path = root / "cases.json"
            risk_cases_path = root / "risk-cases.json"
            reviewers_path = root / "reviewers.json"
            ledger_path = root / "artifact-ledger.json"
            artifact_root = root / "artifacts"
            receipt_path = root / "verification-receipt.json"
            artifact_root.mkdir()
            cases_path.write_text("[]", encoding="utf-8")
            risk_cases_path.write_text("[]", encoding="utf-8")
            reviewers_path.write_text("{}", encoding="utf-8")
            ledger_path.write_text(json.dumps({
                "schema_version": "repo-curator.corpus-artifact-ledger.v1",
                "artifacts": [{"artifact_hash": self._hash("outside"), "path": "../outside.json"}],
            }), encoding="utf-8")

            stderr = io.StringIO()
            with contextlib.redirect_stderr(stderr):
                result = main([
                    "corpus-verify",
                    "--cases", str(cases_path),
                    "--risk-cases", str(risk_cases_path),
                    "--reviewer-registry", str(reviewers_path),
                    "--artifact-ledger", str(ledger_path),
                    "--artifact-root", str(artifact_root),
                    "--output", str(receipt_path),
                ])
            self.assertEqual(result, 2)
            self.assertFalse(receipt_path.exists())
            self.assertIn("artifact ledger path is unsafe", stderr.getvalue())

    @staticmethod
    def _hash(value):
        return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()

    @classmethod
    def _digest(cls, value):
        return cls._hash(json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True))

    def _case(self):
        return {
            "case_id": "pilot-capability-1",
            "claim_type": "capability_family",
            "confidence": "HIGH",
            "evaluator_version": "repo-curator-evaluator/1",
            "expected_label_artifact_hash": self._hash("expected label"),
            "language": "Python",
            "prediction": "ASSERTED",
            "prediction_artifact_hash": self._hash("prediction"),
            "repository_family": "python-ml",
            "repository_id": "pilot-repository-1",
            "repository_snapshot_hash": self._hash("snapshot"),
            "repository_type": "computational-research",
            "review_labels": [
                {"label": "SUPPORTED", "label_artifact_hash": self._hash("label 1"), "reviewer_id": "reviewer-1"},
                {"label": "SUPPORTED", "label_artifact_hash": self._hash("label 2"), "reviewer_id": "reviewer-2"},
            ],
            "run_id": "pilot-run-1",
            "schema_version": "repo-curator.gold-case.v2",
        }


if __name__ == "__main__":
    unittest.main()
