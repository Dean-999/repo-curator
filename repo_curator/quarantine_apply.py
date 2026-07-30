"""Approved, bundle-aware same-filesystem quarantine batch."""

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Sequence, Tuple

from repo_curator.approval import validate_approval
from repo_curator.archive_apply import (
    ArchiveApplyError,
    DECISION_HASH,
    POLICY_HASH,
    _absent,
    _directory_flags,
    _ensure_directory,
    _entry_kind,
    _event,
    _fingerprint,
    _is_git_worktree,
    _open_source,
    _parse_plan,
    _read_regular,
    _safe_component,
    _safe_path,
    _git_head,
    _state_hash,
    _state_records,
    _unchanged,
)
from repo_curator.transactions import (
    TransactionError, approval_sha256, fsync_directory, mutation_lock, parse_journal, write_all,
)


def quarantine_destination(plan_id: str, source_path: str) -> str:
    """Return the sole permitted destination for one quarantine action."""
    if not _safe_component(plan_id) or not _safe_path(source_path):
        raise ArchiveApplyError("PLAN_QUARANTINE_DESTINATION_INVALID")
    digest = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:16]
    return ".repo-curator/quarantine/{}/{}-{}".format(
        plan_id, digest, source_path.rsplit("/", 1)[-1]
    )


def apply_quarantine_batch(
    root: Path, plan_bytes: bytes, approval: Mapping[str, Any], created_at: str
) -> Dict[str, Any]:
    """Move one complete approved quarantine batch, or stop at its first failure."""
    resolved = root.resolve(strict=True)
    if not resolved.is_dir() or not _is_git_worktree(resolved):
        raise ArchiveApplyError("PREFLIGHT_REPOSITORY_MODE")
    plan = _parse_plan(plan_bytes)
    _require_approval(plan_bytes, approval, _plan_context(plan))
    actions = _batch_actions(plan, approval)
    _validate_plan(plan, actions)
    root_fd = os.open(resolved, _directory_flags())
    try:
        try:
            with mutation_lock(root_fd, {
                "created_at": created_at, "operation": "QUARANTINE", "plan_id": plan["plan_id"],
                "process_id": os.getpid(),
            }):
                state = _batch_completion_state(root_fd, plan, approval, actions)
                if state == "VERIFIED":
                    return _result("ALREADY_VERIFIED", [action["action_id"] for action in actions], None, [])
                if state == "AMBIGUOUS":
                    raise ArchiveApplyError("MANUAL_RECOVERY_REQUIRED")
                _require_approval(plan_bytes, approval, _observed_context(resolved))
                _prevalidate_all(root_fd, actions)
                baseline_records = _state_records(root_fd, "")
                baseline_head = _git_head(resolved)
                if _hash_state_records(baseline_records, baseline_head) != plan.get("repository_state_hash"):
                    raise ArchiveApplyError("DRIFT_REPOSITORY_STATE")
                return _execute_batch(
                    root_fd, resolved, plan, approval, actions, created_at, baseline_records, baseline_head
                )
        except TransactionError as error:
            raise ArchiveApplyError(str(error)) from error
    finally:
        os.close(root_fd)


def _plan_context(plan: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        field: plan.get(field)
        for field in ("decision_set_hash", "effective_policy_hash", "repository_state_hash")
    }


def _observed_context(root: Path) -> Dict[str, str]:
    return {
        "decision_set_hash": DECISION_HASH,
        "effective_policy_hash": POLICY_HASH,
        "repository_state_hash": _state_hash(root),
    }


def _require_approval(
    plan_bytes: bytes, approval: Mapping[str, Any], context: Mapping[str, Any]
) -> None:
    result = validate_approval(plan_bytes, approval, context)
    if not result["valid"]:
        raise ArchiveApplyError(result["errors"][0])


def _batch_actions(
    plan: Mapping[str, Any], approval: Mapping[str, Any]
) -> Sequence[Mapping[str, Any]]:
    actions = plan.get("action_candidates")
    approved = approval.get("approved_action_ids")
    if not isinstance(actions, list) or not actions or not isinstance(approved, list):
        raise ArchiveApplyError("PLAN_BATCH_ACTIONS_REQUIRED")
    if not all(isinstance(action, dict) for action in actions):
        raise ArchiveApplyError("PLAN_BATCH_ACTIONS_REQUIRED")
    action_ids = [action.get("action_id") for action in actions]
    if not all(isinstance(action_id, str) for action_id in action_ids):
        raise ArchiveApplyError("PLAN_BATCH_ACTIONS_REQUIRED")
    if action_ids != approved or len(set(action_ids)) != len(action_ids):
        raise ArchiveApplyError("PLAN_BATCH_ACTIONS_REQUIRED")
    return actions


