"""Repository-scoped mutation locks and strict hash-chained journals."""

import errno
import fcntl
import hashlib
import json
import os
import stat
from contextlib import contextmanager
from typing import Any, Dict, Iterator, Mapping, Sequence


JOURNAL_SCHEMA_VERSION = "repo-curator.apply-journal.v2"
JOURNAL_NAME = "apply-journal.jsonl"
MAX_JOURNAL_BYTES = 1024 * 1024
ZERO_EVENT_HASH = "sha256:" + "0" * 64
_EVENT_FIELDS = {
    "action_id", "approval_id", "approval_sha256", "apply_run_id", "created_at",
    "destination_observation", "error", "event_hash", "event_type", "expected_state_hash",
    "journal_event_id", "observed_state_hash", "operator_note", "plan_id", "plan_sha256",
    "previous_event_hash", "rollback_action_id", "rollback_plan_id", "schema_version",
    "sequence", "source_observation", "timestamp",
}


class TransactionError(ValueError):
    """Stable failure for mutation lock and journal integrity checks."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")


def sha256(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def approval_sha256(approval: Mapping[str, Any]) -> str:
    return sha256(canonical_bytes(approval))


@contextmanager
def mutation_lock(root_fd: int, owner: Mapping[str, Any]) -> Iterator[None]:
    control_fd = _ensure_control_directory(root_fd)
    descriptor = None
    try:
        descriptor = os.open(
            "mutation.lock",
            os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=control_fd,
        )
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise TransactionError("MUTATION_LOCK_UNSAFE")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            if error.errno in {errno.EACCES, errno.EAGAIN}:
                raise TransactionError("MUTATION_LOCKED") from error
            raise TransactionError("MUTATION_LOCK_FAILURE") from error
        payload = canonical_bytes(dict(owner)) + b"\n"
        try:
            os.ftruncate(descriptor, 0)
            os.lseek(descriptor, 0, os.SEEK_SET)
            write_all(descriptor, payload)
            os.fsync(descriptor)
            os.fsync(control_fd)
        except OSError as error:
            raise TransactionError("MUTATION_LOCK_FAILURE") from error
        yield
    finally:
        if descriptor is not None:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
        os.close(control_fd)


def append_event(journal_fd: int, record: Mapping[str, Any]) -> Dict[str, Any]:
    events = read_journal(journal_fd, missing_ok=True)
    sequence = len(events) + 1
    value = dict(record)
    value.update({
        "journal_event_id": "journal_{}_{:08d}".format(record["plan_id"], sequence),
        "previous_event_hash": events[-1]["event_hash"] if events else ZERO_EVENT_HASH,
        "schema_version": JOURNAL_SCHEMA_VERSION,
        "sequence": sequence,
    })
    value["event_hash"] = sha256(canonical_bytes(value))
    if set(value) != _EVENT_FIELDS:
        raise TransactionError("JOURNAL_EVENT_MALFORMED")
    existed = _entry_exists(journal_fd, JOURNAL_NAME)
    descriptor = os.open(
        JOURNAL_NAME,
        os.O_WRONLY | os.O_APPEND | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0),
        0o600,
        dir_fd=journal_fd,
    )
    try:
        write_all(descriptor, canonical_bytes(value) + b"\n")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if not existed:
        os.fsync(journal_fd)
    return value


def read_journal(journal_fd: int, missing_ok: bool = False) -> Sequence[Dict[str, Any]]:
    try:
        descriptor = os.open(JOURNAL_NAME, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=journal_fd)
    except FileNotFoundError:
        if missing_ok:
            return []
        raise TransactionError("JOURNAL_MISSING")
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode):
            raise TransactionError("JOURNAL_MALFORMED")
        payload = _read_bounded(descriptor, MAX_JOURNAL_BYTES)
    finally:
        os.close(descriptor)
    return parse_journal(payload)


def parse_journal(payload: bytes) -> Sequence[Dict[str, Any]]:
    if not payload or not payload.endswith(b"\n"):
        raise TransactionError("JOURNAL_MALFORMED")
    events = []
    previous = ZERO_EVENT_HASH
    for sequence, line in enumerate(payload.splitlines(), 1):
        try:
            event = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise TransactionError("JOURNAL_MALFORMED") from error
        if not isinstance(event, dict) or set(event) != _EVENT_FIELDS:
            raise TransactionError("JOURNAL_EVENT_MALFORMED")
        claimed_hash = event.get("event_hash")
        unhashed = dict(event)
        del unhashed["event_hash"]
        if (
            event.get("schema_version") != JOURNAL_SCHEMA_VERSION
            or event.get("sequence") != sequence
            or event.get("previous_event_hash") != previous
            or claimed_hash != sha256(canonical_bytes(unhashed))
            or event.get("journal_event_id") != "journal_{}_{:08d}".format(event.get("plan_id"), sequence)
        ):
            raise TransactionError("JOURNAL_INTEGRITY_FAILURE")
        events.append(event)
        previous = claimed_hash
    return events


def fsync_directory(descriptor: int) -> None:
    os.fsync(descriptor)


def _ensure_control_directory(root_fd: int) -> int:
    try:
        os.mkdir(".repo-curator", 0o700, dir_fd=root_fd)
        os.fsync(root_fd)
    except FileExistsError:
        pass
    try:
        descriptor = os.open(
            ".repo-curator",
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=root_fd,
        )
    except OSError as error:
        raise TransactionError("MUTATION_LOCK_UNSAFE") from error
    return descriptor


def _entry_exists(parent_fd: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
        return True
    except FileNotFoundError:
        return False


def write_all(descriptor: int, payload: bytes) -> None:
    offset = 0
    while offset < len(payload):
        written = os.write(descriptor, payload[offset:])
        if written <= 0:
            raise OSError(errno.EIO, "short write")
        offset += written


def _read_bounded(descriptor: int, maximum: int) -> bytes:
    chunks = []
    size = 0
    while True:
        chunk = os.read(descriptor, min(64 * 1024, maximum + 1 - size))
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        size += len(chunk)
        if size > maximum:
            raise TransactionError("JOURNAL_TOO_LARGE")
