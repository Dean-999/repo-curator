"""Sanitized, read-only Git evidence collection for repository audits."""

import os
import re
import selectors
import shutil
import stat
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from repo_curator.secret_redaction import detect_secret_categories
from repo_curator.git_repository_size import (
    concern_ratios,
    parse_count,
    parse_count_objects,
    parse_reference_count,
    reference_scales,
    summarize_current_checkout,
)
from repo_curator.repository_hygiene import (
    parse_hygiene_status,
    staged_large_files,
)


GIT_OBSERVATION_SCHEMA_VERSION = "repo-curator.git-observation.v1"
HISTORY_LIMIT = 100
HISTORY_SECRET_BLOB_LIMIT = 512
HISTORY_SECRET_BLOB_BYTES = 1024 * 1024
HISTORY_SECRET_TOTAL_BYTES = 16 * 1024 * 1024
HISTORY_SECRET_FINDING_LIMIT = 256
HISTORY_SECRET_PATH_LIMIT = 1024
TREE_PATH_BATCH_LIMIT = 64
HISTORY_SECRET_TREE_OUTPUT_BYTES = 512 * 1024
GIT_COMMAND_INPUT_BYTES = 64 * 1024
GIT_COMMAND_OUTPUT_BYTES = 32 * 1024 * 1024
GIT_COMMAND_ERROR_BYTES = 64 * 1024
GIT_COMMAND_TIMEOUT_SECONDS = 10
GIT_OUTPUT_LIMIT_RETURN_CODE = -1000
LFS_POINTER_LIMIT = 1024
_LFS_POINTER = re.compile(
    rb"\Aversion https://git-lfs.github.com/spec/v1\n"
    rb"oid (sha256:[0-9a-f]{64})\nsize ([0-9]+)\n?\Z"
)


@dataclass(frozen=True)
class GitEvidence:
    head: Optional[str]
    observations: List[Dict[str, Any]]
    repository_mode: str
    warnings: List[str]


def collect_git_evidence(
    root: Path,
    root_fd: int,
    inventory_records: List[Dict[str, Any]],
    run_id: str,
    created_at: str,
) -> GitEvidence:
    """Populate deterministic Git observations without invoking repository helpers."""
    executable = _git_executable()
    if executable is None:
        return GitEvidence(None, [], "FILESYSTEM", ["GIT_UNAVAILABLE"])

    probe = _run_git(executable, root, ["rev-parse", "--is-inside-work-tree"])
    if probe is None:
        return GitEvidence(None, [], "FILESYSTEM", ["GIT_PROBE_UNAVAILABLE"])
    if _output_limited(probe):
        return GitEvidence(None, [], "FILESYSTEM", ["GIT_PROBE_OUTPUT_LIMIT"])
    if probe.returncode != 0 or probe.stdout.strip() != b"true":
        return GitEvidence(None, [], "FILESYSTEM", ["GIT_NOT_REPOSITORY"])

    history_scope_limitations = _history_scope_limitations(executable, root)
    warnings: List[str] = list(history_scope_limitations)
    head = _head(executable, root, warnings)
    tracked_paths = _tracked_paths(executable, root, warnings)
    status_by_path = _status_by_path(executable, root, warnings)
    submodules = _submodules(executable, root, warnings)
    history, history_warnings = _history(executable, root)
    warnings.extend(history_warnings)
    changed_paths, change_warnings = _change_history(executable, root, history)
    warnings.extend(change_warnings)
    secret_summary, secret_warnings = _secret_history(
        executable,
        root,
        history,
        changed_paths,
        change_history_available=not change_warnings,
    )
    warnings.extend(secret_warnings)
    if history_scope_limitations:
        secret_summary["limitations"] = sorted(
            set(secret_summary["limitations"] + history_scope_limitations)
        )
        if secret_summary["status"] != "NOT_APPLICABLE":
            secret_summary["status"] = "PARTIAL"
    _apply_git_state(inventory_records, tracked_paths, status_by_path)
    _apply_lfs_pointers(root_fd, inventory_records)
    size_summary, size_warnings = _repository_size_summary(
        executable, root, inventory_records
    )
    warnings.extend(size_warnings)
    hygiene_summary, hygiene_warnings = _repository_hygiene_summary(
        executable, root, inventory_records
    )
    warnings.extend(hygiene_warnings)

    worktree_kind = _worktree_kind(inventory_records)
    worktree_limitations = sorted(
        set(
            history_scope_limitations
            + (
                ["LINKED_WORKTREE_ADMINISTRATION_NOT_RECURSED"]
                if worktree_kind == "LINKED_WORKTREE"
                else []
            )
        )
    )
    annex_status = _annex_status(root_fd, inventory_records, warnings)
    observations: List[Dict[str, Any]] = [
        _observation(
            run_id,
            1,
            created_at,
            "GIT_WORKTREE",
            {"head": head, "kind": worktree_kind, "limitations": worktree_limitations},
        )
    ]
    observations.append(
        _observation(
            run_id,
            len(observations) + 1,
            created_at,
            "GIT_REPOSITORY_SIZE_SUMMARY",
            size_summary,
        )
    )
    observations.append(
        _observation(
            run_id,
            len(observations) + 1,
            created_at,
            "GIT_REPOSITORY_HYGIENE_SUMMARY",
            hygiene_summary,
        )
    )
    observations.append(
        _observation(
            run_id,
            len(observations) + 1,
            created_at,
            "GIT_ANNEX_METADATA",
            {
                "limitations": (
                    ["GIT_ANNEX_METADATA_NOT_RECURSED"]
                    if annex_status.startswith("PRESENT")
                    else ["GIT_ANNEX_METADATA_NOT_INSPECTED"]
                    if annex_status == "NOT_INSPECTED"
                    else []
                ),
                "status": annex_status,
            },
        )
    )
    observations.append(
        _observation(
            run_id,
            len(observations) + 1,
            created_at,
            "GIT_SECRET_HISTORY_SUMMARY",
            secret_summary,
        )
    )
    for path, object_id in submodules:
        observations.append(
            _observation(
                run_id,
                len(observations) + 1,
                created_at,
                "GIT_SUBMODULE",
                {
                    "limitations": ["SUBMODULE_NOT_RECURSED"],
                    "object_id": object_id,
                    "repository_relative_path": path,
                },
            )
        )
    for commit_id, parent_ids, committed_at in history:
        observations.append(
            _observation(
                run_id,
                len(observations) + 1,
                created_at,
                "GIT_COMMIT",
                {
                    "changed_paths": changed_paths.get(commit_id, []),
                    "commit_id": commit_id,
                    "committed_at_epoch": committed_at,
                    "parent_ids": parent_ids,
                },
            )
        )
    return GitEvidence(head, observations, "GIT_WORKTREE", sorted(set(warnings)))


