"""Journal reconciliation and separately approved no-overwrite rollback."""

import base64
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence

from repo_curator.approval import validate_approval
from repo_curator.archive_apply import (
    ArchiveApplyError, _directory_flags, _ensure_directory, _entry_kind, _fingerprint, _is_git_worktree,
    _open_parent, _protected, _read_regular, _safe_component, _safe_path,
    _unchanged,
)
from repo_curator.archive_apply import archive_destination
from repo_curator.quarantine_apply import quarantine_destination
from repo_curator.transactions import (
    TransactionError, append_event, approval_sha256, canonical_bytes, fsync_directory,
    mutation_lock, parse_journal, sha256, write_all,
)


class RecoveryError(ValueError):
    """Stable recovery or rollback rejection."""


def reconcile_apply(root: Path, plan_bytes: bytes, approval: Mapping[str, Any], created_at: str) -> Dict[str, Any]:
    """Classify actions from current filesystem and journal evidence only."""
    resolved = root.resolve(strict=True)
    plan = _parse(plan_bytes)
    _require_original_approval(plan_bytes, plan, approval)
    actions = _actions(plan)
    root_fd = os.open(resolved, _directory_flags())
    try:
        journal_path = ".repo-curator/applies/{}/apply-journal.jsonl".format(plan["plan_id"])
        events, journal_hash, journal_valid = _journal_events(root_fd, journal_path)
        outcomes = [
            {"action_id": action["action_id"], "status": _outcome(root_fd, plan_bytes, plan, approval, action, events) if journal_valid else "AMBIGUOUS"}
            for action in actions
        ]
    finally:
        os.close(root_fd)
    if outcomes and all(item["status"] == "VERIFIED" for item in outcomes):
        rollback_bytes = _rollback_plan(plan, approval, actions, events, journal_hash, created_at)
        return {"actions": outcomes, "rollback_plan_bytes": rollback_bytes, "status": "SAFE_ROLLBACK_ELIGIBLE"}
    return {"actions": outcomes, "status": "MANUAL_RECOVERY_REQUIRED"}


