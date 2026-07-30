import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from repo_curator.decisions import record_user_decision


class DecisionScenarioTest(unittest.TestCase):
    def test_consistent_intent_emits_no_question(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            (root / "README.md").write_text("Entry point: app.py\n", encoding="utf-8")
            (root / "app.py").write_text("main\n", encoding="utf-8")

            output = self._run_audit(root, "no-question")

            self.assertEqual(self._records(output / "decision-questions.jsonl"), [])
            self.assertEqual(self._records(output / "user-decisions.jsonl"), [])

    def test_conflict_emits_one_contextual_question_and_keeps_assertion_separate(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            (root / "README.md").write_text("Entry point: legacy.py\n", encoding="utf-8")
            workflow = root / ".github" / "workflows"
            workflow.mkdir(parents=True)
            (workflow / "deploy.yml").write_text(
                "Entry point: current.py\n", encoding="utf-8"
            )
            (root / "legacy.py").write_text("legacy\n", encoding="utf-8")
            (root / "current.py").write_text("current\n", encoding="utf-8")

            output = self._run_audit(root, "one-question")
            questions = self._records(output / "decision-questions.jsonl")
            conflicts = self._records(output / "intent-conflicts.jsonl")

            self.assertEqual(len(questions), 1)
            question = questions[0]
            self.assertEqual(question["question_type"], "INTENT_CONFLICT")
            self.assertEqual(question["conservative_recommendation"], "PRESERVE_UNRESOLVED")
            self.assertTrue(question["affected_artifacts"])
            self.assertTrue(question["supporting_evidence_ids"])
            self.assertTrue(question["counter_evidence_ids"])
            self.assertTrue(
                any("UNRESOLVED" in consequence for consequence in question["consequences"])
            )

            decision = record_user_decision(
                question,
                "PREFER_CURRENT",
                "The deployment entry point is current.",
                "2026-07-24T00:00:01Z",
            )
            self.assertEqual(decision["scope"], question["scope"])
            self.assertEqual(decision["supporting_evidence_ids"], question["supporting_evidence_ids"])
            self.assertEqual(decision["counter_evidence_ids"], question["counter_evidence_ids"])
            self.assertTrue(decision["decision_set_hash"].startswith("sha256:"))
            self.assertTrue(conflicts)

    def _run_audit(self, root: Path, run_id: str) -> Path:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "repo_curator",
                "audit",
                "--root",
                str(root),
                "--run-id",
                run_id,
                "--created-at",
                "2026-07-24T00:00:00Z",
            ],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return root / ".repo-curator" / "runs" / run_id

    def _records(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    unittest.main()
