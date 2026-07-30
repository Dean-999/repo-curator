"""Hash-verified prior-run comparison for evidence-review continuity."""

import errno
import hashlib
import json
import os
import re
import stat
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


PRIOR_RUN_COMPARISON_SCHEMA_VERSION = "repo-curator.prior-run-comparison.v1"
_RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
_REQUIRED_FILES = ("inventory.jsonl", "mainline-map.jsonl")
_MAX_TOTAL_INPUT_BYTES = 1_073_741_824
_MAX_JSONL_RECORDS = 200_000
_MAX_OUTPUT_FILES = 128
_MAX_RUN_RECORD_BYTES = 4_194_304
_MAX_OUTPUT_FILE_BYTES = 268_435_456


def compare_with_prior_run(
    root_fd: int,
    prior_run_id: str,
    current_inventory: Sequence[Mapping[str, Any]],
    current_mainline: Sequence[Mapping[str, Any]],
    run_id: str,
    created_at: str,
) -> Dict[str, Any]:
    """Compare current observations with one fully verified earlier audit run."""
    if _RUN_ID_PATTERN.fullmatch(prior_run_id) is None or prior_run_id == run_id:
        raise ValueError("prior run ID is invalid or equals the current run ID")
    prior_run, prior_files = _read_verified_prior_run(root_fd, prior_run_id)
    prior_inventory = _parse_json_lines(prior_files["inventory.jsonl"], "prior inventory")
    prior_mainline = _parse_json_lines(prior_files["mainline-map.jsonl"], "prior mainline")
    artifact_changes = _artifact_changes(prior_inventory, current_inventory)
    evidence_changes = _mainline_changes(prior_mainline, current_mainline)
    return {
        "added_artifact_paths": artifact_changes["added"],
        "changed_artifact_paths": artifact_changes["changed"],
        "created_at": created_at,
        "moved_artifacts": artifact_changes["moved"],
        "newly_conflicting_mainline_paths": evidence_changes["newly_conflicting"],
        "newly_linked_mainline_paths": evidence_changes["newly_linked"],
        "previous_run_id": prior_run_id,
        "previous_run_output_hashes": dict(sorted(prior_run["output_file_hashes"].items())),
        "removed_artifact_paths": artifact_changes["removed"],
        "run_id": run_id,
        "schema_version": PRIOR_RUN_COMPARISON_SCHEMA_VERSION,
        "still_unresolved_mainline_paths": evidence_changes["still_unresolved"],
    }


def _read_verified_prior_run(root_fd: int, run_id: str) -> tuple[Dict[str, Any], Dict[str, bytes]]:
    control_fd = _open_directory_at(root_fd, ".repo-curator")
    try:
        runs_fd = _open_directory_at(control_fd, "runs")
    finally:
        os.close(control_fd)
    try:
        run_fd = _open_directory_at(runs_fd, run_id)
    finally:
        os.close(runs_fd)
    try:
        run_limit = min(_MAX_RUN_RECORD_BYTES, _MAX_TOTAL_INPUT_BYTES)
        run_bytes = _read_regular_file(
            run_fd,
            "run.json",
            run_limit,
            (
                "prior run outputs exceed total byte limit"
                if _MAX_TOTAL_INPUT_BYTES < _MAX_RUN_RECORD_BYTES
                else "prior run record exceeds file byte limit"
            ),
        )
        total_bytes = len(run_bytes)
        run = _parse_json_object(run_bytes, "prior run record")
        if run.get("schema_version") != "repo-curator.run.v1":
            raise ValueError("prior run schema version is unsupported")
        if run.get("final_status") not in {"COMPLETED", "COMPLETED_WITH_LIMITATIONS"}:
            raise ValueError("prior run is not finalized")
        hashes = run.get("output_file_hashes")
        if not isinstance(hashes, dict) or not hashes:
            raise ValueError("prior run output hashes are invalid")
        if len(hashes) > _MAX_OUTPUT_FILES:
            raise ValueError("prior run output declaration limit exceeded")
        files = {}
        for name, expected_hash in sorted(hashes.items()):
            if not _safe_filename(name) or not _sha256_string(expected_hash):
                raise ValueError("prior run output hash declaration is invalid")
            remaining_bytes = _MAX_TOTAL_INPUT_BYTES - total_bytes
            file_limit = min(_MAX_OUTPUT_FILE_BYTES, remaining_bytes)
            content = _read_regular_file(
                run_fd,
                name,
                file_limit,
                (
                    "prior run outputs exceed total byte limit"
                    if remaining_bytes < _MAX_OUTPUT_FILE_BYTES
                    else "prior run output exceeds file byte limit"
                ),
            )
            total_bytes += len(content)
            if hashlib.sha256(content).hexdigest() != expected_hash:
                raise ValueError(f"prior run output hash mismatch: {name}")
            files[name] = content
    finally:
        os.close(run_fd)
    if any(name not in files for name in _REQUIRED_FILES):
        raise ValueError("prior run is missing required comparison outputs")
    return run, files


