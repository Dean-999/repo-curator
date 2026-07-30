"""Read-only interchange exports from verified repo-curator audit records."""

import errno
import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


RO_CRATE_EXPORT_SCHEMA_VERSION = "repo-curator.ro-crate-export.v1"
_RO_CRATE_CONTEXT = "https://w3id.org/ro/crate/1.1/context"
_REPO_CURATOR_NAMESPACE = "https://github.com/Dean-999/repo-curator#"
_EVIDENCE_PROFILE = "https://github.com/Dean-999/repo-curator/tree/main/docs/profiles/evidence-v1"
_REQUIRED_FILES = ("evidence.jsonl", "mainline-map.jsonl", "project-intent.json")
_MAX_TOTAL_INPUT_BYTES = 1_073_741_824
_MAX_JSONL_RECORDS = 200_000
_MAX_OUTPUT_FILES = 128
_MAX_RUN_RECORD_BYTES = 4_194_304
_MAX_OUTPUT_FILE_BYTES = 268_435_456


def export_ro_crate(run_directory: Path, output: Path) -> Path:
    """Write one new non-executable RO-Crate view of a hash-verified audit."""
    run_directory = Path(run_directory)
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"RO-Crate output already exists: {output}")
    run, files = _verified_run(run_directory)
    document = _build_ro_crate(run, files)
    _write_new_json(output, document)
    return output


def _verified_run(run_directory: Path) -> tuple[Dict[str, Any], Dict[str, bytes]]:
    if not run_directory.is_absolute():
        raise ValueError("audit run directory must be absolute")
    directory_stat = os.lstat(run_directory)
    if stat.S_ISLNK(directory_stat.st_mode) or not stat.S_ISDIR(directory_stat.st_mode):
        raise ValueError("audit run directory must be a non-link directory")
    directory_fd = os.open(run_directory, _directory_flags())
    try:
        run_limit = min(_MAX_RUN_RECORD_BYTES, _MAX_TOTAL_INPUT_BYTES)
        run_bytes = _read_regular_file(
            directory_fd,
            "run.json",
            run_limit,
            (
                "audit run outputs exceed total byte limit"
                if _MAX_TOTAL_INPUT_BYTES < _MAX_RUN_RECORD_BYTES
                else "audit run record exceeds file byte limit"
            ),
        )
        total_bytes = len(run_bytes)
        run = _parse_json_object(run_bytes, "run record")
        if run.get("schema_version") != "repo-curator.run.v1":
            raise ValueError("audit run schema version is unsupported")
        if run.get("final_status") not in {"COMPLETED", "COMPLETED_WITH_LIMITATIONS"}:
            raise ValueError("audit run is not finalized")
        output_hashes = run.get("output_file_hashes")
        if not isinstance(output_hashes, dict) or not output_hashes:
            raise ValueError("audit run output hashes are invalid")
        if len(output_hashes) > _MAX_OUTPUT_FILES:
            raise ValueError("audit run output declaration limit exceeded")
        files = {}
        for name, expected_hash in sorted(output_hashes.items()):
            if not _safe_filename(name) or not _sha256_string(expected_hash):
                raise ValueError("audit run output hash declaration is invalid")
            remaining_bytes = _MAX_TOTAL_INPUT_BYTES - total_bytes
            file_limit = min(_MAX_OUTPUT_FILE_BYTES, remaining_bytes)
            content = _read_regular_file(
                directory_fd,
                name,
                file_limit,
                (
                    "audit run outputs exceed total byte limit"
                    if remaining_bytes < _MAX_OUTPUT_FILE_BYTES
                    else "audit run output exceeds file byte limit"
                ),
            )
            total_bytes += len(content)
            if hashlib.sha256(content).hexdigest() != expected_hash:
                raise ValueError(f"audit run output hash mismatch: {name}")
            files[name] = content
    finally:
        os.close(directory_fd)
    if any(name not in files for name in _REQUIRED_FILES):
        raise ValueError("audit run is missing required interchange evidence")
    return run, files


