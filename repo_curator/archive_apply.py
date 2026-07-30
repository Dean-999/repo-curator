"""One exact-approved same-filesystem archive tracer."""

import errno
import hashlib
import json
import os
import shutil
import stat
import subprocess
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from repo_curator.approval import validate_approval
from repo_curator.transactions import (
    JOURNAL_SCHEMA_VERSION, MAX_JOURNAL_BYTES, TransactionError, append_event,
    approval_sha256, fsync_directory, mutation_lock, parse_journal, read_journal, write_all,
)


POLICY_HASH = "sha256:repo-curator-archive-tracer-v1"
DECISION_HASH = "sha256:no-external-decisions-v1"
MAX_PROVENANCE_BYTES = 64 * 1024


class ArchiveApplyError(ValueError):
    """Fail-closed archive-tracer rejection with a stable code."""


def archive_destination(plan_id: str, source_path: str) -> str:
    if not _safe_component(plan_id) or not _safe_path(source_path):
        raise ArchiveApplyError("PLAN_ARCHIVE_DESTINATION_INVALID")
    digest = hashlib.sha256(source_path.encode("utf-8")).hexdigest()[:16]
    return "archive/repo-curator/{}/{:s}-{}".format(
        plan_id, digest, source_path.rsplit("/", 1)[-1]
    )


def observe_apply_context(root: Path) -> Dict[str, str]:
    resolved = root.resolve(strict=True)
    return {
        "decision_set_hash": DECISION_HASH,
        "effective_policy_hash": POLICY_HASH,
        "repository_state_hash": _state_hash(resolved),
    }


def apply_archive(root: Path, plan_bytes: bytes, approval: Mapping[str, Any], created_at: str) -> Dict[str, Any]:
    resolved = root.resolve(strict=True)
    if not resolved.is_dir() or not _is_git_worktree(resolved):
        raise ArchiveApplyError("PREFLIGHT_REPOSITORY_MODE")
    plan = _parse_plan(plan_bytes)
    _require_approval(plan_bytes, approval, {
        field: plan.get(field)
        for field in ("decision_set_hash", "effective_policy_hash", "repository_state_hash")
    })
    action = _single_action(plan, approval)
    _validate_archive_plan(plan, action)
    root_fd = os.open(resolved, _directory_flags())
    try:
        try:
            with mutation_lock(root_fd, {
                "created_at": created_at, "operation": "ARCHIVE", "plan_id": plan["plan_id"],
                "process_id": os.getpid(),
            }):
                completion = _completion_state(root_fd, plan, approval, action)
                if completion == "VERIFIED":
                    return {"action_id": action["action_id"], "status": "ALREADY_VERIFIED"}
                if completion == "AMBIGUOUS":
                    raise ArchiveApplyError("MANUAL_RECOVERY_REQUIRED")
                _require_approval(plan_bytes, approval, observe_apply_context(resolved))
                return _apply(root_fd, plan, action, approval, created_at)
        except TransactionError as error:
            raise ArchiveApplyError(str(error)) from error
    finally:
        os.close(root_fd)


def _parse_plan(payload: bytes) -> Mapping[str, Any]:
    try:
        plan = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ArchiveApplyError("PLAN_MALFORMED") from error
    if not isinstance(plan, dict):
        raise ArchiveApplyError("PLAN_MALFORMED")
    return plan


def _is_git_worktree(root: Path) -> bool:
    try:
        control = os.lstat(root / ".git")
    except OSError:
        return False
    if not (stat.S_ISDIR(control.st_mode) or stat.S_ISREG(control.st_mode)):
        return False
    result = _run_sanitized_git(root, ["rev-parse", "--is-inside-work-tree"])
    return result is not None and result.returncode == 0 and result.stdout.strip() == b"true"


