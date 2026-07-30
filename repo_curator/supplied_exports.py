"""Validate explicit, manifest-bound adapter exports without invoking their tools."""

import hashlib
import errno
import json
import os
import stat
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from repo_curator.workflow_run_crate import observe_workflow_run_crate


SUPPLIED_EXPORT_MANIFEST_SCHEMA_VERSION = "repo-curator.supplied-adapter-export-manifest.v1"
WORKFLOW_RUN_EXPORT_MANIFEST_SCHEMA_VERSION = (
    "repo-curator.workflow-run-ro-crate-export-manifest.v1"
)
OBSERVATION_SCHEMA_VERSION = "repo-curator.adapter-observation.v1"
MAX_MANIFEST_BYTES = 65_536
MAX_PAYLOAD_BYTES = 1_048_576
MAX_EXPORT_MANIFESTS = 16
_REQUIRED_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "adapter_family",
        "source_tool",
        "source_version",
        "snapshot_scope",
        "payload_type",
        "payload",
    }
)
_REQUIRED_PAYLOAD_KEYS = frozenset({"path", "sha256"})
_LIMITATIONS = (
    "SUPPLIED_EXPORT_NOT_EXECUTED",
    "SUPPLIED_EXPORT_PAYLOAD_SEMANTICS_NOT_VALIDATED",
    "SUPPLIED_EXPORT_REPRODUCTION_NOT_VALIDATED",
    "SUPPLIED_EXPORT_REMOTE_CONTENT_NOT_RESOLVED",
)
_WORKFLOW_RUN_LIMITATIONS = (
    "SUPPLIED_EXPORT_NOT_EXECUTED",
    "SUPPLIED_ACTION_STATUS_NOT_EXECUTION_VERIFIED",
    "SUPPLIED_EXPORT_REPRODUCTION_NOT_VALIDATED",
    "SUPPLIED_EXPORT_REMOTE_CONTENT_NOT_RESOLVED",
)


def detect_supplied_exports(
    manifest_paths: Sequence[Path], run_id: str, created_at: str, start_sequence: int
) -> List[Dict[str, Any]]:
    """Return deterministic metadata-only observations from explicitly named exports."""
    normalized_paths = _normalized_manifest_paths(manifest_paths)
    observations = []
    for sequence, manifest_path in enumerate(normalized_paths, start=start_sequence + 1):
        document, manifest_bytes, payload_bytes, parsed_payload = _read_bound_export(
            manifest_path
        )
        payload = document["payload"]
        observation = {
            "adapter_family": document["adapter_family"],
            "coverage": "SUPPLIED_EXPORT_METADATA_ONLY",
            "created_at": created_at,
            "declaration_family": document["adapter_family"],
            "limitations": list(_LIMITATIONS),
            "manifest_path": str(manifest_path),
            "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
            "observation_id": f"obs_{run_id}_{sequence:08d}",
            "payload_path": payload["path"],
            "payload_sha256": hashlib.sha256(payload_bytes).hexdigest(),
            "payload_type": document["payload_type"],
            "run_id": run_id,
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            "snapshot_scope": document["snapshot_scope"],
            "source_tool": document["source_tool"],
            "source_version": document["source_version"],
            "status": "PRESENT",
            "validation_status": "BOUND_MANIFEST_VALIDATED",
        }
        if document["adapter_family"] == "WORKFLOW_RUN_RO_CRATE":
            workflow_run, workflow_limitations = observe_workflow_run_crate(
                parsed_payload
            )
            observation["coverage"] = "SUPPLIED_EXPORT_DECLARATION_GRAPH"
            observation["limitations"] = sorted(
                set(_WORKFLOW_RUN_LIMITATIONS) | set(workflow_limitations)
            )
            observation["validation_status"] = (
                "BOUND_MANIFEST_VALIDATED_DECLARATION_GRAPH_UNAVAILABLE"
                if workflow_run["status"] == "UNAVAILABLE"
                else "BOUND_MANIFEST_VALIDATED_DECLARATION_GRAPH_OBSERVED"
            )
            observation["workflow_run"] = workflow_run
        observations.append(observation)
    return observations


def _normalized_manifest_paths(manifest_paths: Sequence[Path]) -> List[Path]:
    if len(manifest_paths) > MAX_EXPORT_MANIFESTS:
        raise ValueError("adapter export manifest count exceeds limit")
    paths = []
    for supplied_path in manifest_paths:
        path = Path(supplied_path)
        if not path.is_absolute():
            raise ValueError("adapter export manifest path must be absolute")
        try:
            path_stat = os.lstat(path)
        except FileNotFoundError as error:
            raise ValueError(f"adapter export manifest does not exist: {path}") from error
        if stat.S_ISLNK(path_stat.st_mode):
            raise ValueError("adapter export manifest is a symbolic link")
        if not stat.S_ISREG(path_stat.st_mode):
            raise ValueError("adapter export manifest is not a regular file")
        paths.append(path)
    normalized = sorted(paths, key=lambda item: os.fsencode(str(item)))
    if len(set(normalized)) != len(normalized):
        raise ValueError("adapter export manifests must not repeat a path")
    return normalized


