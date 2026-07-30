import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class RelationshipScenarioTest(unittest.TestCase):
    def test_explicit_event_and_responsibility_evidence_create_only_conservative_candidates(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            for path in (
                "active.py", "compat.py", "prototype.py", "same-looking-a.py", "same-looking-b.py",
            ):
                (root / path).write_text("def run(): pass\n", encoding="utf-8")
            (root / "relationship-manifest.json").write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {"path": "active.py", "episode": "commit-123", "responsibility": "scoring", "role": "ACTIVE_MAINLINE"},
                            {"path": "compat.py", "episode": "commit-123", "responsibility": "scoring", "role": "REQUIRED_COMPATIBILITY"},
                            {"path": "prototype.py", "responsibility": "scoring", "role": "HISTORICAL_EVIDENCE"},
                        ]
                    }
                ),
                encoding="utf-8",
            )

            output = self._run_audit(root)
            episodes = self._records(output / "change-episodes.jsonl")
            families = self._records(output / "capability-families.jsonl")
            roles = {item["repository_relative_path"]: item for item in self._records(output / "implementation-roles.jsonl")}
            run = json.loads((output / "run.json").read_text(encoding="utf-8"))

            self.assertEqual(len(episodes), 1)
            self.assertEqual(episodes[0]["event_evidence"], "commit-123")
            self.assertEqual(episodes[0]["candidate_status"], "CANDIDATE")
            self.assertEqual(len(families), 1)
            self.assertEqual(families[0]["responsibility"], "scoring")
            self.assertIn("active.py", families[0]["member_paths"])
            self.assertEqual(roles["compat.py"]["role"], "REQUIRED_COMPATIBILITY")
            self.assertEqual(roles["prototype.py"]["role"], "HISTORICAL_EVIDENCE")
            self.assertEqual(roles["same-looking-a.py"]["role"], "UNRESOLVED")
            self.assertEqual(roles["same-looking-b.py"]["role"], "UNRESOLVED")
            self.assertEqual(
                run["relationship_coverage"],
                {
                    "capability_family": {
                        "candidate_count": 1,
                        "limitations": ["CAPABILITY_FAMILY_DECLARED_ONLY"],
                        "status": "AVAILABLE_DECLARED_ONLY",
                    },
                    "change_episode": {
                        "candidate_count": 1,
                        "limitations": ["CHANGE_EPISODE_DECLARED_ONLY"],
                        "status": "AVAILABLE_DECLARED_ONLY",
                    },
                    "implementation_role": {
                        "resolved_artifact_count": 3,
                        "limitations": ["IMPLEMENTATION_ROLE_DECLARED_ONLY"],
                        "status": "PARTIAL_DECLARED_ONLY",
                        "total_artifact_count": 6,
                    },
                },
            )
            self.assertNotIn("STRUCTURAL_ADAPTER_UNAVAILABLE", run["warnings"])

    def _run_audit(self, root: Path) -> Path:
        result = subprocess.run(
            [sys.executable, "-m", "repo_curator", "audit", "--root", str(root), "--run-id", "relationship-run", "--created-at", "2026-07-24T00:00:00Z"],
            cwd=Path(__file__).resolve().parents[1], text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return root / ".repo-curator" / "runs" / "relationship-run"

    def _records(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    unittest.main()
