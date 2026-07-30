import unittest

from repo_curator.ro_crate_graph import (
    ENTITY_LIMIT,
    EXTERNAL_ID_LIMIT,
    REFERENCE_LIMIT,
    TYPE_LIMIT,
    UNRESOLVED_ID_LIMIT,
    VALUE_NODE_LIMIT,
    observe_ro_crate_graph,
)


def _crate(*entities):
    return {
        "@context": "https://w3id.org/ro/crate/1.2/context",
        "@graph": list(entities),
    }


def _descriptor(about="./", entity_type="CreativeWork"):
    return {
        "@id": "ro-crate-metadata.json",
        "@type": entity_type,
        "about": {"@id": about},
    }


class RoCrateGraphTest(unittest.TestCase):
    def test_rejects_missing_context_or_non_list_graph(self):
        for parsed in (None, {}, {"@context": {}, "@graph": {}}):
            with self.subTest(parsed=parsed):
                details, limitations = observe_ro_crate_graph(parsed)
                self.assertEqual(details["status"], "UNAVAILABLE")
                self.assertEqual(details["entities"], [])
                self.assertEqual(limitations, ("RO_CRATE_GRAPH_SHAPE_INVALID",))

    def test_reports_each_descriptor_and_root_failure_without_guessing(self):
        cases = (
            (_crate({"@id": "./", "@type": "Dataset"}), "RO_CRATE_DESCRIPTOR_MISSING"),
            (_crate(_descriptor(entity_type="File"), {"@id": "./", "@type": "Dataset"}), "RO_CRATE_DESCRIPTOR_INVALID"),
            (_crate(_descriptor("missing"), {"@id": "./", "@type": "Dataset"}), "RO_CRATE_ROOT_MISSING"),
            (_crate(_descriptor(), {"@id": "./", "@type": "Thing"}), "RO_CRATE_ROOT_INVALID"),
        )
        for parsed, expected in cases:
            with self.subTest(expected=expected):
                details, limitations = observe_ro_crate_graph(parsed)
                self.assertEqual(details["status"], "OBSERVED_WITH_LIMITATIONS")
                self.assertIsNone(details["root_entity_id"])
                self.assertIn(expected, limitations)

    def test_bounds_entities_and_types_and_rejects_malformed_or_duplicate_ids(self):
        entities = [
            _descriptor(),
            {"@id": "./", "@type": [f"Type{index:02d}" for index in range(TYPE_LIMIT + 2)]},
            {"@type": "File"},
            {"@id": "./", "@type": "Dataset"},
        ]
        entities.extend(
            {"@id": f"file-{index}", "@type": "File"}
            for index in range(ENTITY_LIMIT)
        )

        details, limitations = observe_ro_crate_graph(_crate(*entities))

        root = next(item for item in details["entities"] if item["entity_id"] == "./")
        self.assertEqual(len(root["types"]), TYPE_LIMIT)
        self.assertEqual(details["entity_count_in_scope"], ENTITY_LIMIT)
        self.assertIn("RO_CRATE_ENTITY_MALFORMED", limitations)
        self.assertIn("RO_CRATE_DUPLICATE_ENTITY_ID", limitations)
        self.assertIn("RO_CRATE_ENTITY_LIMIT", limitations)

    def test_bounds_reference_records_and_external_and_unresolved_identifier_lists(self):
        external = [
            {"@id": f"https://example.invalid/reference/{index}"}
            for index in range(EXTERNAL_ID_LIMIT + 1)
        ]
        unresolved = [
            {"@id": f"missing-{index}"}
            for index in range(max(REFERENCE_LIMIT, UNRESOLVED_ID_LIMIT) + 1)
        ]
        parsed = _crate(
            _descriptor(),
            {
                "@id": "./",
                "@type": "Dataset",
                "external": external,
                "hasPart": unresolved,
            },
        )

        details, limitations = observe_ro_crate_graph(parsed)

        self.assertEqual(details["reference_count_in_scope"], REFERENCE_LIMIT)
        self.assertEqual(len(details["external_reference_ids"]), EXTERNAL_ID_LIMIT)
        self.assertEqual(len(details["unresolved_reference_ids"]), UNRESOLVED_ID_LIMIT)
        self.assertIn("RO_CRATE_REFERENCE_LIMIT", limitations)
        self.assertIn("RO_CRATE_EXTERNAL_REFERENCE_LIMIT", limitations)
        self.assertIn("RO_CRATE_UNRESOLVED_REFERENCE_LIMIT", limitations)
        self.assertIn("RO_CRATE_EXTERNAL_REFERENCE_NOT_RETRIEVED", limitations)
        self.assertIn("RO_CRATE_REFERENCE_UNRESOLVED", limitations)

    def test_bounds_nested_value_traversal(self):
        parsed = _crate(
            _descriptor(),
            {
                "@id": "./",
                "@type": "Dataset",
                "values": list(range(VALUE_NODE_LIMIT + 1)),
            },
        )

        details, limitations = observe_ro_crate_graph(parsed)

        self.assertEqual(details["status"], "OBSERVED_WITH_LIMITATIONS")
        self.assertIn("RO_CRATE_VALUE_NODE_LIMIT", limitations)


if __name__ == "__main__":
    unittest.main()
