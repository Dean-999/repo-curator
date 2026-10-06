"""Bounded, read-only advanced observations for shadow review.

This module deliberately uses lexical observations instead of upstream tool
runtimes. It never evaluates YAML, executes commands, follows links, or
resolves remote references. The feature is opt-in while the contracts are
calibrated against the evaluation corpus.
"""

from __future__ import annotations

import ast
import os
import re
import stat
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SEMANTIC_OBSERVATION_SCHEMA_VERSION = "repo-curator.semantic-adapter-observation.v1"
NEAR_DUPLICATE_SCHEMA_VERSION = "repo-curator.near-duplicate-candidate.v1"
COVERAGE_SCHEMA_VERSION = "repo-curator.evidence-coverage.v1"

MAX_ADAPTER_BYTES = 1_048_576
MAX_ADAPTER_RECORDS = 256
MAX_NEAR_DUPLICATE_FILES = 256
MAX_NEAR_DUPLICATE_BYTES = 16 * 1024 * 1024
TEXT_SUFFIXES = {".csv", ".json", ".md", ".py", ".rst", ".txt", ".yaml", ".yml"}
_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[^\sA-Za-z0-9_]", re.UNICODE)
_STAGE_RE = re.compile(r"^\s{2}([A-Za-z0-9_.-]+):\s*(?:#.*)?$")
_FIELD_RE = re.compile(r"^\s{4}(cmd|deps|outs|params|metrics):(?:\s|$)")
_SAFE_MANIFEST_PATH = re.compile(r"^[^/][^\r\n]*$")


def observe_semantic_adapters(
    root_fd: int,
    inventory_records: Sequence[Mapping[str, Any]],
    run_id: str,
    created_at: str,
) -> List[Dict[str, Any]]:
    """Return bounded semantic observations for local declaration families."""
    by_path = {record["repository_relative_path"]: record for record in inventory_records}
    observations: List[Dict[str, Any]] = []
    observations.extend(_observe_dvc(root_fd, by_path, run_id, created_at))
    observations.extend(_observe_mlflow(root_fd, by_path, run_id, created_at))
    observations.extend(_observe_datalad(root_fd, by_path, run_id, created_at))
    observations.extend(_observe_bagit(root_fd, by_path, run_id, created_at))
    return sorted(observations, key=lambda item: item["observation_id"])


