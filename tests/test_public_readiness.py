import json
import unittest
from pathlib import Path

from repo_curator.cli import _DEFAULT_WAVE3_REPOSITORY_IDS
from repo_curator.wave3 import _DEFAULT_REPOSITORY_IDS


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class PublicReadinessTest(unittest.TestCase):
    def test_pilot_registry_and_wave_defaults_use_public_sources_only(self):
        registry = json.loads(
            (
                REPOSITORY_ROOT
                / "evaluation-corpus"
                / "pilot-2026-07-25"
                / "snapshot-registry.json"
            ).read_text(encoding="utf-8")
        )
        repositories = registry["repositories"]
        public_ids = {item["repository_id"] for item in repositories}

        self.assertEqual(len(repositories), 10)
        self.assertTrue(
            all(item["access"].startswith("public-") for item in repositories)
        )
        self.assertEqual(set(_DEFAULT_REPOSITORY_IDS), public_ids)
        self.assertEqual(set(_DEFAULT_WAVE3_REPOSITORY_IDS), public_ids)

        card = json.loads(
            (
                REPOSITORY_ROOT
                / "evaluation-corpus"
                / "pilot-2026-07-25"
                / "corpus-card.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(card["repository_count"], 10)
        self.assertEqual(card["public_repository_count"], 10)
        self.assertEqual(card["private_repository_count"], 0)

    def test_private_reporting_policy_is_present(self):
        policy = (
            REPOSITORY_ROOT / ".github" / "SECURITY.md"
        ).read_text(encoding="utf-8")
        self.assertIn("private vulnerability reporting", policy)
        self.assertIn("Do not include real credentials", policy)


if __name__ == "__main__":
    unittest.main()
