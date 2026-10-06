import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AdvancedReviewScenarioTest(unittest.TestCase):
    def test_advanced_review_emits_bounded_semantics_candidates_and_coverage(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            (root / ".datalad").mkdir(parents=True)
            (root / "mlruns/0/run-1/params").mkdir(parents=True)
            (root / "mlruns/0/run-1/metrics").mkdir(parents=True)
            (root / "unsafe-marker").write_text("absent", encoding="utf-8")
            (root / "dvc.yaml").write_text(
                "stages:\n"
                "  train:\n"
                "    cmd: touch unsafe-marker\n"
                "    deps:\n"
                "      - input.csv\n"
                "    outs:\n"
                "      - output.csv\n",
                encoding="utf-8",
            )
            (root / ".datalad/config").write_text(
                "[datalad]\nrepo.version=1\n", encoding="utf-8"
            )
            (root / "bagit.txt").write_text(
                "BagIt-Version: 1.0\nTag-File-Character-Encoding: UTF-8\n",
                encoding="utf-8",
            )
            (root / "manifest-sha256.txt").write_text(
                "0" * 64 + "  data/result.csv\n", encoding="utf-8"
            )
            (root / "mlruns/0/run-1/meta.yaml").write_text(
                "run_id: run-1\nstatus: FINISHED\n", encoding="utf-8"
            )
            (root / "mlruns/0/run-1/params/learning_rate").write_text(
                "0.1\n", encoding="utf-8"
            )
            (root / "mlruns/0/run-1/metrics/loss").write_text(
                "0 0.5\n", encoding="utf-8"
            )
            (root / "result-a.txt").write_text(
                "alpha beta gamma conclusion date 2026\n", encoding="utf-8"
            )
            (root / "result-b.txt").write_text(
                "alpha beta gamma conclusion date 2027\n", encoding="utf-8"
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "repo_curator",
                    "audit",
                    "--root",
                    str(root),
                    "--run-id",
                    "advanced-fixture",
                    "--created-at",
                    "2026-10-04T00:00:00Z",
                    "--advanced-review",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            run_directory = root / ".repo-curator/runs/advanced-fixture"
            observations = self._records(run_directory / "adapter-observations.jsonl")
            semantic = [
                item
                for item in observations
                if item["schema_version"].endswith("-observation.v1")
                and item["schema_version"] != "repo-curator.adapter-observation.v1"
            ]
            self.assertEqual(
                {item["declaration_family"] for item in semantic},
                {"DVC", "DATALAD", "MLFLOW", "BAGIT"},
            )
            dvc = next(item for item in semantic if item["declaration_family"] == "DVC")
            self.assertEqual(dvc["details"]["stage_count"], 1)
            self.assertIn("DVC_COMMANDS_NOT_EXECUTED", dvc["limitations"])
            self.assertFalse((root / "unsafe-marker").read_text(encoding="utf-8") == "executed")

            candidates = self._records(run_directory / "near-duplicate-candidates.jsonl")
            self.assertEqual(len(candidates), 1)
            self.assertTrue(candidates[0]["review_required"])
            self.assertFalse(candidates[0].get("executable_in_supported_scope", True))
            self.assertIn("SIMILARITY_DOES_NOT_ESTABLISH_COMMON_PURPOSE", candidates[0]["limitations"])

            coverage = self._records(run_directory / "evidence-coverage.jsonl")
            self.assertTrue(coverage)
            near_coverage = [item for item in coverage if item["claim_kind"] == "NEAR_DUPLICATE_CANDIDATE"]
            self.assertEqual(len(near_coverage), 1)
            self.assertIn("PURPOSE", near_coverage[0]["missing_evidence_classes"])

            run = json.loads((run_directory / "run.json").read_text(encoding="utf-8"))
            self.assertTrue(run["advanced_review"]["enabled"])
            self.assertEqual(
                run["output_file_hashes"]["near-duplicate-candidates.jsonl"],
                hashlib.sha256((run_directory / "near-duplicate-candidates.jsonl").read_bytes()).hexdigest(),
            )

    def test_default_audit_keeps_advanced_outputs_opt_in(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            root.mkdir()
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "repo_curator",
                    "audit",
                    "--root",
                    str(root),
                    "--run-id",
                    "default-fixture",
                    "--created-at",
                    "2026-10-04T00:00:00Z",
                ],
                cwd=Path(__file__).resolve().parents[1],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            run_directory = root / ".repo-curator/runs/default-fixture"
            self.assertFalse((run_directory / "near-duplicate-candidates.jsonl").exists())
            self.assertFalse((run_directory / "evidence-coverage.jsonl").exists())
            run = json.loads((run_directory / "run.json").read_text(encoding="utf-8"))
            self.assertNotIn("advanced_review", run)

    @staticmethod
    def _records(path: Path) -> list[dict]:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


if __name__ == "__main__":
    unittest.main()