def _history_scope_limitations(executable: str, root: Path) -> List[str]:
    result = _run_git(
        executable,
        root,
        ["rev-parse", "--is-shallow-repository"],
        output_limit=16,
    )
    if result is not None and _output_limited(result):
        return ["GIT_SHALLOW_STATE_OUTPUT_LIMIT"]
    if result is None or result.returncode != 0:
        return ["GIT_SHALLOW_STATE_UNAVAILABLE"]
    state = result.stdout.strip()
    if state == b"true":
        return ["GIT_SHALLOW_REPOSITORY_HISTORY_INCOMPLETE"]
    if state == b"false":
        return []
    return ["GIT_SHALLOW_STATE_MALFORMED"]


def _repository_hygiene_summary(
    executable: str,
    root: Path,
    inventory_records: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[str]]:
    warnings = []
    destroyed = []
    destroyed_count = 0
    staged_added_paths: Set[str] = set()
    limitations = {
        "BROKEN_SYMLINKS_REPORTED_BY_INVENTORY_WARNINGS",
        "GIT_REPOSITORY_HYGIENE_NOT_CLEANUP_AUTHORITY",
        "GIT_STAGED_LARGE_FILE_LFS_ATTRIBUTE_NOT_CHECKED",
    }
    result = _run_git(
        executable,
        root,
        [
            "status",
            "--porcelain=v2",
            "-z",
            "--ignore-submodules=none",
            "--no-renames",
            "--untracked-files=no",
        ],
    )
    if result is not None and _output_limited(result):
        warnings.append("GIT_REPOSITORY_HYGIENE_STATUS_OUTPUT_LIMIT")
    elif result is None or result.returncode != 0:
        warnings.append("GIT_REPOSITORY_HYGIENE_STATUS_UNAVAILABLE")
    else:
        (
            staged_added_paths,
            destroyed,
            destroyed_count,
            parse_limitations,
        ) = parse_hygiene_status(result.stdout)
        limitations.update(parse_limitations)
        if "GIT_REPOSITORY_HYGIENE_STATUS_MALFORMED" in parse_limitations:
            warnings.append("GIT_REPOSITORY_HYGIENE_STATUS_MALFORMED")
        if (
            "GIT_REPOSITORY_HYGIENE_NONORDINARY_RECORD_NOT_EVALUATED"
            in parse_limitations
        ):
            warnings.append(
                "GIT_REPOSITORY_HYGIENE_NONORDINARY_RECORD_NOT_EVALUATED"
            )

    large_files, large_file_count, large_limitations = staged_large_files(
        inventory_records, staged_added_paths
    )
    limitations.update(large_limitations)
    limitations.update(warnings)
    return {
        "destroyed_symlink_count": destroyed_count,
        "destroyed_symlinks": destroyed,
        "limitations": sorted(limitations),
        "staged_large_file_count": large_file_count,
        "staged_large_files": large_files,
        "status": "PARTIAL" if warnings else "OBSERVED",
    }, warnings


