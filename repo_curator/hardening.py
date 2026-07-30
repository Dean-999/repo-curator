"""Shared deterministic contracts for adversarial read-only testing."""

import json
import os
import stat
from pathlib import Path
from typing import Dict, List


REQUIRED_ADVERSARIAL_CASES = (
    "global-resource-limit",
    "internally-inconsistent",
    "malformed",
    "missing-reference",
    "oversized",
    "path-escape",
    "secret-bearing-payload",
    "stale-export",
    "symlink-replacement",
    "unsupported-version",
)
_MATRIX_SCHEMA_VERSION = "repo-curator.adapter-adversarial-matrix.v1"
_MAX_MATRIX_BYTES = 256 * 1024
_MAX_FUZZ_CASES = 256
_MAX_FUZZ_BYTES = 1024 * 1024


def load_adversarial_matrix(path: Path) -> Dict[str, Dict[str, str]]:
    """Load one exact, bounded matrix without following a symbolic link."""
    path = Path(path)
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_size > _MAX_MATRIX_BYTES:
            raise ValueError("adversarial matrix must be a bounded regular file")
        payload = os.read(descriptor, _MAX_MATRIX_BYTES + 1)
    finally:
        os.close(descriptor)
    if len(payload) > _MAX_MATRIX_BYTES:
        raise ValueError("adversarial matrix exceeds byte limit")
    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("adversarial matrix is not strict UTF-8 JSON") from error
    if (
        not isinstance(document, dict)
        or set(document) != {"adapters", "schema_version"}
        or document.get("schema_version") != _MATRIX_SCHEMA_VERSION
        or not isinstance(document.get("adapters"), dict)
    ):
        raise ValueError("adversarial matrix schema is unsupported")
    adapters = document["adapters"]
    for adapter, cases in adapters.items():
        if (
            not isinstance(adapter, str)
            or not adapter
            or not isinstance(cases, dict)
            or set(cases) != set(REQUIRED_ADVERSARIAL_CASES)
            or not all(isinstance(reference, str) and reference for reference in cases.values())
        ):
            raise ValueError("adversarial matrix coverage is incomplete")
    return {adapter: dict(sorted(cases.items())) for adapter, cases in sorted(adapters.items())}


def deterministic_byte_mutations(
    seed: bytes, maximum_cases: int = 32, maximum_bytes: int = 64 * 1024
) -> List[bytes]:
    """Return a small deterministic mutation corpus for parser smoke testing."""
    if not isinstance(seed, bytes):
        raise TypeError("fuzz seed must be bytes")
    if (
        not isinstance(maximum_cases, int)
        or isinstance(maximum_cases, bool)
        or maximum_cases < 1
        or maximum_cases > _MAX_FUZZ_CASES
    ):
        raise ValueError("fuzz case limit is invalid")
    if (
        not isinstance(maximum_bytes, int)
        or isinstance(maximum_bytes, bool)
        or maximum_bytes < 1
        or maximum_bytes > _MAX_FUZZ_BYTES
    ):
        raise ValueError("fuzz byte limit is invalid")
    bounded = seed[:maximum_bytes]
    candidates = [bounded, b"", bounded[: len(bounded) // 2], bounded[:-1]]
    for index in sorted({0, len(bounded) // 4, len(bounded) // 2, max(0, len(bounded) - 1)}):
        if index >= len(bounded):
            continue
        flipped = bytearray(bounded)
        flipped[index] ^= 0xFF
        candidates.extend(
            [
                bytes(flipped),
                bounded[:index] + bounded[index + 1 :],
                (bounded[:index] + b"\x00" + bounded[index:])[:maximum_bytes],
            ]
        )
    candidates.extend(
        [
            (bounded + b"\x00")[:maximum_bytes],
            (b"[" + bounded + b"]")[:maximum_bytes],
            (b'{"nested":' + bounded + b"}")[:maximum_bytes],
        ]
    )
    unique = []
    seen = set()
    for candidate in candidates:
        if candidate not in seen:
            unique.append(candidate)
            seen.add(candidate)
        if len(unique) >= maximum_cases:
            break
    return unique


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def _reject_constant(value):
    raise ValueError("non-finite JSON constant: {}".format(value))
