"""Read-only recognition of supported research metadata declarations."""

import hashlib
import json
import os
import re
import stat
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from repo_curator.data_package import observe_data_package
from repo_curator.environment_declarations import environment_declaration_candidate
from repo_curator.research_metadata import (
    CITATION_CFF,
    CODEMETA_JSON,
    observe_codemeta,
    signac_candidate,
)
from repo_curator.ro_crate_graph import observe_ro_crate_graph


OBSERVATION_SCHEMA_VERSION = "repo-curator.adapter-observation.v1"
JSON_VALIDATION_LIMIT_BYTES = 1024 * 1024
RO_CRATE_DECLARATION_TOKEN_LIMIT = 64
DVC_LOCK_SCAN_LIMIT_BYTES = 1024 * 1024
_DVC_LOCK_STAGE_KEY = re.compile(r"^  [^ #][^:]*:\s*(?:#.*)?$")
# These markers are intentionally only enough to establish that a tool's
# declaration exists.  Parsing YAML, launching the corresponding workflow, or
# resolving its references would expand this adapter's authority.
DECLARATION_RULES = {
    "CITATION_CFF": (CITATION_CFF,),
    "CODEMETA": (CODEMETA_JSON,),
    "DATA_PACKAGE": ("datapackage.json",),
    "DVC": ("dvc.yaml", "dvc.lock", ".dvc/config"),
    "DATALAD": (".datalad/config",),
    "MLFLOW": ("MLproject",),
    "RO_CRATE": ("ro-crate-metadata.json",),
    "BAGIT": ("bagit.txt",),
    "SNAKEMAKE": ("Snakefile", "workflow/Snakefile"),
    "NEXTFLOW": ("nextflow.config", "main.nf"),
    "RENKU": (".renku",),
    "SHOWYOURWORK": ("showyourwork.yml",),
    "SIGNAC": (".signac/config",),
    "NOWORKFLOW": (".noworkflow",),
}
DECLARATION_SOURCE_LOCK_IDS = {
    "BAGIT": "bagit-python",
    "COMPUTATIONAL_ENVIRONMENT": "repo2docker",
    "CITATION_CFF": "citation-file-format",
    "CODEMETA": "codemeta",
    "DATA_PACKAGE": "frictionless-py",
    "DATALAD": "datalad",
    "DVC": "dvc",
    "MLFLOW": "mlflow",
    "NEXTFLOW": "nextflow",
    "NOWORKFLOW": "noworkflow",
    "RENKU": "renku-python",
    "RO_CRATE": "ro-crate-py",
    "SACRED": "sacred",
    "SHOWYOURWORK": "showyourwork",
    "SIGNAC": "signac",
    "SNAKEMAKE": "snakemake",
    "WORKFLOW_RUN_RO_CRATE": "ro-crate-py",
}
SYNTAX_LIMITATIONS = (
    "DECLARATION_INTERNAL_REFERENCES_NOT_VALIDATED",
    "DECLARATION_PAYLOAD_AVAILABILITY_NOT_VALIDATED",
    "DECLARATION_REPRODUCTION_NOT_VALIDATED",
    "DECLARATION_SCHEMA_NOT_VALIDATED",
    "DECLARATION_SEMANTICS_NOT_VALIDATED",
)


