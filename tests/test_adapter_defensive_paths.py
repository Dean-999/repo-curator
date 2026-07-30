import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path

from repo_curator import archives, bundle, documents, experiments, relationships


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
RUN_ID = "defensive-run"
CREATED_AT = "2026-07-28T00:00:00Z"


def _inventory(*paths: str) -> list[dict]:
    return [
        {
            "artifact_id": f"artifact-{index}",
            "object_type": "REGULAR_FILE",
            "repository_relative_path": path,
        }
        for index, path in enumerate(paths, start=1)
    ]


class DocumentAdapterDefensivePathTest(unittest.TestCase):
    def test_missing_malformed_and_filtered_document_declarations_are_safe(self):
        self.assertEqual(
            documents.compare_documents(-1, [], RUN_ID, CREATED_AT),
            ([], [], []),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inventory = _inventory("document-manifest.json", "kept.md")
            (root / "document-manifest.json").write_text("{", encoding="utf-8")
            with self._root_fd(root) as root_fd:
                self.assertEqual(
                    documents.compare_documents(root_fd, inventory, RUN_ID, CREATED_AT),
                    ([], [], ["DOCUMENT_MANIFEST_MALFORMED"]),
                )

            (root / "document-manifest.json").write_text(
                json.dumps(
                    {
                        "documents": [
                            {"path": "missing.md", "topic": "ignored"},
                            {"path": "kept.md", "topic": ""},
                            {"path": "kept.md", "topic": "analysis"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with self._root_fd(root) as root_fd:
                comparisons, entries, warnings = documents.compare_documents(
                    root_fd, inventory, RUN_ID, CREATED_AT
                )
            self.assertEqual((comparisons, entries, warnings), ([], [], []))

    def test_document_proposals_distinguish_non_conflict_review_cases(self):
        declared = [
            {"path": "a.md", "topic": "analysis", "audience": "researchers", "lifecycle": "CURRENT", "canonical_entry": True},
            {"path": "b.md", "topic": "analysis", "audience": "researchers", "lifecycle": "CURRENT"},
            {"path": "c.md", "topic": "analysis", "audience": "researchers", "lifecycle": "HISTORICAL"},
            {"path": "d.md", "topic": "analysis", "audience": "auditors", "lifecycle": "HISTORICAL", "role": "AUDIT_RECORD"},
        ]
        inventory = {item["repository_relative_path"]: item for item in _inventory(*(item["path"] for item in declared))}

        comparisons = documents._comparisons(declared, inventory, RUN_ID, CREATED_AT)
        by_paths = {tuple(item["document_paths"]): item for item in comparisons}
        self.assertEqual(by_paths[("a.md", "b.md")]["candidate_subtype"], "MANUAL_REVIEW")
        self.assertEqual(by_paths[("a.md", "c.md")]["candidate_subtype"], "PARTIAL_MERGE_CANDIDATE")
        self.assertEqual(by_paths[("a.md", "d.md")]["candidate_subtype"], "CANONICALIZE_WITHOUT_MERGE")
        self.assertTrue(all(not item["conflicting_fields"] for item in comparisons))
        entries = documents._entries(declared, inventory, RUN_ID, CREATED_AT)
        self.assertEqual(entries[0]["retained_record_paths"], ["b.md", "c.md", "d.md"])

    class _root_fd:
        def __init__(self, root: Path):
            self.root = root

        def __enter__(self) -> int:
            self.descriptor = os.open(self.root, os.O_RDONLY)
            return self.descriptor

        def __exit__(self, exc_type, exc_value, traceback) -> None:
            os.close(self.descriptor)


class ExperimentAdapterDefensivePathTest(unittest.TestCase):
    def test_experiment_adapter_fails_closed_without_manifest_evidence(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inventory = _inventory("experiment-manifest.json")
            (root / "experiment-manifest.json").write_text(
                json.dumps({"attempts": []}),
                encoding="utf-8",
            )

            with DocumentAdapterDefensivePathTest._root_fd(root) as root_fd:
                with self.assertRaisesRegex(
                    ValueError,
                    "EXPERIMENT_MANIFEST_EVIDENCE_UNAVAILABLE",
                ):
                    experiments.reconstruct_experiments(
                        root_fd,
                        inventory,
                        {},
                        RUN_ID,
                        CREATED_AT,
                    )

    def test_experiment_adapter_preserves_gaps_for_invalid_duplicate_and_missing_declarations(self):
        self.assertEqual(
            experiments.reconstruct_experiments(-1, [], {}, RUN_ID, CREATED_AT),
            ([], [], [], [], []),
        )
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            paths = (
                "experiment-manifest.json", "output.json", "input.csv", "config.json",
                "train.py", "validation.txt", "review.txt",
            )
            inventory = _inventory(*paths)
            evidence_by_artifact_id = {
                inventory[0]["artifact_id"]: "evidence-manifest"
            }
            (root / "experiment-manifest.json").write_text("[]", encoding="utf-8")
            with DocumentAdapterDefensivePathTest._root_fd(root) as root_fd:
                result = experiments.reconstruct_experiments(
                    root_fd,
                    inventory,
                    evidence_by_artifact_id,
                    RUN_ID,
                    CREATED_AT,
                )
            self.assertEqual(result, ([], [], [], [], ["EXPERIMENT_MANIFEST_MALFORMED"]))

            (root / "experiment-manifest.json").write_text(
                json.dumps(
                    {
                        "attempts": [
                            "not-an-object",
                            {"id": "trial", "experiment": "e", "result": "ACCEPTED", "output": "output.json"},
                            {"id": "trial", "experiment": "e", "result": "FAILED", "output": "output.json"},
                            {
                                "id": "complete", "experiment": "e", "result": "PARTIAL", "output": "output.json",
                                "inputs": "input.csv", "configuration": "config.json", "generator": "train.py",
                                "validation": "validation.txt", "reviewer_record": "review.txt", "canonical_candidate": False,
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            with DocumentAdapterDefensivePathTest._root_fd(root) as root_fd:
                attempts, bundles, candidates, gaps, warnings = experiments.reconstruct_experiments(
                    root_fd,
                    inventory,
                    evidence_by_artifact_id,
                    RUN_ID,
                    CREATED_AT,
                )
            self.assertEqual(warnings, [])
            self.assertEqual([item["attempt_id"] for item in attempts], ["trial", "complete"])
            self.assertEqual(candidates, [])
            self.assertEqual(bundles[0]["completeness"], "MISSING_REQUIRED_LINK")
            self.assertEqual(bundles[1]["completeness"], "COMPLETE_IN_ANALYZED_SCOPE")
            self.assertEqual(
                [item["missing_or_unresolved"] for item in gaps],
                [["EXPERIMENT_ATTEMPT_MALFORMED"], ["configuration", "generator", "inputs", "reviewer_record", "validation"], ["EXPERIMENT_ATTEMPT_DUPLICATE_ID"]],
            )


class RelationshipAdapterDefensivePathTest(unittest.TestCase):
    def test_manifest_absence_and_invalid_manifest_keep_relationship_coverage_conservative(self):
        inventory = _inventory("entry.py")
        observations = [{"observation_type": "GIT_COMMIT", "changed_paths": ["entry.py"], "commit_id": "a" * 40}]
        episodes, families, roles, coverage, warnings = relationships.build_relationship_candidates(
            -1, inventory, RUN_ID, CREATED_AT, observations
        )
        self.assertEqual((episodes, families), ([], []))
        self.assertEqual(roles[0]["role"], "UNRESOLVED")
        self.assertEqual(coverage["change_episode"]["status"], "AVAILABLE_GIT_COCHANGE_ONLY")
        self.assertIn("NO_MULTI_ARTIFACT_CURRENT_COCHANGE", warnings)

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "relationship-manifest.json").write_text("{", encoding="utf-8")
            inventory = _inventory("relationship-manifest.json", "entry.py")
            with DocumentAdapterDefensivePathTest._root_fd(root) as root_fd:
                _, families, _, coverage, warnings = relationships.build_relationship_candidates(
                    root_fd, inventory, RUN_ID, CREATED_AT
                )
            self.assertEqual(families, [])
            self.assertEqual(coverage["capability_family"]["status"], "UNAVAILABLE")
            self.assertIn("RELATIONSHIP_MANIFEST_MALFORMED", warnings)

    def test_declared_and_syntax_evidence_are_never_conflated(self):
        inventory = _inventory("a.py", "b.py", "c.py", "ignored.py")
        declared = [
            {"path": "a.py", "episode": "event", "responsibility": "score", "role": "ACTIVE_MAINLINE"},
            {"path": "b.py", "episode": "event", "responsibility": "score", "role": "REQUIRED_COMPATIBILITY"},
            {"path": "c.py", "episode": "solo", "responsibility": "solo", "role": "INVALID"},
        ]
        inventory_by_path = {item["repository_relative_path"]: item for item in inventory}
        evidence = {"artifact-1": "evidence-a", "artifact-2": "evidence-b", "structure-a": "evidence-structure"}
        episodes = relationships._episodes(declared, inventory_by_path, RUN_ID, CREATED_AT, evidence)
        families = relationships._families(declared, inventory_by_path, RUN_ID, CREATED_AT, evidence)
        self.assertEqual(episodes[0]["supporting_evidence_ids"], ["evidence-a", "evidence-b"])
        self.assertEqual(families[0]["member_paths"], ["a.py", "b.py"])
        roles = relationships._roles(
            inventory, declared, RUN_ID, CREATED_AT,
            [{"repository_relative_path": "ignored.py", "has_main_guard": True, "structure_id": "structure-a"}],
            [{"repository_relative_path": "ignored.py", "status": "ACTIVE_MAINLINE", "supporting_evidence_ids": ["intent-evidence"]}],
            evidence,
        )
        by_path = {item["repository_relative_path"]: item for item in roles}
        self.assertEqual(by_path["a.py"]["role"], "ACTIVE_MAINLINE")
        self.assertEqual(by_path["ignored.py"]["role"], "ACTIVE_MAINLINE")
        self.assertEqual(by_path["ignored.py"]["limitations"], ["PYTHON_SYNTAX_NOT_RUNTIME_BEHAVIOR"])
        self.assertEqual(by_path["c.py"]["role"], "UNRESOLVED")

    def test_valid_manifest_joins_declared_candidates_without_authorizing_execution(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "relationship-manifest.json").write_text(
                json.dumps(
                    {
                        "artifacts": [
                            {"path": "a.py", "episode": "declared-event", "responsibility": "score", "role": "ACTIVE_MAINLINE"},
                            {"path": "b.py", "episode": "declared-event", "responsibility": "score", "role": "REQUIRED_COMPATIBILITY"},
                            {"path": "not-in-inventory.py", "episode": "ignored"},
                        ]
                    }
                ),
                encoding="utf-8",
            )
            inventory = _inventory("relationship-manifest.json", "a.py", "b.py")
            with DocumentAdapterDefensivePathTest._root_fd(root) as root_fd:
                episodes, families, roles, coverage, warnings = relationships.build_relationship_candidates(
                    root_fd,
                    inventory,
                    RUN_ID,
                    CREATED_AT,
                    evidence_by_source_id={"artifact-2": "evidence-a", "artifact-3": "evidence-b"},
                )
        self.assertEqual(episodes[0]["event_evidence"], "declared-event")
        self.assertEqual(families[0]["responsibility"], "score")
        self.assertEqual([item["role"] for item in roles], ["UNRESOLVED", "ACTIVE_MAINLINE", "REQUIRED_COMPATIBILITY"])
        self.assertEqual(coverage["capability_family"]["status"], "AVAILABLE_DECLARED_ONLY")
        self.assertEqual(coverage["change_episode"]["status"], "AVAILABLE_DECLARED_ONLY")
        self.assertIn("CHANGE_EPISODE_DECLARED_ONLY", warnings)


class BundleGovernanceDefensivePathTest(unittest.TestCase):
    def test_repository_governance_material_is_validated_and_hash_helpers_are_deterministic(self):
        source_lock, notices = bundle._validate_source_governance(REPOSITORY_ROOT)
        registry = bundle._validate_schema_registry(REPOSITORY_ROOT)
        self.assertTrue(source_lock)
        self.assertTrue(notices)
        self.assertTrue(registry)
        self.assertEqual(bundle._canonical_json({"b": 1, "a": 2}), b'{"a":2,"b":1}\n')
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "second.txt").write_text("second\n", encoding="utf-8")
            (root / "nested").mkdir()
            (root / "nested" / "first.txt").write_text("first\n", encoding="utf-8")
            (root / "manifest.json").write_text("ignored\n", encoding="utf-8")
            self.assertEqual(
                list(bundle._hash_bundle_files(root)),
                ["nested/first.txt", "second.txt"],
            )

    def test_bundle_build_copies_a_self_contained_non_overwriting_skill(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            output = Path(temporary_directory) / "repo-curator"
            self.assertEqual(
                bundle.build_skill_bundle(REPOSITORY_ROOT, output), output.resolve()
            )
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["skill_name"], "repo-curator")
            self.assertTrue((output / "scripts" / "repo_curator" / "inventory.py").is_file())
            self.assertTrue((output / "SKILL.md").is_file())
            self.assertEqual(
                manifest["files"]["SKILL.md"],
                bundle._hash_bundle_files(output)["SKILL.md"],
            )


class ArchiveAdapterDefensivePathTest(unittest.TestCase):
    def test_archive_adapter_observes_without_extracting_and_rejects_unsafe_members(self):
        self.assertEqual(archives._archive_kind(b"PK\x03\x04"), "ZIP")
        self.assertEqual(archives._archive_kind(b"7z\xbc\xaf\x27\x1c"), "7Z")
        self.assertEqual(archives._archive_kind(b"Rar!\x1a\x07"), "RAR")
        self.assertIsNone(archives._archive_kind(b"plain text"))
        self.assertTrue(archives._safe_name("nested/result.txt"))
        self.assertFalse(archives._safe_name("../escape.txt"))
        self.assertFalse(archives._safe_name("C:/escape.txt"))

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            with zipfile.ZipFile(root / "safe.zip", "w") as archive:
                archive.writestr("nested/result.txt", "result\n")
            with zipfile.ZipFile(root / "unsafe.zip", "w") as archive:
                archive.writestr("../escape.txt", "never extracted\n")
            # The adapter checks the magic number only and leaves unsupported archives opaque.
            tar_header = bytearray(512)
            tar_header[257:262] = b"ustar"
            (root / "opaque.tar").write_bytes(tar_header)
            (root / "plain.txt").write_text("not an archive\n", encoding="utf-8")
            records = [
                {"artifact_id": "safe", "object_type": "REGULAR_FILE", "profile_eligibility": "ELIGIBLE", "repository_relative_path": "safe.zip"},
                {"artifact_id": "unsafe", "object_type": "REGULAR_FILE", "profile_eligibility": "ELIGIBLE", "repository_relative_path": "unsafe.zip"},
                {"artifact_id": "tar", "object_type": "REGULAR_FILE", "profile_eligibility": "ELIGIBLE", "repository_relative_path": "opaque.tar"},
                {"artifact_id": "plain", "object_type": "REGULAR_FILE", "profile_eligibility": "ELIGIBLE", "repository_relative_path": "plain.txt"},
                {"artifact_id": "skipped", "object_type": "REGULAR_FILE", "profile_eligibility": "SKIPPED", "repository_relative_path": "safe.zip"},
            ]
            with DocumentAdapterDefensivePathTest._root_fd(root) as root_fd:
                observations = archives.inspect_archives(root_fd, records, RUN_ID, CREATED_AT)
            by_path = {item["repository_relative_path"]: item for item in observations}
            self.assertEqual(by_path["safe.zip"]["status"], "INSPECTED")
            self.assertEqual(by_path["safe.zip"]["member_count"], 1)
            self.assertEqual(by_path["unsafe.zip"]["limitations"], ["ARCHIVE_PATH_UNSAFE"])
            self.assertEqual(by_path["opaque.tar"]["status"], "OPAQUE")
            self.assertEqual(by_path["opaque.tar"]["limitations"], ["UNSUPPORTED_FORMAT"])
            self.assertNotIn("plain.txt", by_path)
            self.assertFalse((root / "escape.txt").exists())


if __name__ == "__main__":
    unittest.main()
