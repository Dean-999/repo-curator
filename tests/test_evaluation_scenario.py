import hashlib
import json
import unittest

from repo_curator.evaluation import AdmissionError, evaluate_admission


class EvaluationScenarioTest(unittest.TestCase):
    def test_metrics_are_sliced_and_reviewer_disagreement_remains_visible(self):
        cases = [
            self._case("cap-true", "ASSERTED", "HIGH", ["SUPPORTED", "SUPPORTED"]),
            self._case("cap-false", "ASSERTED", "HIGH", ["UNSUPPORTED", "UNSUPPORTED"]),
            self._case("cap-missed", "ABSTAINED", None, ["SUPPORTED", "SUPPORTED"]),
            self._case("cap-disagreement", "ASSERTED", "HIGH", ["SUPPORTED", "UNSUPPORTED"]),
            self._case("cap-unreviewed", "UNRESOLVED", None, []),
        ]

        report = evaluate_admission(cases, [], "2026-07-25T00:00:00Z")

        slice_report = report["metrics"][0]
        self.assertEqual(slice_report["claim_type"], "capability_family")
        self.assertEqual(slice_report["language"], "Python")
        self.assertEqual(slice_report["repository_type"], "computational-research")
        self.assertEqual(slice_report["candidate_count"], 5)
        self.assertEqual(slice_report["consensus_count"], 3)
        self.assertEqual(slice_report["disagreement_count"], 1)
        self.assertEqual(slice_report["unreviewed_count"], 1)
        self.assertEqual(slice_report["precision"], 0.5)
        self.assertEqual(slice_report["recall"], 0.5)
        self.assertEqual(slice_report["coverage"], 0.6)
        self.assertEqual(slice_report["abstention_rate"], 0.2)
        self.assertEqual(slice_report["unresolved_rate"], 0.2)
        self.assertEqual(report["verdict"], "SHADOW_ONLY")

    def test_mutation_admission_stays_shadow_only_below_the_risk_corpus_threshold(self):
        cases = [
            self._case("inventory", "ASSERTED", "DETERMINISTIC", ["SUPPORTED", "SUPPORTED"], "inventory_artifact"),
            self._case("duplicate", "ASSERTED", "DETERMINISTIC", ["SUPPORTED", "SUPPORTED"], "exact_byte_duplicate"),
            self._case("family", "ASSERTED", "HIGH", ["SUPPORTED", "SUPPORTED"]),
            self._case("episode", "ASSERTED", "STRONG", ["SUPPORTED", "SUPPORTED"], "change_episode"),
        ]
        risk_cases = [
            {
                "candidate_id": "risk-{:04d}".format(index),
                "invariants_passed": True,
                "operation_class": "ARCHIVE",
                "unsafe_false_positive": False,
            }
            for index in range(2_999)
        ]

        report = evaluate_admission(cases, risk_cases, "2026-07-25T00:00:00Z")

        archive_gate = next(gate for gate in report["gates"] if gate["gate_id"] == "mutation-risk-corpus:ARCHIVE")
        self.assertEqual(archive_gate["status"], "BLOCKED")
        self.assertEqual(archive_gate["observed"]["reason"], "INSUFFICIENT_REPOSITORY_DIVERSITY")
        self.assertEqual(report["verdict"], "SHADOW_ONLY")

    def test_mutation_admission_requires_zero_unsafe_false_positives_and_passing_invariants(self):
        cases = [
            self._case("inventory", "ASSERTED", "DETERMINISTIC", ["SUPPORTED", "SUPPORTED"], "inventory_artifact"),
            self._case("duplicate", "ASSERTED", "DETERMINISTIC", ["SUPPORTED", "SUPPORTED"], "exact_byte_duplicate"),
            self._case("family", "ASSERTED", "HIGH", ["SUPPORTED", "SUPPORTED"]),
            self._case("episode", "ASSERTED", "STRONG", ["SUPPORTED", "SUPPORTED"], "change_episode"),
        ]
        risk_cases = [
            {
                "candidate_id": "risk-{:04d}".format(index),
                "invariants_passed": True,
                "operation_class": "QUARANTINE",
                "unsafe_false_positive": index == 2_999,
            }
            for index in range(3_000)
        ]

        report = evaluate_admission(cases, risk_cases, "2026-07-25T00:00:00Z")

        quarantine_gate = next(gate for gate in report["gates"] if gate["gate_id"] == "mutation-risk-corpus:QUARANTINE")
        self.assertEqual(quarantine_gate["status"], "BLOCKED")
        self.assertEqual(quarantine_gate["observed"]["reason"], "INSUFFICIENT_REPOSITORY_DIVERSITY")
        self.assertEqual(report["verdict"], "SHADOW_ONLY")

    def test_missing_supported_mutation_operation_class_remains_shadow_only(self):
        cases = [
            self._case("inventory", "ASSERTED", "DETERMINISTIC", ["SUPPORTED", "SUPPORTED"], "inventory_artifact"),
            self._case("duplicate", "ASSERTED", "DETERMINISTIC", ["SUPPORTED", "SUPPORTED"], "exact_byte_duplicate"),
            self._case("family", "ASSERTED", "HIGH", ["SUPPORTED", "SUPPORTED"]),
            self._case("episode", "ASSERTED", "STRONG", ["SUPPORTED", "SUPPORTED"], "change_episode"),
        ]
        archive_risk_cases = [
            {
                "candidate_id": "risk-{:04d}".format(index),
                "invariants_passed": True,
                "operation_class": "ARCHIVE",
                "unsafe_false_positive": False,
            }
            for index in range(3_000)
        ]

        report = evaluate_admission(cases, archive_risk_cases, "2026-07-25T00:00:00Z")

        quarantine_gate = next(gate for gate in report["gates"] if gate["gate_id"] == "mutation-risk-corpus:QUARANTINE")
        self.assertEqual(quarantine_gate["status"], "BLOCKED")
        self.assertEqual(report["verdict"], "SHADOW_ONLY")

    def test_small_semantic_samples_never_enable_admission(self):
        cases = [
            self._case("inventory", "ASSERTED", "DETERMINISTIC", ["SUPPORTED", "SUPPORTED"], "inventory_artifact"),
            self._case("duplicate", "ASSERTED", "DETERMINISTIC", ["SUPPORTED", "SUPPORTED"], "exact_byte_duplicate"),
            self._case("family", "ASSERTED", "HIGH", ["SUPPORTED", "SUPPORTED"]),
            self._case("episode", "ASSERTED", "STRONG", ["SUPPORTED", "SUPPORTED"], "change_episode"),
        ]
        risk_cases = [
            {
                "candidate_id": "{}-risk-{:04d}".format(operation_class, index),
                "invariants_passed": True,
                "operation_class": operation_class,
                "unsafe_false_positive": False,
            }
            for operation_class in ("ARCHIVE", "QUARANTINE")
            for index in range(3_000)
        ]

        report = evaluate_admission(cases, risk_cases, "2026-07-25T00:00:00Z")

        self.assertTrue(any(gate["status"] == "BLOCKED" for gate in report["gates"]))
        self.assertEqual(report["verdict"], "SHADOW_ONLY")

    def test_admission_requires_manifest_bound_provenance_and_repository_diversity(self):
        case = self._case("manifest-case", "ASSERTED", "HIGH", ["SUPPORTED", "SUPPORTED"])
        case.update({
            "evaluator_version": "repo-curator-evaluator/1",
            "expected_label_artifact_hash": "sha256:" + "1" * 64,
            "prediction_artifact_hash": "sha256:" + "2" * 64,
            "repository_family": "python-ml",
            "repository_id": "repo-1",
            "repository_snapshot_hash": "sha256:" + "3" * 64,
            "run_id": "run-1",
            "schema_version": "repo-curator.gold-case.v2",
        })
        for index, label in enumerate(case["review_labels"]):
            label["label_artifact_hash"] = "sha256:" + str(index + 4) * 64

        with self.assertRaisesRegex(AdmissionError, "EVALUATION_MANIFEST_REQUIRED"):
            evaluate_admission([case], [], "2026-07-25T00:00:00Z")

        manifest = self._manifest([case], [])
        report = evaluate_admission([case], [], "2026-07-25T00:00:00Z", manifest)
        gate = next(item for item in report["gates"] if item["gate_id"] == "capability-family-high-precision")
        self.assertEqual(gate["status"], "BLOCKED")
        self.assertEqual(gate["observed"]["reason"], "INSUFFICIENT_REPOSITORY_DIVERSITY")

    def test_manifest_hashes_bind_exact_case_and_risk_records(self):
        case = self._case("bound-case", "ASSERTED", "HIGH", ["SUPPORTED", "SUPPORTED"])
        case.update({
            "evaluator_version": "repo-curator-evaluator/1",
            "expected_label_artifact_hash": "sha256:" + "1" * 64,
            "prediction_artifact_hash": "sha256:" + "2" * 64,
            "repository_family": "python-ml",
            "repository_id": "repo-1",
            "repository_snapshot_hash": "sha256:" + "3" * 64,
            "run_id": "run-1",
            "schema_version": "repo-curator.gold-case.v2",
        })
        for index, label in enumerate(case["review_labels"]):
            label["label_artifact_hash"] = "sha256:" + str(index + 4) * 64
        manifest = self._manifest([case], [])
        case["prediction"] = "ABSTAINED"

        with self.assertRaisesRegex(AdmissionError, "EVALUATION_MANIFEST_HASH_MISMATCH"):
            evaluate_admission([case], [], "2026-07-25T00:00:00Z", manifest)

    def test_risk_corpus_cannot_gain_independence_by_copying_one_repository(self):
        risk_cases = [self._risk_case(index, "repo-1", "python-ml") for index in range(3_000)]
        manifest = self._manifest([], risk_cases)

        report = evaluate_admission([], risk_cases, "2026-07-25T00:00:00Z", manifest)

        gate = next(item for item in report["gates"] if item["gate_id"] == "mutation-risk-corpus:ARCHIVE")
        self.assertEqual(gate["status"], "BLOCKED")
        self.assertEqual(gate["observed"]["reason"], "INSUFFICIENT_REPOSITORY_DIVERSITY")

    def test_v2_risk_case_requires_fault_injection_and_evidence_artifacts(self):
        risk_case = self._risk_case(1, "repo-1", "python-ml")
        risk_case["evidence_artifact_hashes"] = []
        manifest = self._manifest([], [risk_case])

        with self.assertRaisesRegex(AdmissionError, "EVALUATION_RISK_CASE_MALFORMED"):
            evaluate_admission([], [risk_case], "2026-07-25T00:00:00Z", manifest)

    def test_diverse_manifest_bound_corpus_can_pass_all_gates(self):
        cases = []
        for claim_type, confidence, count in (
            ("inventory_artifact", "DETERMINISTIC", 1_000),
            ("exact_byte_duplicate", "DETERMINISTIC", 1_000),
            ("capability_family", "HIGH", 100),
            ("change_episode", "STRONG", 100),
        ):
            for index in range(count):
                cases.append(self._v2_case("{}-{:04d}".format(claim_type, index), claim_type, confidence, index))
        for claim_type, count in (
            ("inventory_artifact", 100), ("exact_byte_duplicate", 100),
            ("capability_family", 50), ("change_episode", 50),
        ):
            for index in range(count):
                cases.append(self._v2_case(
                    "{}-negative-{:04d}".format(claim_type, index), claim_type, None, index,
                    prediction="ABSTAINED", labels=["UNSUPPORTED", "UNSUPPORTED"],
                ))
        risk_cases = [
            self._risk_case(index, "repo-{}".format(index % 5), "family-{}".format((index % 5) % 3), operation)
            for operation in ("ARCHIVE", "QUARANTINE") for index in range(3_000)
        ]
        manifest = self._manifest(cases, risk_cases)

        report = evaluate_admission(cases, risk_cases, "2026-07-25T00:00:00Z", manifest)

        self.assertEqual(report["verdict"], "ADMISSION_READY")
        self.assertTrue(all(gate["status"] == "PASSED" for gate in report["gates"]))
        self.assertTrue(all("label_coverage" in gate["observed"] for gate in report["gates"] if not gate["gate_id"].startswith("mutation-risk")))

    def test_inventory_and_duplicate_gates_use_the_protocol_reviewed_case_minimum(self):
        cases = []
        gate_ids = {
            "inventory_artifact": "inventory-recall",
            "exact_byte_duplicate": "exact-byte-duplicate-precision",
        }
        for claim_type in gate_ids:
            cases.extend(
                self._v2_case("{}-supported-{:04d}".format(claim_type, index), claim_type, "DETERMINISTIC", index)
                for index in range(900)
            )
            cases.extend(
                self._v2_case(
                    "{}-unsupported-{:04d}".format(claim_type, index), claim_type, None, index,
                    prediction="ABSTAINED", labels=["UNSUPPORTED", "UNSUPPORTED"],
                )
                for index in range(100)
            )

        manifest = self._manifest(cases, [])
        report = evaluate_admission(cases, [], "2026-07-25T00:00:00Z", manifest)

        for gate_id in gate_ids.values():
            gate = next(item for item in report["gates"] if item["gate_id"] == gate_id)
            self.assertEqual(gate["status"], "PASSED")
            self.assertEqual(gate["observed"]["reviewed_case_count"], 1_000)

    def test_capability_and_change_gates_apply_wilson_after_the_protocol_sample_minimum(self):
        cases = []
        gate_ids = {
            "capability_family": ("HIGH", "capability-family-high-precision"),
            "change_episode": ("STRONG", "change-episode-strong-precision"),
        }
        for claim_type, (confidence, _) in gate_ids.items():
            cases.extend(
                self._v2_case("{}-supported-{:04d}".format(claim_type, index), claim_type, confidence, index)
                for index in range(50)
            )
            cases.extend(
                self._v2_case(
                    "{}-unsupported-{:04d}".format(claim_type, index), claim_type, confidence, index,
                    prediction="ASSERTED", labels=["UNSUPPORTED", "UNSUPPORTED"],
                )
                for index in range(50)
            )

        manifest = self._manifest(cases, [])
        report = evaluate_admission(cases, [], "2026-07-25T00:00:00Z", manifest)

        for _, gate_id in gate_ids.values():
            gate = next(item for item in report["gates"] if item["gate_id"] == gate_id)
            self.assertEqual(gate["status"], "BLOCKED")
            self.assertIn("metric", gate["observed"])
            self.assertEqual(gate["observed"]["reviewed_case_count"], 100)

    def test_rejects_non_independent_or_unknown_review_labels(self):
        duplicate_reviewer = self._case("duplicate-reviewer", "ASSERTED", "HIGH", ["SUPPORTED", "SUPPORTED"])
        duplicate_reviewer["review_labels"][1]["reviewer_id"] = "reviewer-1"
        with self.assertRaisesRegex(AdmissionError, "EVALUATION_REVIEWER_INDEPENDENCE"):
            evaluate_admission([duplicate_reviewer], [], "2026-07-25T00:00:00Z")

        invalid_label = self._case("invalid-label", "ASSERTED", "HIGH", ["SUPPORTED", "MAYBE"])
        with self.assertRaisesRegex(AdmissionError, "EVALUATION_LABEL_MALFORMED"):
            evaluate_admission([invalid_label], [], "2026-07-25T00:00:00Z")

        repeated_case = self._case("repeated", "ASSERTED", "HIGH", ["SUPPORTED", "SUPPORTED"])
        with self.assertRaisesRegex(AdmissionError, "EVALUATION_CASE_DUPLICATE"):
            evaluate_admission([repeated_case, repeated_case], [], "2026-07-25T00:00:00Z")

    def _case(self, case_id, prediction, confidence, labels, claim_type="capability_family"):
        return {
            "case_id": case_id,
            "claim_type": claim_type,
            "confidence": confidence,
            "language": "Python",
            "prediction": prediction,
            "repository_type": "computational-research",
            "review_labels": [
                {
                    "label": label,
                    "reviewer_id": "reviewer-{}".format(index + 1),
                }
                for index, label in enumerate(labels)
            ],
            "schema_version": "repo-curator.gold-case.v1",
        }

    def _manifest(self, cases, risk_cases):
        canonical = lambda value: json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return {
            "case_records_sha256": "sha256:" + hashlib.sha256(canonical(cases)).hexdigest(),
            "corpus_id": "corpus-1",
            "evaluator_version": "repo-curator-evaluator/1",
            "risk_records_sha256": "sha256:" + hashlib.sha256(canonical(risk_cases)).hexdigest(),
            "reviewer_registry": {
                label["reviewer_id"]: "sha256:" + hashlib.sha256(label["reviewer_id"].encode()).hexdigest()
                for case in cases for label in case["review_labels"]
            },
            "schema_version": "repo-curator.evaluation-corpus-manifest.v1",
        }

    def _risk_case(self, index, repository_id, repository_family, operation="ARCHIVE"):
        return {
            "candidate_id": "{}-risk-{:04d}".format(operation.lower(), index),
            "evaluator_version": "repo-curator-evaluator/1",
            "evidence_artifact_hashes": ["sha256:" + "6" * 64],
            "fault_injection_report_hash": "sha256:" + "7" * 64,
            "invariant_results": [
                {"invariant_id": "no-overwrite", "status": "PASSED"},
                {"invariant_id": "source-identity", "status": "PASSED"},
                {"invariant_id": "recovery", "status": "PASSED"},
            ],
            "operation_class": operation,
            "outcome": "SAFE",
            "repository_family": repository_family,
            "repository_id": repository_id,
            "repository_snapshot_hash": "sha256:" + str((int(repository_id.rsplit("-", 1)[-1]) % 5) + 3) * 64,
            "schema_version": "repo-curator.mutation-risk-case.v2",
            "test_run_id": "test-run-{:04d}".format(index),
        }

    def _v2_case(self, case_id, claim_type, confidence, index, prediction="ASSERTED", labels=None):
        case = self._case(case_id, prediction, confidence, labels or ["SUPPORTED", "SUPPORTED"], claim_type)
        case.update({
            "evaluator_version": "repo-curator-evaluator/1",
            "expected_label_artifact_hash": "sha256:" + "1" * 64,
            "prediction_artifact_hash": "sha256:" + "2" * 64,
            "repository_family": "family-{}".format((index % 5) % 3),
            "repository_id": "repo-{}".format(index % 5),
            "repository_snapshot_hash": "sha256:" + str((index % 5) + 3) * 64,
            "run_id": "run-{}".format(case_id),
            "schema_version": "repo-curator.gold-case.v2",
        })
        for label_index, label in enumerate(case["review_labels"]):
            label["label_artifact_hash"] = "sha256:" + str(label_index + 8) * 64
        return case


if __name__ == "__main__":
    unittest.main()
