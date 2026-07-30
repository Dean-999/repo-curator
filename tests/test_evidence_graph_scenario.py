import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class EvidenceGraphScenarioTest(unittest.TestCase):
    def test_audit_emits_typed_evidence_and_exact_duplicate_relationships(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            (root / "left.txt").write_text("same bytes\n", encoding="utf-8")
            (root / "right.txt").write_text("same bytes\n", encoding="utf-8")
            (root / "ro-crate-metadata.json").write_text("{}", encoding="utf-8")
            (root / "different.txt").write_text("different bytes\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "repo_curator",
                    "audit",
                    "--root",
                    str(root),
                    "--run-id",
                    "evidence-run",
                    "--created-at",
                    "2026-07-24T00:00:00Z",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            output = root / ".repo-curator" / "runs" / "evidence-run"
            evidence = [
                json.loads(line)
                for line in (output / "evidence.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            relationships = [
                json.loads(line)
                for line in (output / "relationships.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            run = json.loads((output / "run.json").read_text(encoding="utf-8"))

            self.assertTrue(
                any(
                    item["source_type"] == "DECLARATION"
                    and item["assertion_origin"] == "DECLARED"
                    and item["scope"] == "DECLARATION_PRESENCE_ONLY"
                    for item in evidence
                )
            )
            self.assertTrue(
                all(
                    {"counter_evidence_ids", "extractor", "limitations", "source", "source_type"}
                    <= item.keys()
                    for item in evidence
                )
            )
            self.assertEqual(len(relationships), 1)
            relationship = relationships[0]
            self.assertEqual(relationship["relationship_type"], "EXACT_BYTE_DUPLICATE")
            self.assertEqual(relationship["assertion_origin"], "DETERMINISTIC")
            self.assertEqual(relationship["counter_evidence_ids"], [])
            self.assertEqual(len(relationship["supporting_evidence_ids"]), 2)
            inventory = {
                item["repository_relative_path"]: item
                for item in (
                    json.loads(line)
                    for line in (output / "inventory.jsonl").read_text(encoding="utf-8").splitlines()
                )
            }
            self.assertEqual(
                relationship["content_id"],
                inventory["left.txt"]["content_id"],
            )
            self.assertEqual(
                run["output_file_hashes"]["evidence.jsonl"],
                hashlib.sha256((output / "evidence.jsonl").read_bytes()).hexdigest(),
            )
            self.assertEqual(
                run["output_file_hashes"]["relationships.jsonl"],
                hashlib.sha256((output / "relationships.jsonl").read_bytes()).hexdigest(),
            )
            mapping = (
                Path(__file__).resolve().parents[1]
                / "docs"
                / "evidence-standards-mapping.md"
            ).read_text(encoding="utf-8")
            self.assertIn("prov:Entity", mapping)
            self.assertIn("repo-curator:exactByteDuplicate", mapping)

    def test_non_file_content_schemes_never_create_exact_byte_relationships(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            (root / "first").mkdir()
            (root / "second").mkdir()
            (root / "first" / "value.txt").write_text("same\n", encoding="utf-8")
            (root / "second" / "value.txt").write_text("same\n", encoding="utf-8")

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "repo_curator",
                    "audit",
                    "--root",
                    str(root),
                    "--run-id",
                    "directory-run",
                    "--created-at",
                    "2026-07-24T00:00:00Z",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            output = root / ".repo-curator" / "runs" / "directory-run"
            relationships = [
                json.loads(line)
                for line in (output / "relationships.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            self.assertEqual(len(relationships), 1)
            self.assertTrue(
                all(item["content_id"].startswith("sha256-file-v1:") for item in relationships)
            )


if __name__ == "__main__":
    unittest.main()
