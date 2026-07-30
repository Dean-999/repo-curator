import json
import tempfile
import unittest
from pathlib import Path

from repo_curator.cli import main
from repo_curator.ro_crate_validation import (
    MAX_INPUT_BYTES,
    RoCrateValidationError,
    read_evidence_crate,
    validate_evidence_crate,
)


def _crate(root_overrides=None, extra_entities=()):
    root = {
        "@id": "./",
        "@type": ["Dataset"],
        "conformsTo": [
            {
                "@id": "https://github.com/Dean-999/repo-curator/tree/main/"
                "docs/profiles/evidence-v1"
            }
        ],
        "repo-curator:executionAuthorized": False,
        "repo-curator:exportSchemaVersion": "repo-curator.ro-crate-export.v1",
    }
    root.update(root_overrides or {})
    return {
        "@context": [
            "https://w3id.org/ro/crate/1.1/context",
            {
                "repo-curator": "https://github.com/Dean-999/repo-curator#"
            },
        ],
        "@graph": [
            {
                "@id": "ro-crate-metadata.json",
                "@type": ["CreativeWork"],
                "about": {"@id": "./"},
                "conformsTo": [{"@id": "https://w3id.org/ro/crate/1.1"}],
            },
            root,
            *extra_entities,
        ],
    }


class RoCrateValidationTest(unittest.TestCase):
    def test_conforming_export_reports_bounded_scope_without_claiming_full_shacl(self):
        report = validate_evidence_crate(_crate(), "a" * 64)

        self.assertEqual(
            report["schema_version"], "repo-curator.ro-crate-validation-report.v1"
        )
        self.assertEqual(report["status"], "BOUNDED_PROFILE_CONFORMANT")
        self.assertEqual(report["input_sha256"], "a" * 64)
        self.assertFalse(report["full_shacl_conformance_claimed"])
        self.assertFalse(report["shacl_engine_used"])
        self.assertEqual(report["findings"], [])
        self.assertEqual(report["execution_authority"], "NONE")

    def test_execution_authority_wrong_schema_and_missing_reference_fail(self):
        parsed = _crate(
            {
                "repo-curator:executionAuthorized": True,
                "repo-curator:exportSchemaVersion": "repo-curator.ro-crate-export.v2",
                "hasPart": [{"@id": "missing.txt"}],
            }
        )

        report = validate_evidence_crate(parsed, "b" * 64)

        self.assertEqual(report["status"], "NONCONFORMANT")
        self.assertEqual(
            [finding["code"] for finding in report["findings"]],
            [
                "EXECUTION_AUTHORITY_NOT_FALSE",
                "EXPORT_SCHEMA_UNSUPPORTED",
                "LOCAL_REFERENCE_UNRESOLVED",
            ],
        )

    def test_observer_budget_limit_makes_result_incomplete(self):
        parsed = _crate(
            extra_entities=tuple(
                {"@id": "file-{}".format(index), "@type": "File"}
                for index in range(300)
            )
        )

        report = validate_evidence_crate(parsed, "c" * 64)

        self.assertEqual(report["status"], "INCOMPLETE")
        self.assertIn("RO_CRATE_ENTITY_LIMIT", report["limitations"])
        self.assertFalse(report["admission_authority"])

    def test_cli_is_bounded_nofollow_and_create_once(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            source = directory / "ro-crate-metadata.json"
            output = directory / "validation.json"
            source.write_text(json.dumps(_crate()), encoding="utf-8")

            self.assertEqual(
                main(
                    [
                        "validate-ro-crate",
                        "--input",
                        str(source),
                        "--output",
                        str(output),
                    ]
                ),
                0,
            )
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))["status"],
                "BOUNDED_PROFILE_CONFORMANT",
            )
            self.assertEqual(
                main(
                    [
                        "validate-ro-crate",
                        "--input",
                        str(source),
                        "--output",
                        str(output),
                    ]
                ),
                2,
            )

            linked = directory / "linked.json"
            linked.symlink_to(source)
            self.assertEqual(
                main(
                    [
                        "validate-ro-crate",
                        "--input",
                        str(linked),
                        "--output",
                        str(directory / "linked-report.json"),
                    ]
                ),
                2,
            )
            self.assertFalse((directory / "linked-report.json").exists())

    def test_reader_rejects_duplicate_keys_and_oversized_input(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            duplicate = directory / "duplicate.json"
            duplicate.write_text('{"@context":[],"@context":[],"@graph":[]}', encoding="utf-8")
            with self.assertRaisesRegex(RoCrateValidationError, "unique-key"):
                read_evidence_crate(duplicate)

            oversized = directory / "oversized.json"
            oversized.write_bytes(b" " * (MAX_INPUT_BYTES + 1))
            with self.assertRaisesRegex(RoCrateValidationError, "byte limit"):
                read_evidence_crate(oversized)


if __name__ == "__main__":
    unittest.main()
