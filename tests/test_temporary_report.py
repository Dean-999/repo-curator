import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from repo_curator.brief import render_temporary_audit_report
from repo_curator.cli import _temporary_report_for_run, main
from repo_curator.report_html import render_temporary_audit_html


class TemporaryAuditReportTest(unittest.TestCase):
    def test_report_is_short_and_explains_review_boundary(self):
        brief = {
            "audit_scope": {
                "artifact_count": 3,
                "repository_root_realpath": "/tmp/research",
            },
            "observed_evidence": {
                "exact_byte_duplicate_group_count": 1,
                "declaration_observation_count": 2,
            },
            "preservation_risks": {
                "unresolved_artifact_count": 1,
                "reproducibility_gap_count": 0,
                "warnings": ["SYMLINK_TARGET_MISSING"],
            },
            "project_intent": {"status": "UNRESOLVED"},
            "declared_experiment_chains": {
                "complete_bundle_count": 0,
                "incomplete_bundle_count": 0,
            },
            "decision_questions": [],
            "review_attention_items": [
                {
                    "recommendation_type": "REVIEW_EXACT_DUPLICATE",
                    "repository_relative_paths": ["legacy.py"],
                    "limitations": ["EXACT_BYTES_DO_NOT_ESTABLISH_COMMON_PURPOSE"],
                }
            ],
            "run_id": "temporary-report",
        }

        report = render_temporary_audit_report(brief)

        self.assertIn("# 临时审计报告", report)
        self.assertIn("检查重复文件", report)
        self.assertIn("`legacy.py`", report)
        self.assertIn("不会修改仓库", report)
        self.assertIn("符号链接", report)

    def test_html_report_shows_root_folder_size_and_counts(self):
        brief = {
            "audit_scope": {
                "artifact_count": 4,
                "repository_root_realpath": "/tmp/research",
            },
            "observed_evidence": {
                "exact_byte_duplicate_group_count": 0,
                "declaration_observation_count": 0,
            },
            "preservation_risks": {
                "unresolved_artifact_count": 0,
                "reproducibility_gap_count": 0,
                "warnings": [],
            },
            "project_intent": {"status": "SUPPORTED"},
            "declared_experiment_chains": {
                "complete_bundle_count": 0,
                "incomplete_bundle_count": 0,
            },
            "decision_questions": [],
            "review_attention_items": [],
            "run_id": "html-report",
        }
        records = [
            {"repository_relative_path": ".", "object_type": "DIRECTORY", "size_bytes": None},
            {"repository_relative_path": "data", "object_type": "DIRECTORY", "size_bytes": None},
            {"repository_relative_path": "data/results.csv", "object_type": "REGULAR_FILE", "size_bytes": 2_000_000},
            {"repository_relative_path": "data/raw.bin", "object_type": "REGULAR_FILE", "size_bytes": 500_000},
            {"repository_relative_path": "README.md", "object_type": "REGULAR_FILE", "size_bytes": 200},
        ]

        report = render_temporary_audit_html(brief, records, "a" * 64)

        self.assertIn("<!doctype html>", report)
        self.assertIn("data/", report)
        self.assertIn("2.5 MB", report)
        self.assertIn("文件数", report)
        self.assertIn("对象数", report)
        self.assertIn("打印 / 保存为 PDF", report)

    def test_html_report_includes_evidence_questions(self):
        brief = {
            "audit_scope": {"artifact_count": 1, "repository_root_realpath": "/tmp/research"},
            "observed_evidence": {"exact_byte_duplicate_group_count": 0, "declaration_observation_count": 0},
            "preservation_risks": {"unresolved_artifact_count": 1, "reproducibility_gap_count": 0, "warnings": []},
            "project_intent": {"status": "UNRESOLVED"},
            "declared_experiment_chains": {"complete_bundle_count": 0, "incomplete_bundle_count": 0},
            "decision_questions": [{"exact_decision": "确认结果文件是否属于当前主线", "affected_artifacts": ["results.csv"]}],
            "review_attention_items": [],
            "run_id": "question-report",
        }

        report = render_temporary_audit_html(brief, [], "b" * 64)

        self.assertIn("需要确认证据", report)
        self.assertIn("确认结果文件是否属于当前主线", report)

    def test_html_report_rejects_tampered_inventory(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run = root / "runs" / "run-1"
            plan = root / "plans" / "run-1"
            run.mkdir(parents=True)
            plan.mkdir(parents=True)
            inventory = b'{"object_type":"DIRECTORY","repository_relative_path":"."}\n'
            (run / "inventory.jsonl").write_bytes(inventory)
            (run / "run.json").write_text(json.dumps({
                "run_id": "run-1",
                "output_file_hashes": {"inventory.jsonl": hashlib.sha256(inventory).hexdigest()},
            }), encoding="utf-8")
            brief = {
                "audit_scope": {"artifact_count": 1, "repository_root_realpath": "/tmp/research"},
                "observed_evidence": {"exact_byte_duplicate_group_count": 0, "declaration_observation_count": 0},
                "preservation_risks": {"unresolved_artifact_count": 0, "reproducibility_gap_count": 0, "warnings": []},
                "project_intent": {"status": "SUPPORTED"},
                "declared_experiment_chains": {"complete_bundle_count": 0, "incomplete_bundle_count": 0},
                "decision_questions": [], "review_attention_items": [], "run_id": "run-1",
            }
            brief_bytes = json.dumps(brief).encode()
            (plan / "curation-brief.json").write_bytes(brief_bytes)
            (plan / "plan.json").write_text(json.dumps({"curation_brief": {
                "json_file": "curation-brief.json",
                "json_sha256": hashlib.sha256(brief_bytes).hexdigest(),
            }}), encoding="utf-8")
            (run / "inventory.jsonl").write_bytes(b"tampered\n")

            with self.assertRaisesRegex(ValueError, "inventory hash"):
                _temporary_report_for_run(run, Path("report.html"))

    def test_report_command_renders_an_existing_run(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            run = root / "runs" / "run-1"
            plan = root / "plans" / "run-1"
            run.mkdir(parents=True)
            plan.mkdir(parents=True)
            inventory = b'{"object_type":"DIRECTORY","repository_relative_path":"."}\n'
            (run / "inventory.jsonl").write_bytes(inventory)
            (run / "run.json").write_text(json.dumps({
                "run_id": "run-1",
                "output_file_hashes": {"inventory.jsonl": hashlib.sha256(inventory).hexdigest()},
            }), encoding="utf-8")
            brief = {
                "audit_scope": {"artifact_count": 1, "repository_root_realpath": "/tmp/research"},
                "observed_evidence": {"exact_byte_duplicate_group_count": 0, "declaration_observation_count": 0},
                "preservation_risks": {"unresolved_artifact_count": 0, "reproducibility_gap_count": 0, "warnings": []},
                "project_intent": {"status": "SUPPORTED"},
                "declared_experiment_chains": {"complete_bundle_count": 0, "incomplete_bundle_count": 0},
                "decision_questions": [], "review_attention_items": [], "run_id": "run-1",
            }
            brief_bytes = json.dumps(brief).encode()
            (plan / "curation-brief.json").write_bytes(brief_bytes)
            (plan / "plan.json").write_text(json.dumps({"curation_brief": {
                "json_file": "curation-brief.json",
                "json_sha256": hashlib.sha256(brief_bytes).hexdigest(),
            }}), encoding="utf-8")
            output = root / "report.html"

            self.assertEqual(main(["report", "--run-directory", str(run), "--output", str(output)]), 0)
            self.assertIn("临时审计报告", output.read_text(encoding="utf-8"))
