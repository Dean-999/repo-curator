import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class PythonStructuralScenarioTest(unittest.TestCase):
    def test_python_syntax_is_observed_without_importing_or_executing_target_code(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            marker = root / "target-code-executed"
            (root / "analysis.py").write_text(
                "import json\n"
                "from pathlib import Path\n"
                "def analyze():\n    return 1\n"
                "class Model:\n    pass\n"
                "if __name__ == '__main__':\n    analyze()\n"
                f"Path({str(marker)!r}).write_text('executed')\n",
                encoding="utf-8",
            )
            (root / "README.md").write_text(
                "Entry point: analysis.py\n", encoding="utf-8"
            )
            (root / "broken.py").write_text("def broken(:\n", encoding="utf-8")

            output = self._run_audit(root)

            self.assertFalse(marker.exists())
            records = {
                item["repository_relative_path"]: item
                for item in self._records(output / "structural-observations.jsonl")
            }
            analysis = records["analysis.py"]
            self.assertEqual(analysis["module_name"], "analysis")
            self.assertEqual(analysis["imports"], ["json", "pathlib"])
            self.assertEqual(
                analysis["definitions"],
                [
                    {"kind": "CLASS", "name": "Model"},
                    {"kind": "FUNCTION", "name": "analyze"},
                ],
            )
            self.assertTrue(analysis["has_main_guard"])
            self.assertEqual(analysis["limitations"], ["PYTHON_SYNTAX_NOT_RUNTIME_BEHAVIOR"])
            self.assertNotIn("source", analysis)
            self.assertNotIn("executed", json.dumps(analysis))
            self.assertEqual(records["broken.py"]["imports"], [])
            self.assertEqual(records["broken.py"]["definitions"], [])
            self.assertIn("PYTHON_SYNTAX_ERROR", records["broken.py"]["limitations"])

            evidence = self._records(output / "evidence.jsonl")
            structure_evidence = next(
                item
                for item in evidence
                if item["source_type"] == "PYTHON_STRUCTURE"
                and item["source_record_id"] == analysis["structure_id"]
            )
            self.assertEqual(
                structure_evidence["subject"]["artifact_id"], analysis["artifact_id"]
            )
            roles = {
                item["repository_relative_path"]: item
                for item in self._records(output / "implementation-roles.jsonl")
            }
            self.assertEqual(roles["analysis.py"]["role"], "ACTIVE_MAINLINE")
            self.assertIn(
                structure_evidence["evidence_id"],
                roles["analysis.py"]["supporting_evidence_ids"],
            )
            self.assertTrue(
                all(
                    identifier.startswith(("evidence_", "intent_evidence_"))
                    for identifier in roles["analysis.py"]["supporting_evidence_ids"]
                )
            )

            run = json.loads((output / "run.json").read_text(encoding="utf-8"))
            structural_bytes = (output / "structural-observations.jsonl").read_bytes()
            self.assertEqual(
                run["output_file_hashes"]["structural-observations.jsonl"],
                hashlib.sha256(structural_bytes).hexdigest(),
            )
            self.assertEqual(
                run["component_states"]["python_structure"]["status"],
                "COMPLETED_WITH_LIMITATIONS",
            )
            self.assertEqual(
                run["relationship_coverage"]["capability_family"]["status"],
                "PARTIAL_SYNTAX_ONLY",
            )

    def test_oversized_and_over_budget_python_files_are_not_structurally_interpreted(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            (root / "oversized.py").write_bytes(b"import poison\n" + b"#" * (256 * 1024))
            (root / "too-many-nodes.py").write_text(
                "values = [" + ",".join("0" for _ in range(20_001)) + "]\n",
                encoding="utf-8",
            )

            output = self._run_audit(root)

            records = {
                item["repository_relative_path"]: item
                for item in self._records(output / "structural-observations.jsonl")
            }
            self.assertIn("PYTHON_STRUCTURE_SIZE_LIMIT", records["oversized.py"]["limitations"])
            self.assertEqual(records["oversized.py"]["imports"], [])
            self.assertIn(
                "PYTHON_STRUCTURE_NODE_LIMIT",
                records["too-many-nodes.py"]["limitations"],
            )
            self.assertEqual(records["too-many-nodes.py"]["definitions"], [])

    def test_malformed_relationship_manifest_does_not_hide_python_syntax_coverage(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            (root / "entry.py").write_text("import os\n", encoding="utf-8")
            (root / "relationship-manifest.json").write_text("{", encoding="utf-8")

            output = self._run_audit(root)

            run = json.loads((output / "run.json").read_text(encoding="utf-8"))
            self.assertEqual(
                run["relationship_coverage"]["capability_family"]["status"],
                "PARTIAL_SYNTAX_ONLY",
            )
            self.assertEqual(
                run["relationship_coverage"]["implementation_role"]["status"],
                "PARTIAL_SYNTAX_ONLY",
            )
            self.assertIn(
                "RELATIONSHIP_MANIFEST_MALFORMED",
                run["relationship_coverage"]["capability_family"]["limitations"],
            )

    def _run_audit(self, root: Path) -> Path:
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "repo_curator",
                "audit",
                "--root",
                str(root),
                "--run-id",
                "structure-run",
                "--created-at",
                "2026-07-27T00:00:00Z",
            ],
            cwd=Path(__file__).resolve().parents[1],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return root / ".repo-curator" / "runs" / "structure-run"

    def _records(self, path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    unittest.main()
