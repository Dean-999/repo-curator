"""Declared document comparison and non-destructive entry-point proposals."""

import json
import os
import stat
from itertools import combinations
from typing import Any, Dict, List, Sequence, Tuple


COMPARISON_SCHEMA_VERSION = "repo-curator.document-comparison.v1"
ENTRY_SCHEMA_VERSION = "repo-curator.canonical-entry-point.v1"
MANIFEST_NAME = "document-manifest.json"
_READ_LIMIT = 1024 * 1024


def compare_documents(
    root_fd: int, inventory_records: Sequence[Dict[str, Any]], run_id: str, created_at: str
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[str]]:
    inventory = {record["repository_relative_path"]: record for record in inventory_records}
    if MANIFEST_NAME not in inventory:
        return [], [], []
    try:
        manifest = _read_manifest(root_fd)
    except ValueError as error:
        return [], [], [str(error)]
    raw_documents = manifest.get("documents")
    if not isinstance(raw_documents, list):
        return [], [], ["DOCUMENT_MANIFEST_MALFORMED"]
    documents = [
        item for item in raw_documents
        if isinstance(item, dict) and isinstance(item.get("path"), str) and item["path"] in inventory
        and isinstance(item.get("topic"), str) and item["topic"]
    ]
    return _comparisons(documents, inventory, run_id, created_at), _entries(documents, inventory, run_id, created_at), []


def _comparisons(documents: List[Dict[str, Any]], inventory: Dict[str, Dict[str, Any]], run_id: str, created_at: str) -> List[Dict[str, Any]]:
    by_topic: Dict[str, List[Dict[str, Any]]] = {}
    for document in documents:
        by_topic.setdefault(document["topic"], []).append(document)
    records = []
    for topic, group in sorted(by_topic.items()):
        for left, right in combinations(sorted(group, key=lambda item: item["path"]), 2):
            conflicts = _conflicting_fields(left, right)
            subtype = "DO_NOT_MERGE" if conflicts else _subtype(left, right)
            records.append({
                "candidate_subtype": subtype, "conflicting_fields": conflicts,
                "counter_evidence_ids": [inventory[left["path"]]["artifact_id"], inventory[right["path"]]["artifact_id"]] if conflicts else [],
                "created_at": created_at, "document_comparison_id": f"document_comparison_{run_id}_{len(records) + 1:08d}",
                "document_paths": [left["path"], right["path"]], "executable_in_supported_scope": False,
                "human_review_required": True,
                "limitations": ["DECLARED_DOCUMENT_METADATA_ONLY"], "run_id": run_id,
                "schema_version": COMPARISON_SCHEMA_VERSION,
                "supporting_evidence_ids": [inventory[left["path"]]["artifact_id"], inventory[right["path"]]["artifact_id"]],
                "topic": topic,
            })
    return records


def _conflicting_fields(left: Dict[str, Any], right: Dict[str, Any]) -> List[str]:
    return [field for field in ("claim", "value", "status") if left.get(field) is not None and right.get(field) is not None and left[field] != right[field]]


def _subtype(left: Dict[str, Any], right: Dict[str, Any]) -> str:
    if left.get("audience") != right.get("audience") or left.get("role") in {"DECISION_RECORD", "AUDIT_RECORD"} or right.get("role") in {"DECISION_RECORD", "AUDIT_RECORD"}:
        return "CANONICALIZE_WITHOUT_MERGE"
    if left.get("lifecycle") != right.get("lifecycle"):
        return "PARTIAL_MERGE_CANDIDATE"
    return "MANUAL_REVIEW"


def _entries(documents: List[Dict[str, Any]], inventory: Dict[str, Dict[str, Any]], run_id: str, created_at: str) -> List[Dict[str, Any]]:
    entries = [document for document in documents if document.get("canonical_entry") is True]
    records = []
    retained = sorted(document["path"] for document in documents)
    for entry in sorted(entries, key=lambda item: item["path"]):
        records.append({
            "counter_evidence_ids": [], "created_at": created_at,
            "entry_point_id": f"canonical_entry_{run_id}_{len(records) + 1:08d}",
            "entry_point_path": entry["path"], "executable_in_supported_scope": False,
            "human_review_required": True, "limitations": ["DECLARED_ENTRY_POINT_NOT_AUTOMATIC_CANONICALIZATION"],
            "modifies_originals": False, "retained_record_paths": [path for path in retained if path != entry["path"]],
            "run_id": run_id, "schema_version": ENTRY_SCHEMA_VERSION,
            "supporting_evidence_ids": [inventory[entry["path"]]["artifact_id"]],
        })
    return records


def _read_manifest(root_fd: int) -> Dict[str, Any]:
    descriptor = os.open(MANIFEST_NAME, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=root_fd)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("DOCUMENT_MANIFEST_UNAVAILABLE")
        payload = os.read(descriptor, _READ_LIMIT + 1)
    finally:
        os.close(descriptor)
    if len(payload) > _READ_LIMIT:
        raise ValueError("DOCUMENT_MANIFEST_SIZE_LIMIT")
    try:
        result = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise ValueError("DOCUMENT_MANIFEST_MALFORMED")
    if not isinstance(result, dict):
        raise ValueError("DOCUMENT_MANIFEST_MALFORMED")
    return result
