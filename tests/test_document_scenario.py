import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class DocumentScenarioTest(unittest.TestCase):
    def test_document_conflicts_and_canonical_entry_points_are_non_destructive(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            for path in ("overview.md", "historical.md", "decision.md", "audit.md"):
                (root / path).write_text("# document\n", encoding="utf-8")
            (root / "document-manifest.json").write_text(
                json.dumps(
                    {
                        "documents": [
                            {"path": "overview.md", "topic": "analysis", "audience": "reviewers", "lifecycle": "CURRENT", "claim": "accuracy", "value": "0.80", "status": "ACCEPTED", "canonical_entry": True},
                            {"path": "historical.md", "topic": "analysis", "audience": "reviewers", "lifecycle": "HISTORICAL", "claim": "accuracy", "value": "0.90", "status": "ACCEPTED"},
                            {"path": "decision.md", "topic": "analysis", "audience": "maintainers", "lifecycle": "CURRENT", "role": "DECISION_RECORD"},
                            {"path": "audit.md", "topic": "analysis", "audience": "auditors", "lifecycle": "HISTORICAL", "role": "AUDIT_RECORD"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            output = self._run_audit(root)
            comparisons = self._records(output / "document-comparisons.jsonl")
            entries = self._records(output / "canonical-entry-points.jsonl")

            conflicting = next(
                item for item in comparisons
                if set(item["document_paths"]) == {"overview.md", "historical.md"}
            )
            self.assertEqual(conflicting["candidate_subtype"], "DO_NOT_MERGE")
            self.assertIn("value", conflicting["conflicting_fields"])
            self.assertTrue(conflicting["human_review_required"])
            self.assertFalse(conflicting["executable_in_supported_scope"])
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["entry_point_path"], "overview.md")
            self.assertIn("historical.md", entries[0]["retained_record_paths"])
            self.assertIn("decision.md", entries[0]["retained_record_paths"])
            self.assertIn("audit.md", entries[0]["retained_record_paths"])
            self.assertFalse(entries[0]["modifies_originals"])

    def _run_audit(self, root: Path) -> Path:
        result = subprocess.run(
            [sys.executable, "-m", "repo_curator", "audit", "--root", str(root), "--run-id", "document-run", "--created-at", "2026-07-24T00:00:00Z"],
            cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return root / ".repo-curator" / "runs" / "document-run"

    def _records(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    unittest.main()
