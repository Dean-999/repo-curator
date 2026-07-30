"""Fail-closed validation for exact-byte plan approvals."""

import hashlib
import json
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


APPROVAL_SCHEMA_VERSION = "repo-curator.approval.v1"
_SUPPORTED_ACTION_TYPES = {"ARCHIVE", "QUARANTINE"}
_BUDGET_FIELDS = {"max_actions", "max_affected_bytes", "max_blast_radius"}
_PROTECTED_PREFIXES = (".git", ".repo-curator", ".agents/skills/repo-curator")
_EXPANSION_FIELDS = {"actions", "capabilities", "destinations", "path_patterns", "wildcards"}
_REQUIRED_APPROVAL_FIELDS = {
    "approval_id", "approval_created_at", "approval_schema_version",
    "approved_action_ids", "approved_plan_id", "approved_plan_sha256",
    "approved_recommendation_ids", "approving_actor", "decision_set_hash",
    "effective_policy_hash", "mutation_budget", "repository_state_hash",
}
_ALLOWED_APPROVAL_FIELDS = _REQUIRED_APPROVAL_FIELDS | {"reviewer_notes", "supersedes_approval_id"}


def validate_approval(
    plan_bytes: bytes, approval: Mapping[str, Any], context: Mapping[str, Any]
) -> Dict[str, Any]:
    """Validate a proposed approval without reading or changing repository content."""
    errors: List[str] = []
    plan = _parse_plan(plan_bytes, errors)
    if plan is None:
        return _result(errors, [])
    _validate_approval_shape(approval, errors)
    _validate_exact_plan(plan_bytes, plan, approval, errors)
    _validate_bound_context(plan, approval, context, errors)
    actions = _actions_by_id(plan.get("action_candidates"), errors)
    recommendation_ids = plan.get("recommendation_ids")
    approved_action_ids = _string_list(approval.get("approved_action_ids"), "APPROVAL_ACTIONS_MALFORMED", errors)
    approved_recommendation_ids = _string_list(
        approval.get("approved_recommendation_ids"), "APPROVAL_RECOMMENDATIONS_MALFORMED", errors
    )
    if not isinstance(recommendation_ids, list) or not all(isinstance(item, str) for item in recommendation_ids):
        errors.append("PLAN_RECOMMENDATIONS_MALFORMED")
        recommendation_ids = []
    _validate_selected_ids(approved_action_ids, actions, approved_recommendation_ids, recommendation_ids, errors)
    selected_actions = [actions[action_id] for action_id in approved_action_ids if action_id in actions]
    _validate_actions(selected_actions, plan, errors)
    _validate_budget(
        selected_actions, approval.get("mutation_budget"), plan.get("mutation_budget"), errors
    )
    return _result(errors, approved_action_ids)