def _validate_plan(plan: Mapping[str, Any], actions: Sequence[Mapping[str, Any]]) -> None:
    if (
        plan.get("schema_version") != "repo-curator.quarantine-plan.v1"
        or plan.get("planner") != "repo_curator.quarantine_batch.v1"
    ):
        raise ArchiveApplyError("PLAN_UNSUPPORTED_PLANNER")
    if plan.get("execution_mode") != "APPLY_READY":
        raise ArchiveApplyError("PLAN_UNSUPPORTED_ACTION")
    plan_id = plan.get("plan_id")
    if not _safe_component(plan_id):
        raise ArchiveApplyError("PLAN_MALFORMED")
    for action in actions:
        if action.get("type") != "QUARANTINE":
            raise ArchiveApplyError("PLAN_UNSUPPORTED_ACTION")
        source_path = action.get("source_path")
        if not isinstance(source_path, str) or action.get("destination_path") != quarantine_destination(plan_id, source_path):
            raise ArchiveApplyError("PLAN_QUARANTINE_DESTINATION_INVALID")
        if action.get("resolution_status") != "RESOLVED":
            raise ArchiveApplyError("ACTION_UNRESOLVED")
    _validate_bundles(actions)


def _validate_bundles(actions: Sequence[Mapping[str, Any]]) -> None:
    action_ids = {action["action_id"] for action in actions}
    bundles: Dict[str, list[Mapping[str, Any]]] = {}
    for action in actions:
        bundle_id = action.get("bundle_id")
        if not isinstance(bundle_id, str) or not bundle_id:
            raise ArchiveApplyError("BUNDLE_PARTIAL_MOVEMENT")
        bundles.setdefault(bundle_id, []).append(action)
    for members in bundles.values():
        member_ids = {member["action_id"] for member in members}
        for action in members:
            declared = action.get("bundle_member_action_ids")
            if not isinstance(declared, list) or set(declared) != member_ids:
                raise ArchiveApplyError("BUNDLE_PARTIAL_MOVEMENT")
    if not action_ids:
        raise ArchiveApplyError("PLAN_BATCH_ACTIONS_REQUIRED")


def _prevalidate_all(root_fd: int, actions: Sequence[Mapping[str, Any]]) -> None:
    destinations = set()
    sources = set()
    for action in actions:
        source = action["source_path"]
        destination = action["destination_path"]
        if source in sources or destination in destinations or source in destinations:
            raise ArchiveApplyError("PLAN_ACTION_CONFLICT")
        sources.add(source)
        destinations.add(destination)
        _validate_source(root_fd, action)
        _validate_destination(root_fd, destination)


def _validate_source(root_fd: int, action: Mapping[str, Any]) -> None:
    parent_fd, _, descriptor, observed = _open_source(root_fd, action["source_path"])
    try:
        if _fingerprint(descriptor) != action.get("source_fingerprint"):
            raise ArchiveApplyError("DRIFT_SOURCE_FINGERPRINT")
        _unchanged(parent_fd, action["source_path"].rsplit("/", 1)[-1], observed)
    finally:
        os.close(descriptor)
        os.close(parent_fd)


def _validate_destination(root_fd: int, destination: str) -> None:
    if not _safe_path(destination) or not destination.startswith(".repo-curator/quarantine/"):
        raise ArchiveApplyError("PLAN_QUARANTINE_DESTINATION_INVALID")
    parts = destination.split("/")
    parent_fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            try:
                next_fd = os.open(part, _directory_flags(), dir_fd=parent_fd)
            except FileNotFoundError:
                return
            os.close(parent_fd)
            parent_fd = next_fd
        try:
            os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return
        raise ArchiveApplyError("PATH_DESTINATION_EXISTS")
    except OSError as error:
        raise ArchiveApplyError("PATH_EXTERNAL_SYMLINK") from error
    finally:
        os.close(parent_fd)


def _execute_batch(
    root_fd: int,
    root: Path,
    plan: Mapping[str, Any],
    approval: Mapping[str, Any],
    actions: Sequence[Mapping[str, Any]],
    created_at: str,
    baseline_records: Sequence[Sequence[Any]],
    baseline_head: Any,
) -> Dict[str, Any]:
    journal_fd = _ensure_directory(root_fd, [".repo-curator", "applies", plan["plan_id"]])
    completed = []
    try:
        for index, action in enumerate(actions):
            try:
                expected_state = _expected_state_hash(
                    baseline_records,
                    baseline_head,
                    [item["source_path"] for item in actions[:index]],
                )
                _execute_action(
                    root_fd, journal_fd, plan, approval, action, created_at, root, expected_state
                )
            except ArchiveApplyError as error:
                skipped = list(actions[index + 1:])
                for remaining in skipped:
                    _event(journal_fd, plan, approval, remaining, created_at, "ACTION_SKIPPED", str(error))
                return _result("PARTIAL_FAILURE", completed, action["action_id"], [item["action_id"] for item in skipped])
            completed.append(action["action_id"])
        _event(journal_fd, plan, approval, None, created_at, "TRANSACTION_COMMITTED")
    finally:
        os.close(journal_fd)
    return _result("APPLIED", completed, None, [])


