"""Read declared experiment attempts without executing repository workflows."""

import json
import os
import stat
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


ATTEMPT_SCHEMA_VERSION = "repo-curator.experiment-attempt.v2"
BUNDLE_SCHEMA_VERSION = "repo-curator.experiment-bundle.v2"
CANDIDATE_SCHEMA_VERSION = "repo-curator.canonical-result-candidate.v2"
GAP_SCHEMA_VERSION = "repo-curator.reproducibility-gap.v2"
MANIFEST_NAME = "experiment-manifest.json"
_READ_LIMIT = 1024 * 1024
_REQUIRED_BUNDLE_FIELDS = ("inputs", "configuration", "generator", "validation", "reviewer_record")


def reconstruct_experiments(
    root_fd: int,
    inventory_records: Sequence[Dict[str, Any]],
    evidence_by_artifact_id: Mapping[str, str],
    run_id: str,
    created_at: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    """Build conservative lineage records from a bounded local manifest only."""
    inventory = {record["repository_relative_path"]: record for record in inventory_records}
    if MANIFEST_NAME not in inventory:
        return [], [], [], [], []
    manifest_record = inventory[MANIFEST_NAME]
    manifest_evidence_id = evidence_by_artifact_id.get(manifest_record["artifact_id"])
    if manifest_evidence_id is None:
        raise ValueError("EXPERIMENT_MANIFEST_EVIDENCE_UNAVAILABLE")
    try:
        manifest = _read_manifest(root_fd)
    except ValueError as error:
        return [], [], [], [], [str(error)]
    raw_attempts = manifest.get("attempts")
    if not isinstance(raw_attempts, list):
        return [], [], [], [], ["EXPERIMENT_MANIFEST_MALFORMED"]
    attempts = []
    bundles = []
    candidates = []
    gaps = []
    known_ids = set()
    for raw in raw_attempts:
        if not isinstance(raw, dict) or not _valid_attempt(raw):
            gaps.append(
                _gap(
                    run_id,
                    created_at,
                    "unknown",
                    ["EXPERIMENT_ATTEMPT_MALFORMED"],
                    manifest_evidence_id,
                )
            )
            continue
        attempt_id = raw["id"]
        if attempt_id in known_ids:
            gaps.append(
                _gap(
                    run_id,
                    created_at,
                    attempt_id,
                    ["EXPERIMENT_ATTEMPT_DUPLICATE_ID"],
                    manifest_evidence_id,
                )
            )
            continue
        known_ids.add(attempt_id)
        output_path = raw["output"]
        attempt = {
            "attempt_id": attempt_id,
            "counter_evidence_ids": [],
            "created_at": created_at,
            "declared_by_artifact_id": manifest_record["artifact_id"],
            "experiment_id": raw["experiment"],
            "limitations": ["DECLARED_LINEAGE_NOT_EXECUTION_VERIFIED"],
            "output_artifact_id": inventory.get(output_path, {}).get("artifact_id"),
            "output_path": output_path,
            "result": raw["result"],
            "retry_of": raw.get("retry_of"),
            "run_id": run_id,
            "schema_version": ATTEMPT_SCHEMA_VERSION,
            "supporting_evidence_ids": [manifest_evidence_id],
        }
        attempts.append(attempt)
        bundle, bundle_gaps = _bundle(
            raw,
            inventory,
            manifest_evidence_id,
            run_id,
            created_at,
        )
        bundles.append(bundle)
        gaps.extend(bundle_gaps)
        if raw.get("canonical_candidate") is True:
            candidates.append(
                {
                    "attempt_id": attempt_id,
                    "candidate_id": f"canonical_candidate_{run_id}_{len(candidates) + 1:08d}",
                    "counter_evidence_ids": [],
                    "created_at": created_at,
                    "executable_in_supported_scope": False,
                    "governance_state": "CANDIDATE",
                    "limitations": ["DECLARED_CANDIDATE_NOT_CANONICAL_CONFIRMATION"],
                    "output_path": output_path,
                    "run_id": run_id,
                    "schema_version": CANDIDATE_SCHEMA_VERSION,
                    "supporting_evidence_ids": [manifest_evidence_id],
                }
            )
    return attempts, bundles, candidates, gaps, []


def _valid_attempt(value: Dict[str, Any]) -> bool:
    return (
        all(isinstance(value.get(field), str) and value[field] for field in ("id", "experiment", "result", "output"))
        and value["result"] in {"ACCEPTED", "FAILED", "INCONCLUSIVE", "PARTIAL"}
        and ("retry_of" not in value or isinstance(value["retry_of"], str))
        and ("canonical_candidate" not in value or isinstance(value["canonical_candidate"], bool))
        and all(isinstance(value[field], (str, list)) for field in _REQUIRED_BUNDLE_FIELDS if field in value)
    )


def _bundle(
    attempt: Dict[str, Any],
    inventory: Dict[str, Dict[str, Any]],
    manifest_evidence_id: str,
    run_id: str,
    created_at: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    member_specs = [("OUTPUT", attempt["output"])]
    unresolved = []
    role_by_field = {
        "inputs": "INPUT",
        "configuration": "CONFIGURATION",
        "generator": "GENERATOR",
        "validation": "VALIDATION",
        "reviewer_record": "REVIEWER_RECORD",
    }
    for field in _REQUIRED_BUNDLE_FIELDS:
        value = attempt.get(field)
        values = value if isinstance(value, list) else [value] if isinstance(value, str) else []
        if not values:
            unresolved.append(field)
        else:
            member_specs.extend((role_by_field[field], path) for path in values)
    members = [path for _, path in member_specs]
    missing = [path for path in members if path not in inventory]
    unresolved.extend(missing)
    completeness = "COMPLETE_IN_ANALYZED_SCOPE" if not unresolved else "MISSING_REQUIRED_LINK"
    bundle = {
        "attempt_id": attempt["id"],
        "bundle_id": f"bundle_{run_id}_{attempt['id']}",
        "counter_evidence_ids": [],
        "created_at": created_at,
        "completeness": completeness,
        "member_artifact_ids": [inventory[path]["artifact_id"] for path in members if path in inventory],
        "member_paths": sorted(set(members)),
        "members": [
            {
                "artifact_id": inventory.get(path, {}).get("artifact_id"),
                "declared_path": path,
                "role": role,
                "status": "PRESENT_IN_INVENTORY" if path in inventory else "MISSING",
            }
            for role, path in sorted(set(member_specs))
        ],
        "partial_movement_permitted": False,
        "run_id": run_id,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "supporting_evidence_ids": [manifest_evidence_id],
        "unresolved_dependencies": sorted(set(unresolved)),
    }
    gaps = []
    if unresolved:
        gaps.append(
            _gap(
                run_id,
                created_at,
                attempt["id"],
                sorted(set(unresolved)),
                manifest_evidence_id,
            )
        )
    return bundle, gaps


def _gap(
    run_id: str,
    created_at: str,
    attempt_id: str,
    missing: Iterable[str],
    manifest_evidence_id: str,
) -> Dict[str, Any]:
    unresolved = list(missing)
    return {
        "attempt_id": attempt_id,
        "counter_evidence_ids": [],
        "created_at": created_at,
        "gap_id": f"gap_{run_id}_{attempt_id}_{len(unresolved):04d}",
        "limitations": ["LINEAGE_UNRESOLVED"],
        "missing_or_unresolved": unresolved,
        "run_id": run_id,
        "schema_version": GAP_SCHEMA_VERSION,
        "status": "MISSING_REQUIRED_LINK",
        "supporting_evidence_ids": [manifest_evidence_id],
    }


def _read_manifest(root_fd: int) -> Dict[str, Any]:
    descriptor = os.open(MANIFEST_NAME, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=root_fd)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("EXPERIMENT_MANIFEST_UNAVAILABLE")
        payload = os.read(descriptor, _READ_LIMIT + 1)
    finally:
        os.close(descriptor)
    if len(payload) > _READ_LIMIT:
        raise ValueError("EXPERIMENT_MANIFEST_SIZE_LIMIT")
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise ValueError("EXPERIMENT_MANIFEST_MALFORMED")
    if not isinstance(parsed, dict):
        raise ValueError("EXPERIMENT_MANIFEST_MALFORMED")
    return parsed