def detect_declarations(
    root_fd: int, inventory_records: List[Dict[str, Any]], run_id: str, created_at: str
) -> List[Dict[str, Any]]:
    """Return typed observations without importing or launching an upstream tool."""
    all_records = {
        record["repository_relative_path"]: record for record in inventory_records
    }
    regular_files = {
        record["repository_relative_path"]: record
        for record in inventory_records
        if record["object_type"] == "REGULAR_FILE"
    }
    candidates = []
    for family in DECLARATION_RULES:
        if family in {"DATA_PACKAGE", "SIGNAC"}:
            continue
        markers = _marker_records(family, all_records)
        if markers:
            source_record = markers[0]
            validation_records = tuple(
                record for record in markers if record["object_type"] == "REGULAR_FILE"
            )
            candidates.append((family, source_record, validation_records, (), markers, {}))
    candidates.extend(
        (*candidate, candidate[2], {}) for candidate in _sacred_candidates(regular_files)
    )
    signac = signac_candidate(all_records)
    if signac is not None:
        source_record, marker_records, limitations, details = signac
        candidates.append(
            ("SIGNAC", source_record, (), limitations, marker_records, details)
        )
    candidates.extend(
        (
            "DATA_PACKAGE",
            record,
            (record,),
            (),
            (record,),
            {},
        )
        for record in sorted(
            (
                record
                for path, record in regular_files.items()
                if _basename(path) == "datapackage.json"
            ),
            key=_path_bytes,
        )
    )
    environment_candidate = environment_declaration_candidate(all_records)
    if environment_candidate is not None:
        source_record, marker_records, limitations, details = environment_candidate
        candidates.append(
            (
                "COMPUTATIONAL_ENVIRONMENT",
                source_record,
                (),
                limitations,
                marker_records,
                details,
            )
        )

    observations = []
    sequence = 0
    for (
        family,
        source_record,
        validation_records,
        base_limitations,
        marker_records,
        candidate_details,
    ) in sorted(candidates, key=lambda candidate: (_path_bytes(candidate[1]), candidate[0])):
        status, validation_status, limitations, details = _validation_result(
            root_fd, family, validation_records, base_limitations, all_records
        )
        sequence += 1
        observation = {
            "coverage": "DECLARATION_PRESENCE_ONLY",
            "created_at": created_at,
            "declaration_family": family,
            "limitations": limitations,
            "marker_artifact_ids": [record["artifact_id"] for record in marker_records],
            "marker_paths": [record["repository_relative_path"] for record in marker_records],
            "observation_id": f"obs_{run_id}_{sequence:08d}",
            "run_id": run_id,
            "schema_version": OBSERVATION_SCHEMA_VERSION,
            "source_artifact_id": source_record["artifact_id"],
            "source_location_id": source_record["location_id"],
            "status": status,
            "validation_status": validation_status,
            **candidate_details,
            **details,
        }
        observations.append(observation)
        if family == "RO_CRATE" and details.get("workflow_run_ro_crate_declared"):
            sequence += 1
            observations.append(
                {
                    **observation,
                    "declaration_family": "WORKFLOW_RUN_RO_CRATE",
                    "limitations": sorted(
                        set(observation["limitations"] + ["WORKFLOW_RUN_RO_CRATE_DECLARATION_ONLY"])
                    ),
                    "observation_id": f"obs_{run_id}_{sequence:08d}",
                    "source_observation_id": observation["observation_id"],
                }
            )
    return observations


def _marker_records(
    family: str, all_records: Dict[str, Dict[str, Any]]
) -> Tuple[Dict[str, Any], ...]:
    exact_paths = set(DECLARATION_RULES[family])
    matches = [
        record
        for path, record in all_records.items()
        if (
            (path in exact_paths or _matches_family_marker(family, path, record))
            and (
                family not in {"CITATION_CFF", "CODEMETA"}
                or record["object_type"] == "REGULAR_FILE"
            )
        )
    ]
    return tuple(sorted(matches, key=_path_bytes))


def _matches_family_marker(
    family: str, path: str, record: Dict[str, Any]
) -> bool:
    if family == "DVC":
        return record["object_type"] == "REGULAR_FILE" and path.endswith(".dvc")
    if family == "SNAKEMAKE":
        return record["object_type"] == "REGULAR_FILE" and _basename(path) == "Snakefile"
    if family == "MLFLOW":
        return "/" not in path and path.casefold() == "mlproject"
    if family == "NOWORKFLOW":
        return path.startswith(".noworkflow/")
    return False