def find_near_duplicate_candidates(
    root_fd: int,
    inventory_records: Sequence[Mapping[str, Any]],
    run_id: str,
    created_at: str,
) -> List[Dict[str, Any]]:
    """Find text candidates using bounded token-shingle similarity.

    This is a review signal only.  It cannot authorize merge, archive, or
    deletion and intentionally excludes exact-byte duplicates.
    """
    eligible = [
        record
        for record in inventory_records
        if record.get("object_type") == "REGULAR_FILE"
        and _suffix(record["repository_relative_path"]) in TEXT_SUFFIXES
        and isinstance(record.get("size_bytes"), int)
        and record["size_bytes"] <= MAX_ADAPTER_BYTES
    ]
    eligible = sorted(eligible, key=lambda item: item["repository_relative_path"].encode("utf-8", "surrogateescape"))
    payloads: Dict[str, Tuple[Mapping[str, Any], bytes]] = {}
    total = 0
    for record in eligible[:MAX_NEAR_DUPLICATE_FILES]:
        if total + record["size_bytes"] > MAX_NEAR_DUPLICATE_BYTES:
            break
        payload = _read_inventory_file(root_fd, record)
        if payload is None:
            continue
        total += len(payload)
        payloads[record["artifact_id"]] = (record, payload)

    buckets: Dict[Tuple[str, int], List[Tuple[Mapping[str, Any], bytes]]] = defaultdict(list)
    for record, payload in payloads.values():
        buckets[(_suffix(record["repository_relative_path"]), _size_bucket(len(payload)))].append((record, payload))

    candidates: List[Dict[str, Any]] = []
    for bucket in buckets.values():
        for index, (left, left_payload) in enumerate(bucket):
            left_tokens = _normalized_tokens(left_payload)
            if len(left_tokens) < 3:
                continue
            for right, right_payload in bucket[index + 1 :]:
                if left.get("content_id") == right.get("content_id"):
                    continue
                right_tokens = _normalized_tokens(right_payload)
                similarity = _jaccard(left_tokens, right_tokens)
                if similarity < 0.70:
                    continue
                confirmation = _confirmation(left, left_payload, right, right_payload)
                candidate_number = len(candidates) + 1
                content_ids = [
                    content_id
                    for content_id in (left.get("content_id"), right.get("content_id"))
                    if isinstance(content_id, str)
                ]
                candidates.append(
                    {
                        "candidate_id": f"near_duplicate_{run_id}_{candidate_number:08d}",
                        "candidate_type": "NEAR_DUPLICATE_CANDIDATE",
                        "confirmation_status": confirmation,
                        "content_ids": sorted(content_ids),
                        "created_at": created_at,
                        "executable_in_supported_scope": False,
                        "fingerprint_method": "normalized-token-jaccard-v1",
                        "limitations": [
                            "SIMILARITY_DOES_NOT_ESTABLISH_COMMON_PURPOSE",
                            "REVIEW_ONLY_NO_MUTATION_AUTHORITY",
                        ],
                        "normalization": "unicode-casefold-tokenization-without-values",
                        "repository_relative_paths": sorted(
                            [left["repository_relative_path"], right["repository_relative_path"]]
                        ),
                        "run_id": run_id,
                        "schema_version": NEAR_DUPLICATE_SCHEMA_VERSION,
                        "similarity": round(similarity, 6),
                        "supporting_evidence_ids": [],
                        "counter_evidence_ids": [],
                        "review_required": True,
                    }
                )
    return candidates


def build_evidence_coverage(
    classifications: Sequence[Mapping[str, Any]],
    recommendations: Sequence[Mapping[str, Any]],
    near_duplicates: Sequence[Mapping[str, Any]],
    run_id: str,
    created_at: str,
) -> List[Dict[str, Any]]:
    """Build an explicit support/counter/missing-evidence matrix."""
    records: List[Dict[str, Any]] = []
    for classification in classifications:
        support = sorted(set(classification.get("supporting_evidence_ids", [])))
        counter = sorted(set(classification.get("counter_evidence_ids", [])))
        limitations = sorted(set(classification.get("limitations", [])))
        status = "SUPPORTED" if support and not counter and not limitations else "PARTIAL"
        if not support:
            status = "UNSUPPORTED"
        records.append(
            {
                "claim_id": classification["classification_id"],
                "claim_kind": "CLASSIFICATION",
                "counter_evidence_ids": counter,
                "created_at": created_at,
                "decision_impact": "REVIEW_ONLY",
                "missing_evidence_classes": ["SEMANTIC_CONFIRMATION"] if not support else [],
                "observed_evidence_classes": ["INVENTORY"] if support else [],
                "required_evidence_classes": ["INVENTORY", "SEMANTIC_CONFIRMATION"],
                "limitations": limitations,
                "run_id": run_id,
                "schema_version": COVERAGE_SCHEMA_VERSION,
                "status": status,
                "supporting_evidence_ids": support,
                "scope": classification.get("repository_relative_path"),
            }
        )
    for recommendation in recommendations:
        support = sorted(set(recommendation.get("supporting_evidence_ids", [])))
        counter = sorted(set(recommendation.get("counter_evidence_ids", [])))
        records.append(
            {
                "claim_id": recommendation["recommendation_id"],
                "claim_kind": "RECOMMENDATION",
                "counter_evidence_ids": counter,
                "created_at": created_at,
                "decision_impact": "NO_EXECUTION_AUTHORITY",
                "missing_evidence_classes": ["USER_REVIEW"],
                "observed_evidence_classes": ["RECOMMENDATION_INPUT"] if support else [],
                "required_evidence_classes": ["RECOMMENDATION_INPUT", "USER_REVIEW"],
                "limitations": sorted(set(recommendation.get("limitations", []))),
                "run_id": run_id,
                "schema_version": COVERAGE_SCHEMA_VERSION,
                "status": "REVIEW_REQUIRED",
                "supporting_evidence_ids": support,
                "scope": recommendation.get("repository_relative_paths", []),
            }
        )
    for candidate in near_duplicates:
        records.append(
            {
                "claim_id": candidate["candidate_id"],
                "claim_kind": "NEAR_DUPLICATE_CANDIDATE",
                "counter_evidence_ids": list(candidate.get("counter_evidence_ids", [])),
                "created_at": created_at,
                "decision_impact": "REVIEW_ONLY",
                "missing_evidence_classes": ["PURPOSE", "LINEAGE", "USER_REVIEW"],
                "observed_evidence_classes": ["CONTENT_SIMILARITY"],
                "required_evidence_classes": ["CONTENT_SIMILARITY", "PURPOSE", "LINEAGE", "USER_REVIEW"],
                "limitations": list(candidate.get("limitations", [])),
                "run_id": run_id,
                "schema_version": COVERAGE_SCHEMA_VERSION,
                "status": "REVIEW_REQUIRED",
                "supporting_evidence_ids": list(candidate.get("supporting_evidence_ids", [])),
                "scope": candidate.get("repository_relative_paths", []),
            }
        )
    return sorted(records, key=lambda item: (item["claim_kind"], item["claim_id"]))


