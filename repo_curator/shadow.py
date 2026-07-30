"""Build conservative, non-executable curation projections from audit records."""

from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


CLASSIFICATION_SCHEMA_VERSION = "repo-curator.classification.v2"
RECOMMENDATION_SCHEMA_VERSION = "repo-curator.recommendation.v1"
PLAN_SCHEMA_VERSION = "repo-curator.shadow-plan.v1"
_ROLE_STATES = {
    "ACTIVE_MAINLINE",
    "REQUIRED_COMPATIBILITY",
    "HISTORICAL_EVIDENCE",
    "EXPERIMENTAL_ACTIVE",
}
_ABSENCE_ONLY_UNRESOLVED_LIMITATIONS = frozenset({
    "NO_MAINLINE_EVIDENCE",
    "NO_ROLE_EVIDENCE",
})


def build_shadow_mode(
    inventory_records: Sequence[Dict[str, Any]],
    mainline: Sequence[Dict[str, Any]],
    implementation_roles: Sequence[Dict[str, Any]],
    relationships: Sequence[Dict[str, Any]],
    attempts: Sequence[Dict[str, Any]],
    bundles: Sequence[Dict[str, Any]],
    candidates: Sequence[Dict[str, Any]],
    document_comparisons: Sequence[Dict[str, Any]],
    declaration_evidence_by_artifact: Mapping[str, Mapping[str, Sequence[str]]],
    run_id: str,
    created_at: str,
    repository_state_hash: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Dict[str, Any], str]:
    """Return review-only states, recommendations, and separate plan projections."""
    mainline_by_artifact = {record["artifact_id"]: record for record in mainline}
    role_by_artifact = {record["artifact_id"]: record for record in implementation_roles}
    attempt_by_output = {record["output_path"]: record for record in attempts}
    candidate_paths = {record["output_path"] for record in candidates}
    conflicting_paths = {
        path
        for comparison in document_comparisons
        if comparison["candidate_subtype"] == "DO_NOT_MERGE"
        for path in comparison["document_paths"]
    }
    bundle_members, incomplete_bundle_members = _bundle_members(bundles)
    duplicate_replacements = _duplicate_replacements(relationships)

    classifications = []
    for record in inventory_records:
        classification = _classify(
            record,
            mainline_by_artifact.get(record["artifact_id"]),
            role_by_artifact.get(record["artifact_id"]),
            attempt_by_output.get(record["repository_relative_path"]),
            record["repository_relative_path"] in candidate_paths,
            record["repository_relative_path"] in conflicting_paths,
            bool(record["warnings"]),
            record["artifact_id"] in incomplete_bundle_members,
            duplicate_replacements.get(record["artifact_id"]),
            declaration_evidence_by_artifact.get(record["artifact_id"]),
            run_id,
            created_at,
        )
        classifications.append(classification)

    recommendations = _artifact_recommendations(
        classifications, bundle_members, run_id, created_at
    )
    recommendations.extend(
        _document_recommendations(document_comparisons, run_id, created_at)
    )
    recommendations.sort(key=lambda item: item["recommendation_id"])
    plan = _plan(
        classifications, recommendations, run_id, created_at, repository_state_hash
    )
    return classifications, recommendations, plan, _plan_markdown(plan, recommendations)


def _bundle_members(
    bundles: Sequence[Dict[str, Any]],
) -> Tuple[Mapping[str, List[str]], set[str]]:
    members: Dict[str, List[str]] = defaultdict(list)
    incomplete = set()
    for bundle in bundles:
        for artifact_id in bundle["member_artifact_ids"]:
            members[artifact_id].append(bundle["bundle_id"])
            if bundle["completeness"] != "COMPLETE_IN_ANALYZED_SCOPE":
                incomplete.add(artifact_id)
    return members, incomplete