def _sacred_candidates(
    regular_files: Dict[str, Dict[str, Any]],
) -> Iterable[Tuple[str, Dict[str, Any], Tuple[Dict[str, Any], ...], Tuple[str, ...]]]:
    directories = set()
    for path in regular_files:
        if _basename(path) in {"config.json", "run.json"}:
            directories.add(_parent(path))
    for directory in directories:
        config_path = _join(directory, "config.json")
        run_path = _join(directory, "run.json")
        config_record = regular_files.get(config_path)
        run_record = regular_files.get(run_path)
        if config_record is not None and run_record is not None:
            yield "SACRED", run_record, (config_record, run_record), ()
        elif config_record is not None:
            yield (
                "SACRED",
                config_record,
                (config_record,),
                ("DECLARATION_PARTIAL", "SACRED_RUN_JSON_MISSING"),
            )
        elif run_record is not None:
            yield (
                "SACRED",
                run_record,
                (run_record,),
                ("DECLARATION_PARTIAL", "SACRED_CONFIG_JSON_MISSING"),
            )


def _validation_result(
    root_fd: int,
    family: str,
    records: Sequence[Dict[str, Any]],
    base_limitations: Sequence[str],
    all_records: Dict[str, Dict[str, Any]],
) -> Tuple[str, str, List[str], Dict[str, Any]]:
    if family == "CITATION_CFF":
        return (
            "PRESENT",
            "NOT_APPLICABLE",
            [
                *base_limitations,
                "CITATION_CFF_CONTENT_NOT_PARSED",
                "CITATION_CFF_SCHEMA_NOT_VALIDATED",
            ],
            {},
        )
    if family not in {"RO_CRATE", "SACRED", "DVC", "DATA_PACKAGE", "CODEMETA"}:
        return "PRESENT", "NOT_APPLICABLE", list(base_limitations), {}
    if family == "DVC":
        details, lock_limitations = _dvc_lock_details(root_fd, records)
        return "PRESENT", "NOT_APPLICABLE", sorted(set(base_limitations) | set(lock_limitations)), details
    results = [_validate_json_declaration(root_fd, record) for record in records]
    limitations = set(base_limitations)
    for result, result_limitations, _ in results:
        limitations.update(result_limitations)
    result_values = {result for result, _, _ in results}
    if "MALFORMED" in result_values:
        status, validation_status = "MALFORMED", "MALFORMED"
    elif result_values & {"SIZE_LIMIT", "UNAVAILABLE", "CHANGED"}:
        status = "PRESENT_UNVALIDATED"
        validation_status = next(
            result
            for result in ("SIZE_LIMIT", "UNAVAILABLE", "CHANGED")
            if result in result_values
        )
    else:
        status, validation_status = "PRESENT", "SYNTAX_VALIDATED"
        limitations.update(SYNTAX_LIMITATIONS)
    if base_limitations:
        status = "PARTIAL"
    details = {}
    if family == "RO_CRATE":
        parsed = next(
            (payload for result, _, payload in results if result == "SYNTAX_VALIDATED"),
            None,
        )
        details, detail_limitations = _ro_crate_details(parsed)
        limitations.update(detail_limitations)
    elif family == "DATA_PACKAGE":
        parsed = next(
            (payload for result, _, payload in results if result == "SYNTAX_VALIDATED"),
            None,
        )
        descriptor_path = records[0]["repository_relative_path"] if records else ""
        details, detail_limitations = observe_data_package(
            parsed, descriptor_path, all_records
        )
        limitations.update(detail_limitations)
    elif family == "CODEMETA":
        valid_payloads = [
            payload for result, _, payload in results if result == "SYNTAX_VALIDATED"
        ]
        if valid_payloads:
            details, detail_limitations = observe_codemeta(valid_payloads[0])
            limitations.update(detail_limitations)
    return status, validation_status, sorted(limitations), details