def _artifact_changes(
    prior: Sequence[Mapping[str, Any]], current: Sequence[Mapping[str, Any]]
) -> Dict[str, List[Any]]:
    prior_by_path = _records_by_path(prior, "prior inventory")
    current_by_path = _records_by_path(current, "current inventory")
    prior_by_path = _non_directory_records(prior_by_path)
    current_by_path = _non_directory_records(current_by_path)
    added = sorted(set(current_by_path) - set(prior_by_path))
    removed = sorted(set(prior_by_path) - set(current_by_path))
    changed = sorted(
        path
        for path in set(prior_by_path) & set(current_by_path)
        if prior_by_path[path].get("content_id") != current_by_path[path].get("content_id")
    )
    prior_by_content = _unique_regular_paths_by_content(prior_by_path, removed)
    current_by_content = _unique_regular_paths_by_content(current_by_path, added)
    moved = [
        {"from_path": prior_by_content[content_id], "to_path": current_by_content[content_id]}
        for content_id in sorted(set(prior_by_content) & set(current_by_content))
    ]
    moved_from = {item["from_path"] for item in moved}
    moved_to = {item["to_path"] for item in moved}
    return {
        "added": [path for path in added if path not in moved_to],
        "changed": changed,
        "moved": moved,
        "removed": [path for path in removed if path not in moved_from],
    }


def _mainline_changes(
    prior: Sequence[Mapping[str, Any]], current: Sequence[Mapping[str, Any]]
) -> Dict[str, List[str]]:
    prior_by_path = _records_by_path(prior, "prior mainline")
    current_by_path = _records_by_path(current, "current mainline")
    newly_linked = []
    newly_conflicting = []
    still_unresolved = []
    for path in sorted(set(prior_by_path) & set(current_by_path)):
        previous = prior_by_path[path].get("status", "UNRESOLVED")
        latest = current_by_path[path].get("status", "UNRESOLVED")
        if previous == "UNRESOLVED" and latest != "UNRESOLVED":
            newly_linked.append(path)
        elif previous != "UNRESOLVED" and latest == "UNRESOLVED":
            newly_conflicting.append(path)
        elif previous == latest == "UNRESOLVED":
            still_unresolved.append(path)
    return {
        "newly_conflicting": newly_conflicting,
        "newly_linked": newly_linked,
        "still_unresolved": still_unresolved,
    }


def _records_by_path(records: Iterable[Mapping[str, Any]], label: str) -> Dict[str, Mapping[str, Any]]:
    result = {}
    for record in records:
        path = record.get("repository_relative_path")
        if not isinstance(path, str) or not path or path in result:
            raise ValueError(f"{label} records have invalid paths")
        result[path] = record
    return result


def _unique_regular_paths_by_content(
    records: Mapping[str, Mapping[str, Any]], paths: Iterable[str]
) -> Dict[str, str]:
    groups: Dict[str, List[str]] = {}
    for path in paths:
        record = records[path]
        content_id = record.get("content_id")
        if record.get("object_type") == "REGULAR_FILE" and isinstance(content_id, str):
            groups.setdefault(content_id, []).append(path)
    return {
        content_id: members[0]
        for content_id, members in groups.items()
        if len(members) == 1
    }


def _non_directory_records(
    records: Mapping[str, Mapping[str, Any]]
) -> Dict[str, Mapping[str, Any]]:
    return {
        path: record
        for path, record in records.items()
        if path != "." and record.get("object_type") != "DIRECTORY"
    }


def _open_directory_at(parent_fd: int, name: str) -> int:
    try:
        return os.open(name, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ValueError(f"prior run directory is a symbolic link: {name}") from error
        raise


def _read_regular_file(
    parent_fd: int, name: str, maximum_bytes: int, limit_error: str
) -> bytes:
    try:
        descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ValueError(f"prior run output is a symbolic link: {name}") from error
        raise
    try:
        result = os.fstat(descriptor)
        if not stat.S_ISREG(result.st_mode):
            raise ValueError(f"prior run output is not a regular file: {name}")
        if result.st_size > maximum_bytes:
            raise ValueError(limit_error)
        chunks = []
        bytes_read = 0
        while True:
            chunk = os.read(descriptor, min(65_536, maximum_bytes - bytes_read + 1))
            if not chunk:
                return b"".join(chunks)
            bytes_read += len(chunk)
            if bytes_read > maximum_bytes:
                raise ValueError(limit_error)
            chunks.append(chunk)
    finally:
        os.close(descriptor)


def _safe_filename(value: Any) -> bool:
    return isinstance(value, str) and value and "/" not in value and "\\" not in value and value not in {".", ".."}


def _sha256_string(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _parse_json_object(content: bytes, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(content.decode("utf-8"), parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"{label} is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _parse_json_lines(content: bytes, label: str) -> List[Dict[str, Any]]:
    if not content:
        return []
    record_count = content.count(b"\n") + (0 if content.endswith(b"\n") else 1)
    if record_count > _MAX_JSONL_RECORDS:
        raise ValueError(f"{label} exceeds record limit")
    return [_parse_json_object(line, label) for line in content.splitlines()]


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")