def _build_ro_crate(run: Mapping[str, Any], files: Mapping[str, bytes]) -> Dict[str, Any]:
    evidence = _parse_json_lines(files["evidence.jsonl"], "evidence")
    mainline = _parse_json_lines(files["mainline-map.jsonl"], "mainline map")
    project_intent = _parse_json_object(files["project-intent.json"], "project intent")
    run_id = run["run_id"]
    graph: List[Dict[str, Any]] = []
    root_id = "./"
    run_id_ref = "#audit-run"
    graph.append(
        {
            "@id": "ro-crate-metadata.json",
            "@type": ["CreativeWork"],
            "about": {"@id": root_id},
            "conformsTo": [{"@id": "https://w3id.org/ro/crate/1.1"}],
        }
    )
    graph.append(
        {
            "@id": root_id,
            "@type": ["Dataset"],
            "conformsTo": [{"@id": _EVIDENCE_PROFILE}],
            "name": "repo-curator read-only evidence export",
            "repo-curator:executionAuthorized": False,
            "repo-curator:exportSchemaVersion": RO_CRATE_EXPORT_SCHEMA_VERSION,
            "repo-curator:sourceRun": {"@id": run_id_ref},
        }
    )
    graph.append(
        {
            "@id": run_id_ref,
            "@type": ["CreativeWork"],
            "identifier": run_id,
            "repo-curator:executionMode": run["execution_mode"],
            "repo-curator:finalStatus": run["final_status"],
            "repo-curator:outputSha256": dict(sorted(run["output_file_hashes"].items())),
            "repo-curator:repositoryStateHash": run["repository_state_hash"],
            "repo-curator:warnings": list(run.get("warnings", [])),
        }
    )
    graph.append(
        {
            "@id": "#project-intent",
            "@type": ["CreativeWork"],
            "repo-curator:claimStatus": project_intent.get("status", "UNRESOLVED"),
            "repo-curator:counterEvidence": list(project_intent.get("counter_evidence_ids", [])),
            "repo-curator:confidence": "NOT_ASSIGNED",
            "repo-curator:limitations": list(project_intent.get("uncertainty", [])),
            "repo-curator:supportingEvidence": list(project_intent.get("supporting_evidence_ids", [])),
        }
    )
    for record in sorted(evidence, key=lambda item: item["evidence_id"]):
        graph.append(
            {
                "@id": f"#evidence/{record['evidence_id']}",
                "@type": ["CreativeWork"],
                "conformsTo": list(record.get("conforms_to", [_EVIDENCE_PROFILE])),
                "identifier": record["evidence_id"],
                "repo-curator:assertionOrigin": record.get("assertion_origin", "OBSERVED"),
                "repo-curator:confidence": "NOT_ASSIGNED",
                "repo-curator:counterEvidence": list(record.get("counter_evidence_ids", [])),
                "repo-curator:extractor": record.get("extractor"),
                "repo-curator:limitations": list(record.get("limitations", [])),
                "repo-curator:scope": record.get("scope"),
                "repo-curator:source": record.get("source"),
                "repo-curator:subject": record.get("subject"),
            }
        )
    for record in sorted(mainline, key=lambda item: item["mainline_id"]):
        graph.append(
            {
                "@id": f"#mainline/{record['mainline_id']}",
                "@type": ["CreativeWork"],
                "identifier": record["mainline_id"],
                "repo-curator:claimStatus": record.get("status", "UNRESOLVED"),
                "repo-curator:confidence": "NOT_ASSIGNED",
                "repo-curator:counterEvidence": list(record.get("counter_evidence_ids", [])),
                "repo-curator:limitations": list(record.get("uncertainty", [])),
                "repo-curator:repositoryRelativePath": record.get("repository_relative_path"),
                "repo-curator:supportingEvidence": list(record.get("supporting_evidence_ids", [])),
            }
        )
    graph[1]["hasPart"] = [
        {"@id": item["@id"]}
        for item in graph[2:]
    ]
    return {
        "@context": [_RO_CRATE_CONTEXT, {"repo-curator": _REPO_CURATOR_NAMESPACE}],
        "@graph": graph,
    }


def _write_new_json(output: Path, document: Mapping[str, Any]) -> None:
    if not output.is_absolute():
        raise ValueError("RO-Crate output path must be absolute")
    if not output.name or output.name in {".", ".."}:
        raise ValueError("RO-Crate output filename is invalid")
    encoded = (json.dumps(document, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    resolved_parent = output.parent.resolve(strict=False)
    parent_fd = _open_or_create_absolute_directory(resolved_parent)
    try:
        descriptor = os.open(
            output.name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
            0o600,
            dir_fd=parent_fd,
        )
        try:
            _write_all(descriptor, encoded)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.fsync(parent_fd)
        named_parent = os.stat(resolved_parent, follow_symlinks=False)
        opened_parent = os.fstat(parent_fd)
        if (named_parent.st_dev, named_parent.st_ino) != (
            opened_parent.st_dev,
            opened_parent.st_ino,
        ):
            raise ValueError("RO-Crate output parent changed during publication")
    finally:
        os.close(parent_fd)


def _open_or_create_absolute_directory(directory: Path) -> int:
    if not directory.is_absolute():
        raise ValueError("RO-Crate output parent must be absolute")
    parts = directory.parts
    if not parts or parts[0] != os.sep or ".." in parts:
        raise ValueError("RO-Crate output parent is invalid")
    current_fd = os.open(os.sep, _directory_flags())
    try:
        for component in parts[1:]:
            if component in {"", "."}:
                continue
            try:
                os.mkdir(component, mode=0o700, dir_fd=current_fd)
            except FileExistsError:
                pass
            next_fd = os.open(component, _directory_flags(), dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except BaseException:
        os.close(current_fd)
        raise


def _write_all(descriptor: int, content: bytes) -> None:
    remaining = memoryview(content)
    while remaining:
        written = os.write(descriptor, remaining)
        if written <= 0:
            raise OSError(errno.EIO, "RO-Crate output write made no progress")
        remaining = remaining[written:]


def _read_regular_file(
    parent_fd: int, name: str, maximum_bytes: int, limit_error: str
) -> bytes:
    try:
        descriptor = os.open(name, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=parent_fd)
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ValueError(f"audit run output is a symbolic link: {name}") from error
        raise
    try:
        result = os.fstat(descriptor)
        if not stat.S_ISREG(result.st_mode):
            raise ValueError(f"audit run output is not a regular file: {name}")
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


def _directory_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


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


def _parse_json_lines(content: bytes, label: str) -> Sequence[Dict[str, Any]]:
    if not content:
        return []
    record_count = content.count(b"\n") + (0 if content.endswith(b"\n") else 1)
    if record_count > _MAX_JSONL_RECORDS:
        raise ValueError(f"{label} exceeds entity limit")
    records = []
    for line in content.splitlines():
        records.append(_parse_json_object(line, label))
    return records


def _reject_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON constant: {value}")
