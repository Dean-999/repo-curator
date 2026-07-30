import unittest

from repo_curator.calibration import build_calibration_report


class CalibrationScenarioTest(unittest.TestCase):
    def test_report_exposes_hand_calculated_risk_coverage_points(self):
        cases = [
            self._case("supported-high", "ASSERTED", "HIGH", ["SUPPORTED", "SUPPORTED"]),
            self._case("unsupported-medium", "ASSERTED", "MEDIUM", ["UNSUPPORTED", "UNSUPPORTED"]),
            self._case("supported-low", "ABSTAINED", "LOW", ["SUPPORTED", "SUPPORTED"]),
        ]

        report = build_calibration_report(
            cases, [], None, "2026-07-29T00:00:00Z"
        )

        self.assertEqual(
            report["schema_version"], "repo-curator.calibration-report.v1"
        )
        self.assertEqual(report["status"], "NOT_CALIBRATED")
        self.assertFalse(report["admission_authority"])
        self.assertEqual(len(report["slices"]), 1)
        points = report["slices"][0]["risk_coverage_points"]
        self.assertEqual(
            points,
            [
                {
                    "accepted_count": 1,
                    "coverage": 0.333333333333,
                    "selective_risk": 0.0,
                    "threshold": "HIGH",
                },
                {
                    "accepted_count": 2,
                    "coverage": 0.666666666667,
                    "selective_risk": 0.5,
                    "threshold": "MEDIUM",
                },
                {
                    "accepted_count": 2,
                    "coverage": 0.666666666667,
                    "selective_risk": 0.5,
                    "threshold": "LOW",
                },
            ],
        )

    def test_disagreement_remains_outside_selective_risk_denominator(self):
        cases = [
            self._case("disagreed", "ASSERTED", "HIGH", ["SUPPORTED", "UNSUPPORTED"]),
            self._case("supported", "ASSERTED", "HIGH", ["SUPPORTED", "SUPPORTED"]),
        ]

        report = build_calibration_report(
            cases, [], None, "2026-07-29T00:00:00Z"
        )

        slice_report = report["slices"][0]
        self.assertEqual(slice_report["candidate_count"], 2)
        self.assertEqual(slice_report["consensus_count"], 1)
        self.assertEqual(slice_report["disagreement_count"], 1)
        self.assertEqual(
            slice_report["risk_coverage_points"][0]["accepted_count"], 1
        )

    @staticmethod
    def _case(case_id, prediction, confidence, labels):
        return {
            "case_id": case_id,
            "claim_type": "capability_family",
            "confidence": confidence,
            "language": "Python",
            "prediction": prediction,
            "repository_type": "computational-research",
            "review_labels": [
                {"label": label, "reviewer_id": "reviewer-{}".format(index)}
                for index, label in enumerate(labels)
            ],
            "schema_version": "repo-curator.gold-case.v1",
        }