def _observe_dvc(root_fd: int, records: Mapping[str, Mapping[str, Any]], run_id: str, created_at: str) -> List[Dict[str, Any]]:
    record = records.get("dvc.yaml")
    if record is None:
        return []
    payload = _read_inventory_file(root_fd, record)
    limitations = ["DVC_COMMANDS_NOT_EXECUTED", "DVC_YAML_LEXICAL_ONLY"]
    details: Dict[str, Any] = {"stage_count": 0, "stages": []}
    if payload is None:
        limitations.append("ADAPTER_PAYLOAD_UNAVAILABLE")
        status = "UNAVAILABLE"
    else:
        try:
            text = payload.decode("utf-8")
            in_stages = False
            current: Optional[Dict[str, Any]] = None
            for line in text.splitlines():
                if line.strip() == "stages:":
                    in_stages = True
                    continue
                if in_stages and line and not line[0].isspace():
                    break
                if in_stages:
                    match = _STAGE_RE.match(line)
                    if match:
                        current = {"name": match.group(1), "declared_fields": []}
                        details["stages"].append(current)
                    elif current is not None:
                        field = _FIELD_RE.match(line)
                        if field and field.group(1) not in current["declared_fields"]:
                            current["declared_fields"].append(field.group(1))
            details["stage_count"] = len(details["stages"])
            status = "OBSERVED"
        except UnicodeDecodeError:
            limitations.append("ADAPTER_PAYLOAD_NOT_UTF8")
            status = "MALFORMED"
    return [_semantic_record("DVC", record, details, limitations, status, run_id, created_at)]


def _observe_mlflow(root_fd: int, records: Mapping[str, Mapping[str, Any]], run_id: str, created_at: str) -> List[Dict[str, Any]]:
    mlflow_records = [record for path, record in records.items() if path.startswith("mlruns/")]
    if not mlflow_records:
        return []
    run_dirs = set()
    params = 0
    metrics = 0
    artifacts = 0
    for record in mlflow_records[:MAX_ADAPTER_RECORDS]:
        path = record["repository_relative_path"]
        parts = path.split("/")
        if len(parts) >= 3 and parts[1] != ".trash":
            run_dirs.add("/".join(parts[:3]))
        if "/params/" in f"/{path}":
            params += 1
        elif "/metrics/" in f"/{path}":
            metrics += 1
        elif "/artifacts/" in f"/{path}":
            artifacts += 1
    limitations = ["MLFLOW_METADATA_KEYS_ONLY", "MLFLOW_PROJECT_NOT_EXECUTED"]
    if len(mlflow_records) > MAX_ADAPTER_RECORDS:
        limitations.append("ADAPTER_RECORD_LIMIT")
    source = next((record for record in mlflow_records if record["repository_relative_path"].endswith("meta.yaml")), mlflow_records[0])
    return [_semantic_record(
        "MLFLOW",
        source,
        {"run_count": len(run_dirs), "parameter_file_count": params, "metric_file_count": metrics, "artifact_entry_count": artifacts},
        limitations,
        "OBSERVED",
        run_id,
        created_at,
    )]


