import unittest

from repo_curator.workflow_run_crate import (
    ACTION_LIMIT,
    ACTION_REFERENCE_LIMIT,
    observe_workflow_run_crate,
)


class WorkflowRunCrateTest(unittest.TestCase):
    def test_accepts_json_ld_type_and_status_references(self):
        parsed = {
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
                    "@type": "https://schema.org/CreateAction",
                    "actionStatus": {
                        "@id": "https://schema.org/CompletedActionStatus"
                    },
                },
            ],
        }

        details, limitations = observe_workflow_run_crate(parsed)

        self.assertEqual(details["actions"][0]["status"], "COMPLETED_DECLARED")
        self.assertNotIn("WORKFLOW_RUN_ACTION_STATUS_UNRESOLVED", limitations)

    def test_malformed_crate_root_is_retained_as_a_limitation(self):
        parsed = {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "about": {"@id": "./"},
                }
            ],
        }

        details, limitations = observe_workflow_run_crate(parsed)

        self.assertEqual(details["status"], "UNAVAILABLE")
        self.assertEqual(details["actions"], [])
        self.assertIn("RO_CRATE_ROOT_MISSING", limitations)

    def test_malformed_action_references_are_counted_and_limited(self):
        parsed = {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "about": {"@id": "./"},
                },
                {"@id": "./", "@type": "Dataset"},
                {"@id": "input.csv", "@type": "File"},
                {
                    "@id": "#run",
                    "@type": "CreateAction",
                    "object": [{"@id": "input.csv"}, {}, "bad"],
                    "result": {"@id": ""},
                    "instrument": 42,
                },
            ],
        }

        details, limitations = observe_workflow_run_crate(parsed)

        action = details["actions"][0]
        self.assertEqual(action["input_ids"], ["input.csv"])
        self.assertEqual(action["malformed_input_count"], 2)
        self.assertEqual(action["malformed_output_count"], 1)
        self.assertEqual(action["malformed_instrument_count"], 1)
        self.assertIn("WORKFLOW_RUN_ACTION_INPUT_MALFORMED", limitations)
        self.assertIn("WORKFLOW_RUN_ACTION_OUTPUT_MALFORMED", limitations)
        self.assertIn("WORKFLOW_RUN_ACTION_INSTRUMENT_MALFORMED", limitations)

    def test_bounds_actions_and_references_with_explicit_omission_counts(self):
        input_ids = [f"input-{index:03d}.csv" for index in range(65)]
        actions = [
            {
                "@id": f"#action-{index:03d}",
                "@type": "CreateAction",
                "object": (
                    [{"@id": identifier} for identifier in input_ids]
                    if index == 0
                    else []
                ),
                "actionStatus": "http://schema.org/CompletedActionStatus",
            }
            for index in range(ACTION_LIMIT + 1)
        ]
        parsed = {
            "@context": "https://w3id.org/ro/crate/1.1/context",
            "@graph": [
                {
                    "@id": "ro-crate-metadata.json",
                    "@type": "CreativeWork",
                    "about": {"@id": "./"},
                },
                {"@id": "./", "@type": "Dataset"},
                *({"@id": identifier, "@type": "File"} for identifier in input_ids),
                *actions,
            ],
        }

        details, limitations = observe_workflow_run_crate(parsed)

        self.assertEqual(details["action_count_in_scope"], ACTION_LIMIT + 1)
        self.assertEqual(len(details["actions"]), ACTION_LIMIT)
        self.assertEqual(details["omitted_action_count"], 1)
        first = details["actions"][0]
        self.assertEqual(len(first["input_ids"]), ACTION_REFERENCE_LIMIT)
        self.assertEqual(first["omitted_input_count"], 1)
        self.assertIn("WORKFLOW_RUN_ACTION_LIMIT", limitations)
        self.assertIn("WORKFLOW_RUN_ACTION_INPUT_LIMIT", limitations)


if __name__ == "__main__":
    unittest.main()
