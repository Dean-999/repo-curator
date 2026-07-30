import json
import unittest
from pathlib import Path

from repo_curator.declarations import DECLARATION_RULES, DECLARATION_SOURCE_LOCK_IDS


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class DeclarationSourceGovernanceTest(unittest.TestCase):
    def test_every_emitted_declaration_family_has_a_locked_upstream_source(self):
        source_lock = json.loads(
            (REPOSITORY_ROOT / "third_party" / "sources.lock.yaml").read_text(
                encoding="utf-8"
            )
        )
        locked_ids = {entry["id"] for entry in source_lock["entries"]}

        emitted_families = set(DECLARATION_RULES) | {
            "COMPUTATIONAL_ENVIRONMENT",
            "SACRED",
            "WORKFLOW_RUN_RO_CRATE",
        }
        self.assertEqual(set(DECLARATION_SOURCE_LOCK_IDS), emitted_families)
        self.assertTrue(set(DECLARATION_SOURCE_LOCK_IDS.values()).issubset(locked_ids))


if __name__ == "__main__":
    unittest.main()