def _observe_datalad(root_fd: int, records: Mapping[str, Mapping[str, Any]], run_id: str, created_at: str) -> List[Dict[str, Any]]:
    source = records.get(".datalad/config")
    if source is None:
        return []
    payload = _read_inventory_file(root_fd, source)
    limitations = ["DATALAD_OPERATIONS_NOT_EXECUTED", "GIT_ANNEX_CONTENT_NOT_RETRIEVED"]
    key_count = 0
    if payload is None:
        status = "UNAVAILABLE"
        limitations.append("ADAPTER_PAYLOAD_UNAVAILABLE")
    else:
        try:
            key_count = sum(1 for line in payload.decode("utf-8").splitlines() if "=" in line and not line.lstrip().startswith("#"))
            status = "OBSERVED"
        except UnicodeDecodeError:
            status = "MALFORMED"
            limitations.append("ADAPTER_PAYLOAD_NOT_UTF8")
    return [_semantic_record("DATALAD", source, {"config_key_count": key_count, "dataset_boundary": ".datalad"}, limitations, status, run_id, created_at)]


def _observe_bagit(root_fd: int, records: Mapping[str, Mapping[str, Any]], run_id: str, created_at: str) -> List[Dict[str, Any]]:
    source = records.get("bagit.txt")
    if source is None:
        return []
    payload = _read_inventory_file(root_fd, source)
    limitations = ["BAGIT_FETCH_NOT_EXECUTED", "BAGIT_MANIFEST_SCOPE_LOCAL_ONLY"]
    details: Dict[str, Any] = {"manifest_algorithms": [], "manifest_entry_count": 0, "fixity_status": "UNAVAILABLE"}
    if payload is None:
        status = "UNAVAILABLE"
        limitations.append("ADAPTER_PAYLOAD_UNAVAILABLE")
    else:
        try:
            text = payload.decode("utf-8")
            details["bagit_version_declared"] = any(line.startswith("BagIt-Version:") for line in text.splitlines())
            manifest_records = [(path, record) for path, record in records.items() if path.startswith("manifest-") and path.endswith(".txt")]
            details["manifest_algorithms"] = sorted({path[len("manifest-") : -4] for path, _ in manifest_records})
            details["manifest_entry_count"] = sum(_manifest_entry_count(root_fd, record) for _, record in manifest_records)
            details["fixity_status"] = "DECLARED_MANIFEST_PRESENT" if manifest_records else "MANIFEST_UNAVAILABLE"
            status = "OBSERVED"
        except UnicodeDecodeError:
            status = "MALFORMED"
            limitations.append("ADAPTER_PAYLOAD_NOT_UTF8")
    return [_semantic_record("BAGIT", source, details, limitations, status, run_id, created_at)]


def _manifest_entry_count(root_fd: int, record: Mapping[str, Any]) -> int:
    payload = _read_inventory_file(root_fd, record)
    if payload is None:
        return 0
    count = 0
    for line in payload.decode("utf-8", errors="replace").splitlines():
        if not line.strip() or "  " not in line:
            continue
        digest, path = line.split(None, 1)
        if (
            len(digest) >= 16
            and _SAFE_MANIFEST_PATH.match(path.strip())
            and all(part not in {"", ".", ".."} for part in path.strip().split("/"))
        ):
            count += 1
    return count