def _duplicate_replacements(
    relationships: Sequence[Dict[str, Any]],
) -> Mapping[str, Dict[str, Any]]:
    replacements = {}
    for relationship in relationships:
        if relationship["relationship_type"] != "EXACT_BYTE_DUPLICATE":
            continue
        members = sorted(relationship["member_artifact_ids"])
        for artifact_id in members[1:]:
            replacements[artifact_id] = {
                "relationship_id": relationship["relationship_id"],
                "replacement_artifact_id": members[0],
                "supporting_evidence_ids": relationship["supporting_evidence_ids"],
            }
    return replacements


def _classify(
    artifact: Dict[str, Any],
    mainline: Optional[Mapping[str, Any]],
    role: Optional[Mapping[str, Any]],
    attempt: Optional[Mapping[str, Any]],
    is_canonical_candidate: bool,
    has_document_conflict: bool,
    has_inventory_limitation: bool,
    has_bundle_guard: bool,
    duplicate_replacement: Optional[Mapping[str, Any]],
    declaration_evidence: Optional[Mapping[str, Sequence[str]]],
    run_id: str,
    created_at: str,
) -> Dict[str, Any]:
    supporting = []
    counter = []
    limitations = []
    state = "UNRESOLVED"
    asserted_states = set()

    if artifact["object_type"] != "REGULAR_FILE":
        if artifact["object_type"] == "DIRECTORY":
            state = "PROTECTED"
        limitations.append("NON_REGULAR_ARTIFACT_PRESERVED")
    elif declaration_evidence is not None:
        state = "DECLARATION_EVIDENCE"
        supporting.extend(declaration_evidence["supporting_evidence_ids"])
        limitations.extend(declaration_evidence["limitations"])
    if mainline is not None:
        supporting.extend(mainline["supporting_evidence_ids"])
        counter.extend(mainline["counter_evidence_ids"])
        limitations.extend(mainline["uncertainty"])
        if mainline["status"] in _ROLE_STATES:
            state = mainline["status"]
            asserted_states.add(state)
    if role is not None:
        supporting.extend(role["supporting_evidence_ids"])
        limitations.extend(role["limitations"])
        if role["role"] in _ROLE_STATES:
            state = role["role"]
            asserted_states.add(state)
    if attempt is not None:
        supporting.extend(attempt["supporting_evidence_ids"])
        limitations.extend(attempt["limitations"])
        if attempt["result"] in {"FAILED", "INCONCLUSIVE", "PARTIAL"}:
            state = "HISTORICAL_EVIDENCE"
            asserted_states.add(state)
        elif attempt["result"] == "ACCEPTED" or is_canonical_candidate:
            state = "EXPERIMENTAL_ACTIVE"
            asserted_states.add(state)
    if len(asserted_states) > 1:
        state = "UNRESOLVED"
        limitations.append("MATERIAL_ROLE_CONFLICT")
    if has_document_conflict:
        state = "UNRESOLVED"
        limitations.append("MATERIAL_DOCUMENT_CONFLICT")
    if has_inventory_limitation:
        state = "UNRESOLVED"
        limitations.append("INVENTORY_COVERAGE_LIMITATION")
    if mainline is not None and mainline["status"] == "UNRESOLVED" and mainline[
        "counter_evidence_ids"
    ]:
        state = "UNRESOLVED"
        limitations.append("MATERIAL_INTENT_CONFLICT")
    if has_bundle_guard:
        state = "UNRESOLVED"
        limitations.append("BUNDLE_MOVEMENT_GUARD")
    if (
        state in {"UNRESOLVED", "DECLARATION_EVIDENCE"}
        and duplicate_replacement is not None
        and not has_document_conflict
        and not has_inventory_limitation
        and not has_bundle_guard
    ):
        state = "EXACT_DUPLICATE_REVIEW"
        supporting.extend(duplicate_replacement["supporting_evidence_ids"])
        limitations.append("EXACT_BYTES_DO_NOT_ESTABLISH_COMMON_PURPOSE")

    coverage = "SUFFICIENT_FOR_SHADOW_REVIEW" if supporting and not counter else "INSUFFICIENT"
    if state == "UNRESOLVED":
        coverage = "INSUFFICIENT"
    return {
        "artifact_id": artifact["artifact_id"],
        "classification_id": f"classification_{run_id}_{artifact['artifact_id'].rsplit('_', 1)[-1]}",
        "counter_evidence_ids": sorted(set(counter)),
        "created_at": created_at,
        "evidence_coverage": coverage,
        "limitations": sorted(set(limitations or ["NO_CLASSIFICATION_EVIDENCE"])),
        "preservation_required": True,
        "repository_relative_path": artifact["repository_relative_path"],
        "run_id": run_id,
        "schema_version": CLASSIFICATION_SCHEMA_VERSION,
        "state": state,
        "supporting_evidence_ids": sorted(set(supporting)),
    }


