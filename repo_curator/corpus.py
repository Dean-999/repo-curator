"""Build and evaluate manifest-bound corpus artifacts without executing repository content."""

import hashlib
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from repo_curator.evaluation import (
    CORPUS_MANIFEST_SCHEMA_VERSION,
    evaluate_admission,
)


_MAX_CORPUS_FILE_BYTES = 64 * 1024 * 1024
_MAX_ARTIFACT_BYTES = 512 * 1024 * 1024
_SHA256_PREFIX = "sha256:"
_ARTIFACT_LEDGER_SCHEMA_VERSION = "repo-curator.corpus-artifact-ledger.v1"
_ARTIFACT_VERIFICATION_SCHEMA_VERSION = "repo-curator.corpus-artifact-verification.v1"
_GOLD_CASE_SCHEMA_VERSION_V2 = "repo-curator.gold-case.v2"
_RISK_CASE_SCHEMA_VERSION_V2 = "repo-curator.mutation-risk-case.v2"


class CorpusError(ValueError):
    """Stable rejection for corpus pipeline input or output errors."""


def read_record_array(path: Path, name: str) -> List[Mapping[str, Any]]:
    """Read a bounded UTF-8 JSON array from one explicit regular file."""
    value = _read_json(path, name)
    if not isinstance(value, list):
        raise CorpusError("{} must contain a JSON array".format(name))
    if not all(isinstance(record, Mapping) for record in value):
        raise CorpusError("{} must contain only JSON objects".format(name))
    return list(value)


def read_reviewer_registry(path: Path) -> Dict[str, str]:
    """Read reviewer provenance hashes that the manifest binds to case labels."""
    value = _read_json(path, "reviewer registry")
    if not isinstance(value, Mapping) or not all(
        isinstance(reviewer_id, str) and reviewer_id and _is_sha256_digest(provenance_hash)
        for reviewer_id, provenance_hash in value.items()
    ):
        raise CorpusError("reviewer registry must map nonempty reviewer IDs to sha256 hashes")
    return dict(value)


def read_json_object(path: Path, name: str) -> Dict[str, Any]:
    """Read one bounded UTF-8 JSON object from an explicit regular file."""
    value = _read_json(path, name)
    if not isinstance(value, Mapping):
        raise CorpusError("{} must contain a JSON object".format(name))
    return dict(value)


def build_manifest(
    cases: Sequence[Mapping[str, Any]],
    risk_cases: Sequence[Mapping[str, Any]],
    reviewer_registry: Mapping[str, str],
    corpus_id: str,
    evaluator_version: str,
) -> Dict[str, Any]:
    """Create the exact v1 manifest required by the conservative evaluator."""
    if not isinstance(corpus_id, str) or not corpus_id:
        raise CorpusError("corpus ID must be a nonempty string")
    if not isinstance(evaluator_version, str) or not evaluator_version:
        raise CorpusError("evaluator version must be a nonempty string")
    if not all(isinstance(record, Mapping) for record in list(cases) + list(risk_cases)):
        raise CorpusError("corpus records must be JSON objects")
    if not isinstance(reviewer_registry, Mapping) or not all(
        isinstance(reviewer_id, str) and reviewer_id and _is_sha256_digest(provenance_hash)
        for reviewer_id, provenance_hash in reviewer_registry.items()
    ):
        raise CorpusError("reviewer registry must map nonempty reviewer IDs to sha256 hashes")
    return {
        "case_records_sha256": _digest(cases),
        "corpus_id": corpus_id,
        "evaluator_version": evaluator_version,
        "reviewer_registry": dict(reviewer_registry),
        "risk_records_sha256": _digest(risk_cases),
        "schema_version": CORPUS_MANIFEST_SCHEMA_VERSION,
    }


def evaluate_corpus(
    cases: Sequence[Mapping[str, Any]],
    risk_cases: Sequence[Mapping[str, Any]],
    manifest: Mapping[str, Any],
    created_at: str,
    artifact_ledger: Optional[Mapping[str, Any]] = None,
    artifact_root: Optional[Path] = None,
) -> Dict[str, Any]:
    """Evaluate explicit corpus records with the same fail-closed admission gates."""
    if not isinstance(created_at, str) or not created_at:
        raise CorpusError("created at must be a nonempty string")
    report = evaluate_admission(cases, risk_cases, created_at, manifest)
    requires_artifact_verification = _has_v2_records(cases, risk_cases)
    if requires_artifact_verification and (artifact_ledger is None or artifact_root is None):
        raise CorpusError("artifact verification is required for v2 corpus records")
    if not requires_artifact_verification and (artifact_ledger is not None or artifact_root is not None):
        raise CorpusError("artifact verification is only supported for v2 corpus records")
    if requires_artifact_verification:
        report["artifact_verification"] = verify_corpus_artifacts(
            cases, risk_cases, manifest["reviewer_registry"], artifact_ledger, artifact_root
        )
    return report


