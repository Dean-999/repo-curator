"""Bounded Git repository-size metrics adapted from git-sizer.

Metric categories, reference scales, and the ``value / scale`` concern model
are adapted from github/git-sizer ``sizes/sizes.go`` and ``sizes/output.go`` at
commit 88eaa80df48db1b47291f3a43b084b8c79082339 (MIT). This port deliberately
does not traverse every reachable object, resolve object paths, read historical
file/blob content, or recommend history rewriting. Git execution remains owned
by ``git_evidence``.
"""

from typing import Any, Dict, Iterable, Optional


_COUNT_OBJECT_KEYS = frozenset(
    {
        "count",
        "garbage",
        "in-pack",
        "packs",
        "prune-packable",
        "size",
        "size-garbage",
        "size-pack",
    }
)
_REFERENCE_SCALES = {
    "current_checkout_file_count": 50_000,
    "current_checkout_size_bytes": 1_000_000_000,
    "max_regular_file_size_bytes": 10_000_000,
    "reachable_commit_count": 500_000,
    "reference_count": 25_000,
}
_MAX_UINT64 = (1 << 64) - 1
_MAX_COUNT_DIGITS = 20


def parse_count(payload: bytes) -> Optional[int]:
    """Parse one non-negative decimal count with no trailing material."""
    value = payload.strip()
    if (
        not value
        or len(value) > _MAX_COUNT_DIGITS
        or not value.isdigit()
    ):
        return None
    parsed = int(value)
    return parsed if parsed <= _MAX_UINT64 else None


def parse_reference_count(payload: bytes) -> Optional[int]:
    """Count newline-delimited ref records without retaining their names."""
    if not payload:
        return 0
    if b"\0" in payload or not payload.endswith(b"\n"):
        return None
    return len(payload.splitlines())


def parse_count_objects(payload: bytes) -> Optional[Dict[str, int]]:
    """Parse fixed ``git count-objects -v`` numeric fields."""
    values: Dict[str, int] = {}
    for line in payload.splitlines():
        key, separator, raw_value = line.partition(b": ")
        if not separator:
            return None
        try:
            key_text = key.decode("ascii")
        except UnicodeDecodeError:
            return None
        if key_text == "alternate":
            continue
        if key_text not in _COUNT_OBJECT_KEYS or key_text in values:
            return None
        parsed = parse_count(raw_value)
        if parsed is None:
            return None
        values[key_text] = parsed
    if set(values) != _COUNT_OBJECT_KEYS:
        return None
    if any(
        values[key] > _MAX_UINT64 // 1024
        for key in ("size", "size-garbage", "size-pack")
    ):
        return None
    return {
        "garbage": values["garbage"],
        "garbage_size_bytes": values["size-garbage"] * 1024,
        "in_pack": values["in-pack"],
        "loose_objects": values["count"],
        "loose_size_bytes": values["size"] * 1024,
        "pack_count": values["packs"],
        "packed_size_bytes": values["size-pack"] * 1024,
        "prune_packable": values["prune-packable"],
    }


def summarize_current_checkout(records: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize inventoried regular files without reading their content."""
    regular = [
        record
        for record in records
        if record["object_type"] == "REGULAR_FILE"
        and isinstance(record.get("size_bytes"), int)
    ]
    largest = min(
        regular,
        key=lambda record: (
            -record["size_bytes"],
            record["repository_relative_path"].encode(
                "utf-8", errors="surrogateescape"
            ),
        ),
        default=None,
    )
    return {
        "max_regular_file_artifact_id": (
            largest["artifact_id"] if largest is not None else None
        ),
        "max_regular_file_path": (
            largest["repository_relative_path"] if largest is not None else None
        ),
        "max_regular_file_size_bytes": (
            largest["size_bytes"] if largest is not None else 0
        ),
        "regular_file_count": len(regular),
        "regular_file_size_bytes": sum(record["size_bytes"] for record in regular),
    }


def concern_ratios(
    reference_count: int,
    reachable_commit_count: int,
    checkout: Dict[str, Any],
) -> Dict[str, float]:
    """Return git-sizer-style context ratios, never an action decision."""
    values = {
        "current_checkout_file_count": checkout["regular_file_count"],
        "current_checkout_size_bytes": checkout["regular_file_size_bytes"],
        "max_regular_file_size_bytes": checkout["max_regular_file_size_bytes"],
        "reachable_commit_count": reachable_commit_count,
        "reference_count": reference_count,
    }
    return {
        key: round(values[key] / scale, 6)
        for key, scale in _REFERENCE_SCALES.items()
    }


def reference_scales() -> Dict[str, int]:
    """Return a copy of the frozen git-sizer reference scales."""
    return dict(_REFERENCE_SCALES)
