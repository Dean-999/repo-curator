import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class ShadowModeScenarioTest(unittest.TestCase):
    def test_declaration_evidence_does_not_hide_exact_duplicate_review(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            binder = root / "binder"
            binder.mkdir()
            for path in (root / "requirements.txt", binder / "requirements.txt"):
                path.write_text("numpy==2.0\n", encoding="utf-8")

            output = self._run_audit(root)
            classifications = {
                item["repository_relative_path"]: item
                for item in self._records(output / "classifications.jsonl")
            }
            recommendations = {
                item["repository_relative_paths"][0]: item
                for item in self._records(output / "recommendations.jsonl")
                if len(item["repository_relative_paths"]) == 1
            }
            marker_paths = ("binder/requirements.txt", "requirements.txt")
            duplicate_path = next(
                path
                for path in marker_paths
                if classifications[path]["state"] == "EXACT_DUPLICATE_REVIEW"
            )

            self.assertEqual(
                recommendations[duplicate_path]["recommendation_type"],
                "REVIEW_EXACT_DUPLICATE",
            )
            self.assertGreaterEqual(
                len(classifications[duplicate_path]["supporting_evidence_ids"]),
                2,
            )
            self.assertIn(
                "EXACT_BYTES_DO_NOT_ESTABLISH_COMMON_PURPOSE",
                classifications[duplicate_path]["limitations"],
            )

    def test_local_declaration_marker_is_classified_as_preserved_evidence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            (root / "pyproject.toml").write_text(
                "[project]\nname = 'research-code'\n",
                encoding="utf-8",
            )

            output = self._run_audit(root)
            classification = next(
                item
                for item in self._records(output / "classifications.jsonl")
                if item["repository_relative_path"] == "pyproject.toml"
            )
            recommendation = next(
                item
                for item in self._records(output / "recommendations.jsonl")
                if item["repository_relative_paths"] == ["pyproject.toml"]
            )
            evidence = {
                item["evidence_id"]: item
                for item in self._records(output / "evidence.jsonl")
            }

            self.assertEqual(
                classification["schema_version"],
                "repo-curator.classification.v2",
            )
            self.assertEqual(classification["state"], "DECLARATION_EVIDENCE")
            self.assertEqual(len(classification["supporting_evidence_ids"]), 1)
            declaration_evidence = evidence[
                classification["supporting_evidence_ids"][0]
            ]
            self.assertEqual(declaration_evidence["assertion_origin"], "DECLARED")
            self.assertEqual(declaration_evidence["source_type"], "DECLARATION")
            self.assertIn(
                "ENVIRONMENT_DECLARATION_NOT_ENVIRONMENT_AVAILABILITY",
                classification["limitations"],
            )
            self.assertEqual(recommendation["recommendation_type"], "KEEP")
            self.assertFalse(recommendation["executable_in_supported_scope"])
            self.assertEqual(recommendation["action_candidates"], [])

    def test_absence_only_unresolved_file_is_preserved_without_review_attention(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            (root / "notes.txt").write_text("unclassified notes\n", encoding="utf-8")

            output = self._run_audit(root)
            classification = next(
                item
                for item in self._records(output / "classifications.jsonl")
                if item["repository_relative_path"] == "notes.txt"
            )
            recommendation = next(
                item
                for item in self._records(output / "recommendations.jsonl")
                if item["repository_relative_paths"] == ["notes.txt"]
            )

            self.assertEqual(classification["state"], "UNRESOLVED")
            self.assertTrue(classification["preservation_required"])
            self.assertEqual(
                classification["limitations"],
                ["NO_MAINLINE_EVIDENCE", "NO_ROLE_EVIDENCE"],
            )
            self.assertEqual(recommendation["recommendation_type"], "KEEP")
            self.assertIn("PRESERVE_UNRESOLVED", recommendation["limitations"])
            self.assertTrue(recommendation["human_review_required"])
            self.assertFalse(recommendation["executable_in_supported_scope"])
            self.assertEqual(recommendation["action_candidates"], [])

    def test_preserved_directories_do_not_create_manual_review_work(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            (root / ".git").mkdir()
            ordinary_directory = root / "results"
            ordinary_directory.mkdir()
            (ordinary_directory / "result.txt").write_text("result\n", encoding="utf-8")
            (root / "result-link").symlink_to("results/result.txt")

            output = self._run_audit(root)
            classifications = {
                item["repository_relative_path"]: item
                for item in self._records(output / "classifications.jsonl")
            }
            recommendations = {
                item["repository_relative_paths"][0]: item
                for item in self._records(output / "recommendations.jsonl")
                if len(item["repository_relative_paths"]) == 1
            }

            self.assertEqual(classifications["results"]["state"], "PROTECTED")
            self.assertTrue(classifications["results"]["preservation_required"])
            self.assertIn(
                "NON_REGULAR_ARTIFACT_PRESERVED",
                classifications["results"]["limitations"],
            )
            self.assertEqual(recommendations["results"]["recommendation_type"], "KEEP")
            self.assertTrue(recommendations["results"]["human_review_required"])
            self.assertFalse(recommendations["results"]["executable_in_supported_scope"])
            self.assertEqual(recommendations["results"]["action_candidates"], [])

            self.assertEqual(classifications["."]["state"], "UNRESOLVED")
            self.assertEqual(recommendations["."]["recommendation_type"], "MANUAL_REVIEW")
            self.assertEqual(classifications["result-link"]["state"], "UNRESOLVED")
            self.assertEqual(
                recommendations["result-link"]["recommendation_type"],
                "MANUAL_REVIEW",
            )

    def test_shadow_reports_and_plan_are_deterministic_for_fixed_inputs(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            (root / "README.md").write_text("Entry point: app.py\n", encoding="utf-8")
            (root / "app.py").write_text("main\n", encoding="utf-8")

            first_output = self._run_audit(root)
            first_bytes = {
                name: (first_output / name).read_bytes()
                for name in ("classifications.jsonl", "recommendations.jsonl")
            }
            first_plan_bytes = {
                name: (root / ".repo-curator" / "plans" / "shadow-run" / name).read_bytes()
                for name in (
                    "plan.json",
                    "plan.md",
                    "curation-brief.json",
                    "curation-brief.md",
                )
            }

            shutil.rmtree(root / ".repo-curator")
            second_output = self._run_audit(root)

            self.assertEqual(
                {name: (second_output / name).read_bytes() for name in first_bytes},
                first_bytes,
            )
            self.assertEqual(
                {
                    name: (root / ".repo-curator" / "plans" / "shadow-run" / name).read_bytes()
                    for name in first_plan_bytes
                },
                first_plan_bytes,
            )

    def test_conflicting_mainline_and_role_evidence_remains_unresolved(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            (root / "README.md").write_text("Entry point: app.py\n", encoding="utf-8")
            (root / "app.py").write_text("main\n", encoding="utf-8")
            (root / "relationship-manifest.json").write_text(
                json.dumps({"artifacts": [{"path": "app.py", "role": "HISTORICAL_EVIDENCE"}]}),
                encoding="utf-8",
            )

            output = self._run_audit(root)
            classification = next(
                item for item in self._records(output / "classifications.jsonl")
                if item["repository_relative_path"] == "app.py"
            )

            self.assertEqual(classification["state"], "UNRESOLVED")
            self.assertIn("MATERIAL_ROLE_CONFLICT", classification["limitations"])

    def test_inventory_limitation_downgrades_mainline_claim_to_unresolved(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            (root / "README.md").write_text("Entry point: large.py\n", encoding="utf-8")
            (root / "large.py").write_text("main content exceeds one byte\n", encoding="utf-8")

            output = self._run_audit(root, max_file_bytes=1)
            classifications = {
                item["repository_relative_path"]: item
                for item in self._records(output / "classifications.jsonl")
            }
            recommendations = {
                item["repository_relative_paths"][0]: item
                for item in self._records(output / "recommendations.jsonl")
                if len(item["repository_relative_paths"]) == 1
            }

            self.assertEqual(classifications["large.py"]["state"], "UNRESOLVED")
            self.assertIn("INVENTORY_COVERAGE_LIMITATION", classifications["large.py"]["limitations"])
            self.assertEqual(recommendations["large.py"]["recommendation_type"], "MANUAL_REVIEW")

    def test_curation_brief_escapes_untrusted_markdown_in_paths(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            dangerous_name = "result`\n## Forged heading.md"
            (root / dangerous_name).symlink_to("missing-result")

            self._run_audit(root)

            brief_markdown = (
                root
                / ".repo-curator"
                / "plans"
                / "shadow-run"
                / "curation-brief.md"
            ).read_text(encoding="utf-8")
            self.assertNotIn("\n## Forged heading.md", brief_markdown)
            self.assertIn("result`\\n## Forged heading.md", brief_markdown)

    def test_shadow_outputs_are_evidence_bound_and_never_executable(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            for path in (
                "active.py", "compat.py", "historical.py", "duplicate-keep.txt",
                "duplicate-candidate.txt", "guarded.txt", "overview.md", "decision.md",
                "conflict-a.md", "conflict-b.md", "config.json", "train.py",
                "validate.txt", "review.txt",
            ):
                (root / path).write_text("same duplicate\n" if path.startswith("duplicate") else path + "\n", encoding="utf-8")
            (root / "README.md").write_text("Entry point: active.py\n", encoding="utf-8")
            (root / "AGENTS.md").write_text(
                "Compatibility: compat.py\nArchive: historical.py\n", encoding="utf-8"
            )
            (root / "experiment-manifest.json").write_text(
                json.dumps({"attempts": [{
                    "id": "incomplete", "experiment": "trial", "result": "ACCEPTED",
                    "output": "guarded.txt", "inputs": ["missing-data.csv"],
                    "configuration": "config.json", "generator": "train.py",
                    "validation": "validate.txt", "reviewer_record": "review.txt",
                }]}),
                encoding="utf-8",
            )
            (root / "document-manifest.json").write_text(
                json.dumps({"documents": [
                    {"path": "overview.md", "topic": "overview", "audience": "reviewers", "lifecycle": "CURRENT"},
                    {"path": "decision.md", "topic": "overview", "audience": "maintainers", "lifecycle": "CURRENT", "role": "DECISION_RECORD"},
                    {"path": "conflict-a.md", "topic": "conflict", "claim": "score", "value": "0.8"},
                    {"path": "conflict-b.md", "topic": "conflict", "claim": "score", "value": "0.9"},
                ]}),
                encoding="utf-8",
            )

            output = self._run_audit(root)
            classifications = self._records(output / "classifications.jsonl")
            recommendations = self._records(output / "recommendations.jsonl")
            plan_directory = root / ".repo-curator" / "plans" / "shadow-run"
            plan = json.loads((plan_directory / "plan.json").read_text(encoding="utf-8"))
            brief_bytes = (plan_directory / "curation-brief.json").read_bytes()
            brief_markdown_bytes = (plan_directory / "curation-brief.md").read_bytes()
            brief = json.loads(brief_bytes)
            run = json.loads((output / "run.json").read_text(encoding="utf-8"))

            by_path = {item["repository_relative_path"]: item for item in classifications}
            self.assertEqual(by_path["active.py"]["state"], "ACTIVE_MAINLINE")
            self.assertEqual(by_path["compat.py"]["state"], "REQUIRED_COMPATIBILITY")
            self.assertEqual(by_path["historical.py"]["state"], "HISTORICAL_EVIDENCE")
            self.assertEqual(by_path["guarded.txt"]["state"], "UNRESOLVED")
            self.assertIn("BUNDLE_MOVEMENT_GUARD", by_path["guarded.txt"]["limitations"])
            self.assertEqual(by_path["conflict-a.md"]["state"], "UNRESOLVED")
            duplicate_states = {
                path: by_path[path]["state"]
                for path in ("duplicate-keep.txt", "duplicate-candidate.txt")
            }
            self.assertEqual(list(duplicate_states.values()).count("EXACT_DUPLICATE_REVIEW"), 1)
            self.assertTrue(all(by_path[path]["preservation_required"] for path in duplicate_states))

            by_path_recommendation = {
                item["repository_relative_paths"][0]: item
                for item in recommendations
                if len(item["repository_relative_paths"]) == 1
            }
            self.assertEqual(by_path_recommendation["active.py"]["recommendation_type"], "KEEP")
            self.assertEqual(by_path_recommendation["historical.py"]["recommendation_type"], "ARCHIVE")
            self.assertEqual(by_path_recommendation["guarded.txt"]["recommendation_type"], "MANUAL_REVIEW")
            duplicate_reviews = [
                item for item in recommendations
                if item["recommendation_type"] == "REVIEW_EXACT_DUPLICATE"
                and item["repository_relative_paths"][0] in duplicate_states
            ]
            self.assertEqual(len(duplicate_reviews), 1)
            self.assertEqual(duplicate_reviews[0]["expected_loss"], "NONE")
            self.assertEqual(duplicate_reviews[0]["retention_closure"]["status"], "PRESERVED_OR_REVIEW_REQUIRED")
            self.assertIn("NO_MOVE_OR_DELETE_AUTHORIZED", duplicate_reviews[0]["limitations"])
            self.assertTrue(all(not item["executable_in_supported_scope"] for item in recommendations))
            self.assertNotIn("QUARANTINE", {item["recommendation_type"] for item in recommendations})
            self.assertIn("MERGE", {item["recommendation_type"] for item in recommendations})
            self.assertIn("MANUAL_REVIEW", {item["recommendation_type"] for item in recommendations})

            self.assertEqual(plan["execution_mode"], "SHADOW")
            self.assertFalse(plan["executable"])
            self.assertEqual(plan["action_candidates"], [])
            self.assertEqual(set(plan["classification_ids"]), {item["classification_id"] for item in classifications})
            self.assertEqual(set(plan["recommendation_ids"]), {item["recommendation_id"] for item in recommendations})
            self.assertEqual(run["shadow_plan_directory"], ".repo-curator/plans/shadow-run")
            self.assertEqual(run["output_file_hashes"]["classifications.jsonl"], hashlib.sha256((output / "classifications.jsonl").read_bytes()).hexdigest())
            self.assertEqual(run["output_file_hashes"]["recommendations.jsonl"], hashlib.sha256((output / "recommendations.jsonl").read_bytes()).hexdigest())
            self.assertIn("authorizes no repository action", (plan_directory / "plan.md").read_text(encoding="utf-8"))

            self.assertEqual(brief["schema_version"], "repo-curator.curation-brief.v3")
            self.assertEqual(brief["run_id"], "shadow-run")
            self.assertFalse(brief["execution_authorized"])
            self.assertEqual(
                brief["structural_coverage"],
                {
                    "capability_family": {
                        "candidate_count": 0,
                        "limitations": [
                            "CAPABILITY_FAMILY_SYNTAX_ONLY_NO_EQUIVALENCE",
                            "PYTHON_SYNTAX_NOT_RUNTIME_BEHAVIOR",
                        ],
                        "status": "PARTIAL_SYNTAX_ONLY",
                    },
                    "change_episode": {
                        "candidate_count": 0,
                        "limitations": ["CHANGE_EPISODE_EVIDENCE_UNAVAILABLE"],
                        "status": "UNAVAILABLE",
                    },
                    "implementation_role": {
                        "limitations": ["PYTHON_SYNTAX_NOT_RUNTIME_BEHAVIOR"],
                        "resolved_artifact_count": 0,
                        "status": "PARTIAL_SYNTAX_ONLY",
                        "total_artifact_count": 18,
                    },
                },
            )
            self.assertNotIn("STRUCTURAL_ADAPTER_UNAVAILABLE", run["warnings"])
            self.assertEqual(
                brief["recommendation_counts"],
                {
                    kind: sum(
                        item["recommendation_type"] == kind
                        for item in recommendations
                    )
                    for kind in sorted(
                        {item["recommendation_type"] for item in recommendations}
                    )
                },
            )
            self.assertEqual(
                plan["curation_brief"],
                {
                    "json_file": "curation-brief.json",
                    "json_sha256": hashlib.sha256(brief_bytes).hexdigest(),
                    "markdown_file": "curation-brief.md",
                    "markdown_sha256": hashlib.sha256(
                        brief_markdown_bytes
                    ).hexdigest(),
                },
            )
            self.assertFalse(
                any(
                    item["repository_relative_paths"] == ["."]
                    for item in brief["review_attention_items"]
                )
            )
            brief_markdown = brief_markdown_bytes.decode("utf-8")
            for heading in (
                "## Audit scope",
                "## Project intent and scientific mainline",
                "## Preservation risks",
                "## Conservative recommendations",
                "## Decision questions",
                "## Next safe action",
            ):
                self.assertIn(heading, brief_markdown)
            self.assertIn("authorizes no repository action", brief_markdown)
            self.assertEqual(
                brief_markdown.count("- Reproducibility-evidence gaps:"), 1
            )
            self.assertIn("REVIEW_EXACT_DUPLICATE", brief_markdown)
            self.assertNotIn("QUARANTINE", brief_markdown)
            self.assertNotIn("CLEANUP_CANDIDATE", brief_markdown)

    def _run_audit(self, root: Path, max_file_bytes: int = 33_554_432) -> Path:
        result = subprocess.run(
            [sys.executable, "-m", "repo_curator", "audit", "--root", str(root), "--run-id", "shadow-run", "--created-at", "2026-07-24T00:00:00Z", "--max-file-bytes", str(max_file_bytes)],
            cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return root / ".repo-curator" / "runs" / "shadow-run"

    def _records(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    unittest.main()