def _execute_action(
    root_fd: int,
    journal_fd: int,
    plan: Mapping[str, Any],
    approval: Mapping[str, Any],
    action: Mapping[str, Any],
    created_at: str,
    root: Path,
    expected_state_hash: str,
) -> None:
    source_parent_fd = None
    source_fd = None
    destination_parent_fd = None
    try:
        _event(journal_fd, plan, approval, action, created_at, "ACTION_VALIDATION_STARTED")
        if _state_hash(root) != expected_state_hash:
            raise ArchiveApplyError("DRIFT_REPOSITORY_STATE")
        source_parent_fd, source_name, source_fd, source_stat = _open_source(root_fd, action["source_path"])
        if _fingerprint(source_fd) != action.get("source_fingerprint"):
            raise ArchiveApplyError("DRIFT_SOURCE_FINGERPRINT")
        destination_parent_fd, destination_name = _quarantine_parent(root_fd, action["destination_path"])
        _destination_absent(destination_parent_fd, destination_name)
        if source_stat.st_dev != os.fstat(destination_parent_fd).st_dev:
            raise ArchiveApplyError("CROSS_FILESYSTEM_MOVE_UNSUPPORTED")
        _unchanged(source_parent_fd, source_name, source_stat)
        _event(journal_fd, plan, approval, action, created_at, "MOVE_STARTED")
        os.link(source_name, destination_name, src_dir_fd=source_parent_fd, dst_dir_fd=destination_parent_fd, follow_symlinks=False)
        fsync_directory(destination_parent_fd)
        destination_fd = os.open(destination_name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=destination_parent_fd)
        try:
            destination_stat = os.fstat(destination_fd)
            if (
                not stat.S_ISREG(destination_stat.st_mode)
                or (destination_stat.st_dev, destination_stat.st_ino) != (source_stat.st_dev, source_stat.st_ino)
                or _fingerprint(destination_fd) != action["source_fingerprint"]
            ):
                raise ArchiveApplyError("VERIFY_DESTINATION_FINGERPRINT")
        finally:
            os.close(destination_fd)
        _unchanged(source_parent_fd, source_name, source_stat)
        _event(journal_fd, plan, approval, action, created_at, "DESTINATION_OBSERVED")
        _provenance(destination_parent_fd, destination_name, plan["plan_id"], action["source_path"], created_at)
        _unchanged(source_parent_fd, source_name, source_stat)
        os.unlink(source_name, dir_fd=source_parent_fd)
        fsync_directory(source_parent_fd)
        _absent(source_parent_fd, source_name)
        _unchanged(destination_parent_fd, destination_name, destination_stat)
        _event(journal_fd, plan, approval, action, created_at, "SOURCE_REMOVAL_OBSERVED")
        _event(journal_fd, plan, approval, action, created_at, "ACTION_VERIFIED")
        if not _action_files_verified(root_fd, plan, action):
            raise ArchiveApplyError("VERIFY_POSTCONDITION")
    except (ArchiveApplyError, OSError) as error:
        failure = error if isinstance(error, ArchiveApplyError) else ArchiveApplyError("ACTION_FILESYSTEM_FAILURE")
        _event(journal_fd, plan, approval, action, created_at, "ACTION_FAILED", str(failure))
        raise failure from error
    finally:
        if destination_parent_fd is not None:
            os.close(destination_parent_fd)
        if source_fd is not None:
            os.close(source_fd)
        if source_parent_fd is not None:
            os.close(source_parent_fd)


def _quarantine_parent(root_fd: int, destination: str) -> Tuple[int, str]:
    parts = destination.split("/")
    return _ensure_directory(root_fd, parts[:-1]), parts[-1]


def _destination_absent(parent_fd: int, name: str) -> None:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise ArchiveApplyError("PATH_DESTINATION_EXISTS")


