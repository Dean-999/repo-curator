"""Deterministic evidence records and exact-byte duplicate relationships."""

from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


EVIDENCE_SCHEMA_VERSION = "repo-curator.evidence.v1"
EVIDENCE_PROFILE_URI = "https://github.com/Dean-999/repo-curator/tree/main/docs/profiles/evidence-v1"
RELATIONSHIP_SCHEMA_VERSION = "repo-curator.relationship.v2"
_FILE_FINGERPRINT_SCHEME = "sha256-file-v1"


def build_evidence_graph(
    inventory_records: Sequence[Dict[str, Any]],
    declaration_observations: Sequence[Dict[str, Any]],
    git_observations: Sequence[Dict[str, Any]],
    profiles: Sequence[Dict[str, Any]],
    archive_observations: Sequence[Dict[str, Any]],
    structural_observations: Sequence[Dict[str, Any]],
    run_id: str,
    created_at: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return provenance-preserving evidence and only exact-byte relationships."""
    candidates = []
    candidates.extend(
        _inventory_candidates(inventory_records, run_id, created_at)
    )
    candidates.extend(
        _observation_candidates(
            declaration_observations,
            "DECLARATION",
            "DECLARED",
            "repo_curator.declarations.detect_declarations",
            run_id,
            created_at,
        )
    )
    candidates.extend(
        _observation_candidates(
            git_observations,
            "GIT",
            "OBSERVED",
            "repo_curator.git_evidence.collect_git_evidence",
            run_id,
            created_at,
        )
    )
    candidates.extend(
        _observation_candidates(
            profiles,
            "PROFILE",
            "OBSERVED",
            "repo_curator.profiles.profile_artifacts",
            run_id,
            created_at,
        )
    )
    candidates.extend(
        _observation_candidates(
            archive_observations,
            "ARCHIVE",
            "OBSERVED",
            "repo_curator.archives.inspect_archives",
            run_id,
            created_at,
        )
    )
    candidates.extend(
        _observation_candidates(
            structural_observations,
            "PYTHON_STRUCTURE",
            "OBSERVED",
            "repo_curator.structural.observe_python_structure",
            run_id,
            created_at,
        )
    )

    evidence: List[Dict[str, Any]] = []
    evidence_by_artifact_id: Dict[str, str] = {}
    for sequence, candidate in enumerate(sorted(candidates, key=_candidate_key), start=1):
        record = {
            "assertion_origin": candidate["assertion_origin"],
            "counter_evidence_ids": [],
            "conforms_to": [EVIDENCE_PROFILE_URI],
            "created_at": created_at,
            "evidence_id": f"evidence_{run_id}_{sequence:08d}",
            "extractor": candidate["extractor"],
            "limitations": sorted(set(candidate["limitations"])),
            "run_id": run_id,
            "schema_version": EVIDENCE_SCHEMA_VERSION,
            "scope": candidate["scope"],
            "source": {
                "record_id": candidate["source_record_id"],
                "type": candidate["source_type"],
            },
            "source_record_id": candidate["source_record_id"],
            "source_type": candidate["source_type"],
            "subject": candidate["subject"],
        }
        evidence.append(record)
        artifact_id = record["subject"].get("artifact_id")
        if record["source_type"] == "INVENTORY" and artifact_id is not None:
            evidence_by_artifact_id[artifact_id] = record["evidence_id"]
    return evidence, _exact_byte_relationships(
        inventory_records, evidence_by_artifact_id, run_id, created_at
    )


def _inventory_candidates(
    records: Iterable[Dict[str, Any]], run_id: str, created_at: str
) -> Iterable[Dict[str, Any]]:
    del run_id, created_at
    for record in records:
        yield {
            "assertion_origin": "DETERMINISTIC",
            "extractor": "repo_curator.inventory._inventory_records",
            "limitations": record["warnings"],
            "scope": "FILESYSTEM_ARTIFACT",
            "source_record_id": record["artifact_id"],
            "source_type": "INVENTORY",
            "subject": {
                "artifact_id": record["artifact_id"],
                "content_id": record["content_id"],
                "location_id": record["location_id"],
            },
        }


def _observation_candidates(
    observations: Iterable[Dict[str, Any]],
    source_type: str,
    assertion_origin: str,
    extractor: str,
    run_id: str,
    created_at: str,
) -> Iterable[Dict[str, Any]]:
    del run_id, created_at
    for observation in observations:
        source_record_id = (
            observation.get("observation_id")
            or observation.get("profile_id")
            or observation.get("structure_id")
        )
        if source_record_id is None:
            source_record_id = observation.get("evidence_id", "unidentified-observation")
        subject = {
            key: observation[key]
            for key in ("artifact_id", "repository_relative_path", "source_artifact_id", "source_location_id")
            if key in observation
        }
        yield {
            "assertion_origin": observation.get("assertion_origin", assertion_origin),
            "extractor": extractor,
            "limitations": observation.get("limitations", []),
            "scope": observation.get("coverage", "OBSERVATION_ONLY"),
            "source_record_id": source_record_id,
            "source_type": source_type,
            "subject": subject,
        }


def _candidate_key(candidate: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        candidate["source_type"],
        candidate["source_record_id"],
        candidate["assertion_origin"],
    )


def _exact_byte_relationships(
    inventory_records: Iterable[Dict[str, Any]],
    evidence_by_artifact_id: Mapping[str, str],
    run_id: str,
    created_at: str,
) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for record in inventory_records:
        if (
            record["object_type"] == "REGULAR_FILE"
            and record["fingerprint_scheme"] == _FILE_FINGERPRINT_SCHEME
            and record["fingerprint"] is not None
        ):
            groups.setdefault(record["content_id"], []).append(record)
    relationships = []
    for content_id, group in sorted(groups.items()):
        if len(group) < 2:
            continue
        ordered_group = sorted(group, key=lambda item: item["artifact_id"])
        relationships.append(
            {
                "assertion_origin": "DETERMINISTIC",
                "content_id": content_id,
                "counter_evidence_ids": [],
                "created_at": created_at,
                "limitations": [
                    "EQUAL_BYTES_DO_NOT_ESTABLISH_COMMON_LINEAGE_OR_PURPOSE"
                ],
                "member_artifact_ids": [item["artifact_id"] for item in ordered_group],
                "relationship_id": f"relationship_{run_id}_{len(relationships) + 1:08d}",
                "relationship_shape": "ARTIFACT_GROUP",
                "relationship_type": "EXACT_BYTE_DUPLICATE",
                "run_id": run_id,
                "schema_version": RELATIONSHIP_SCHEMA_VERSION,
                "supporting_evidence_ids": [
                    evidence_by_artifact_id[item["artifact_id"]] for item in ordered_group
                ],
            }
        )
    return relationships


def build_declared_experiment_relationships(
    bundles: Sequence[Mapping[str, Any]], run_id: str, created_at: str
) -> List[Dict[str, Any]]:
    """Project inventory-resolved manifest members into declared-only edges."""
    relationships = []
    for bundle in sorted(bundles, key=lambda item: item["bundle_id"]):
        for member in sorted(
            bundle["members"],
            key=lambda item: (item["role"], item["declared_path"]),
        ):
            artifact_id = member["artifact_id"]
            if artifact_id is None:
                continue
            relationships.append(
                {
                    "assertion_origin": "DECLARED",
                    "counter_evidence_ids": [],
                    "created_at": created_at,
                    "declared_path": member["declared_path"],
                    "limitations": ["DECLARED_LINEAGE_NOT_EXECUTION_VERIFIED"],
                    "relationship_id": (
                        f"relationship_{run_id}_declared_{len(relationships) + 1:08d}"
                    ),
                    "relationship_shape": "DIRECTED_EDGE",
                    "relationship_type": f"DECLARED_{member['role']}",
                    "run_id": run_id,
                    "schema_version": RELATIONSHIP_SCHEMA_VERSION,
                    "source": {
                        "entity_id": bundle["attempt_id"],
                        "entity_type": "EXPERIMENT_ATTEMPT",
                    },
                    "supporting_evidence_ids": list(
                        bundle["supporting_evidence_ids"]
                    ),
                    "target": {
                        "entity_id": artifact_id,
                        "entity_type": "ARTIFACT",
                    },
                }
            )
    return relationships
