import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from repo_curator.cli import main
from repo_curator.wave3 import (
    Wave3MaterializationError,
    Wave3SelectionConfig,
    materialize_wave3,
)


class Wave3MaterializationTest(unittest.TestCase):
    def test_cli_materializes_to_a_new_output_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus_root = Path(temporary)
            snapshot_registry, audit_registry = self._frozen_inputs(corpus_root)
            output = corpus_root / "wave-3-pre-review"

            self.assertEqual(main([
                "materialize-wave3",
                "--snapshot-registry", str(snapshot_registry),
                "--audit-run-registry", str(audit_registry),
                "--corpus-root", str(corpus_root),
                "--output", str(output),
                "--created-at", "2026-07-26T14:36:08Z",
                "--repository-ids", "repo-a,repo-b",
                "--inventory-assertions-per-repository", "1",
                "--inventory-extra-repository-count", "0",
                "--controls-per-repository", "1",
            ]), 0)

            self.assertTrue((output / "selection.json").is_file())

    def test_materializes_frozen_positive_and_negative_cases_without_labels(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus_root = Path(temporary)
            snapshot_registry, audit_registry = self._frozen_inputs(corpus_root)
            output = corpus_root / "wave-3-pre-review"
            config = Wave3SelectionConfig(
                repository_ids=("repo-a", "repo-b"),
                inventory_assertions_per_repository=2,
                inventory_extra_repository_count=1,
                controls_per_repository=1,
            )

            materialize_wave3(
                snapshot_registry=snapshot_registry,
                audit_run_registry=audit_registry,
                corpus_root=corpus_root,
                output=output,
                created_at="2026-07-26T14:36:08Z",
                config=config,
            )

            selection = json.loads((output / "selection.json").read_text(encoding="utf-8"))
            self.assertEqual(selection["case_count"], 11)
            self.assertEqual(selection["claim_counts"], {
                "exact_byte_duplicate": 4,
                "inventory_artifact": 7,
            })
            self.assertFalse((output / "labels").exists())

            negative_inventory = json.loads(
                (output / "predictions" / "wave3-inventory-repo-a-control-001.json").read_text(encoding="utf-8")
            )
            expected_inventory = json.loads(
                (output / "expected-labels" / "wave3-inventory-repo-a-control-001.json").read_text(encoding="utf-8")
            )
            self.assertEqual(negative_inventory["prediction"], "ABSTAINED")
            self.assertEqual(expected_inventory["expected_truth"], "UNSUPPORTED")
            self.assertNotIn("UNSUPPORTED", (output / "case-cards" / "wave3-inventory-repo-a-control-001.md").read_text(encoding="utf-8"))

            negative_duplicate = json.loads(
                (output / "predictions" / "wave3-duplicate-repo-b-control-001.json").read_text(encoding="utf-8")
            )
            self.assertEqual(negative_duplicate["prediction"], "ABSTAINED")

    def test_rejects_mismatched_audit_head_before_creating_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus_root = Path(temporary)
            snapshot_registry, audit_registry = self._frozen_inputs(corpus_root, mismatched_head=True)
            output = corpus_root / "wave-3-pre-review"
            config = Wave3SelectionConfig(
                repository_ids=("repo-a", "repo-b"),
                inventory_assertions_per_repository=1,
                inventory_extra_repository_count=0,
                controls_per_repository=1,
            )

            with self.assertRaisesRegex(Wave3MaterializationError, "audit run head"):
                materialize_wave3(
                    snapshot_registry=snapshot_registry,
                    audit_run_registry=audit_registry,
                    corpus_root=corpus_root,
                    output=output,
                    created_at="2026-07-26T14:36:08Z",
                    config=config,
                )

            self.assertFalse(output.exists())

    def test_refuses_to_overwrite_an_existing_wave_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus_root = Path(temporary)
            snapshot_registry, audit_registry = self._frozen_inputs(corpus_root)
            output = corpus_root / "wave-3-pre-review"
            output.mkdir()
            sentinel = output / "sentinel.txt"
            sentinel.write_text("existing evidence", encoding="utf-8")
            config = Wave3SelectionConfig(
                repository_ids=("repo-a", "repo-b"),
                inventory_assertions_per_repository=1,
                inventory_extra_repository_count=0,
                controls_per_repository=1,
            )

            with self.assertRaisesRegex(Wave3MaterializationError, "output already exists"):
                materialize_wave3(
                    snapshot_registry=snapshot_registry,
                    audit_run_registry=audit_registry,
                    corpus_root=corpus_root,
                    output=output,
                    created_at="2026-07-26T14:36:08Z",
                    config=config,
                )

            self.assertEqual(sentinel.read_text(encoding="utf-8"), "existing evidence")

    def test_preserves_all_members_of_a_frozen_duplicate_group(self):
        with tempfile.TemporaryDirectory() as temporary:
            corpus_root = Path(temporary)
            snapshot_registry, audit_registry = self._frozen_inputs(corpus_root, relationship_members=3)
            output = corpus_root / "wave-3-pre-review"
            config = Wave3SelectionConfig(
                repository_ids=("repo-a", "repo-b"),
                inventory_assertions_per_repository=1,
                inventory_extra_repository_count=0,
                controls_per_repository=1,
            )

            materialize_wave3(
                snapshot_registry=snapshot_registry,
                audit_run_registry=audit_registry,
                corpus_root=corpus_root,
                output=output,
                created_at="2026-07-26T14:36:08Z",
                config=config,
            )

            predictions = list((output / "predictions").glob("wave3-duplicate-repo-a-*.json"))
            asserted = next(
                json.loads(path.read_text(encoding="utf-8"))
                for path in predictions
                if json.loads(path.read_text(encoding="utf-8"))["prediction"] == "ASSERTED"
            )
            self.assertEqual(len(asserted["evidence"]["member_artifact_ids"]), 3)

    def _frozen_inputs(self, corpus_root, mismatched_head=False, relationship_members=2):
        artifacts = corpus_root / "artifacts"
        snapshots = artifacts / "repository-snapshots"
        snapshots.mkdir(parents=True)
        audit_runs = artifacts / "audit-runs"
        repository_entries = []
        audit_entries = []
        for index, repository_id in enumerate(("repo-a", "repo-b"), start=1):
            commit = "{}".format(index) * 40
            descriptor = {
                "git_commit_sha": commit,
                "repository_id": repository_id,
                "repository_family": "family-{}".format(index),
                "repository_type": "computational-research",
                "schema_version": "repo-curator.repository-snapshot-descriptor.v1",
            }
            descriptor_path = snapshots / "{}.json".format(repository_id)
            descriptor_path.write_text(json.dumps(descriptor, sort_keys=True), encoding="utf-8")
            descriptor_hash = self._sha256_file(descriptor_path)
            run_id = "run-{}".format(repository_id)
            run_directory = audit_runs / repository_id / run_id
            run_directory.mkdir(parents=True)
            inventory = [
                self._inventory_record(run_id, repository_id, item, "content-{}".format(item))
                for item in range(1, 5)
            ]
            for record in inventory[1:relationship_members]:
                record["content_id"] = inventory[0]["content_id"]
            self._write_json_lines(run_directory / "inventory.jsonl", inventory)
            relationship = {
                "content_id": inventory[0]["content_id"],
                "member_artifact_ids": [record["artifact_id"] for record in inventory[:relationship_members]],
                "relationship_id": "relationship-{}-001".format(repository_id),
                "relationship_type": "EXACT_BYTE_DUPLICATE",
                "run_id": run_id,
                "schema_version": "repo-curator.relationship.v1",
            }
            self._write_json_lines(run_directory / "relationships.jsonl", [relationship])
            run = {
                "git_head": "f" * 40 if mismatched_head and repository_id == "repo-a" else commit,
                "output_file_hashes": {
                    "inventory.jsonl": self._bare_sha256_file(run_directory / "inventory.jsonl"),
                    "relationships.jsonl": self._bare_sha256_file(run_directory / "relationships.jsonl"),
                },
                "run_id": run_id,
                "schema_version": "repo-curator.run.v1",
            }
            run_path = run_directory / "run.json"
            run_path.write_text(json.dumps(run, sort_keys=True), encoding="utf-8")
            repository_entries.append({
                "access": "test",
                "commit_sha": commit,
                "repository_family": descriptor["repository_family"],
                "repository_id": repository_id,
                "repository_type": descriptor["repository_type"],
                "snapshot_descriptor_path": "artifacts/repository-snapshots/{}.json".format(repository_id),
                "snapshot_descriptor_sha256": descriptor_hash,
                "source_url": "https://example.test/{}.git".format(repository_id),
            })
            audit_entries.append({
                "repository_id": repository_id,
                "run_id": run_id,
                "run_path": "artifacts/audit-runs/{}/{}/run.json".format(repository_id, run_id),
                "run_sha256": self._sha256_file(run_path),
                "snapshot_descriptor_sha256": descriptor_hash,
            })
        snapshot_registry = corpus_root / "snapshot-registry.json"
        snapshot_registry.write_text(json.dumps({
            "purpose": "test",
            "repositories": repository_entries,
            "schema_version": "repo-curator.pilot-snapshot-registry.v1",
        }, sort_keys=True), encoding="utf-8")
        audit_registry = corpus_root / "audit-run-registry.json"
        audit_registry.write_text(json.dumps({
            "audit_runs": audit_entries,
            "schema_version": "repo-curator.pilot-audit-run-registry.v1",
        }, sort_keys=True), encoding="utf-8")
        return snapshot_registry, audit_registry

    @staticmethod
    def _inventory_record(run_id, repository_id, item, content):
        return {
            "artifact_id": "art-{}-{:03d}".format(repository_id, item),
            "content_id": "sha256-file-v1:{}".format(content),
            "object_type": "REGULAR_FILE",
            "profile_eligibility": "ELIGIBLE",
            "repository_relative_path": "path-{:03d}.txt".format(item),
            "run_id": run_id,
            "warnings": [],
        }

    @staticmethod
    def _sha256_file(path):
        return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _bare_sha256_file(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    @staticmethod
    def _write_json_lines(path, records):
        path.write_text("".join(json.dumps(record, sort_keys=True) + "\n" for record in records), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