def _provenance(
    parent_fd: int, name: str, plan_id: str, source_path: str, created_at: str
) -> None:
    descriptor = os.open(
        name + ".provenance.json",
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=parent_fd,
    )
    try:
        payload = {
            "created_at": created_at,
            "original_path": source_path,
            "plan_id": plan_id,
        }
        write_all(descriptor, (json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8"))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    fsync_directory(parent_fd)


def _batch_completion_state(
    root_fd: int,
    plan: Mapping[str, Any],
    approval: Mapping[str, Any],
    actions: Sequence[Mapping[str, Any]],
) -> str:
    journal = ".repo-curator/applies/{}/apply-journal.jsonl".format(plan["plan_id"])
    scope = ".repo-curator/applies/{}".format(plan["plan_id"])
    journal_kind = _entry_kind(root_fd, journal)
    if journal_kind == "ABSENT":
        return "NOT_STARTED" if _entry_kind(root_fd, scope) == "ABSENT" else "AMBIGUOUS"
    if journal_kind != "REGULAR":
        return "AMBIGUOUS"
    try:
        events = parse_journal(_read_regular(root_fd, journal, 1024 * 1024))
    except (ArchiveApplyError, OSError, UnicodeDecodeError, json.JSONDecodeError, TransactionError):
        return "AMBIGUOUS"
    if not _journal_verifies_actions(events, plan, approval, actions):
        return "AMBIGUOUS"
    for action in actions:
        if not _action_verified(root_fd, plan, approval, action):
            return "AMBIGUOUS"
    return "VERIFIED"


def _action_verified(
    root_fd: int,
    plan: Mapping[str, Any],
    approval: Mapping[str, Any],
    action: Mapping[str, Any],
) -> bool:
    return _action_files_verified(root_fd, plan, action)


def _action_files_verified(
    root_fd: int, plan: Mapping[str, Any], action: Mapping[str, Any]
) -> bool:
    if (
        _entry_kind(root_fd, action["source_path"]) != "ABSENT"
        or _entry_kind(root_fd, action["destination_path"]) != "REGULAR"
        or _entry_kind(root_fd, action["destination_path"] + ".provenance.json") != "REGULAR"
    ):
        return False
    try:
        payload = _read_regular(root_fd, action["destination_path"], None)
        stated = json.loads(_read_regular(root_fd, action["destination_path"] + ".provenance.json", 64 * 1024).decode("utf-8"))
    except (ArchiveApplyError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return False
    return isinstance(stated, dict) and (
        hashlib.sha256(payload).hexdigest() == action.get("source_fingerprint")
        and stated.get("plan_id") == plan["plan_id"]
        and stated.get("original_path") == action["source_path"]
        and stated.get("created_at") is not None
    )


def _journal_verifies_actions(
    events: Sequence[Mapping[str, Any]],
    plan: Mapping[str, Any],
    approval: Mapping[str, Any],
    actions: Sequence[Mapping[str, Any]],
) -> bool:
    expected_types = (
        "ACTION_VALIDATION_STARTED",
        "MOVE_STARTED",
        "DESTINATION_OBSERVED",
        "SOURCE_REMOVAL_OBSERVED",
        "ACTION_VERIFIED",
    )
    if len(events) != len(actions) * len(expected_types) + 1:
        return False
    commit = events[-1]
    if commit.get("event_type") != "TRANSACTION_COMMITTED" or commit.get("action_id") is not None:
        return False
    for index, action in enumerate(actions):
        action_events = events[index * len(expected_types):(index + 1) * len(expected_types)]
        if [event.get("event_type") for event in action_events] != list(expected_types):
            return False
        for offset, event in enumerate(action_events, 1):
            if (
                event.get("schema_version") != "repo-curator.apply-journal.v2"
                or event.get("plan_id") != plan["plan_id"]
                or event.get("approval_id") != approval["approval_id"]
                or event.get("plan_sha256") != approval["approved_plan_sha256"]
                or event.get("approval_sha256") != approval_sha256(approval)
                or event.get("action_id") != action["action_id"]
                or event.get("sequence") != index * len(expected_types) + offset
            ):
                return False
    return (
        commit.get("plan_id") == plan["plan_id"]
        and commit.get("approval_id") == approval["approval_id"]
        and commit.get("plan_sha256") == approval["approved_plan_sha256"]
        and commit.get("approval_sha256") == approval_sha256(approval)
    )


def _expected_state_hash(
    baseline_records: Sequence[Sequence[Any]], baseline_head: Any, completed_sources: Iterable[str]
) -> str:
    completed = set(completed_sources)
    records = [record for record in baseline_records if record[0] not in completed]
    return _hash_state_records(records, baseline_head)


def _hash_state_records(records: Sequence[Sequence[Any]], git_head: Any) -> str:
    projection = list(records) + [[".git/HEAD", "GIT_HEAD", git_head]]
    encoded = json.dumps(sorted(projection), ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _result(
    status: str,
    completed_action_ids: Iterable[str],
    failed_action_id: Any,
    skipped_action_ids: Iterable[str],
) -> Dict[str, Any]:
    return {
        "completed_action_ids": list(completed_action_ids),
        "failed_action_id": failed_action_id,
        "skipped_action_ids": list(skipped_action_ids),
        "status": status,
    }