def _artifact_recommendations(
    classifications: Iterable[Dict[str, Any]],
    bundle_members: Mapping[str, List[str]],
    run_id: str,
    created_at: str,
) -> List[Dict[str, Any]]:
    records = []
    for classification in classifications:
        kind, expected_loss, availability, downgrade = _recommendation_for_state(
            classification, bundle_members
        )
        records.append(
            {
                "action_candidates": [],
                "affected_artifact_ids": [classification["artifact_id"]],
                "classification_ids": [classification["classification_id"]],
                "counter_evidence_ids": classification["counter_evidence_ids"],
                "created_at": created_at,
                "evidence_coverage": classification["evidence_coverage"],
                "executable_in_supported_scope": False,
                "expected_loss": expected_loss,
                "human_review_required": True,
                "limitations": sorted(set(classification["limitations"] + downgrade)),
                "recommendation_id": f"recommendation_{run_id}_{len(records) + 1:08d}",
                "recommendation_type": kind,
                "retention_closure": _retention_closure(classification, kind),
                "repository_relative_paths": [classification["repository_relative_path"]],
                "run_id": run_id,
                "schema_version": RECOMMENDATION_SCHEMA_VERSION,
                "shadow_mode": True,
                "supporting_evidence_ids": classification["supporting_evidence_ids"],
                "availability_proof": availability,
            }
        )
    return records


def _recommendation_for_state(
    classification: Mapping[str, Any], bundle_members: Mapping[str, List[str]]
) -> Tuple[str, str, Dict[str, Any], List[str]]:
    artifact_id = classification["artifact_id"]
    state = classification["state"]
    bundle_ids = bundle_members.get(artifact_id, [])
    if state == "UNRESOLVED":
        if set(classification["limitations"]) == _ABSENCE_ONLY_UNRESOLVED_LIMITATIONS:
            return "KEEP", "NONE", _unavailable(), ["PRESERVE_UNRESOLVED"]
        return "MANUAL_REVIEW", "NONE", _unavailable(), ["PRESERVE_UNRESOLVED"]
    if state in {
        "PROTECTED",
        "DECLARATION_EVIDENCE",
        "ACTIVE_MAINLINE",
        "REQUIRED_COMPATIBILITY",
        "EXPERIMENTAL_ACTIVE",
    }:
        return "KEEP", "NONE", _unavailable(), []
    if state == "HISTORICAL_EVIDENCE":
        if bundle_ids:
            return "MANUAL_REVIEW", "NONE", _unavailable(), _bundle_limits(bundle_ids)
        return (
            "ARCHIVE",
            "LOCATION_ONLY_AFTER_APPROVED_MOVE",
            _unavailable(),
            ["ARCHIVE_REQUIRES_FUTURE_AVAILABILITY_VALIDATION"],
        )
    if state == "EXACT_DUPLICATE_REVIEW":
        if bundle_ids:
            return "MANUAL_REVIEW", "NONE", _unavailable(), _bundle_limits(bundle_ids)
        return (
            "REVIEW_EXACT_DUPLICATE",
            "NONE",
            {
                "status": "EXACT_BYTE_REPLACEMENT_OBSERVED",
                "scope": "ANALYZED_REPOSITORY",
            },
            [
                "EXACT_BYTES_DO_NOT_ESTABLISH_COMMON_PURPOSE",
                "NO_MOVE_OR_DELETE_AUTHORIZED",
            ],
        )
    raise ValueError(f"unsupported preservation state: {state}")


