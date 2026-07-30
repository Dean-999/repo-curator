import json
import os
import tempfile
import unittest
from pathlib import Path

from repo_curator.notebook_envelope import (
    CELL_LIMIT,
    OUTPUT_LIMIT,
    observe_notebook_envelope,
)
from repo_curator.profiles import profile_artifacts


class NotebookEnvelopeTest(unittest.TestCase):
    def test_rejects_truncated_non_json_and_non_object_envelopes(self):
        cases = (
            (b"{}", True, "NOTEBOOK_ENVELOPE_TRUNCATED"),
            (b"{", False, "NOTEBOOK_ENVELOPE_MALFORMED"),
            (b"\xff", False, "NOTEBOOK_ENVELOPE_MALFORMED"),
            (b"[]", False, "NOTEBOOK_ENVELOPE_NOT_OBJECT"),
            (b'{"nbformat":NaN}', False, "NOTEBOOK_ENVELOPE_MALFORMED"),
        )
        for payload, truncated, expected in cases:
            with self.subTest(expected=expected):
                metadata, limitations = observe_notebook_envelope(payload, truncated)
                self.assertEqual(metadata, {})
                self.assertIn(expected, limitations)

    def test_requires_explicit_version_and_v4_cells(self):
        cases = (
            ({"cells": []}, "NOTEBOOK_VERSION_MALFORMED"),
            ({"nbformat": True, "nbformat_minor": 0, "cells": []}, "NOTEBOOK_VERSION_MALFORMED"),
            ({"nbformat": 4, "nbformat_minor": 5, "cells": {}}, "NOTEBOOK_CELLS_MALFORMED"),
        )
        for notebook, expected in cases:
            with self.subTest(expected=expected):
                _, limitations = observe_notebook_envelope(json.dumps(notebook).encode())
                self.assertIn(expected, limitations)

    def test_older_versions_are_retained_without_conversion_or_cell_guessing(self):
        metadata, limitations = observe_notebook_envelope(
            json.dumps({"nbformat": 3, "nbformat_minor": 0, "worksheets": []}).encode()
        )

        self.assertEqual(metadata, {"nbformat": 3, "nbformat_minor": 0})
        self.assertIn("NOTEBOOK_VERSION_UNSUPPORTED_FOR_CELL_SUMMARY", limitations)
        self.assertIn("NOTEBOOK_SCHEMA_NOT_VALIDATED", limitations)

    def test_bounds_cells_outputs_and_declared_metadata_strings(self):
        cells = [
            {
                "cell_type": "code",
                "execution_count": 1,
                "outputs": [
                    {"output_type": "stream"}
                    for _ in range(OUTPUT_LIMIT + 1)
                ],
                "source": ["never persisted"],
            }
        ]
        cells.extend(
            {"cell_type": "unexpected", "source": "never persisted"}
            for _ in range(CELL_LIMIT)
        )
        notebook = {
            "cells": cells,
            "metadata": {
                "kernelspec": {
                    "display_name": "x" * 300,
                    "language": "python",
                    "name": "python3",
                },
                "language_info": {"name": "python", "version": "3.12"},
            },
            "nbformat": 4,
            "nbformat_minor": 5,
        }

        metadata, limitations = observe_notebook_envelope(json.dumps(notebook).encode())

        self.assertEqual(metadata["cell_count"], CELL_LIMIT)
        self.assertEqual(metadata["cell_type_counts"], {"code": 1, "unknown": CELL_LIMIT - 1})
        self.assertEqual(metadata["output_count"], OUTPUT_LIMIT)
        self.assertEqual(metadata["output_type_counts"], {"stream": OUTPUT_LIMIT})
        self.assertNotIn("display_name", metadata["kernel"])
        self.assertIn("NOTEBOOK_CELL_LIMIT", limitations)
        self.assertIn("NOTEBOOK_OUTPUT_LIMIT", limitations)
        self.assertIn("NOTEBOOK_METADATA_STRING_LIMIT", limitations)
        self.assertIn("NOTEBOOK_OUTPUTS_UNTRUSTED_NOT_PERSISTED", limitations)

    def test_unreadable_or_ineligible_notebook_is_not_misclassified_as_malformed(self):
        record = {
            "artifact_id": "notebook-artifact",
            "object_type": "REGULAR_FILE",
            "profile_eligibility": "SKIPPED",
            "repository_relative_path": "large.ipynb",
        }
        descriptor = os.open(".", os.O_RDONLY)
        try:
            profile = profile_artifacts(
                descriptor, [record], "notebook-run", "2026-07-28T00:00:00Z"
            )[0]
        finally:
            os.close(descriptor)

        self.assertEqual(profile["format"], "NOTEBOOK")
        self.assertEqual(profile["metadata"], {})
        self.assertIn("PROFILE_SKIPPED_SIZE_LIMIT", profile["limitations"])
        self.assertNotIn("NOTEBOOK_ENVELOPE_MALFORMED", profile["limitations"])

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            root_fd = os.open(root, os.O_RDONLY)
            try:
                unreadable = {**record, "profile_eligibility": "ELIGIBLE", "repository_relative_path": "missing.ipynb"}
                profile = profile_artifacts(
                    root_fd, [unreadable], "notebook-run", "2026-07-28T00:00:00Z"
                )[0]
            finally:
                os.close(root_fd)
        self.assertIn("PROFILE_UNREADABLE", profile["limitations"])
        self.assertNotIn("NOTEBOOK_ENVELOPE_MALFORMED", profile["limitations"])


if __name__ == "__main__":
    unittest.main()