def apply_rollback(
    root: Path,
    rollback_bytes: bytes,
    approval: Mapping[str, Any],
    created_at: str,
    original_plan_bytes: Optional[bytes] = None,
    original_approval: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Restore only an exact-approved, fully prevalidated rollback plan."""
    resolved = root.resolve(strict=True)
    if not resolved.is_dir() or not _is_git_worktree(resolved):
        raise RecoveryError("PREFLIGHT_REPOSITORY_MODE")
    plan = _parse(rollback_bytes)
    if plan.get("schema_version") != "repo-curator.rollback-plan.v2":
        raise RecoveryError("ROLLBACK_PLAN_MALFORMED")
    actions = _rollback_actions(plan)
    _require_rollback_approval(rollback_bytes, plan, actions, approval)
    _require_original_evidence(plan, original_plan_bytes, original_approval)
    root_fd = os.open(resolved, _directory_flags())
    try:
        try:
            with mutation_lock(root_fd, {
                "created_at": created_at, "operation": "ROLLBACK", "plan_id": plan["plan_id"],
                "process_id": os.getpid(),
            }):
                events = _require_journal_prefix(root_fd, plan, original_plan_bytes, original_approval)
                statuses = {action["action_id"]: _rollback_action_status(root_fd, plan, approval, action, events) for action in actions}
                if any(status == "AMBIGUOUS" for status in statuses.values()):
                    raise RecoveryError("ROLLBACK_RECONCILIATION_REQUIRED")
                if all(status == "VERIFIED" for status in statuses.values()):
                    completed = any(event.get("event_type") == "ROLLBACK_COMPLETED" and event.get("rollback_plan_id") == plan["plan_id"] for event in events)
                    if not completed:
                        _append_rollback_event(root_fd, plan, approval, "ROLLBACK_COMPLETED", created_at)
                    return {"restored_action_ids": [action["action_id"] for action in actions], "status": "ALREADY_ROLLED_BACK" if completed else "ROLLED_BACK"}
                for action in actions:
                    if statuses[action["action_id"]] == "PENDING":
                        _validate_rollback_action(root_fd, plan, action)
                if not any(event.get("event_type") == "ROLLBACK_APPROVED" and event.get("rollback_plan_id") == plan["plan_id"] for event in events):
                    _append_rollback_event(root_fd, plan, approval, "ROLLBACK_APPROVED", created_at)
                active_action = None
                try:
                    for action in actions:
                        if statuses[action["action_id"]] == "VERIFIED":
                            continue
                        active_action = action
                        _validate_rollback_action(root_fd, plan, action)
                        _append_rollback_event(root_fd, plan, approval, "ROLLBACK_ACTION_STARTED", created_at, action)
                        _restore(root_fd, plan, approval, action, created_at)
                        _append_rollback_event(root_fd, plan, approval, "ROLLBACK_ACTION_VERIFIED", created_at, action)
                except RecoveryError as error:
                    _append_rollback_event(root_fd, plan, approval, "ROLLBACK_FAILED", created_at, active_action, str(error))
                    raise
                _append_rollback_event(root_fd, plan, approval, "ROLLBACK_COMPLETED", created_at)
        except TransactionError as error:
            raise RecoveryError(str(error)) from error
    finally:
        os.close(root_fd)
    return {"restored_action_ids": [action["action_id"] for action in actions], "status": "ROLLED_BACK"}


def _parse(payload: bytes) -> Mapping[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RecoveryError("PLAN_MALFORMED") from error
    if not isinstance(value, dict):
        raise RecoveryError("PLAN_MALFORMED")
    return value


def _require_original_approval(plan_bytes: bytes, plan: Mapping[str, Any], approval: Mapping[str, Any]) -> None:
    context = {field: plan.get(field) for field in ("decision_set_hash", "effective_policy_hash", "repository_state_hash")}
    result = validate_approval(plan_bytes, approval, context)
    if not result["valid"]:
        raise RecoveryError(result["errors"][0])


def _require_original_evidence(
    rollback_plan: Mapping[str, Any],
    original_plan_bytes: Optional[bytes],
    original_approval: Optional[Mapping[str, Any]],
) -> None:
    if original_plan_bytes is None or original_approval is None:
        raise RecoveryError("ROLLBACK_ORIGINAL_EVIDENCE_REQUIRED")
    original_plan = _parse(original_plan_bytes)
    _require_original_approval(original_plan_bytes, original_plan, original_approval)
    if (
        rollback_plan.get("original_plan_id") != original_plan.get("plan_id")
        or rollback_plan.get("original_plan_sha256") != sha256(original_plan_bytes)
        or rollback_plan.get("original_approval_sha256") != approval_sha256(original_approval)
        or rollback_plan.get("source_approval_id") != original_approval.get("approval_id")
    ):
        raise RecoveryError("ROLLBACK_ORIGINAL_EVIDENCE_MISMATCH")


def _actions(plan: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    actions = plan.get("action_candidates")
    if not isinstance(actions, list) or not actions or not all(isinstance(action, dict) for action in actions):
        raise RecoveryError("PLAN_ACTIONS_MALFORMED")
    if any(action.get("type") not in {"ARCHIVE", "QUARANTINE"} for action in actions):
        raise RecoveryError("PLAN_UNSUPPORTED_ACTION")
    return actions


def _journal_events(root_fd: int, journal_path: str) -> tuple[Sequence[Mapping[str, Any]], str, bool]:
    try:
        payload = _read_regular(root_fd, journal_path, 1024 * 1024)
        return (parse_journal(payload), "sha256:" + hashlib.sha256(payload).hexdigest(), True)
    except (ArchiveApplyError, OSError, UnicodeDecodeError, json.JSONDecodeError, TransactionError):
        return [], "sha256:unavailable", False


def _require_journal_prefix(
    root_fd: int,
    plan: Mapping[str, Any],
    original_plan_bytes: bytes,
    original_approval: Mapping[str, Any],
) -> Sequence[Mapping[str, Any]]:
    plan_id = plan.get("original_plan_id")
    expected = plan.get("journal_hash")
    event_count = plan.get("source_journal_event_count")
    if not isinstance(plan_id, str) or not _safe_component(plan_id) or not isinstance(expected, str) or not isinstance(event_count, int):
        raise RecoveryError("ROLLBACK_PLAN_MALFORMED")
    journal_path = ".repo-curator/applies/{}/apply-journal.jsonl".format(plan_id)
    try:
        payload = _read_regular(root_fd, journal_path, 1024 * 1024)
    except (ArchiveApplyError, OSError):
        raise RecoveryError("ROLLBACK_JOURNAL_DRIFT")
    try:
        events = parse_journal(payload)
    except TransactionError as error:
        raise RecoveryError("ROLLBACK_JOURNAL_DRIFT") from error
    if len(events) < event_count:
        raise RecoveryError("ROLLBACK_JOURNAL_DRIFT")
    prefix = b"".join(canonical_bytes(event) + b"\n" for event in events[:event_count])
    if expected != sha256(prefix):
        raise RecoveryError("ROLLBACK_JOURNAL_DRIFT")
    source = events[event_count - 1]
    if (
        source.get("event_hash") != plan.get("source_transaction_event_hash")
        or source.get("event_type") != "TRANSACTION_COMMITTED"
        or source.get("plan_sha256") != sha256(original_plan_bytes)
        or source.get("approval_sha256") != approval_sha256(original_approval)
    ):
        raise RecoveryError("ROLLBACK_JOURNAL_DRIFT")
    return events


def _outcome(root_fd: int, plan_bytes: bytes, plan: Mapping[str, Any], approval: Mapping[str, Any], action: Mapping[str, Any], events: Sequence[Mapping[str, Any]]) -> str:
    own = [event for event in events if event.get("action_id") == action.get("action_id")]
    types = [event.get("event_type") for event in own]
    committed = bool(events) and events[-1].get("event_type") == "TRANSACTION_COMMITTED"
    bound = all(
        event.get("plan_id") == plan.get("plan_id")
        and event.get("plan_sha256") == sha256(plan_bytes)
        and event.get("approval_id") == approval.get("approval_id")
        and event.get("approval_sha256") == approval_sha256(approval)
        for event in events
    )
    if _files_verified(root_fd, plan, action) and committed and bound and types == ["ACTION_VALIDATION_STARTED", "MOVE_STARTED", "DESTINATION_OBSERVED", "SOURCE_REMOVAL_OBSERVED", "ACTION_VERIFIED"]:
        return "VERIFIED"
    source = _entry_kind(root_fd, action.get("source_path", ""))
    destination = _entry_kind(root_fd, action.get("destination_path", ""))
    provenance = _entry_kind(root_fd, str(action.get("destination_path", "")) + ".provenance.json")
    if source == "REGULAR" and destination == provenance == "ABSENT" and types in ([], ["ACTION_VALIDATION_STARTED"], ["ACTION_VALIDATION_STARTED", "ACTION_FAILED"]):
        return "PREPARED" if types else "NOT_STARTED"
    if "MOVE_STARTED" in types and source == "REGULAR" and destination == "REGULAR":
        return "MOVED"
    if "ACTION_FAILED" in types:
        return "FAILED"
    return "AMBIGUOUS"


def _files_verified(root_fd: int, plan: Mapping[str, Any], action: Mapping[str, Any]) -> bool:
    source = action.get("source_path")
    destination = action.get("destination_path")
    if not isinstance(source, str) or not isinstance(destination, str):
        return False
    if _entry_kind(root_fd, source) != "ABSENT" or _entry_kind(root_fd, destination) != "REGULAR" or _entry_kind(root_fd, destination + ".provenance.json") != "REGULAR":
        return False
    try:
        payload = _read_regular(root_fd, destination, None)
        provenance = json.loads(_read_regular(root_fd, destination + ".provenance.json", 64 * 1024).decode("utf-8"))
    except (ArchiveApplyError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(provenance, dict) and hashlib.sha256(payload).hexdigest() == action.get("source_fingerprint") and provenance.get("plan_id") == plan.get("plan_id") and provenance.get("original_path") == source


def _rollback_plan(plan: Mapping[str, Any], approval: Mapping[str, Any], actions: Sequence[Mapping[str, Any]], events: Sequence[Mapping[str, Any]], journal_hash: str, created_at: str) -> bytes:
    candidates = []
    for action in actions:
        candidates.append({"action_id": "rollback-" + action["action_id"], "destination_path": action["source_path"], "expected_fingerprint": action["source_fingerprint"], "original_action_id": action["action_id"], "source_path": action["destination_path"], "source_type": action["type"]})
    value = {
        "action_candidates": candidates, "created_at": created_at, "journal_hash": journal_hash,
        "original_approval_sha256": approval_sha256(approval), "original_plan_id": plan["plan_id"],
        "original_plan_sha256": approval["approved_plan_sha256"],
        "plan_id": "rollback-{}-{}".format(plan["plan_id"], journal_hash.split(":", 1)[1][:16]),
        "schema_version": "repo-curator.rollback-plan.v2", "source_apply_run_id": _apply_run_id(events),
        "source_approval_id": approval.get("approval_id"), "source_journal_event_count": len(events),
        "source_transaction_event_hash": events[-1]["event_hash"],
    }
    return _canonical(value)


def _apply_run_id(events: Sequence[Mapping[str, Any]]) -> Any:
    return events[0].get("apply_run_id") if events else None


def _require_rollback_approval(
    payload: bytes,
    plan: Mapping[str, Any],
    actions: Sequence[Mapping[str, Any]],
    approval: Mapping[str, Any],
) -> None:
    required = {"approval_id", "approved_plan_id", "approved_plan_sha256", "approved_action_ids"}
    if set(approval) != required or not isinstance(approval.get("approval_id"), str) or approval.get("approved_plan_id") != plan.get("plan_id"):
        raise RecoveryError("ROLLBACK_APPROVAL_MALFORMED")
    if approval.get("approved_plan_sha256") != "sha256:" + hashlib.sha256(payload).hexdigest():
        raise RecoveryError("ROLLBACK_APPROVAL_PLAN_HASH_MISMATCH")
    if approval.get("approved_action_ids") != [action["action_id"] for action in actions]:
        raise RecoveryError("ROLLBACK_APPROVAL_SCOPE_EXPANSION")


def _rollback_actions(plan: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    actions = plan.get("action_candidates")
    if not isinstance(actions, list) or not actions or not all(isinstance(action, dict) for action in actions):
        raise RecoveryError("ROLLBACK_PLAN_MALFORMED")
    action_ids = [action.get("action_id") for action in actions]
    if not all(isinstance(action_id, str) and action_id for action_id in action_ids) or len(set(action_ids)) != len(action_ids):
        raise RecoveryError("ROLLBACK_PLAN_MALFORMED")
    return actions


def _rollback_action_status(
    root_fd: int,
    plan: Mapping[str, Any],
    approval: Mapping[str, Any],
    action: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
) -> str:
    own = [
        event for event in events
        if event.get("rollback_plan_id") == plan.get("plan_id")
        and event.get("rollback_action_id") == action.get("action_id")
    ]
    if not own:
        return "PENDING"
    expected = [
        "ROLLBACK_ACTION_STARTED", "ROLLBACK_DESTINATION_OBSERVED",
        "ROLLBACK_ARCHIVE_SOURCE_REMOVED", "ROLLBACK_ACTION_VERIFIED",
    ]
    if [event.get("event_type") for event in own] != expected:
        return "AMBIGUOUS"
    if not all(
        event.get("approval_id") == approval.get("approval_id")
        and event.get("approval_sha256") == approval_sha256(approval)
        and event.get("plan_sha256") == plan.get("original_plan_sha256")
        for event in own
    ):
        return "AMBIGUOUS"
    receipt_path = ".repo-curator/applies/{}/rollback-receipts/{}.json".format(
        plan["original_plan_id"], action["action_id"]
    )
    if (
        _entry_kind(root_fd, action["source_path"]) != "ABSENT"
        or _entry_kind(root_fd, action["source_path"] + ".provenance.json") != "ABSENT"
        or _entry_kind(root_fd, action["destination_path"]) != "REGULAR"
        or _entry_kind(root_fd, receipt_path) != "REGULAR"
    ):
        return "AMBIGUOUS"
    try:
        restored = _read_regular(root_fd, action["destination_path"], None)
        receipt = json.loads(_read_regular(root_fd, receipt_path, 128 * 1024).decode("utf-8"))
        provenance = base64.b64decode(receipt["provenance_base64"], validate=True)
    except (ArchiveApplyError, OSError, UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return "AMBIGUOUS"
    if (
        hashlib.sha256(restored).hexdigest() != action.get("expected_fingerprint")
        or not isinstance(receipt, dict)
        or receipt.get("rollback_action_id") != action.get("action_id")
        or receipt.get("provenance_sha256") != sha256(provenance)
    ):
        return "AMBIGUOUS"
    return "VERIFIED"


def _validate_rollback_action(root_fd: int, plan: Mapping[str, Any], action: Mapping[str, Any]) -> None:
    if not isinstance(action, dict) or action.get("source_type") not in {"ARCHIVE", "QUARANTINE"}:
        raise RecoveryError("ROLLBACK_PLAN_MALFORMED")
    source = action.get("source_path")
    destination = action.get("destination_path")
    if (
        not isinstance(plan.get("original_plan_id"), str)
        or not _safe_component(plan["original_plan_id"])
        or not isinstance(source, str)
        or not isinstance(destination, str)
        or not _safe_path(source)
        or not _safe_path(destination)
        or _protected(destination)
    ):
        raise RecoveryError("PATH_TRAVERSAL")
    try:
        expected = archive_destination(plan["original_plan_id"], destination) if action["source_type"] == "ARCHIVE" else quarantine_destination(plan["original_plan_id"], destination)
    except ArchiveApplyError as error:
        raise RecoveryError("ROLLBACK_PLAN_MALFORMED") from error
    if source != expected:
        raise RecoveryError("ROLLBACK_PLAN_MALFORMED")
    if _entry_kind(root_fd, destination) != "ABSENT":
        raise RecoveryError("ROLLBACK_DESTINATION_EXISTS")
    parent_fd = None
    descriptor = None
    try:
        parent_fd, name = _open_parent(root_fd, source)
        descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode) or _fingerprint(descriptor) != action.get("expected_fingerprint"):
            raise RecoveryError("ROLLBACK_SOURCE_DRIFT")
    except ArchiveApplyError as error:
        raise RecoveryError("ROLLBACK_SOURCE_DRIFT") from error
    except OSError as error:
        raise RecoveryError("ROLLBACK_SOURCE_DRIFT") from error
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if parent_fd is not None:
            os.close(parent_fd)
    try:
        provenance = json.loads(_read_regular(root_fd, source + ".provenance.json", 64 * 1024).decode("utf-8"))
    except (ArchiveApplyError, OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RecoveryError("ROLLBACK_PROVENANCE_MISSING") from error
    if not isinstance(provenance, dict) or provenance.get("plan_id") != plan.get("original_plan_id") or provenance.get("original_path") != destination:
        raise RecoveryError("ROLLBACK_PROVENANCE_DRIFT")


def _restore(
    root_fd: int,
    plan: Mapping[str, Any],
    approval: Mapping[str, Any],
    action: Mapping[str, Any],
    created_at: str,
) -> None:
    source_parent_fd = None
    destination_parent_fd = None
    source_fd = None
    try:
        source_parent_fd, source_name = _open_parent(root_fd, action["source_path"])
        destination_parent_fd, destination_name = _open_parent(root_fd, action["destination_path"])
        source_fd = os.open(source_name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=source_parent_fd)
        source_stat = os.fstat(source_fd)
        if not stat.S_ISREG(source_stat.st_mode) or _fingerprint(source_fd) != action.get("expected_fingerprint"):
            raise RecoveryError("ROLLBACK_SOURCE_DRIFT")
        try:
            os.stat(destination_name, dir_fd=destination_parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            pass
        else:
            raise RecoveryError("ROLLBACK_DESTINATION_EXISTS")
        _unchanged(source_parent_fd, source_name, source_stat)
        os.link(source_name, destination_name, src_dir_fd=source_parent_fd, dst_dir_fd=destination_parent_fd, follow_symlinks=False)
        fsync_directory(destination_parent_fd)
        destination_fd = os.open(destination_name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=destination_parent_fd)
        try:
            destination_stat = os.fstat(destination_fd)
            if (
                not stat.S_ISREG(destination_stat.st_mode)
                or (destination_stat.st_dev, destination_stat.st_ino) != (source_stat.st_dev, source_stat.st_ino)
                or _fingerprint(destination_fd) != action.get("expected_fingerprint")
            ):
                raise RecoveryError("ROLLBACK_SOURCE_DRIFT")
        finally:
            os.close(destination_fd)
        _append_rollback_event(root_fd, plan, approval, "ROLLBACK_DESTINATION_OBSERVED", created_at, action)
        _unchanged(source_parent_fd, source_name, source_stat)
        _write_rollback_receipt(root_fd, plan, action, created_at)
        os.unlink(source_name, dir_fd=source_parent_fd)
        os.unlink(source_name + ".provenance.json", dir_fd=source_parent_fd)
        fsync_directory(source_parent_fd)
        _append_rollback_event(root_fd, plan, approval, "ROLLBACK_ARCHIVE_SOURCE_REMOVED", created_at, action)
    except ArchiveApplyError as error:
        raise RecoveryError("ROLLBACK_SOURCE_DRIFT") from error
    except OSError as error:
        raise RecoveryError("ROLLBACK_FILESYSTEM_FAILURE") from error
    finally:
        if source_fd is not None:
            os.close(source_fd)
        if destination_parent_fd is not None:
            os.close(destination_parent_fd)
        if source_parent_fd is not None:
            os.close(source_parent_fd)


def _append_rollback_event(
    root_fd: int,
    plan: Mapping[str, Any],
    approval: Mapping[str, Any],
    event_type: str,
    created_at: str,
    action: Optional[Mapping[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    journal = ".repo-curator/applies/{}/apply-journal.jsonl".format(plan["original_plan_id"])
    parent_fd = None
    try:
        parent_fd, _ = _open_parent(root_fd, journal)
        append_event(parent_fd, {
            "action_id": None,
            "approval_id": approval["approval_id"],
            "approval_sha256": approval_sha256(approval),
            "apply_run_id": plan.get("source_apply_run_id"),
            "created_at": created_at,
            "destination_observation": None,
            "error": error,
            "event_type": event_type,
            "expected_state_hash": None,
            "observed_state_hash": None,
            "operator_note": None,
            "plan_id": plan["original_plan_id"],
            "plan_sha256": plan["original_plan_sha256"],
            "rollback_action_id": action.get("action_id") if action else None,
            "rollback_plan_id": plan["plan_id"],
            "source_observation": None,
            "timestamp": created_at,
        })
    except (ArchiveApplyError, OSError) as error:
        raise RecoveryError("ROLLBACK_JOURNAL_FAILURE") from error
    finally:
        if parent_fd is not None:
            os.close(parent_fd)


def _write_rollback_receipt(
    root_fd: int,
    plan: Mapping[str, Any],
    action: Mapping[str, Any],
    created_at: str,
) -> None:
    provenance = _read_regular(root_fd, action["source_path"] + ".provenance.json", 64 * 1024)
    receipt_directory = _ensure_directory(
        root_fd, [".repo-curator", "applies", plan["original_plan_id"], "rollback-receipts"]
    )
    try:
        name = action["action_id"] + ".json"
        descriptor = os.open(
            name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600, dir_fd=receipt_directory,
        )
        try:
            payload = canonical_bytes({
                "created_at": created_at,
                "original_action_id": action["original_action_id"],
                "provenance_base64": base64.b64encode(provenance).decode("ascii"),
                "provenance_sha256": sha256(provenance),
                "rollback_action_id": action["action_id"],
                "rollback_plan_id": plan["plan_id"],
                "schema_version": "repo-curator.rollback-receipt.v1",
            }) + b"\n"
            write_all(descriptor, payload)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        fsync_directory(receipt_directory)
    finally:
        os.close(receipt_directory)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