def _read_bound_export(
    manifest_path: Path,
) -> tuple[Dict[str, Any], bytes, bytes, Dict[str, Any]]:
    parent_path = manifest_path.parent.resolve(strict=True)
    parent_fd = _open_directory(parent_path)
    try:
        manifest_bytes = _read_regular_file(parent_fd, manifest_path.name, MAX_MANIFEST_BYTES, "manifest")
        document = _parse_json_object(manifest_bytes, "adapter export manifest")
        _validate_manifest(document)
        payload_bytes = _read_contained_payload(parent_fd, document["payload"]["path"])
    finally:
        os.close(parent_fd)
    actual_sha256 = hashlib.sha256(payload_bytes).hexdigest()
    if actual_sha256 != document["payload"]["sha256"]:
        raise ValueError("adapter export payload SHA-256 does not match manifest")
    payload_label = (
        "Workflow Run RO-Crate payload"
        if document["adapter_family"] == "WORKFLOW_RUN_RO_CRATE"
        else "ReproZip metadata payload"
    )
    parsed_payload = _parse_json_object(payload_bytes, payload_label)
    return document, manifest_bytes, payload_bytes, parsed_payload


def _validate_manifest(document: Dict[str, Any]) -> None:
    if set(document) != _REQUIRED_MANIFEST_KEYS:
        raise ValueError("adapter export manifest has unsupported fields")
    schema_version = document.get("schema_version")
    if schema_version not in {
        SUPPLIED_EXPORT_MANIFEST_SCHEMA_VERSION,
        WORKFLOW_RUN_EXPORT_MANIFEST_SCHEMA_VERSION,
    }:
        raise ValueError("adapter export manifest schema version is unsupported")
    expected_contract = {
        SUPPLIED_EXPORT_MANIFEST_SCHEMA_VERSION: (
            "REPROZIP",
            "reprozip",
            "REPROZIP_METADATA_JSON",
        ),
        WORKFLOW_RUN_EXPORT_MANIFEST_SCHEMA_VERSION: (
            "WORKFLOW_RUN_RO_CRATE",
            None,
            "WORKFLOW_RUN_RO_CRATE_JSON",
        ),
    }[schema_version]
    expected_family, expected_tool, expected_payload_type = expected_contract
    if document.get("adapter_family") != expected_family:
        raise ValueError("adapter export manifest adapter family is unsupported")
    if expected_tool is not None and document.get("source_tool") != expected_tool:
        raise ValueError("adapter export manifest source tool is unsupported")
    for field in ("source_tool", "source_version", "snapshot_scope"):
        value = document.get(field)
        if not isinstance(value, str) or not value or len(value) > 128:
            raise ValueError(f"adapter export manifest {field} must be a bounded nonempty string")
    if document.get("payload_type") != expected_payload_type:
        raise ValueError("adapter export manifest payload type is unsupported")
    payload = document.get("payload")
    if not isinstance(payload, dict) or set(payload) != _REQUIRED_PAYLOAD_KEYS:
        raise ValueError("adapter export manifest payload is invalid")
    path = payload.get("path")
    if not isinstance(path, str) or not path or len(path) > 512:
        raise ValueError("adapter export manifest payload path is invalid")
    sha256 = payload.get("sha256")
    if not isinstance(sha256, str) or len(sha256) != 64 or any(
        character not in "0123456789abcdef" for character in sha256
    ):
        raise ValueError("adapter export manifest payload SHA-256 is invalid")


def _read_contained_payload(parent_fd: int, relative_path: str) -> bytes:
    parts = relative_path.split("/")
    if (
        relative_path.startswith("/")
        or any(part in {"", ".", ".."} for part in parts)
        or "\\" in relative_path
    ):
        raise ValueError("adapter export payload path must be a contained relative path")
    current_fd = os.dup(parent_fd)
    try:
        for component in parts[:-1]:
            next_fd = _open_directory_at(current_fd, component)
            os.close(current_fd)
            current_fd = next_fd
        return _read_regular_file(current_fd, parts[-1], MAX_PAYLOAD_BYTES, "payload")
    finally:
        os.close(current_fd)


def _open_directory(path: Path) -> int:
    return os.open(path, _directory_flags())


def _open_directory_at(parent_fd: int, name: str) -> int:
    return os.open(name, _directory_flags(), dir_fd=parent_fd)


def _directory_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _read_regular_file(parent_fd: int, name: str, max_bytes: int, label: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(name, flags, dir_fd=parent_fd)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ValueError(f"adapter export {label} is a symbolic link") from error
        raise
    try:
        result = os.fstat(descriptor)
        if not stat.S_ISREG(result.st_mode):
            raise ValueError(f"adapter export {label} is not a regular file")
        if result.st_size > max_bytes:
            raise ValueError(f"adapter export {label} exceeds byte limit")
        chunks = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(descriptor, min(65_536, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        if len(content) > max_bytes:
            raise ValueError(f"adapter export {label} exceeds byte limit")
        return content
    finally:
        os.close(descriptor)


def _parse_json_object(content: bytes, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(content.decode("utf-8"), parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError(f"{label} is not strict UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")