def _validate_json_declaration(
    root_fd: int, record: Dict[str, Any]
) -> Tuple[str, Tuple[str, ...], Any]:
    if record["fingerprint_scheme"] is None or record["fingerprint"] is None:
        return "UNAVAILABLE", ("DECLARATION_VALIDATION_UNAVAILABLE",), None
    if record["size_bytes"] > JSON_VALIDATION_LIMIT_BYTES:
        return "SIZE_LIMIT", ("DECLARATION_VALIDATION_SIZE_LIMIT",), None
    try:
        descriptor = _open_regular_file(root_fd, record["repository_relative_path"])
    except (FileNotFoundError, PermissionError):
        return "UNAVAILABLE", ("DECLARATION_VALIDATION_UNAVAILABLE",), None
    except (OSError, ValueError):
        return "CHANGED", ("DECLARATION_CHANGED_DURING_VALIDATION",), None
    try:
        before = os.fstat(descriptor)
        if not _matches_inventory(before, record):
            return "CHANGED", ("DECLARATION_CHANGED_DURING_VALIDATION",), None
        payload = _read_at_most(descriptor, JSON_VALIDATION_LIMIT_BYTES + 1)
        after = os.fstat(descriptor)
    except (OSError, PermissionError):
        return "UNAVAILABLE", ("DECLARATION_VALIDATION_UNAVAILABLE",), None
    finally:
        os.close(descriptor)
    if len(payload) > JSON_VALIDATION_LIMIT_BYTES:
        return "SIZE_LIMIT", ("DECLARATION_VALIDATION_SIZE_LIMIT",), None
    if not _matches_inventory(after, record) or not _matches_fingerprint(payload, record):
        return "CHANGED", ("DECLARATION_CHANGED_DURING_VALIDATION",), None
    try:
        parsed = json.loads(payload.decode("utf-8"), parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError, RecursionError):
        return "MALFORMED", ("DECLARATION_MALFORMED",), None
    return "SYNTAX_VALIDATED", (), parsed


def _ro_crate_details(parsed: Any) -> Tuple[Dict[str, Any], Tuple[str, ...]]:
    if not isinstance(parsed, dict):
        return {}, ("RO_CRATE_ROOT_NOT_OBJECT",)
    profile_uris = _declared_string_values(parsed, "conformsTo")
    type_tokens = _declared_string_values(parsed, "@type")
    graph = parsed.get("@graph")
    if isinstance(graph, list):
        for item in graph:
            if isinstance(item, dict):
                profile_uris.extend(_declared_string_values(item, "conformsTo"))
                type_tokens.extend(_declared_string_values(item, "@type"))
    profiles, profile_limited = _bounded_tokens(profile_uris)
    types, type_limited = _bounded_tokens(type_tokens)
    workflow_declared = any(
        "workflow-ro-crate" in token.casefold() or "workflowruncrate" in token.casefold()
        for token in [*profiles, *types]
    )
    limitations = []
    if profile_limited or type_limited:
        limitations.append("RO_CRATE_DECLARATION_TOKEN_LIMIT")
    graph_details, graph_limitations = observe_ro_crate_graph(parsed)
    limitations.extend(graph_limitations)
    return {
        "declared_profile_uris": profiles,
        "declared_type_tokens": types,
        "ro_crate_graph": graph_details,
        "workflow_run_ro_crate_declared": workflow_declared,
    }, tuple(limitations)


def _declared_string_values(record: Dict[str, Any], key: str) -> List[str]:
    value = record.get(key)
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    if isinstance(value, dict):
        identifier = value.get("@id")
        return [identifier] if isinstance(identifier, str) else []
    return []


def _bounded_tokens(values: Iterable[str]) -> Tuple[List[str], bool]:
    tokens = sorted(set(values))
    return tokens[:RO_CRATE_DECLARATION_TOKEN_LIMIT], len(tokens) > RO_CRATE_DECLARATION_TOKEN_LIMIT


