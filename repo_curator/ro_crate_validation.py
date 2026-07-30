"""Bounded local validation for repo-curator RO-Crate evidence exports."""

import errno
import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple

from repo_curator.ro_crate_graph import observe_ro_crate_graph


VALIDATION_SCHEMA_VERSION = "repo-curator.ro-crate-validation-report.v1"
EXPORT_SCHEMA_VERSION = "repo-curator.ro-crate-export.v1"
EVIDENCE_PROFILE = (
    "https://github.com/Dean-999/repo-curator/tree/main/docs/profiles/evidence-v1"
)
SHAPE_PROFILE = "schemas/ro-crate-evidence-profile.shacl.ttl"
MAX_INPUT_BYTES = 4 * 1024 * 1024
_BUDGET_LIMITATIONS = {
    "RO_CRATE_ENTITY_LIMIT",
    "RO_CRATE_EXTERNAL_REFERENCE_LIMIT",
    "RO_CRATE_REFERENCE_LIMIT",
    "RO_CRATE_UNRESOLVED_REFERENCE_LIMIT",
    "RO_CRATE_VALUE_NODE_LIMIT",
}
_STRUCTURAL_VIOLATIONS = {
    "RO_CRATE_DESCRIPTOR_INVALID",
    "RO_CRATE_DESCRIPTOR_MISSING",
    "RO_CRATE_DUPLICATE_ENTITY_ID",
    "RO_CRATE_ENTITY_MALFORMED",
    "RO_CRATE_GRAPH_SHAPE_INVALID",
    "RO_CRATE_REFERENCE_UNRESOLVED",
    "RO_CRATE_ROOT_INVALID",
    "RO_CRATE_ROOT_MISSING",
}


class RoCrateValidationError(ValueError):
    """Stable rejection for unsafe inputs and unsupported validation records."""


def read_evidence_crate(path: Path) -> Tuple[Dict[str, Any], str]:
    """Read one no-follow regular UTF-8 JSON object under a hard byte limit."""
    try:
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise RoCrateValidationError(
                "RO-Crate input must not be a symbolic link"
            ) from error
        raise
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise RoCrateValidationError("RO-Crate input must be a regular file")
        if details.st_size > MAX_INPUT_BYTES:
            raise RoCrateValidationError("RO-Crate input exceeds byte limit")
        payload = bytearray()
        while len(payload) <= MAX_INPUT_BYTES:
            chunk = os.read(
                descriptor, min(1024 * 1024, MAX_INPUT_BYTES + 1 - len(payload))
            )
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) > MAX_INPUT_BYTES:
            raise RoCrateValidationError("RO-Crate input exceeds byte limit")
    finally:
        os.close(descriptor)
    digest = hashlib.sha256(payload).hexdigest()
    try:
        parsed = json.loads(
            payload.decode("utf-8"), object_pairs_hook=_unique_json_object
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise RoCrateValidationError("RO-Crate input is not valid unique-key UTF-8 JSON") from error
    if not isinstance(parsed, dict):
        raise RoCrateValidationError("RO-Crate input must contain a JSON object")
    return parsed, digest


def validate_evidence_crate(
    parsed: Mapping[str, Any], input_sha256: str
) -> Dict[str, Any]:
    """Validate the documented local subset without claiming full SHACL."""
    if (
        not isinstance(parsed, Mapping)
        or not isinstance(input_sha256, str)
        or len(input_sha256) != 64
        or any(character not in "0123456789abcdef" for character in input_sha256)
    ):
        raise RoCrateValidationError("validation input identity is invalid")
    observation, observed_limitations = observe_ro_crate_graph(parsed)
    findings = []
    for limitation in observed_limitations:
        if limitation in _STRUCTURAL_VIOLATIONS:
            findings.append(_finding(_finding_code(limitation)))

    root = _entity(parsed, observation.get("root_entity_id"))
    if root is not None:
        if root.get("repo-curator:executionAuthorized") is not False:
            findings.append(_finding("EXECUTION_AUTHORITY_NOT_FALSE"))
        if root.get("repo-curator:exportSchemaVersion") != EXPORT_SCHEMA_VERSION:
            findings.append(_finding("EXPORT_SCHEMA_UNSUPPORTED"))
        if EVIDENCE_PROFILE not in _reference_ids(root.get("conformsTo")):
            findings.append(_finding("EVIDENCE_PROFILE_MISSING"))

    limitations = sorted(set(observed_limitations))
    incomplete = any(item in _BUDGET_LIMITATIONS for item in limitations)
    if findings:
        status = "NONCONFORMANT"
    elif incomplete:
        status = "INCOMPLETE"
    else:
        status = "BOUNDED_PROFILE_CONFORMANT"
    return {
        "admission_authority": False,
        "execution_authority": "NONE",
        "findings": sorted(findings, key=lambda item: item["code"]),
        "full_shacl_conformance_claimed": False,
        "input_sha256": input_sha256,
        "limitations": limitations,
        "profile": EVIDENCE_PROFILE,
        "schema_version": VALIDATION_SCHEMA_VERSION,
        "shacl_engine_used": False,
        "shape_profile": SHAPE_PROFILE,
        "status": status,
        "validation_scope": "BOUNDED_LOCAL_STRUCTURAL_SUBSET",
    }


def validate_evidence_crate_file(path: Path, output: Path) -> Path:
    """Validate one explicit file and durably publish one create-once report."""
    parsed, digest = read_evidence_crate(path)
    _write_new_json(output, validate_evidence_crate(parsed, digest))
    return output


def _finding(code: str) -> Dict[str, str]:
    return {"code": code, "severity": "VIOLATION"}


def _finding_code(limitation: str) -> str:
    if limitation == "RO_CRATE_REFERENCE_UNRESOLVED":
        return "LOCAL_REFERENCE_UNRESOLVED"
    return limitation


def _entity(parsed: Mapping[str, Any], identifier: Any) -> Any:
    if not isinstance(identifier, str):
        return None
    graph = parsed.get("@graph")
    if not isinstance(graph, list):
        return None
    matches = [
        item
        for item in graph
        if isinstance(item, Mapping) and item.get("@id") == identifier
    ]
    return matches[0] if len(matches) == 1 else None


def _reference_ids(value: Any) -> set:
    values = value if isinstance(value, list) else [value]
    return {
        item["@id"]
        for item in values
        if isinstance(item, Mapping)
        and isinstance(item.get("@id"), str)
        and item["@id"]
    }


def _unique_json_object(pairs: list) -> Dict[str, Any]:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON object key")
        value[key] = item
    return value


def _write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    parent = path.parent
    if not parent.is_dir():
        raise RoCrateValidationError("validation output parent does not exist")
    payload = (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=".repo-curator-ro-crate-validation-", dir=str(parent)
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise RoCrateValidationError("validation output already exists") from error
        directory = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