def _repository_size_summary(
    executable: str,
    root: Path,
    inventory_records: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[str]]:
    warnings = []
    object_database = None
    reference_count = None
    reachable_commit_count = None

    object_result = _run_git(executable, root, ["count-objects", "-v"])
    if object_result is not None and _output_limited(object_result):
        warnings.append("GIT_SIZE_OBJECT_DATABASE_OUTPUT_LIMIT")
    elif object_result is None or object_result.returncode != 0:
        warnings.append("GIT_SIZE_OBJECT_DATABASE_UNAVAILABLE")
    else:
        object_database = parse_count_objects(object_result.stdout)
        if object_database is None:
            warnings.append("GIT_SIZE_OBJECT_DATABASE_MALFORMED")

    reference_result = _run_git(
        executable, root, ["for-each-ref", "--format=x"]
    )
    if reference_result is not None and _output_limited(reference_result):
        warnings.append("GIT_SIZE_REFERENCES_OUTPUT_LIMIT")
    elif reference_result is None or reference_result.returncode != 0:
        warnings.append("GIT_SIZE_REFERENCES_UNAVAILABLE")
    else:
        reference_count = parse_reference_count(reference_result.stdout)
        if reference_count is None:
            warnings.append("GIT_SIZE_REFERENCES_MALFORMED")

    commit_result = _run_git(executable, root, ["rev-list", "--count", "--all"])
    if commit_result is not None and _output_limited(commit_result):
        warnings.append("GIT_SIZE_COMMITS_OUTPUT_LIMIT")
    elif commit_result is None or commit_result.returncode != 0:
        warnings.append("GIT_SIZE_COMMITS_UNAVAILABLE")
    else:
        reachable_commit_count = parse_count(commit_result.stdout)
        if reachable_commit_count is None:
            warnings.append("GIT_SIZE_COMMITS_MALFORMED")

    checkout = summarize_current_checkout(inventory_records)
    limitations = {
        "GIT_OBJECT_DATABASE_MAY_INCLUDE_UNREACHABLE_OBJECTS_OR_ALTERNATES",
        "GIT_SIZE_HISTORY_FILE_CONTENT_NOT_READ",
        "GIT_SIZE_METRICS_NOT_CLEANUP_AUTHORITY",
        "GIT_SIZER_REFERENCE_SCALES_CONTEXT_ONLY",
        *warnings,
    }
    details: Dict[str, Any] = {
        "concern_ratios": None,
        "current_checkout": checkout,
        "limitations": sorted(limitations),
        "object_database": object_database,
        "reachable_commit_count": reachable_commit_count,
        "reference_count": reference_count,
        "reference_scales": reference_scales(),
        "status": "PARTIAL" if warnings else "OBSERVED",
    }
    if reference_count is not None and reachable_commit_count is not None:
        details["concern_ratios"] = concern_ratios(
            reference_count, reachable_commit_count, checkout
        )
    return details, warnings


def _git_executable() -> Optional[str]:
    return shutil.which("git", path=os.defpath)


def _run_git(
    executable: str,
    root: Path,
    arguments: List[str],
    input_bytes: Optional[bytes] = None,
    output_limit: int = GIT_COMMAND_OUTPUT_BYTES,
) -> Optional[subprocess.CompletedProcess[bytes]]:
    environment = _git_environment()
    command = [
        executable,
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.untrackedCache=false",
        "-c",
        "core.pager=cat",
        "--no-pager",
        *arguments,
    ]
    if input_bytes is not None and len(input_bytes) > GIT_COMMAND_INPUT_BYTES:
        return subprocess.CompletedProcess(
            command, GIT_OUTPUT_LIMIT_RETURN_CODE, b"", b""
        )
    return _run_bounded_process(
        command,
        root,
        environment,
        input_bytes,
        output_limit,
        GIT_COMMAND_ERROR_BYTES,
        GIT_COMMAND_TIMEOUT_SECONDS,
    )


