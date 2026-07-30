import copy
import json
import unittest
from pathlib import Path

from repo_curator.hardening import (
    REQUIRED_ADVERSARIAL_CASES,
    load_adversarial_matrix,
)
from repo_curator.workflow_run_crate import observe_workflow_run_crate


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class MetamorphicScenarioTest(unittest.TestCase):
    def test_every_adapter_declares_the_complete_adversarial_contract(self):
        matrix = load_adversarial_matrix(
            REPOSITORY_ROOT / "tests" / "fixtures" / "adapter-adversarial-matrix.json"
        )

        self.assertEqual(
            set(matrix),
            {
                "data-package",
                "environment-declaration",
                "notebook-envelope",
                "research-metadata",
                "ro-crate-graph",
                "supplied-export",
                "workflow-run-ro-crate",
            },
        )
        for adapter, cases in matrix.items():
            self.assertEqual(set(cases), set(REQUIRED_ADVERSARIAL_CASES), adapter)
            self.assertTrue(all(cases[name] for name in REQUIRED_ADVERSARIAL_CASES))

    def test_matrix_references_resolvable_regression_tests(self):
        matrix = load_adversarial_matrix(
            REPOSITORY_ROOT / "tests" / "fixtures" / "adapter-adversarial-matrix.json"
        )
        loader = unittest.TestLoader()

        for adapter, cases in matrix.items():
            for case_name, reference in cases.items():
                suite = loader.loadTestsFromName(reference)
                failures = [
                    test
                    for test in suite
                    if test.__class__.__name__ == "_FailedTest"
                ]
                self.assertEqual(failures, [], (adapter, case_name, reference))
                self.assertEqual(suite.countTestCases(), 1, reference)

    def test_json_key_order_does_not_change_workflow_run_observation(self):
        crate = self._crate()
        reordered = json.loads(
            json.dumps(crate, sort_keys=True, separators=(",", ":"))
        )

        self.assertEqual(
            observe_workflow_run_crate(crate),
            observe_workflow_run_crate(reordered),
        )

    def test_removing_evidence_weakens_reference_coverage_without_adding_authority(self):
        complete = self._crate()
        missing_output = copy.deepcopy(complete)
        missing_output["@graph"] = [
            entity for entity in missing_output["@graph"] if entity.get("@id") != "result.csv"
        ]

        complete_observation, complete_limitations = observe_workflow_run_crate(complete)
        missing_observation, missing_limitations = observe_workflow_run_crate(missing_output)

        self.assertEqual(complete_observation["action_count_in_scope"], 1)
        self.assertEqual(missing_observation["action_count_in_scope"], 1)
        self.assertEqual(
            missing_observation["actions"][0]["unresolved_output_ids"],
            ["result.csv"],
        )
        self.assertNotIn("RO_CRATE_REFERENCE_UNRESOLVED", complete_limitations)
        self.assertIn("RO_CRATE_REFERENCE_UNRESOLVED", missing_limitations)

    @staticmethod
    def _crate():
        return {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "about": {"@id": "./"},
                },
                {"@id": "./", "@type": "Dataset"},
                {
                    "@id": "#run",
                    "@type": "CreateAction",
                    "actionStatus": "CompletedActionStatus",
                    "object": {"@id": "input.csv"},
                    "result": {"@id": "result.csv"},
                },
                {"@id": "input.csv", "@type": "File"},
                {"@id": "result.csv", "@type": "File"},
            ],
        }