def read_artifact_ledger(path: Path) -> Dict[str, Any]:
    """Read one exact artifact ledger that locates every v2 evidence byte stream."""
    return _validated_ledger(read_json_object(path, "artifact ledger"))


def verify_corpus_artifacts(
    cases: Sequence[Mapping[str, Any]],
    risk_cases: Sequence[Mapping[str, Any]],
    reviewer_registry: Mapping[str, str],
    artifact_ledger: Mapping[str, Any],
    artifact_root: Path,
) -> Dict[str, Any]:
    """Verify every v2 evidence hash against one no-follow artifact directory."""
    _validate_v2_records(cases, risk_cases, reviewer_registry)
    ledger = _validated_ledger(artifact_ledger)
    references = _artifact_references(cases, risk_cases, reviewer_registry)
    ledger_by_hash = {artifact["artifact_hash"]: artifact["path"] for artifact in ledger["artifacts"]}
    if set(ledger_by_hash) != references:
        raise CorpusError("artifact ledger references do not match corpus evidence")
    root_fd = _open_artifact_root(artifact_root)
    try:
        for artifact_hash in sorted(references):
            observed_hash = _hash_artifact(root_fd, ledger_by_hash[artifact_hash])
            if observed_hash != artifact_hash:
                raise CorpusError("artifact hash mismatch")
    finally:
        os.close(root_fd)
    return {
        "artifact_ledger_sha256": _digest(ledger),
        "referenced_artifact_count": len(references),
        "schema_version": _ARTIFACT_VERIFICATION_SCHEMA_VERSION,
        "verified_artifact_hashes": sorted(references),
    }


def write_new_json(path: Path, value: Mapping[str, Any]) -> None:
    """Durably publish JSON once; never replace an existing evidence artifact."""
    if not isinstance(value, Mapping):
        raise CorpusError("output must be a JSON object")
    parent = path.parent
    if not parent.is_dir():
        raise CorpusError("output parent directory does not exist")
    payload = _canonical_json_bytes(value) + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=".repo-curator-evaluation-", dir=str(parent))
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        try:
            os.link(temporary_path, path)
        except FileExistsError as error:
            raise CorpusError("output already exists") from error
        _fsync_directory(parent)
    finally:
        try:
            temporary_path.unlink()
        except FileNotFoundError:
            pass


