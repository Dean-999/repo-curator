"""Deterministic, independent identities for inventory observations."""

import hashlib
import json
import os
import unicodedata
from typing import Any, Iterable, Mapping, Optional


def length_prefix(*parts: bytes) -> bytes:
    """Encode byte strings without delimiter ambiguity."""
    return b"".join(len(part).to_bytes(8, "big") + part for part in parts)


def location_identity(
    root_realpath: str, object_type: str, repository_relative_path: bytes
) -> str:
    """Identify an observed filesystem location, independently of its content."""
    payload = length_prefix(
        os.fsencode(root_realpath), object_type.encode("utf-8"), repository_relative_path
    )
    return f"location-filesystem-v1:{hashlib.sha256(payload).hexdigest()}"


def content_identity(
    observation: Any, child_manifest: Optional[Iterable[Mapping[str, Any]]] = None
) -> Optional[str]:
    """Return an exact content identity without considering repository location."""
    if child_manifest is not None:
        return directory_merkle(child_manifest)
    fingerprint_scheme = _observation_value(observation, "fingerprint_scheme")
    fingerprint = _observation_value(observation, "fingerprint")
    if fingerprint_scheme is None or fingerprint is None:
        return None
    return f"{fingerprint_scheme}:{fingerprint}"


def directory_merkle(children: Iterable[Mapping[str, Any]]) -> str:
    """Hash a location-free child manifest in raw-byte filename order."""
    manifest = sorted(children, key=lambda child: os.fsencode(child["name"]))
    digest = hashlib.sha256(_canonical_json_bytes(manifest)).hexdigest()
    return f"merkle-dir-v1:{digest}"


def repository_state_identity(
    root_realpath: str, inventory_records: Iterable[Mapping[str, Any]]
) -> str:
    """Hash the deterministic inventory projection for a repository root."""
    state_artifacts = [
        {
            "content_id": record["content_id"],
            "executable": record["executable"],
            "mode": record["mode"],
            "mtime_ns": record["mtime_ns"],
            "object_type": record["object_type"],
            "repository_relative_path": record["repository_relative_path"],
            "size_bytes": record["size_bytes"],
        }
        for record in inventory_records
    ]
    payload = _canonical_json_bytes(
        {
            "artifacts": state_artifacts,
            "repository_root_realpath": root_realpath,
            "scheme": "sha256-repo-state-v1",
        }
    )
    return f"sha256-repo-state-v1:{hashlib.sha256(payload).hexdigest()}"


def collision_key(path: str) -> str:
    """Normalize a path for case-insensitive collision detection."""
    return unicodedata.normalize("NFC", path).casefold()


def _observation_value(observation: Any, name: str) -> Any:
    if isinstance(observation, Mapping):
        return observation.get(name)
    return getattr(observation, name)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