def _run_sanitized_git(root: Path, arguments: list[str]) -> Optional[subprocess.CompletedProcess[bytes]]:
    executable = shutil.which("git", path=os.defpath)
    if executable is None:
        return None
    environment = {
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_PAGER": "cat",
        "GIT_TERMINAL_PROMPT": "0",
        "HOME": os.devnull,
        "LC_ALL": "C",
        "PAGER": "cat",
        "PATH": os.defpath,
    }
    try:
        return subprocess.run(
            [
                executable, "-c", "core.fsmonitor=false", "-c", "core.pager=cat",
                "--no-pager", *arguments,
            ],
            cwd=root, env=environment, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, check=False, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None


def _git_head(root: Path) -> Optional[str]:
    result = _run_sanitized_git(root, ["rev-parse", "--verify", "HEAD"])
    if result is None or result.returncode != 0:
        return None
    try:
        head = result.stdout.strip().decode("ascii", "strict")
    except UnicodeDecodeError:
        return None
    return head if len(head) in {40, 64} and all(character in "0123456789abcdef" for character in head) else None


def _single_action(plan: Mapping[str, Any], approval: Mapping[str, Any]) -> Mapping[str, Any]:
    actions = plan.get("action_candidates")
    approved = approval.get("approved_action_ids")
    if not isinstance(actions, list) or len(actions) != 1 or not isinstance(approved, list) or len(approved) != 1:
        raise ArchiveApplyError("PLAN_SINGLE_ACTION_REQUIRED")
    action = actions[0]
    if not isinstance(action, dict) or action.get("action_id") != approved[0]:
        raise ArchiveApplyError("PLAN_SINGLE_ACTION_REQUIRED")
    return action


def _validate_archive_plan(plan: Mapping[str, Any], action: Mapping[str, Any]) -> None:
    if plan.get("schema_version") != "repo-curator.archive-plan.v1" or plan.get("planner") != "repo_curator.archive_tracer.v1":
        raise ArchiveApplyError("PLAN_UNSUPPORTED_PLANNER")
    if plan.get("execution_mode") != "APPLY_READY" or action.get("type") != "ARCHIVE":
        raise ArchiveApplyError("PLAN_UNSUPPORTED_ACTION")
    plan_id = plan.get("plan_id")
    source_path = action.get("source_path")
    if not isinstance(plan_id, str) or not isinstance(source_path, str):
        raise ArchiveApplyError("PLAN_MALFORMED")
    if action.get("destination_path") != archive_destination(plan_id, source_path):
        raise ArchiveApplyError("PLAN_ARCHIVE_DESTINATION_INVALID")


def _require_approval(plan_bytes: bytes, approval: Mapping[str, Any], context: Mapping[str, Any]) -> None:
    result = validate_approval(plan_bytes, approval, context)
    if not result["valid"]:
        raise ArchiveApplyError(result["errors"][0])


def _apply(root_fd: int, plan: Mapping[str, Any], action: Mapping[str, Any], approval: Mapping[str, Any], created_at: str) -> Dict[str, Any]:
    journal_fd = _ensure_directory(root_fd, [".repo-curator", "applies", plan["plan_id"]])
    source_parent_fd = None
    source_fd = None
    destination_parent_fd = None
    try:
        _event(journal_fd, plan, approval, action, created_at, "ACTION_VALIDATION_STARTED")
        source_parent_fd, source_name, source_fd, source_stat = _open_source(root_fd, action["source_path"])
        if _fingerprint(source_fd) != action.get("source_fingerprint"):
            raise ArchiveApplyError("DRIFT_SOURCE_FINGERPRINT")
        destination_parent_fd, destination_name = _destination_parent(root_fd, action["destination_path"])
        try:
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
                if (not stat.S_ISREG(destination_stat.st_mode) or
                        (destination_stat.st_dev, destination_stat.st_ino) != (source_stat.st_dev, source_stat.st_ino) or
                        _fingerprint(destination_fd) != action["source_fingerprint"]):
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
            if not _verify_completed_action(root_fd, plan, approval, action, require_commit=False):
                raise ArchiveApplyError("VERIFY_POSTCONDITION")
            _event(journal_fd, plan, approval, None, created_at, "TRANSACTION_COMMITTED")
            if not _verify_completed_action(root_fd, plan, approval, action, require_commit=True):
                raise ArchiveApplyError("VERIFY_POSTCONDITION")
            return {"action_id": action["action_id"], "status": "APPLIED"}
        finally:
            os.close(destination_parent_fd)
    except (ArchiveApplyError, OSError) as error:
        failure = error if isinstance(error, ArchiveApplyError) else ArchiveApplyError("ACTION_FILESYSTEM_FAILURE")
        _event(journal_fd, plan, approval, action, created_at, "ACTION_FAILED", str(failure))
        raise failure from error
    finally:
        if source_fd is not None:
            os.close(source_fd)
        if source_parent_fd is not None:
            os.close(source_parent_fd)
        os.close(journal_fd)


def _completion_state(root_fd: int, plan: Mapping[str, Any], approval: Mapping[str, Any], action: Mapping[str, Any]) -> str:
    source = _entry_kind(root_fd, action["source_path"])
    destination = _entry_kind(root_fd, action["destination_path"])
    provenance = _entry_kind(root_fd, action["destination_path"] + ".provenance.json")
    journal = _entry_kind(root_fd, ".repo-curator/applies/{}/apply-journal.jsonl".format(plan["plan_id"]))
    if "UNSAFE" in {destination, provenance, journal}:
        return "AMBIGUOUS"
    if source == "ABSENT" and destination == provenance == journal == "REGULAR":
        return "VERIFIED" if _verify_completed_action(root_fd, plan, approval, action) else "AMBIGUOUS"
    if source == "ABSENT" and (destination != "ABSENT" or provenance != "ABSENT" or journal != "ABSENT"):
        return "AMBIGUOUS"
    if source == "REGULAR" and (provenance != "ABSENT" or journal != "ABSENT"):
        return "AMBIGUOUS"
    return "NOT_STARTED"


def _verify_completed_action(root_fd: int, plan: Mapping[str, Any], approval: Mapping[str, Any], action: Mapping[str, Any], require_commit: bool = True) -> bool:
    try:
        if _entry_kind(root_fd, action["source_path"]) != "ABSENT":
            return False
        destination = _read_regular(root_fd, action["destination_path"], None)
        if hashlib.sha256(destination).hexdigest() != action.get("source_fingerprint"):
            return False
        provenance = json.loads(_read_regular(root_fd, action["destination_path"] + ".provenance.json", MAX_PROVENANCE_BYTES).decode("utf-8"))
        if not isinstance(provenance, dict) or provenance.get("plan_id") != plan["plan_id"] or provenance.get("original_path") != action["source_path"] or not isinstance(provenance.get("created_at"), str):
            return False
        journal_payload = _read_regular(root_fd, ".repo-curator/applies/{}/apply-journal.jsonl".format(plan["plan_id"]), MAX_JOURNAL_BYTES)
        events = parse_journal(journal_payload)
    except (ArchiveApplyError, OSError, UnicodeDecodeError, json.JSONDecodeError, TransactionError):
        return False
    expected_types = ["ACTION_VALIDATION_STARTED", "MOVE_STARTED", "DESTINATION_OBSERVED", "SOURCE_REMOVAL_OBSERVED", "ACTION_VERIFIED"]
    if require_commit:
        expected_types.append("TRANSACTION_COMMITTED")
    if [event.get("event_type") for event in events] != expected_types:
        return False
    return all(
        event.get("schema_version") == JOURNAL_SCHEMA_VERSION
        and event.get("plan_id") == plan["plan_id"]
        and event.get("approval_id") == approval["approval_id"]
        and event.get("plan_sha256") == approval["approved_plan_sha256"]
        and event.get("approval_sha256") == approval_sha256(approval)
        and event.get("action_id") == (None if event.get("event_type") == "TRANSACTION_COMMITTED" else action["action_id"])
        and event.get("sequence") == index
        for index, event in enumerate(events, 1)
    )


def _open_source(root_fd: int, path: str) -> Tuple[int, str, int, os.stat_result]:
    if not _safe_path(path):
        raise ArchiveApplyError("PATH_TRAVERSAL")
    if _protected(path):
        raise ArchiveApplyError("PATH_PROTECTED")
    parent_fd, name = _open_parent(root_fd, path)
    try:
        descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
    except OSError as error:
        os.close(parent_fd)
        code = "PATH_EXTERNAL_SYMLINK" if error.errno == errno.ELOOP else "DRIFT_SOURCE_MISSING"
        raise ArchiveApplyError(code) from error
    observed = os.fstat(descriptor)
    if not stat.S_ISREG(observed.st_mode):
        os.close(descriptor)
        os.close(parent_fd)
        raise ArchiveApplyError("PATH_EXTERNAL_SYMLINK")
    return parent_fd, name, descriptor, observed


def _destination_parent(root_fd: int, path: str) -> Tuple[int, str]:
    if not _safe_path(path) or _protected(path) or not path.startswith("archive/repo-curator/"):
        raise ArchiveApplyError("PATH_TRAVERSAL")
    parts = path.split("/")
    return _ensure_directory(root_fd, parts[:-1]), parts[-1]


def _open_parent(root_fd: int, path: str) -> Tuple[int, str]:
    parts = path.split("/")
    parent_fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            next_fd = os.open(part, _directory_flags(), dir_fd=parent_fd)
            os.close(parent_fd)
            parent_fd = next_fd
        return parent_fd, parts[-1]
    except OSError as error:
        os.close(parent_fd)
        raise ArchiveApplyError("PATH_EXTERNAL_SYMLINK") from error


def _ensure_directory(root_fd: int, parts: list[str]) -> int:
    descriptor = os.dup(root_fd)
    try:
        for part in parts:
            try:
                os.mkdir(part, 0o700, dir_fd=descriptor)
                fsync_directory(descriptor)
            except FileExistsError:
                pass
            next_fd = os.open(part, _directory_flags(), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_fd
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _event(journal_fd: int, plan: Mapping[str, Any], approval: Mapping[str, Any], action: Optional[Mapping[str, Any]], created_at: str, event_type: str, error: Optional[str] = None) -> None:
    record = {
        "action_id": action["action_id"] if action else None,
        "approval_id": approval["approval_id"],
        "approval_sha256": approval_sha256(approval),
        "apply_run_id": _apply_run_id(plan, approval, created_at),
        "created_at": created_at,
        "destination_observation": {
            "expected_fingerprint": action.get("source_fingerprint"), "path": action.get("destination_path"),
        } if action else None,
        "error": error,
        "event_type": event_type,
        "expected_state_hash": plan.get("repository_state_hash"),
        "observed_state_hash": None,
        "operator_note": None,
        "plan_id": plan["plan_id"],
        "plan_sha256": approval["approved_plan_sha256"],
        "rollback_action_id": None,
        "rollback_plan_id": None,
        "source_observation": {
            "expected_fingerprint": action.get("source_fingerprint"), "path": action.get("source_path"),
        } if action else None,
        "timestamp": created_at,
    }
    append_event(journal_fd, record)


def _sequence(journal_fd: int) -> int:
    try:
        return len(read_journal(journal_fd, missing_ok=True))
    except TransactionError as error:
        raise ArchiveApplyError("MANUAL_RECOVERY_REQUIRED") from error


def _apply_run_id(plan: Mapping[str, Any], approval: Mapping[str, Any], created_at: str) -> str:
    payload = _json_bytes({
        "approval_id": approval.get("approval_id"),
        "created_at": created_at,
        "plan_id": plan.get("plan_id"),
    })
    return "apply_" + hashlib.sha256(payload).hexdigest()[:16]


def _provenance(parent_fd: int, name: str, plan_id: str, source_path: str, created_at: str) -> None:
    descriptor = os.open(name + ".provenance.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, dir_fd=parent_fd)
    try:
        write_all(descriptor, _json_bytes({"created_at": created_at, "original_path": source_path, "plan_id": plan_id}))
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    fsync_directory(parent_fd)


def _destination_absent(parent_fd: int, name: str) -> None:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise ArchiveApplyError("PATH_DESTINATION_EXISTS")


def _absent(parent_fd: int, name: str) -> None:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise ArchiveApplyError("DRIFT_SOURCE_REPLACED")


def _entry_kind(root_fd: int, path: str) -> str:
    if not _safe_path(path):
        return "UNSAFE"
    parts = path.split("/")
    parent_fd = os.dup(root_fd)
    try:
        try:
            for part in parts[:-1]:
                next_fd = os.open(part, _directory_flags(), dir_fd=parent_fd)
                os.close(parent_fd)
                parent_fd = next_fd
            observed = os.stat(parts[-1], dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            return "ABSENT"
        except OSError:
            return "UNSAFE"
    finally:
        os.close(parent_fd)
    return "REGULAR" if stat.S_ISREG(observed.st_mode) else "UNSAFE"


def _read_regular(root_fd: int, path: str, maximum_bytes: Optional[int]) -> bytes:
    parent_fd, name = _open_parent(root_fd, path)
    try:
        descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
    except OSError as error:
        os.close(parent_fd)
        raise ArchiveApplyError("MANUAL_RECOVERY_REQUIRED") from error
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode):
            raise ArchiveApplyError("MANUAL_RECOVERY_REQUIRED")
        payload = _read_all(descriptor, maximum_bytes)
        _unchanged(parent_fd, name, observed)
        return payload
    finally:
        os.close(descriptor)
        os.close(parent_fd)


def _read_all(descriptor: int, maximum_bytes: Optional[int]) -> bytes:
    chunks = []
    size = 0
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        size += len(chunk)
        if maximum_bytes is not None and size > maximum_bytes:
            raise ArchiveApplyError("MANUAL_RECOVERY_REQUIRED")
        chunks.append(chunk)


def _unchanged(parent_fd: int, name: str, expected: os.stat_result) -> None:
    try:
        observed = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except FileNotFoundError as error:
        raise ArchiveApplyError("DRIFT_SOURCE_MISSING") from error
    if not stat.S_ISREG(observed.st_mode) or (observed.st_dev, observed.st_ino) != (expected.st_dev, expected.st_ino):
        raise ArchiveApplyError("DRIFT_SOURCE_REPLACED")


def _fingerprint(descriptor: int) -> str:
    os.lseek(descriptor, 0, os.SEEK_SET)
    digest = hashlib.sha256()
    while True:
        chunk = os.read(descriptor, 1024 * 1024)
        if not chunk:
            return digest.hexdigest()
        digest.update(chunk)


def _state_hash(root: Path) -> str:
    root_fd = os.open(root, _directory_flags())
    try:
        records = _state_records(root_fd, "")
    except OSError as error:
        raise ArchiveApplyError("DRIFT_REPOSITORY_STATE") from error
    finally:
        os.close(root_fd)
    records.append([".git/HEAD", "GIT_HEAD", _git_head(root)])
    return "sha256:" + hashlib.sha256(json.dumps(sorted(records), ensure_ascii=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _state_records(directory_fd: int, prefix: str) -> list[list[Any]]:
    records = []
    for name in sorted(os.listdir(directory_fd)):
        if not prefix and name in {".git", ".repo-curator"}:
            continue
        relative = name if not prefix else prefix + "/" + name
        observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        if stat.S_ISREG(observed.st_mode):
            records.append([relative, "FILE", observed.st_size, observed.st_mode & 0o7777, _safe_digest_entry(directory_fd, name, observed)])
        elif stat.S_ISDIR(observed.st_mode):
            records.append([relative, "DIRECTORY", 0, observed.st_mode & 0o7777, None])
            child_fd = os.open(name, _directory_flags(), dir_fd=directory_fd)
            try:
                child = os.fstat(child_fd)
                _same_object(observed, child)
                records.extend(_state_records(child_fd, relative))
            finally:
                os.close(child_fd)
            _same_named_entry(directory_fd, name, observed)
        elif stat.S_ISLNK(observed.st_mode):
            target = os.readlink(name, dir_fd=directory_fd)
            _same_named_entry(directory_fd, name, observed)
            records.append([relative, "SYMLINK", 0, observed.st_mode & 0o7777, target])
    return records


def _safe_digest_entry(parent_fd: int, name: str, expected: os.stat_result) -> str:
    try:
        descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
    except OSError as error:
        raise ArchiveApplyError("DRIFT_REPOSITORY_STATE") from error
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode):
            raise ArchiveApplyError("DRIFT_REPOSITORY_STATE")
        _same_object(expected, observed)
        digest = _fingerprint(descriptor)
        _same_named_entry(parent_fd, name, expected)
        return digest
    finally:
        os.close(descriptor)


def _same_named_entry(parent_fd: int, name: str, expected: os.stat_result) -> None:
    try:
        observed = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError as error:
        raise ArchiveApplyError("DRIFT_REPOSITORY_STATE") from error
    _same_object(expected, observed)


def _same_object(expected: os.stat_result, observed: os.stat_result) -> None:
    if (expected.st_dev, expected.st_ino) != (observed.st_dev, observed.st_ino):
        raise ArchiveApplyError("DRIFT_REPOSITORY_STATE")


def _safe_component(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value
        and chr(0) not in value
        and "/" not in value
        and chr(92) not in value
        and value not in {".", ".."}
    )


def _safe_path(value: Any) -> bool:
    return (
        isinstance(value, str)
        and value
        and chr(0) not in value
        and not value.startswith("/")
        and chr(92) not in value
        and all(part not in {"", ".", ".."} for part in value.split("/"))
    )


def _protected(path: str) -> bool:
    return any(path == prefix or path.startswith(prefix + "/") for prefix in (".git", ".repo-curator", ".agents"))


def _directory_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _json_bytes(value: Mapping[str, Any]) -> bytes:
    return (json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