def _unavailable() -> Dict[str, Any]:
    return {"status": "NOT_ESTABLISHED", "scope": "NOT_AN_EXECUTION_PROOF"}


def _retention_closure(classification: Mapping[str, Any], recommendation_type: str) -> Dict[str, Any]:
    return {
        "evidence_ids": list(classification["supporting_evidence_ids"]),
        "scopes": ["ANALYZED_REPOSITORY"],
        "status": "PRESERVED_OR_REVIEW_REQUIRED",
    }


def _bundle_limits(bundle_ids: Sequence[str]) -> List[str]:
    return [f"BUNDLE_GUARD:{bundle_id}" for bundle_id in sorted(bundle_ids)]


def _document_recommendations(
    comparisons: Sequence[Dict[str, Any]], run_id: str, created_at: str
) -> List[Dict[str, Any]]:
    records = []
    for comparison in comparisons:
        kind = "MANUAL_REVIEW" if comparison["candidate_subtype"] == "DO_NOT_MERGE" else "MERGE"
        records.append(
            {
                "action_candidates": [],
                "affected_artifact_ids": [],
                "classification_ids": [],
                "counter_evidence_ids": comparison["counter_evidence_ids"],
                "created_at": created_at,
                "evidence_coverage": "DECLARED_METADATA_ONLY",
                "executable_in_supported_scope": False,
                "expected_loss": "DOCUMENT_HISTORY_AND_AUDIT_RECORDS_MUST_BE_RETAINED",
                "human_review_required": True,
                "limitations": comparison["limitations"] + ["MERGE_AND_DELETE_NEVER_EXECUTABLE"],
                "recommendation_id": f"recommendation_{run_id}_document_{len(records) + 1:08d}",
                "recommendation_type": kind,
                "repository_relative_paths": comparison["document_paths"],
                "run_id": run_id,
                "schema_version": RECOMMENDATION_SCHEMA_VERSION,
                "shadow_mode": True,
                "supporting_evidence_ids": comparison["supporting_evidence_ids"],
                "availability_proof": _unavailable(),
            }
        )
    return records


def _plan(
    classifications: Sequence[Dict[str, Any]],
    recommendations: Sequence[Dict[str, Any]],
    run_id: str,
    created_at: str,
    repository_state_hash: str,
) -> Dict[str, Any]:
    return {
        "action_candidates": [],
        "analysis_run_id": run_id,
        "classification_ids": [item["classification_id"] for item in classifications],
        "created_at": created_at,
        "execution_mode": "SHADOW",
        "executable": False,
        "expected_loss_summary": {
            "location_change_candidates": sum(
                item["expected_loss"] != "NONE" for item in recommendations
            ),
            "permanent_deletion_candidates": 0,
        },
        "plan_id": f"shadow_plan_{run_id}",
        "recommendation_ids": [item["recommendation_id"] for item in recommendations],
        "repository_state_hash": repository_state_hash,
        "run_id": run_id,
        "schema_version": PLAN_SCHEMA_VERSION,
    }


def _plan_markdown(plan: Mapping[str, Any], recommendations: Sequence[Mapping[str, Any]]) -> str:
    counts: Dict[str, int] = defaultdict(int)
    for recommendation in recommendations:
        counts[recommendation["recommendation_type"]] += 1
    lines = [
        "# Shadow-mode curation plan",
        "",
        "This report is explanatory only. It authorizes no repository action.",
        "",
        f"Plan ID: `{plan['plan_id']}`",
        f"Analysis run: `{plan['analysis_run_id']}`",
        f"Executable actions: `{len(plan['action_candidates'])}`",
        "",
        "## Recommendation counts",
        "",
    ]
    lines.extend(f"- `{kind}`: {counts[kind]}" for kind in sorted(counts))
    lines.extend(
        [
            "",
            "Any archive, quarantine, merge, or delete suggestion remains subject to later",
            "approval, availability, protected-path, drift, and transaction validation.",
            "",
        ]
    )
    return "\n".join(lines)