def _dvc_lock_details(
    root_fd: int, records: Sequence[Dict[str, Any]]
) -> Tuple[Dict[str, Any], Tuple[str, ...]]:
    record = next((item for item in records if item["repository_relative_path"] == "dvc.lock"), None)
    if record is None:
        return {}, ()
    if record["fingerprint_scheme"] is None or record["fingerprint"] is None:
        return {"dvc_lock_scan_status": "UNAVAILABLE"}, ("DVC_LOCK_SCAN_UNAVAILABLE",)
    if record["size_bytes"] > DVC_LOCK_SCAN_LIMIT_BYTES:
        return {"dvc_lock_scan_status": "SIZE_LIMIT"}, ("DVC_LOCK_SCAN_SIZE_LIMIT",)
    try:
        descriptor = _open_regular_file(root_fd, record["repository_relative_path"])
    except (FileNotFoundError, PermissionError):
        return {"dvc_lock_scan_status": "UNAVAILABLE"}, ("DVC_LOCK_SCAN_UNAVAILABLE",)
    except (OSError, ValueError):
        return {"dvc_lock_scan_status": "CHANGED"}, ("DVC_LOCK_CHANGED_DURING_SCAN",)
    try:
        before = os.fstat(descriptor)
        if not _matches_inventory(before, record):
            return {"dvc_lock_scan_status": "CHANGED"}, ("DVC_LOCK_CHANGED_DURING_SCAN",)
        payload = _read_at_most(descriptor, DVC_LOCK_SCAN_LIMIT_BYTES + 1)
        after = os.fstat(descriptor)
    except (OSError, PermissionError):
        return {"dvc_lock_scan_status": "UNAVAILABLE"}, ("DVC_LOCK_SCAN_UNAVAILABLE",)
    finally:
        os.close(descriptor)
    if len(payload) > DVC_LOCK_SCAN_LIMIT_BYTES:
        return {"dvc_lock_scan_status": "SIZE_LIMIT"}, ("DVC_LOCK_SCAN_SIZE_LIMIT",)
    if not _matches_inventory(after, record) or not _matches_fingerprint(payload, record):
        return {"dvc_lock_scan_status": "CHANGED"}, ("DVC_LOCK_CHANGED_DURING_SCAN",)
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return {"dvc_lock_scan_status": "MALFORMED"}, ("DVC_LOCK_NOT_UTF8",)
    return {
        "dvc_lock_scan_status": "LEXICAL_OBSERVED",
        "dvc_lock_stage_key_count": _dvc_lock_stage_key_count(text),
    }, ("DVC_LOCK_STAGE_KEYS_LEXICAL_ONLY",)


def _dvc_lock_stage_key_count(text: str) -> int:
    in_stages = False
    count = 0
    for line in text.splitlines():
        if not in_stages:
            in_stages = line == "stages:"
            continue
        if line and not line[0].isspace():
            break
        if _DVC_LOCK_STAGE_KEY.fullmatch(line):
            count += 1
    return count


def _matches_inventory(observed: os.stat_result, record: Dict[str, Any]) -> bool:
    return (
        stat.S_ISREG(observed.st_mode)
        and observed.st_size == record["size_bytes"]
        and (observed.st_mode & 0o7777) == record["mode"]
        and observed.st_mtime_ns == record["mtime_ns"]
    )


def _matches_fingerprint(payload: bytes, record: Dict[str, Any]) -> bool:
    return (
        record["fingerprint_scheme"] == "sha256-file-v1"
        and hashlib.sha256(payload).hexdigest() == record["fingerprint"]
    )


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")


def _open_regular_file(root_fd: int, path: str) -> int:
    components = path.split("/")
    if not path or any(component in {"", ".", ".."} for component in components):
        raise ValueError("invalid declaration path")
    directory_fd = os.dup(root_fd)
    try:
        for component in components[:-1]:
            next_fd = os.open(component, _directory_open_flags(), dir_fd=directory_fd)
            os.close(directory_fd)
            directory_fd = next_fd
        descriptor = os.open(
            components[-1],
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0),
            dir_fd=directory_fd,
        )
    finally:
        os.close(directory_fd)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise ValueError("declaration changed type during validation")
    return descriptor


def _directory_open_flags() -> int:
    return os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)


def _read_at_most(descriptor: int, limit: int) -> bytes:
    chunks = []
    remaining = limit
    while remaining:
        chunk = os.read(descriptor, remaining)
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _path_bytes(record: Dict[str, Any]) -> bytes:
    return record["repository_relative_path"].encode("utf-8", errors="surrogateescape")


def _basename(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _parent(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _join(parent: str, name: str) -> str:
    return f"{parent}/{name}" if parent else name