def _semantic_record(family: str, source: Mapping[str, Any], details: Mapping[str, Any], limitations: Iterable[str], status: str, run_id: str, created_at: str) -> Dict[str, Any]:
    schema_by_family = {
        "DVC": "repo-curator.dvc-observation.v1",
        "MLFLOW": "repo-curator.mlflow-observation.v1",
        "DATALAD": "repo-curator.datalad-observation.v1",
        "BAGIT": "repo-curator.bagit-observation.v1",
    }
    return {
        "adapter_id": family.casefold(),
        "assertion_origin": "OBSERVED",
        "coverage": "BOUNDED_SEMANTIC_OBSERVATION",
        "created_at": created_at,
        "declaration_family": family,
        "details": dict(details),
        "limitations": sorted(set(limitations)),
        "observation_id": f"semantic_{run_id}_{family.casefold()}",
        "schema_version": schema_by_family.get(family, SEMANTIC_OBSERVATION_SCHEMA_VERSION),
        "source_artifact_id": source["artifact_id"],
        "source_location_id": source["location_id"],
        "source_path": source["repository_relative_path"],
        "status": status,
        "run_id": run_id,
    }


def _confirmation(left: Mapping[str, Any], left_payload: bytes, right: Mapping[str, Any], right_payload: bytes) -> str:
    if _suffix(left["repository_relative_path"]) == ".py":
        try:
            left_tree = ast.dump(ast.parse(left_payload.decode("utf-8")), annotate_fields=False)
            right_tree = ast.dump(ast.parse(right_payload.decode("utf-8")), annotate_fields=False)
            return "STRUCTURALLY_SIMILAR" if left_tree == right_tree else "TEXTUALLY_SIMILAR"
        except (SyntaxError, UnicodeDecodeError, ValueError):
            return "TEXTUALLY_SIMILAR"
    return "TEXTUALLY_SIMILAR"


def _normalized_tokens(payload: bytes) -> set[str]:
    text = payload.decode("utf-8", errors="replace").casefold()
    tokens = _TOKEN_RE.findall(text)
    return {token for token in tokens if token.strip()}


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _read_inventory_file(root_fd: int, record: Mapping[str, Any]) -> Optional[bytes]:
    path = record.get("repository_relative_path")
    if not isinstance(path, str) or not path or any(part in {"", ".", ".."} for part in path.split("/")):
        return None
    descriptor = os.dup(root_fd)
    try:
        components = path.split("/")
        for component in components[:-1]:
            next_descriptor = os.open(component, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        file_descriptor = os.open(components[-1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=descriptor)
    except (OSError, ValueError):
        os.close(descriptor)
        return None
    finally:
        if descriptor is not None:
            try:
                os.close(descriptor)
            except OSError:
                pass
    try:
        before = os.fstat(file_descriptor)
        if not stat.S_ISREG(before.st_mode):
            return None
        if not _matches_inventory(before, record):
            return None
        chunks = []
        remaining = MAX_ADAPTER_BYTES + 1
        while remaining:
            chunk = os.read(file_descriptor, min(131_072, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        after = os.fstat(file_descriptor)
        if not _matches_inventory(after, record):
            return None
        return payload if len(payload) <= MAX_ADAPTER_BYTES else None
    except OSError:
        return None
    finally:
        os.close(file_descriptor)


def _matches_inventory(observed: os.stat_result, record: Mapping[str, Any]) -> bool:
    expected_size = record.get("size_bytes")
    expected_mode = record.get("mode")
    expected_mtime = record.get("mtime_ns")
    return (
        stat.S_ISREG(observed.st_mode)
        and isinstance(expected_size, int)
        and observed.st_size == expected_size
        and (expected_mode is None or observed.st_mode & 0o7777 == expected_mode)
        and (expected_mtime is None or observed.st_mtime_ns == expected_mtime)
    )


def _suffix(path: str) -> str:
    return os.path.splitext(path.casefold())[1]


def _size_bucket(size: int) -> int:
    return max(0, size.bit_length() // 2)
