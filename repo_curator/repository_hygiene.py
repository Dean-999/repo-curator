"""Bounded repository hygiene checks adapted from pre-commit-hooks.

The 500 KiB staged-file threshold and destroyed-symlink mode test are adapted
from ``check_added_large_files.py`` and ``destroyed_symlinks.py`` at commit
4189d189e039fd49eb235357c9d9977b026c6c8e (MIT). Broken-link behavior from
``check_symlinks.py`` is already implemented by the descriptor-relative scanner.
This port emits review evidence only and never changes the index or filesystem.
"""

import os
import re
from typing import Any, Dict, Iterable, List, Set, Tuple


ADDED_LARGE_FILE_KIB = 500
HYGIENE_FINDING_LIMIT = 256
PERMS_LINK = b"120000"
PERMS_NONEXIST = b"000000"
_OBJECT_ID = re.compile(rb"[0-9a-f]{40,64}\Z")
_MODE = re.compile(rb"[0-7]{6}\Z")


def staged_large_files(
    records: Iterable[Dict[str, Any]],
    staged_added_paths: Set[str],
) -> Tuple[List[Dict[str, Any]], int, Tuple[str, ...]]:
    retained = []
    count = 0
    for record in records:
        size_bytes = record.get("size_bytes")
        if (
            record["object_type"] != "REGULAR_FILE"
            or record["repository_relative_path"] not in staged_added_paths
            or not isinstance(size_bytes, int)
            or size_bytes <= ADDED_LARGE_FILE_KIB * 1024
        ):
            continue
        count += 1
        finding = {
            "artifact_id": record["artifact_id"],
            "repository_relative_path": record["repository_relative_path"],
            "size_bytes": size_bytes,
            "threshold_kib": ADDED_LARGE_FILE_KIB,
        }
        _retain_smallest(retained, finding)
    limitations = (
        ("GIT_REPOSITORY_HYGIENE_FINDING_LIMIT",)
        if count > HYGIENE_FINDING_LIMIT
        else ()
    )
    return [item for _, item in retained], count, limitations


def parse_hygiene_status(
    payload: bytes,
) -> Tuple[Set[str], List[Dict[str, Any]], int, Tuple[str, ...]]:
    if payload and not payload.endswith(b"\0"):
        return set(), [], 0, ("GIT_REPOSITORY_HYGIENE_STATUS_MALFORMED",)

    staged_added_paths = set()
    retained = []
    count = 0
    limitations = set()
    seen_paths = set()
    entries = payload.split(b"\0")[:-1] if payload else []
    entry_index = 0
    while entry_index < len(entries):
        entry = entries[entry_index]
        entry_index += 1
        if entry.startswith(b"u "):
            if not _valid_unmerged_entry(entry):
                return set(), [], 0, (
                    "GIT_REPOSITORY_HYGIENE_STATUS_MALFORMED",
                )
            limitations.add(
                "GIT_REPOSITORY_HYGIENE_NONORDINARY_RECORD_NOT_EVALUATED"
            )
            continue
        if entry.startswith((b"? ", b"! ")):
            if len(entry) < 3:
                return set(), [], 0, (
                    "GIT_REPOSITORY_HYGIENE_STATUS_MALFORMED",
                )
            limitations.add(
                "GIT_REPOSITORY_HYGIENE_NONORDINARY_RECORD_NOT_EVALUATED"
            )
            continue
        if entry.startswith(b"2 "):
            if (
                not _valid_rename_entry(entry)
                or entry_index >= len(entries)
                or not entries[entry_index]
            ):
                return set(), [], 0, (
                    "GIT_REPOSITORY_HYGIENE_STATUS_MALFORMED",
                )
            entry_index += 1
            limitations.add(
                "GIT_REPOSITORY_HYGIENE_NONORDINARY_RECORD_NOT_EVALUATED"
            )
            continue
        if not entry.startswith(b"1 "):
            return set(), [], 0, ("GIT_REPOSITORY_HYGIENE_STATUS_MALFORMED",)
        fields = entry.split(b" ", 8)
        if len(fields) != 9:
            return set(), [], 0, ("GIT_REPOSITORY_HYGIENE_STATUS_MALFORMED",)
        _, xy, submodule, mode_head, mode_index, mode_worktree, hash_head, hash_index, path = fields
        if (
            len(xy) != 2
            or len(submodule) != 4
            or any(_MODE.fullmatch(mode) is None for mode in (mode_head, mode_index, mode_worktree))
            or _OBJECT_ID.fullmatch(hash_head) is None
            or _OBJECT_ID.fullmatch(hash_index) is None
            or not path
            or path in seen_paths
        ):
            return set(), [], 0, ("GIT_REPOSITORY_HYGIENE_STATUS_MALFORMED",)
        seen_paths.add(path)
        decoded_path = os.fsdecode(path)
        if xy[:1] == b"A":
            staged_added_paths.add(decoded_path)
        if mode_head != PERMS_LINK or mode_index in {PERMS_LINK, PERMS_NONEXIST}:
            continue
        count += 1
        finding = {
            "index_mode": mode_index.decode("ascii"),
            "match_status": (
                "CONTENT_ID_EQUAL"
                if hash_head == hash_index
                else "MODE_CHANGE_CANDIDATE"
            ),
            "repository_relative_path": decoded_path,
        }
        _retain_smallest(retained, finding)
        if hash_head != hash_index:
            limitations.add("GIT_DESTROYED_SYMLINK_CONTENT_NOT_COMPARED")
    if count > HYGIENE_FINDING_LIMIT:
        limitations.add("GIT_REPOSITORY_HYGIENE_FINDING_LIMIT")
    return (
        staged_added_paths,
        [item for _, item in retained],
        count,
        tuple(sorted(limitations)),
    )


def _valid_unmerged_entry(entry: bytes) -> bool:
    fields = entry.split(b" ", 10)
    return (
        len(fields) == 11
        and fields[0] == b"u"
        and len(fields[1]) == 2
        and len(fields[2]) == 4
        and all(_MODE.fullmatch(mode) for mode in fields[3:7])
        and all(_OBJECT_ID.fullmatch(object_id) for object_id in fields[7:10])
        and bool(fields[10])
    )


def _valid_rename_entry(entry: bytes) -> bool:
    fields = entry.split(b" ", 9)
    return (
        len(fields) == 10
        and fields[0] == b"2"
        and len(fields[1]) == 2
        and len(fields[2]) == 4
        and all(_MODE.fullmatch(mode) for mode in fields[3:6])
        and all(_OBJECT_ID.fullmatch(object_id) for object_id in fields[6:8])
        and re.fullmatch(rb"[RC][0-9]+", fields[8]) is not None
        and bool(fields[9])
    )


def _retain_smallest(retained: List[Any], finding: Dict[str, Any]) -> None:
    key = finding["repository_relative_path"].encode(
        "utf-8", errors="surrogateescape"
    )
    insertion_index = 0
    while insertion_index < len(retained) and retained[insertion_index][0] <= key:
        insertion_index += 1
    if len(retained) < HYGIENE_FINDING_LIMIT:
        retained.insert(insertion_index, (key, finding))
    elif insertion_index < HYGIENE_FINDING_LIMIT:
        retained.insert(insertion_index, (key, finding))
        retained.pop()
