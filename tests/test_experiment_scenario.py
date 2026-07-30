import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ExperimentScenarioTest(unittest.TestCase):
    def test_curation_brief_bounds_declared_chain_details_and_reports_omissions(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            input_paths = [f"input-{index:03d}.csv" for index in range(70)]
            output_paths = [f"output-{index:02d}.json" for index in range(26)]
            for path in (*input_paths, *output_paths):
                (root / path).write_text(path + "\n", encoding="utf-8")
            attempts = [
                {
                    "id": f"attempt-{index:02d}",
                    "experiment": "bounded-report",
                    "result": "ACCEPTED",
                    "output": output_path,
                    **(
                        {"inputs": input_paths}
                        if index == 0
                        else {
                            "inputs": [
                                f"missing-{missing_index:03d}.csv"
                                for missing_index in range(70)
                            ]
                        }
                        if index == 1
                        else {}
                    ),
                }
                for index, output_path in enumerate(output_paths)
            ]
            (root / "experiment-manifest.json").write_text(
                json.dumps({"attempts": attempts}),
                encoding="utf-8",
            )

            self._run_audit(root)
            brief = json.loads(
                (
                    root
                    / ".repo-curator"
                    / "plans"
                    / "experiment-run"
                    / "curation-brief.json"
                ).read_text(encoding="utf-8")
            )
            declared_chains = brief["declared_experiment_chains"]

            self.assertEqual(declared_chains["attempt_count"], 26)
            self.assertEqual(declared_chains["directed_edge_count"], 96)
            self.assertEqual(len(declared_chains["chains"]), 25)
            self.assertEqual(declared_chains["omitted_chain_count"], 1)
            first_chain = declared_chains["chains"][0]
            self.assertEqual(first_chain["attempt_id"], "attempt-00")
            self.assertEqual(first_chain["declared_edge_count"], 71)
            self.assertEqual(len(first_chain["declared_edges"]), 64)
            self.assertEqual(first_chain["omitted_declared_edge_count"], 7)
            second_chain = declared_chains["chains"][1]
            self.assertEqual(second_chain["unresolved_dependency_count"], 74)
            self.assertEqual(len(second_chain["unresolved_dependencies"]), 64)
            self.assertEqual(
                second_chain["omitted_unresolved_dependency_count"], 10
            )
            gap_review = brief["reproducibility_gap_review"]
            self.assertEqual(gap_review["gap_count"], 26)
            self.assertEqual(len(gap_review["gaps"]), 25)
            self.assertEqual(gap_review["omitted_gap_count"], 1)
            self.assertEqual(gap_review["gaps"][0]["attempt_id"], "attempt-01")
            self.assertEqual(gap_review["gaps"][0]["unresolved_item_count"], 74)
            self.assertEqual(len(gap_review["gaps"][0]["missing_or_unresolved"]), 64)
            self.assertEqual(
                gap_review["gaps"][0]["omitted_unresolved_item_count"], 10
            )

    def test_curation_brief_prioritizes_incomplete_chains_before_report_cap(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            for path in (
                "data.csv",
                "config.json",
                "train.py",
                "validate.txt",
                "review.txt",
            ):
                (root / path).write_text(path + "\n", encoding="utf-8")
            attempts = []
            for index in range(25):
                output_path = f"complete-{index:02d}.json"
                (root / output_path).write_text(output_path + "\n", encoding="utf-8")
                attempts.append(
                    {
                        "id": f"a-complete-{index:02d}",
                        "experiment": "priority-report",
                        "result": "ACCEPTED",
                        "output": output_path,
                        "inputs": ["data.csv"],
                        "configuration": "config.json",
                        "generator": "train.py",
                        "validation": "validate.txt",
                        "reviewer_record": "review.txt",
                    }
                )
            (root / "incomplete.json").write_text("incomplete\n", encoding="utf-8")
            attempts.append(
                {
                    "id": "z-incomplete",
                    "experiment": "priority-report",
                    "result": "ACCEPTED",
                    "output": "incomplete.json",
                    "inputs": ["missing.csv"],
                }
            )
            (root / "experiment-manifest.json").write_text(
                json.dumps({"attempts": attempts}),
                encoding="utf-8",
            )

            self._run_audit(root)
            brief = json.loads(
                (
                    root
                    / ".repo-curator"
                    / "plans"
                    / "experiment-run"
                    / "curation-brief.json"
                ).read_text(encoding="utf-8")
            )
            chains = brief["declared_experiment_chains"]["chains"]

            self.assertEqual(len(chains), 25)
            self.assertEqual(chains[0]["attempt_id"], "z-incomplete")
            self.assertIn("missing.csv", chains[0]["unresolved_dependencies"])
            self.assertNotIn(
                "a-complete-24", {item["attempt_id"] for item in chains}
            )

    def test_declared_attempts_bundles_and_canonical_candidates_remain_evidence_bound(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            for path in (
                "data.csv", "config.json", "train.py", "validate.txt", "review.txt",
                "accepted.json", "failed.json", "inconclusive.json", "missing.json",
            ):
                (root / path).write_text(path + "\n", encoding="utf-8")
            (root / "experiment-manifest.json").write_text(
                json.dumps(
                    {
                        "attempts": [
                            {
                                "id": "accepted-attempt",
                                "experiment": "trial-a",
                                "result": "ACCEPTED",
                                "output": "accepted.json",
                                "inputs": ["data.csv"],
                                "configuration": "config.json",
                                "generator": "train.py",
                                "validation": "validate.txt",
                                "reviewer_record": "review.txt",
                                "canonical_candidate": True,
                            },
                            {
                                "id": "failed-retry",
                                "experiment": "trial-a",
                                "retry_of": "accepted-attempt",
                                "result": "FAILED",
                                "output": "failed.json",
                            },
                            {
                                "id": "inconclusive-attempt",
                                "experiment": "trial-b",
                                "result": "INCONCLUSIVE",
                                "output": "inconclusive.json",
                            },
                            {
                                "id": "incomplete-attempt",
                                "experiment": "trial-c",
                                "result": "ACCEPTED",
                                "output": "missing.json",
                                "inputs": ["missing-input.csv"],
                                "configuration": "config.json",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )

            output = self._run_audit(root)
            attempts = self._records(output / "experiment-attempts.jsonl")
            bundles = {item["attempt_id"]: item for item in self._records(output / "experiment-bundles.jsonl")}
            candidates = self._records(output / "canonical-result-candidates.jsonl")
            gaps = self._records(output / "reproducibility-gaps.jsonl")
            inventory = {
                item["repository_relative_path"]: item
                for item in self._records(output / "inventory.jsonl")
            }
            evidence = {
                item["evidence_id"]: item
                for item in self._records(output / "evidence.jsonl")
            }
            relationships = [
                item
                for item in self._records(output / "relationships.jsonl")
                if item["assertion_origin"] == "DECLARED"
            ]
            plan_directory = root / ".repo-curator" / "plans" / "experiment-run"
            brief = json.loads(
                (plan_directory / "curation-brief.json").read_text(encoding="utf-8")
            )
            brief_markdown = (plan_directory / "curation-brief.md").read_text(
                encoding="utf-8"
            )

            by_id = {item["attempt_id"]: item for item in attempts}
            self.assertEqual(by_id["failed-retry"]["result"], "FAILED")
            self.assertEqual(by_id["failed-retry"]["retry_of"], "accepted-attempt")
            self.assertEqual(by_id["inconclusive-attempt"]["result"], "INCONCLUSIVE")
            self.assertEqual(
                {item["schema_version"] for item in attempts},
                {"repo-curator.experiment-attempt.v2"},
            )
            self.assertEqual(
                {item["schema_version"] for item in bundles.values()},
                {"repo-curator.experiment-bundle.v2"},
            )
            self.assertEqual(bundles["accepted-attempt"]["completeness"], "COMPLETE_IN_ANALYZED_SCOPE")
            self.assertEqual(bundles["incomplete-attempt"]["completeness"], "MISSING_REQUIRED_LINK")
            self.assertIn("missing-input.csv", bundles["incomplete-attempt"]["unresolved_dependencies"])
            self.assertEqual(candidates[0]["governance_state"], "CANDIDATE")
            self.assertEqual(
                candidates[0]["schema_version"],
                "repo-curator.canonical-result-candidate.v2",
            )
            self.assertFalse(candidates[0]["executable_in_supported_scope"])
            self.assertTrue(any(item["attempt_id"] == "incomplete-attempt" for item in gaps))
            self.assertEqual(
                {item["schema_version"] for item in gaps},
                {"repo-curator.reproducibility-gap.v2"},
            )
            self.assertTrue(
                all(
                    item["supporting_evidence_ids"]
                    and set(item["supporting_evidence_ids"]).issubset(evidence)
                    for item in gaps
                )
            )
            self.assertEqual(
                {
                    evidence[evidence_id]["subject"]["artifact_id"]
                    for item in gaps
                    for evidence_id in item["supporting_evidence_ids"]
                },
                {inventory["experiment-manifest.json"]["artifact_id"]},
            )
            supporting_ids = {
                evidence_id
                for record in (*attempts, *bundles.values(), *candidates)
                for evidence_id in record["supporting_evidence_ids"]
            }
            self.assertTrue(supporting_ids)
            self.assertTrue(supporting_ids.issubset(evidence))
            self.assertEqual(
                {
                    evidence[evidence_id]["subject"]["artifact_id"]
                    for evidence_id in supporting_ids
                },
                {inventory["experiment-manifest.json"]["artifact_id"]},
            )
            self.assertEqual(len(relationships), 10)
            self.assertEqual(
                {item["schema_version"] for item in relationships},
                {"repo-curator.relationship.v2"},
            )
            self.assertEqual(
                {item["relationship_type"] for item in relationships},
                {
                    "DECLARED_CONFIGURATION",
                    "DECLARED_GENERATOR",
                    "DECLARED_INPUT",
                    "DECLARED_OUTPUT",
                    "DECLARED_REVIEWER_RECORD",
                    "DECLARED_VALIDATION",
                },
            )
            self.assertTrue(
                all(
                    item["relationship_shape"] == "DIRECTED_EDGE"
                    and item["source"]["entity_type"] == "EXPERIMENT_ATTEMPT"
                    and item["target"]["entity_type"] == "ARTIFACT"
                    and set(item["supporting_evidence_ids"]).issubset(evidence)
                    and "DECLARED_LINEAGE_NOT_EXECUTION_VERIFIED"
                    in item["limitations"]
                    for item in relationships
                )
            )
            self.assertNotIn(
                "missing-input.csv",
                {item["declared_path"] for item in relationships},
            )
            self.assertEqual(
                brief["schema_version"], "repo-curator.curation-brief.v3"
            )
            declared_chains = brief["declared_experiment_chains"]
            self.assertEqual(declared_chains["attempt_count"], 4)
            self.assertEqual(declared_chains["directed_edge_count"], 10)
            self.assertEqual(
                declared_chains["relationship_type_counts"],
                {
                    "DECLARED_CONFIGURATION": 2,
                    "DECLARED_GENERATOR": 1,
                    "DECLARED_INPUT": 1,
                    "DECLARED_OUTPUT": 4,
                    "DECLARED_REVIEWER_RECORD": 1,
                    "DECLARED_VALIDATION": 1,
                },
            )
            accepted_chain = next(
                item
                for item in declared_chains["chains"]
                if item["attempt_id"] == "accepted-attempt"
            )
            self.assertEqual(
                accepted_chain["completeness"], "COMPLETE_IN_ANALYZED_SCOPE"
            )
            self.assertEqual(len(accepted_chain["declared_edges"]), 6)
            self.assertTrue(
                all(
                    set(item["supporting_evidence_ids"]).issubset(evidence)
                    and "DECLARED_LINEAGE_NOT_EXECUTION_VERIFIED"
                    in item["limitations"]
                    for item in accepted_chain["declared_edges"]
                )
            )
            incomplete_chain = next(
                item
                for item in declared_chains["chains"]
                if item["attempt_id"] == "incomplete-attempt"
            )
            self.assertIn("missing-input.csv", incomplete_chain["unresolved_dependencies"])
            self.assertNotIn(
                "missing-input.csv",
                {item["declared_path"] for item in incomplete_chain["declared_edges"]},
            )
            self.assertIn("## Declared experiment chains", brief_markdown)
            self.assertIn("declaration-only; execution was not verified", brief_markdown)
            candidate_review = brief["canonical_result_review"]
            self.assertEqual(candidate_review["candidate_count"], 1)
            self.assertEqual(candidate_review["omitted_candidate_count"], 0)
            self.assertEqual(
                candidate_review["candidates"],
                [
                    {
                        "attempt_id": "accepted-attempt",
                        "candidate_id": candidates[0]["candidate_id"],
                        "counter_evidence_ids": [],
                        "executable_in_supported_scope": False,
                        "governance_state": "CANDIDATE",
                        "limitations": [
                            "DECLARED_CANDIDATE_NOT_CANONICAL_CONFIRMATION"
                        ],
                        "output_path": "accepted.json",
                        "supporting_evidence_ids": candidates[0][
                            "supporting_evidence_ids"
                        ],
                    }
                ],
            )
            gap_review = brief["reproducibility_gap_review"]
            self.assertEqual(gap_review["gap_count"], 3)
            self.assertEqual(gap_review["omitted_gap_count"], 0)
            incomplete_gap = next(
                item
                for item in gap_review["gaps"]
                if item["attempt_id"] == "incomplete-attempt"
            )
            self.assertEqual(
                incomplete_gap["supporting_evidence_ids"],
                next(
                    item
                    for item in gaps
                    if item["attempt_id"] == "incomplete-attempt"
                )["supporting_evidence_ids"],
            )
            self.assertIn(
                "missing-input.csv",
                incomplete_gap["missing_or_unresolved"],
            )
            self.assertIn("## Canonical-result candidates", brief_markdown)
            self.assertIn("## Reproducibility-evidence gaps", brief_markdown)

    def _run_audit(self, root: Path) -> Path:
        result = subprocess.run(
            [
                sys.executable, "-m", "repo_curator", "audit", "--root", str(root),
                "--run-id", "experiment-run", "--created-at", "2026-07-24T00:00:00Z",
            ],
            cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return root / ".repo-curator" / "runs" / "experiment-run"

    def _records(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    unittest.main()
