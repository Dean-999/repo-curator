import json
import re
import unittest
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class RepresentativeAuditSlicesTest(unittest.TestCase):
    def test_minimized_slices_bind_sources_and_preserve_conservative_limits(self):
        fixture = json.loads(
            (
                REPOSITORY_ROOT
                / "tests"
                / "fixtures"
                / "representative-audit-slices.json"
            ).read_text(encoding="utf-8")
        )

        self.assertEqual(
            fixture["schema_version"],
            "repo-curator.representative-audit-slices.v1",
        )
        cases = fixture["cases"]
        self.assertEqual(len(cases), 3)
        self.assertEqual(
            {case["repository_family"] for case in cases},
            {
                "bioinformatics-workflow",
                "climate-process-modeling",
                "neuroimaging-pipeline",
            },
        )
        for case in cases:
            self.assertRegex(case["source_commit"], r"^[0-9a-f]{40}$")
            self.assertIn(case["license"], {"Apache-2.0", "MIT"})
            self.assertEqual(
                case["positive_observation"]["relationship_type"],
                "EXACT_BYTE_DUPLICATE",
            )
            self.assertEqual(
                case["limitation"],
                "EQUAL_BYTES_DO_NOT_ESTABLISH_COMMON_LINEAGE_OR_PURPOSE",
            )
            outcome = case["conservative_outcome"]
            self.assertEqual(outcome["recommendation_type"], "MANUAL_REVIEW")
            self.assertEqual(outcome["evidence_coverage"], "INSUFFICIENT")
            self.assertFalse(outcome["executable_in_supported_scope"])
            self.assertTrue(outcome["shadow_mode"])
            for digest in case["source_members"].values():
                self.assertTrue(
                    re.fullmatch(r"sha256:[0-9a-f]{64}", digest)
                )


if __name__ == "__main__":
    unittest.main()