def _git_environment() -> Dict[str, str]:
    return {
        "GIT_ALLOW_PROTOCOL": "",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ATTR_NOSYSTEM": "1",
        "GIT_LITERAL_PATHSPECS": "1",
        "GIT_NO_LAZY_FETCH": "1",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_PAGER": "cat",
        "GIT_PROTOCOL_FROM_USER": "0",
        "GIT_TERMINAL_PROMPT": "0",
        "HOME": os.devnull,
        "LC_ALL": "C",
        "PAGER": "cat",
        "PATH": os.defpath,
    }


def _run_bounded_process(
    command: List[str],
    root: Path,
    environment: Dict[str, str],
    input_bytes: Optional[bytes],
    output_limit: int,
    error_limit: int,
    timeout_seconds: float,
) -> Optional[subprocess.CompletedProcess[bytes]]:
    if output_limit < 0 or error_limit < 0 or timeout_seconds <= 0:
        raise ValueError("Git command budgets must be positive")
    try:
        process = subprocess.Popen(
            command,
            cwd=root,
            env=environment,
            stdin=subprocess.PIPE if input_bytes is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
    except OSError:
        return None
    selector = selectors.DefaultSelector()
    stdout = bytearray()
    stderr = bytearray()
    deadline = time.monotonic() + timeout_seconds
    try:
        if input_bytes is not None and process.stdin is not None:
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(
                process.stdin,
                selectors.EVENT_WRITE,
                ("write", memoryview(input_bytes)),
            )
        if process.stdout is None or process.stderr is None:
            _terminate_process(process)
            return None
        selector.register(
            process.stdout,
            selectors.EVENT_READ,
            ("read", stdout, output_limit),
        )
        selector.register(
            process.stderr,
            selectors.EVENT_READ,
            ("read", stderr, error_limit),
        )
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _terminate_process(process)
                return None
            events = selector.select(remaining)
            if not events:
                continue
            for key, _ in events:
                if key.data[0] == "write":
                    pending = key.data[1]
                    try:
                        written = os.write(key.fd, pending)
                    except BlockingIOError:
                        continue
                    except BrokenPipeError:
                        written = len(pending)
                    if written == len(pending):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                    else:
                        selector.modify(
                            key.fileobj,
                            selectors.EVENT_WRITE,
                            ("write", pending[written:]),
                        )
                    continue
                try:
                    chunk = os.read(key.fd, 64 * 1024)
                except BlockingIOError:
                    continue
                if not chunk:
                    selector.unregister(key.fileobj)
                    key.fileobj.close()
                    continue
                _, buffer, limit = key.data
                available = max(0, limit - len(buffer))
                buffer.extend(chunk[:available])
                if len(chunk) > available:
                    _terminate_process(process)
                    return subprocess.CompletedProcess(
                        command,
                        GIT_OUTPUT_LIMIT_RETURN_CODE,
                        bytes(stdout),
                        bytes(stderr),
                    )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            _terminate_process(process)
            return None
        try:
            return_code = process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            _terminate_process(process)
            return None
        return subprocess.CompletedProcess(
            command, return_code, bytes(stdout), bytes(stderr)
        )
    finally:
        selector.close()
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()
        if process.poll() is None:
            _terminate_process(process)


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    process.kill()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        pass


def _output_limited(result: subprocess.CompletedProcess[bytes]) -> bool:
    return result.returncode == GIT_OUTPUT_LIMIT_RETURN_CODE


def _head(executable: str, root: Path, warnings: List[str]) -> Optional[str]:
    result = _run_git(executable, root, ["rev-parse", "--verify", "HEAD"])
    if result is not None and _output_limited(result):
        warnings.append("GIT_HEAD_OUTPUT_LIMIT")
        return None
    if result is None or result.returncode != 0:
        warnings.append("GIT_HEAD_UNAVAILABLE")
        return None
    try:
        value = result.stdout.strip().decode("ascii", "strict")
    except UnicodeDecodeError:
        warnings.append("GIT_HEAD_MALFORMED")
        return None
    if not re.fullmatch(r"[0-9a-f]{40,64}", value):
        warnings.append("GIT_HEAD_MALFORMED")
        return None
    return value


def _tracked_paths(executable: str, root: Path, warnings: List[str]) -> Set[str]:
    result = _run_git(executable, root, ["ls-files", "-z", "--cached"])
    if result is not None and _output_limited(result):
        warnings.append("GIT_INDEX_OUTPUT_LIMIT")
        return set()
    if result is None or result.returncode != 0:
        warnings.append("GIT_INDEX_UNAVAILABLE")
        return set()
    return {os.fsdecode(path) for path in result.stdout.split(b"\0") if path}


def _status_by_path(
    executable: str, root: Path, warnings: List[str]
) -> Dict[str, str]:
    result = _run_git(
        executable,
        root,
        [
            "status",
            "--porcelain=v1",
            "-z",
            "--ignored=matching",
            "--ignore-submodules=none",
            "--no-renames",
            "--untracked-files=all",
        ],
    )
    if result is not None and _output_limited(result):
        warnings.append("GIT_STATUS_OUTPUT_LIMIT")
        return {}
    if result is None or result.returncode != 0:
        warnings.append("GIT_STATUS_UNAVAILABLE")
        return {}
    statuses: Dict[str, str] = {}
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        if len(entry) < 4 or entry[2:3] != b" ":
            warnings.append("GIT_STATUS_MALFORMED")
            continue
        try:
            statuses[os.fsdecode(entry[3:])] = entry[:2].decode("ascii", "strict")
        except UnicodeDecodeError:
            warnings.append("GIT_STATUS_MALFORMED")
    return statuses


def _submodules(
    executable: str, root: Path, warnings: List[str]
) -> List[Tuple[str, str]]:
    result = _run_git(executable, root, ["ls-files", "--stage", "-z"])
    if result is not None and _output_limited(result):
        warnings.append("GIT_INDEX_OUTPUT_LIMIT")
        return []
    if result is None or result.returncode != 0:
        warnings.append("GIT_INDEX_UNAVAILABLE")
        return []
    submodules = []
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        try:
            metadata, path = entry.split(b"\t", 1)
            mode, object_id, stage = metadata.split(b" ")
        except ValueError:
            warnings.append("GIT_INDEX_MALFORMED")
            continue
        if mode != b"160000" or stage != b"0":
            continue
        if not re.fullmatch(rb"[0-9a-f]{40,64}", object_id):
            warnings.append("GIT_INDEX_MALFORMED")
            continue
        submodules.append((os.fsdecode(path), object_id.decode("ascii")))
    return sorted(submodules)


def _history(
    executable: str, root: Path
) -> Tuple[List[Tuple[str, List[str], int]], List[str]]:
    result = _run_git(
        executable,
        root,
        [
            "log",
            "-z",
            "--no-decorate",
            "--no-renames",
            f"--max-count={HISTORY_LIMIT}",
            "--format=%H%x00%P%x00%ct",
        ],
    )
    if result is not None and _output_limited(result):
        return [], ["GIT_HISTORY_OUTPUT_LIMIT"]
    if result is None or result.returncode != 0:
        return [], ["GIT_HISTORY_UNAVAILABLE"]
    return _parse_history(result.stdout)


def _parse_history(payload: bytes) -> Tuple[List[Tuple[str, List[str], int]], List[str]]:
    parts = payload.rstrip(b"\0").split(b"\0") if payload else []
    if len(parts) % 3 != 0:
        return [], ["GIT_HISTORY_MALFORMED"]
    history = []
    for index in range(0, len(parts), 3):
        commit, parents, committed_at = parts[index : index + 3]
        if not re.fullmatch(rb"[0-9a-f]{40,64}", commit) or not committed_at.isdigit():
            return [], ["GIT_HISTORY_MALFORMED"]
        parent_ids = parents.split() if parents else []
        if any(not re.fullmatch(rb"[0-9a-f]{40,64}", parent) for parent in parent_ids):
            return [], ["GIT_HISTORY_MALFORMED"]
        history.append(
            (
                commit.decode("ascii"),
                [parent.decode("ascii") for parent in parent_ids],
                int(committed_at),
            )
        )
    return history, []


def _change_history(
    executable: str,
    root: Path,
    history: List[Tuple[str, List[str], int]],
) -> Tuple[Dict[str, List[str]], List[str]]:
    if not history:
        return {}, []
    commit_ids = [commit_id for commit_id, _, _ in history]
    result = _run_git(
        executable,
        root,
        [
            "diff-tree",
            "--stdin",
            "--root",
            "--always",
            "--raw",
            "-r",
            "-z",
            "--no-renames",
        ],
        ("\n".join(commit_ids) + "\n").encode("ascii"),
    )
    if result is not None and _output_limited(result):
        return {}, ["GIT_CHANGE_HISTORY_OUTPUT_LIMIT"]
    if result is None or result.returncode != 0:
        return {}, ["GIT_CHANGE_HISTORY_UNAVAILABLE"]
    return _parse_changed_paths(result.stdout, commit_ids)


def _parse_changed_paths(
    payload: bytes, expected_commits: List[str]
) -> Tuple[Dict[str, List[str]], List[str]]:
    expected = [commit.encode("ascii") for commit in expected_commits]
    tokens = payload.rstrip(b"\0").split(b"\0") if payload else []
    changed: Dict[str, List[str]] = {}
    token_index = 0
    expected_index = 0
    while expected_index < len(expected):
        if token_index >= len(tokens) or tokens[token_index] != expected[expected_index]:
            return {}, ["GIT_CHANGE_HISTORY_MALFORMED"]
        commit = expected_commits[expected_index]
        changed[commit] = []
        token_index += 1
        expected_index += 1
        next_commit = expected[expected_index] if expected_index < len(expected) else None
        while token_index < len(tokens) and tokens[token_index] != next_commit:
            metadata = tokens[token_index]
            if not _valid_raw_change_metadata(metadata) or token_index + 1 >= len(tokens):
                return {}, ["GIT_CHANGE_HISTORY_MALFORMED"]
            changed[commit].append(os.fsdecode(tokens[token_index + 1]))
            token_index += 2
    if token_index != len(tokens):
        return {}, ["GIT_CHANGE_HISTORY_MALFORMED"]
    return {commit: sorted(set(paths)) for commit, paths in changed.items()}, []


def _valid_raw_change_metadata(value: bytes) -> bool:
    fields = value.split(b" ")
    return (
        len(fields) == 5
        and fields[0].startswith(b":")
        and len(fields[0]) == 7
        and len(fields[1]) == 6
        and re.fullmatch(rb"[0-7]{6}", fields[0][1:]) is not None
        and re.fullmatch(rb"[0-7]{6}", fields[1]) is not None
        and re.fullmatch(rb"[0-9a-f]{40,64}", fields[2]) is not None
        and re.fullmatch(rb"[0-9a-f]{40,64}", fields[3]) is not None
        and re.fullmatch(rb"[A-Z]", fields[4]) is not None
    )


def _secret_history(
    executable: str,
    root: Path,
    history: List[Tuple[str, List[str], int]],
    changed_paths: Dict[str, List[str]],
    change_history_available: bool,
) -> Tuple[Dict[str, Any], List[str]]:
    limitations = {
        "GIT_SECRET_VALUES_NOT_PERSISTED",
        "GIT_SECRET_CREDENTIAL_VALIDATION_NOT_PERFORMED",
        "GIT_SECRET_HISTORY_RECENT_COMMITS_ONLY",
        "GIT_SECRET_PATTERN_MATCH_NOT_CREDENTIAL_VALIDITY",
    }
    operational_limitations: Set[str] = set()
    occurrences: Dict[str, List[Tuple[str, str]]] = {}
    blob_sizes: Dict[str, int] = {}
    paths_considered = 0

    if not change_history_available:
        operational_limitations.add("GIT_SECRET_HISTORY_CHANGE_PATHS_UNAVAILABLE")

    stop = False
    for commit_id, _, _ in history:
        paths = changed_paths.get(commit_id, [])
        for offset in range(0, len(paths), TREE_PATH_BATCH_LIMIT):
            batch = paths[offset : offset + TREE_PATH_BATCH_LIMIT]
            remaining_paths = HISTORY_SECRET_PATH_LIMIT - paths_considered
            if remaining_paths <= 0:
                operational_limitations.add("GIT_SECRET_HISTORY_PATH_LIMIT")
                stop = True
                break
            if len(batch) > remaining_paths:
                batch = batch[:remaining_paths]
                operational_limitations.add("GIT_SECRET_HISTORY_PATH_LIMIT")
                stop = True
            paths_considered += len(batch)
            result = _run_git(
                executable,
                root,
                ["ls-tree", "-z", "--long", commit_id, "--", *batch],
                output_limit=HISTORY_SECRET_TREE_OUTPUT_BYTES,
            )
            if result is not None and _output_limited(result):
                operational_limitations.add("GIT_SECRET_HISTORY_TREE_OUTPUT_LIMIT")
                continue
            if result is None or result.returncode != 0:
                operational_limitations.add("GIT_SECRET_HISTORY_TREE_UNAVAILABLE")
                continue
            entries, tree_warnings = _parse_history_tree(result.stdout, set(batch))
            operational_limitations.update(tree_warnings)
            for path, object_id, size in entries:
                if object_id not in occurrences and len(occurrences) >= HISTORY_SECRET_BLOB_LIMIT:
                    operational_limitations.add("GIT_SECRET_HISTORY_BLOB_LIMIT")
                    stop = True
                    break
                occurrences.setdefault(object_id, []).append((commit_id, path))
                blob_sizes[object_id] = size
            if stop:
                break
        if stop:
            break

    findings: List[Dict[str, str]] = []
    blob_count_scanned = 0
    bytes_scanned = 0
    for object_id in sorted(occurrences):
        size = blob_sizes[object_id]
        if size > HISTORY_SECRET_BLOB_BYTES:
            operational_limitations.add("GIT_SECRET_HISTORY_BLOB_SIZE_LIMIT")
            continue
        if bytes_scanned + size > HISTORY_SECRET_TOTAL_BYTES:
            operational_limitations.add("GIT_SECRET_HISTORY_TOTAL_BYTES_LIMIT")
            break
        result = _run_git(
            executable,
            root,
            ["cat-file", "blob", object_id],
            output_limit=size,
        )
        if result is not None and _output_limited(result):
            operational_limitations.add("GIT_SECRET_HISTORY_BLOB_OUTPUT_LIMIT")
            continue
        if result is None or result.returncode != 0 or len(result.stdout) != size:
            operational_limitations.add("GIT_SECRET_HISTORY_BLOB_UNAVAILABLE")
            continue
        blob_count_scanned += 1
        bytes_scanned += size
        categories, category_limitations = detect_secret_categories(result.stdout)
        operational_limitations.update(category_limitations)
        for commit_id, path in occurrences[object_id]:
            for category in categories:
                if len(findings) >= HISTORY_SECRET_FINDING_LIMIT:
                    operational_limitations.add("GIT_SECRET_HISTORY_FINDING_LIMIT")
                    break
                findings.append(
                    {
                        "category": category,
                        "commit_id": commit_id,
                        "repository_relative_path": path,
                    }
                )
            if "GIT_SECRET_HISTORY_FINDING_LIMIT" in operational_limitations:
                break
        if "GIT_SECRET_HISTORY_FINDING_LIMIT" in operational_limitations:
            break

    limitations.update(operational_limitations)
    status = (
        "NOT_APPLICABLE"
        if not history
        else "PARTIAL"
        if operational_limitations
        else "OBSERVED"
    )
    summary = {
        "blob_count_scanned": blob_count_scanned,
        "bytes_scanned": bytes_scanned,
        "commit_count_considered": len(history),
        "coverage": "RECENT_CHANGED_BLOBS_ONLY",
        "credential_validation": "NOT_PERFORMED",
        "findings": sorted(
            findings,
            key=lambda finding: (
                finding["commit_id"],
                finding["repository_relative_path"],
                finding["category"],
            ),
        ),
        "limitations": sorted(limitations),
        "status": status,
    }
    return summary, sorted(operational_limitations)


def _parse_history_tree(
    payload: bytes, requested_paths: Set[str]
) -> Tuple[List[Tuple[str, str, int]], List[str]]:
    entries: List[Tuple[str, str, int]] = []
    for record in payload.rstrip(b"\0").split(b"\0") if payload else []:
        try:
            metadata, raw_path = record.split(b"\t", 1)
            mode, object_type, object_id, raw_size = metadata.split()
            path = os.fsdecode(raw_path)
        except ValueError:
            return [], ["GIT_SECRET_HISTORY_TREE_MALFORMED"]
        if (
            re.fullmatch(rb"[0-7]{6}", mode) is None
            or path not in requested_paths
            or re.fullmatch(rb"[0-9a-f]{40,64}", object_id) is None
        ):
            return [], ["GIT_SECRET_HISTORY_TREE_MALFORMED"]
        if mode not in {b"100644", b"100755"}:
            continue
        if object_type != b"blob" or not raw_size.isdigit():
            return [], ["GIT_SECRET_HISTORY_TREE_MALFORMED"]
        entries.append((path, object_id.decode("ascii"), int(raw_size)))
    return sorted(set(entries)), []


def _apply_git_state(
    records: Iterable[Dict[str, Any]],
    tracked_paths: Set[str],
    status_by_path: Dict[str, str],
) -> None:
    ignored_prefixes = [
        path for path, status in status_by_path.items() if status == "!!" and path.endswith("/")
    ]
    for record in records:
        if record["object_type"] not in {"REGULAR_FILE", "SYMLINK"}:
            continue
        path = record["repository_relative_path"]
        status = status_by_path.get(path)
        if status is None and any(path.startswith(prefix) for prefix in ignored_prefixes):
            status = "!!"
        state = record["git_state"]
        if path in tracked_paths:
            state.update(
                {
                    "ignored_included": False,
                    "index_status": status,
                    "modified": bool(status and status != "  "),
                    "tracked": True,
                    "untracked": False,
                }
            )
        elif status == "??":
            state.update(
                {
                    "ignored_included": False,
                    "index_status": status,
                    "modified": False,
                    "tracked": False,
                    "untracked": True,
                }
            )
        elif status == "!!":
            state.update(
                {
                    "ignored_included": True,
                    "index_status": status,
                    "modified": False,
                    "tracked": False,
                    "untracked": False,
                }
            )
        else:
            state.update(
                {
                    "ignored_included": False,
                    "index_status": None,
                    "modified": False,
                    "tracked": False,
                    "untracked": False,
                }
            )


def _apply_lfs_pointers(root_fd: int, records: Iterable[Dict[str, Any]]) -> None:
    for record in records:
        if record["git_state"]["tracked"] is not True:
            continue
        pointer = _lfs_pointer(root_fd, record)
        if pointer is not None:
            record["lfs_pointer"] = pointer
            record["warnings"].append("LFS_CONTENT_NOT_DOWNLOADED")


def _lfs_pointer(root_fd: int, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    size_bytes = record["size_bytes"]
    if (
        record["object_type"] != "REGULAR_FILE"
        or not isinstance(size_bytes, int)
        or size_bytes > LFS_POINTER_LIMIT
    ):
        return None
    components = os.fsencode(record["repository_relative_path"]).split(b"/")
    current_fd = os.dup(root_fd)
    try:
        for component in components[:-1]:
            next_fd = os.open(
                component,
                os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
        file_fd = os.open(
            components[-1],
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
            dir_fd=current_fd,
        )
        try:
            if not stat.S_ISREG(os.fstat(file_fd).st_mode):
                return None
            match = _LFS_POINTER.fullmatch(os.read(file_fd, LFS_POINTER_LIMIT + 1))
        finally:
            os.close(file_fd)
    except OSError:
        return None
    finally:
        os.close(current_fd)
    if match is None:
        return None
    return {"oid": match.group(1).decode("ascii"), "size_bytes": int(match.group(2))}


def _worktree_kind(inventory_records: Iterable[Dict[str, Any]]) -> str:
    git_control = next(
        (record for record in inventory_records if record["repository_relative_path"] == ".git"),
        None,
    )
    if git_control is not None and git_control["object_type"] == "REGULAR_FILE":
        return "LINKED_WORKTREE"
    return "MAIN_WORKTREE"


def _annex_status(
    root_fd: int, inventory_records: Iterable[Dict[str, Any]], warnings: List[str]
) -> str:
    git_control = next(
        (record for record in inventory_records if record["repository_relative_path"] == ".git"),
        None,
    )
    if git_control is None or git_control["object_type"] != "DIRECTORY":
        return "NOT_INSPECTED"
    try:
        git_fd = os.open(
            ".git",
            os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=root_fd,
        )
        try:
            annex = os.stat("annex", dir_fd=git_fd, follow_symlinks=False)
        except FileNotFoundError:
            return "ABSENT"
        finally:
            os.close(git_fd)
    except OSError:
        warnings.append("GIT_ANNEX_UNAVAILABLE")
        return "NOT_INSPECTED"
    return "PRESENT" if stat.S_ISDIR(annex.st_mode) else "PRESENT_NON_DIRECTORY"


def _observation(
    run_id: str,
    sequence: int,
    created_at: str,
    observation_type: str,
    details: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "assertion_class": "OBSERVED",
        "created_at": created_at,
        "limitations": [],
        "observation_id": f"gitobs_{run_id}_{sequence:08d}",
        "observation_type": observation_type,
        "origin": "DETERMINISTIC",
        "run_id": run_id,
        "schema_version": GIT_OBSERVATION_SCHEMA_VERSION,
        "scope": "ROOT_GIT_WORKTREE",
        **details,
    }
