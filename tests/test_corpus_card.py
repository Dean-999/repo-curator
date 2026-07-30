import json
import tempfile
import unittest
from pathlib import Path

from repo_curator.cli import main
from repo_curator.corpus_card import CorpusCardError, build_corpus_card


class CorpusCardTest(unittest.TestCase):
    def test_card_reports_scope_and_archival_identifier_coverage(self):
        registry = self._registry()

        card = build_corpus_card(
            registry, "pilot-1", "2026-07-29T00:00:00Z"
        )

        self.assertEqual(card["schema_version"], "repo-curator.corpus-card.v1")
        self.assertEqual(card["repository_count"], 2)
        self.assertEqual(card["public_repository_count"], 1)
        self.assertEqual(card["private_repository_count"], 1)
        self.assertEqual(
            card["repository_family_counts"],
            {"bioinformatics-workflow": 1, "computational-sensing": 1},
        )
        self.assertEqual(
            card["source_identity_coverage"],
            {
                "git_commit_count": 2,
                "public_archival_identifier_count": 1,
                "swhid_count": 1,
            },
        )
        self.assertEqual(card["admission_authority"], "NONE")
        self.assertTrue(card["limitations"])

    def test_invalid_registry_version_commit_or_swhid_fails_closed(self):
        registry = self._registry()
        registry["schema_version"] = "repo-curator.pilot-snapshot-registry.v2"
        with self.assertRaisesRegex(CorpusCardError, "unsupported"):
            build_corpus_card(registry, "pilot-1", "2026-07-29T00:00:00Z")

        registry = self._registry()
        registry["repositories"][0]["commit_sha"] = "main"
        with self.assertRaisesRegex(CorpusCardError, "commit"):
            build_corpus_card(registry, "pilot-1", "2026-07-29T00:00:00Z")

        registry = self._registry()
        registry["repositories"][0]["swhid"] = "swh:1:rev:not-a-hash"
        with self.assertRaisesRegex(CorpusCardError, "SWHID"):
            build_corpus_card(registry, "pilot-1", "2026-07-29T00:00:00Z")

    def test_cli_publishes_once_and_rejects_overwrite(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            registry = root / "snapshots.json"
            output = root / "corpus-card.json"
            registry.write_text(json.dumps(self._registry()), encoding="utf-8")
            arguments = [
                "corpus-card",
                "--snapshot-registry",
                str(registry),
                "--corpus-id",
                "pilot-1",
                "--created-at",
                "2026-07-29T00:00:00Z",
                "--output",
                str(output),
            ]

            self.assertEqual(main(arguments), 0)
            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8"))["corpus_id"],
                "pilot-1",
            )
            self.assertEqual(main(arguments), 2)

    @staticmethod
    def _registry():
        return {
            "purpose": "source-registry-only",
            "repositories": [
                {
                    "access": "public-mit",
                    "commit_sha": "1" * 40,
                    "repository_family": "bioinformatics-workflow",
                    "repository_id": "workflow",
                    "repository_type": "computational-research",
                    "snapshot_descriptor_path": "snapshots/workflow.json",
                    "snapshot_descriptor_sha256": "sha256:" + "2" * 64,
                    "source_url": "https://example.test/workflow",
                    "swhid": "swh:1:rev:" + "3" * 40,
                },
                {
                    "access": "user-authorized-private",
                    "commit_sha": "4" * 40,
                    "repository_family": "computational-sensing",
                    "repository_id": "private",
                    "repository_type": "computational-research",
                    "snapshot_descriptor_path": "snapshots/private.json",
                    "snapshot_descriptor_sha256": "sha256:" + "5" * 64,
                    "source_url": "https://example.test/private",
                },
            ],
            "schema_version": "repo-curator.pilot-snapshot-registry.v1",
        }