def _parse_plan(plan_bytes: bytes, errors: List[str]) -> Optional[Dict[str, Any]]:
    try:
        plan = json.loads(plan_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        errors.append("PLAN_MALFORMED")
        return None
    if not isinstance(plan, dict):
        errors.append("PLAN_MALFORMED")
        return None
    return plan


def _validate_approval_shape(approval: Mapping[str, Any], errors: List[str]) -> None:
    missing = _REQUIRED_APPROVAL_FIELDS - set(approval)
    if missing or approval.get("approval_schema_version") != APPROVAL_SCHEMA_VERSION:
        errors.append("APPROVAL_MALFORMED")
    if _EXPANSION_FIELDS & set(approval) or set(approval) - _ALLOWED_APPROVAL_FIELDS:
        errors.append("APPROVAL_SCOPE_EXPANSION")


def _validate_exact_plan(
    plan_bytes: bytes, plan: Mapping[str, Any], approval: Mapping[str, Any], errors: List[str]
) -> None:
    digest = "sha256:" + hashlib.sha256(plan_bytes).hexdigest()
    if approval.get("approved_plan_sha256") != digest:
        errors.append("APPROVAL_PLAN_HASH_MISMATCH")
    if not isinstance(plan.get("plan_id"), str) or approval.get("approved_plan_id") != plan.get("plan_id"):
        errors.append("APPROVAL_PLAN_ID_MISMATCH")


def _validate_bound_context(
    plan: Mapping[str, Any], approval: Mapping[str, Any], context: Mapping[str, Any], errors: List[str]
) -> None:
    for field, code in (
        ("repository_state_hash", "DRIFT_REPOSITORY_STATE"),
        ("effective_policy_hash", "APPROVAL_POLICY_HASH_MISMATCH"),
        ("decision_set_hash", "APPROVAL_DECISION_SET_HASH_MISMATCH"),
    ):
        value = plan.get(field)
        if not isinstance(value, str) or context.get(field) != value:
            errors.append(code)
        elif approval.get(field) != value:
            errors.append(code)


def _actions_by_id(value: Any, errors: List[str]) -> Dict[str, Mapping[str, Any]]:
    if not isinstance(value, list):
        errors.append("PLAN_ACTIONS_MALFORMED")
        return {}
    actions = {}
    for action in value:
        if not isinstance(action, dict) or not isinstance(action.get("action_id"), str) or action["action_id"] in actions:
            errors.append("PLAN_ACTIONS_MALFORMED")
            continue
        actions[action["action_id"]] = action
    return actions


def _string_list(value: Any, code: str, errors: List[str]) -> List[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        errors.append(code)
        return []
    if len(set(value)) != len(value):
        errors.append(code)
        return []
    return value


def _validate_selected_ids(
    approved_actions: Sequence[str],
    actions: Mapping[str, Mapping[str, Any]],
    approved_recommendations: Sequence[str],
    recommendations: Iterable[str],
    errors: List[str],
) -> None:
    if any(action_id not in actions for action_id in approved_actions):
        errors.append("APPROVAL_UNKNOWN_ACTION")
    known_recommendations = set(recommendations)
    if any(item not in known_recommendations for item in approved_recommendations):
        errors.append("APPROVAL_UNKNOWN_RECOMMENDATION")


def _validate_actions(
    actions: Iterable[Mapping[str, Any]], plan: Mapping[str, Any], errors: List[str]
) -> None:
    for action in actions:
        if action.get("type") not in _SUPPORTED_ACTION_TYPES:
            errors.append("ACTION_UNSUPPORTED_TYPE")
        if action.get("executable_in_supported_scope") is not True or action.get("approval_required") is not True:
            errors.append("ACTION_NOT_EXECUTABLE")
        if action.get("repository_mode") != "GIT_WORKTREE":
            errors.append("PREFLIGHT_REPOSITORY_MODE")
        for path_field in ("source_path", "destination_path"):
            if not _safe_repository_path(action.get(path_field)):
                errors.append("PATH_TRAVERSAL")
            elif _protected_path(action[path_field]) and not _is_managed_quarantine_destination(
                action, path_field, plan.get("plan_id")
            ):
                errors.append("PATH_PROTECTED")
        if action.get("source_external_symlink") is True:
            errors.append("PATH_EXTERNAL_SYMLINK")
        if action.get("destination_exists") is True:
            errors.append("PATH_DESTINATION_EXISTS")
        if action.get("case_collision") is True:
            errors.append("PATH_CASE_COLLISION")
        if action.get("same_filesystem") is not True:
            errors.append("CROSS_FILESYSTEM_MOVE_UNSUPPORTED")
        if not isinstance(action.get("affected_bytes"), int) or isinstance(action["affected_bytes"], bool) or action["affected_bytes"] < 0:
            errors.append("ACTION_MALFORMED")
        retention_evidence = action.get("retention_evidence_ids")
        if (
            action.get("retention_closure_satisfied") is not True
            or not isinstance(retention_evidence, list)
            or not retention_evidence
            or not all(isinstance(item, str) and item for item in retention_evidence)
        ):
            errors.append("RETENTION_CLOSURE_INCOMPLETE")
        _validate_bundle(action, errors)


def _safe_repository_path(path: Any) -> bool:
    if not isinstance(path, str) or not path or chr(0) in path or path.startswith("/") or chr(92) in path:
        return False
    return all(part not in {"", ".", ".."} for part in path.split("/"))


def _protected_path(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in _PROTECTED_PREFIXES)


def _is_managed_quarantine_destination(
    action: Mapping[str, Any], path_field: str, plan_id: Any
) -> bool:
    if path_field != "destination_path" or action.get("type") != "QUARANTINE":
        return False
    if not isinstance(plan_id, str) or not plan_id or "/" in plan_id or chr(92) in plan_id:
        return False
    prefix = ".repo-curator/quarantine/" + plan_id + "/"
    return action.get("destination_path", "").startswith(prefix)


def _validate_bundle(action: Mapping[str, Any], errors: List[str]) -> None:
    affected = action.get("affected_artifact_ids")
    bundle_members = action.get("bundle_member_artifact_ids")
    if not isinstance(affected, list) or not all(isinstance(item, str) for item in affected):
        errors.append("ACTION_MALFORMED")
        return
    if action.get("bundle_complete") is not True:
        errors.append("BUNDLE_INCOMPLETE")
    if not isinstance(bundle_members, list) or set(bundle_members) != set(affected):
        errors.append("BUNDLE_PARTIAL_MOVEMENT")


def _validate_budget(
    actions: Sequence[Mapping[str, Any]], approval_budget: Any, plan_budget: Any, errors: List[str]
) -> None:
    if not _valid_budget(approval_budget):
        errors.append("APPROVAL_BUDGET_MALFORMED")
        return
    if not _valid_budget(plan_budget):
        errors.append("PLAN_BUDGET_MALFORMED")
        return
    if any(approval_budget[field] > plan_budget[field] for field in _BUDGET_FIELDS):
        errors.append("APPROVAL_BUDGET_EXPANSION")
    if len(actions) > approval_budget["max_actions"]:
        errors.append("BUDGET_ACTION_COUNT")
    affected_values = [action.get("affected_bytes") for action in actions]
    if not all(isinstance(value, int) and not isinstance(value, bool) and value >= 0 for value in affected_values):
        errors.append("ACTION_MALFORMED")
        return
    affected_bytes = sum(affected_values)
    if affected_bytes > approval_budget["max_affected_bytes"]:
        errors.append("BUDGET_AFFECTED_BYTES")
    blast_radius = {artifact_id for action in actions for artifact_id in action.get("affected_artifact_ids", [])}
    if len(blast_radius) > approval_budget["max_blast_radius"]:
        errors.append("BUDGET_BLAST_RADIUS")


def _valid_budget(value: Any) -> bool:
    return isinstance(value, dict) and set(value) == _BUDGET_FIELDS and all(
        isinstance(value.get(field), int) and not isinstance(value[field], bool) and value[field] >= 0
        for field in _BUDGET_FIELDS
    )


def _result(errors: Iterable[str], approved_action_ids: Sequence[str]) -> Dict[str, Any]:
    ordered_errors = sorted(set(errors))
    return {
        "approved_action_ids": list(approved_action_ids) if not ordered_errors else [],
        "errors": ordered_errors,
        "valid": not ordered_errors,
    }