def _read_json(path: Path, name: str) -> Any:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise CorpusError("{} must be a regular file".format(name))
        if details.st_size > _MAX_CORPUS_FILE_BYTES:
            raise CorpusError("{} exceeds the 64 MiB corpus file limit".format(name))
        chunks = []
        total = 0
        while total <= _MAX_CORPUS_FILE_BYTES:
            chunk = os.read(descriptor, min(1_048_576, _MAX_CORPUS_FILE_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        if total > _MAX_CORPUS_FILE_BYTES:
            raise CorpusError("{} exceeds the 64 MiB corpus file limit".format(name))
    finally:
        os.close(descriptor)
    try:
        return json.loads(b"".join(chunks).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, RecursionError) as error:
        raise CorpusError("{} is not valid UTF-8 JSON".format(name)) from error


def _fsync_directory(path: Path) -> None:
    descriptor = os.open(path, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _digest(value: Any) -> str:
    return _SHA256_PREFIX + hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _is_sha256_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == len(_SHA256_PREFIX) + 64
        and value.startswith(_SHA256_PREFIX)
        and all(character in "0123456789abcdef" for character in value[len(_SHA256_PREFIX):])
    )


def _validated_ledger(ledger: Mapping[str, Any]) -> Dict[str, Any]:
    if not isinstance(ledger, Mapping) or set(ledger) != {"artifacts", "schema_version"} or ledger.get("schema_version") != _ARTIFACT_LEDGER_SCHEMA_VERSION:
        raise CorpusError("artifact ledger is malformed")
    artifacts = ledger.get("artifacts")
    if not isinstance(artifacts, list):
        raise CorpusError("artifact ledger is malformed")
    hashes = set()
    paths = set()
    normalized = []
    for artifact in artifacts:
        if not isinstance(artifact, Mapping) or set(artifact) != {"artifact_hash", "path"}:
            raise CorpusError("artifact ledger is malformed")
        artifact_hash = artifact.get("artifact_hash")
        artifact_path = artifact.get("path")
        if not _is_sha256_digest(artifact_hash):
            raise CorpusError("artifact ledger is malformed")
        _artifact_path_parts(artifact_path)
        if artifact_hash in hashes or artifact_path in paths:
            raise CorpusError("artifact ledger has duplicate artifact references")
        hashes.add(artifact_hash)
        paths.add(artifact_path)
        normalized.append({"artifact_hash": artifact_hash, "path": artifact_path})
    return {"artifacts": normalized, "schema_version": _ARTIFACT_LEDGER_SCHEMA_VERSION}


def _validate_v2_records(
    cases: Sequence[Mapping[str, Any]], risk_cases: Sequence[Mapping[str, Any]], reviewer_registry: Mapping[str, str]
) -> None:
    records = list(cases) + list(risk_cases)
    if not records or not _has_v2_records(cases, risk_cases) or any(
        not isinstance(record, Mapping) or record.get("schema_version") not in {_GOLD_CASE_SCHEMA_VERSION_V2, _RISK_CASE_SCHEMA_VERSION_V2}
        for record in records
    ):
        raise CorpusError("artifact verification requires nonempty v2 corpus records")
    evaluator_versions = {record.get("evaluator_version") for record in records}
    if len(evaluator_versions) != 1 or not isinstance(next(iter(evaluator_versions)), str):
        raise CorpusError("artifact verification requires one evaluator version")
    manifest = build_manifest(cases, risk_cases, reviewer_registry, "artifact-verification", next(iter(evaluator_versions)))
    evaluate_admission(cases, risk_cases, "artifact-verification", manifest)


def _artifact_references(
    cases: Sequence[Mapping[str, Any]], risk_cases: Sequence[Mapping[str, Any]], reviewer_registry: Mapping[str, str]
) -> set[str]:
    references = set(reviewer_registry.values())
    for case in cases:
        references.update({
            case["expected_label_artifact_hash"], case["prediction_artifact_hash"], case["repository_snapshot_hash"],
        })
        references.update(label["label_artifact_hash"] for label in case["review_labels"])
    for risk_case in risk_cases:
        references.update({risk_case["fault_injection_report_hash"], risk_case["repository_snapshot_hash"]})
        references.update(risk_case["evidence_artifact_hashes"])
    return references


def _has_v2_records(cases: Sequence[Mapping[str, Any]], risk_cases: Sequence[Mapping[str, Any]]) -> bool:
    return any(
        isinstance(record, Mapping) and record.get("schema_version") in {_GOLD_CASE_SCHEMA_VERSION_V2, _RISK_CASE_SCHEMA_VERSION_V2}
        for record in list(cases) + list(risk_cases)
    )


def _artifact_path_parts(value: Any) -> List[str]:
    if not isinstance(value, str) or not value or "\\" in value:
        raise CorpusError("artifact ledger path is unsafe")
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise CorpusError("artifact ledger path is unsafe")
    return parts


def _open_artifact_root(path: Path) -> int:
    return os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))


def _hash_artifact(root_fd: int, relative_path: str) -> str:
    current_fd = os.dup(root_fd)
    try:
        parts = _artifact_path_parts(relative_path)
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        descriptor = os.open(parts[-1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=current_fd)
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode):
                raise CorpusError("artifact must be a regular file")
            if details.st_size > _MAX_ARTIFACT_BYTES:
                raise CorpusError("artifact exceeds the 512 MiB verification limit")
            digest = hashlib.sha256()
            total = 0
            while total <= _MAX_ARTIFACT_BYTES:
                payload = os.read(descriptor, min(1_048_576, _MAX_ARTIFACT_BYTES + 1 - total))
                if not payload:
                    break
                digest.update(payload)
                total += len(payload)
            if total > _MAX_ARTIFACT_BYTES:
                raise CorpusError("artifact exceeds the 512 MiB verification limit")
            return _SHA256_PREFIX + digest.hexdigest()
        finally:
            os.close(descriptor)
    finally:
        os.close(current_fd)
