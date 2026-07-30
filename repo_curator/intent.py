"""Bounded, read-only project intent discovery from repository text."""

import os
import re
import stat
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from repo_curator.evidence import EVIDENCE_PROFILE_URI


INTENT_SCHEMA_VERSION = "repo-curator.project-intent.v1"
RETENTION_SCHEMA_VERSION = "repo-curator.retention-policy.v1"
MAINLINE_SCHEMA_VERSION = "repo-curator.mainline-map.v1"
CONFLICT_SCHEMA_VERSION = "repo-curator.intent-conflict.v1"
_READ_LIMIT = 64 * 1024
_ENTRY_POINT = re.compile(
    r"(?im)^\s*(?:entry[ _-]?point|mainline|deploy(?:ment)?[ _-]?entry[ _-]?point)\s*:\s*([^\s]+)\s*$"
)
_RETENTION = re.compile(r"(?im)^\s*(retain|protect|keep|archive|historical|prototype)\s*:\s*([^\s]+)\s*$")
_COMPATIBILITY = re.compile(r"(?im)^\s*(?:retain[ _-]?)?compatibility\s*:\s*([^\s]+)\s*$")


@dataclass(frozen=True)
class IntentDiscovery:
    conflicts: List[Dict[str, Any]]
    evidence: List[Dict[str, Any]]
    mainline: List[Dict[str, Any]]
    project_intent: Dict[str, Any]
    retention_policy: Dict[str, Any]
    warnings: List[str]


def discover_intent(
    root_fd: int,
    inventory_records: Sequence[Dict[str, Any]],
    run_id: str,
    created_at: str,
) -> IntentDiscovery:
    """Extract limited document claims without interpreting or executing text."""
    records_by_path = {
        record["repository_relative_path"]: record
        for record in inventory_records
        if record["object_type"] == "REGULAR_FILE"
    }
    source_claims, warnings = _source_claims(root_fd, records_by_path)
    evidence = _evidence_by_claim(source_claims, run_id)
    claims_by_path: Dict[str, List[Dict[str, Any]]] = {}
    for claim in source_claims:
        claims_by_path.setdefault(claim["repository_relative_path"], []).append(claim)

    mainline, conflict_specs = _mainline_records(
        inventory_records, claims_by_path, evidence, run_id, created_at
    )
    conflicts = _conflict_records(conflict_specs, evidence, run_id, created_at)
    project_intent = _project_intent(
        source_claims, conflict_specs, evidence, run_id, created_at
    )
    retention_policy = _retention_policy(source_claims, evidence, run_id, created_at)
    return IntentDiscovery(
        conflicts=conflicts,
        evidence=_intent_evidence_records(source_claims, evidence, run_id, created_at),
        mainline=mainline,
        project_intent=project_intent,
        retention_policy=retention_policy,
        warnings=sorted(set(warnings)),
    )


def _intent_evidence_records(
    claims: Sequence[Dict[str, Any]],
    evidence: Mapping[Tuple[str, str, str], str],
    run_id: str,
    created_at: str,
) -> List[Dict[str, Any]]:
    records = []
    for claim in sorted(
        claims,
        key=lambda item: (
            item["repository_relative_path"], item["source_path"], item["status"]
        ),
    ):
        records.append(
            {
                "assertion_origin": "DECLARED",
                "counter_evidence_ids": [],
                "conforms_to": [EVIDENCE_PROFILE_URI],
                "created_at": created_at,
                "evidence_id": evidence[
                    (
                        claim["source_path"],
                        claim["repository_relative_path"],
                        claim["status"],
                    )
                ],
                "extractor": "repo_curator.intent.discover_intent",
                "limitations": ["INTENT_EXPLICIT_LABEL_PARSER_ONLY"],
                "run_id": run_id,
                "schema_version": "repo-curator.evidence.v1",
                "scope": "REPOSITORY",
                "source": {
                    "record_id": claim["artifact_id"],
                    "type": claim["source_type"],
                },
                "source_record_id": claim["artifact_id"],
                "source_type": claim["source_type"],
                "subject": {
                    "repository_relative_path": claim["repository_relative_path"]
                },
            }
        )
    return records


def _source_claims(
    root_fd: int, records_by_path: Mapping[str, Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[str]]:
    claims = []
    warnings = []
    for path, record in sorted(records_by_path.items()):
        source_type = _source_type(path)
        if source_type is None:
            continue
        try:
            content, truncated = _read_text(root_fd, path)
        except OSError:
            warnings.append("INTENT_SOURCE_UNREADABLE")
            continue
        if truncated:
            warnings.append("INTENT_SOURCE_TRUNCATED")
        for status, target in _claims_from_text(content, path, source_type):
            if target not in records_by_path:
                continue
            claims.append(
                {
                    "artifact_id": record["artifact_id"],
                    "repository_relative_path": target,
                    "source_path": path,
                    "source_type": source_type,
                    "status": status,
                }
            )
    return claims, warnings


def _source_type(path: str) -> Optional[str]:
    name = path.rsplit("/", 1)[-1].lower()
    if name in {"agents.md", "claude.md"}:
        return "SCOPED_RULE"
    if path.startswith(".github/workflows/") or name in {
        "docker-compose.yml",
        "docker-compose.yaml",
        "dockerfile",
    }:
        return "DELIVERY_WIRING"
    if name.startswith("readme") or name.startswith("contributing"):
        return "DOCUMENTATION"
    if path.startswith("docs/") or name in {
        "context.md",
        "pyproject.toml",
        "package.json",
    }:
        return "DOCUMENTATION"
    return None


def _claims_from_text(
    content: str, source_path: str, source_type: str
) -> Iterable[Tuple[str, str]]:
    parent = _parent(source_path) if source_type == "SCOPED_RULE" else ""
    for match in _ENTRY_POINT.finditer(content):
        target = _scoped_path(parent, match.group(1))
        if target is not None:
            yield "ACTIVE_MAINLINE", target
    for match in _COMPATIBILITY.finditer(content):
        target = _scoped_path(parent, match.group(1))
        if target is not None:
            yield "REQUIRED_COMPATIBILITY", target
    for match in _RETENTION.finditer(content):
        target = _scoped_path(parent, match.group(2))
        if target is None:
            continue
        verb = match.group(1).lower()
        status = "HISTORICAL_EVIDENCE" if verb in {"archive", "historical", "prototype"} else "REQUIRED"
        yield status, target


def _scoped_path(parent: str, target: str) -> Optional[str]:
    target = target.replace("\\", "/")
    if not target or target.startswith("/") or ":" in target:
        return None
    parts = target.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    return f"{parent}/{target}" if parent else target


def _parent(path: str) -> str:
    return path.rsplit("/", 1)[0] if "/" in path else ""


def _evidence_by_claim(claims: Sequence[Dict[str, Any]], run_id: str) -> Dict[Tuple[str, str, str], str]:
    return {
        (claim["source_path"], claim["repository_relative_path"], claim["status"]): (
            f"intent_evidence_{run_id}_{sequence:08d}"
        )
        for sequence, claim in enumerate(
            sorted(
                claims,
                key=lambda item: (
                    item["repository_relative_path"],
                    item["source_path"],
                    item["status"],
                ),
            ),
            start=1,
        )
    }


def _mainline_records(
    inventory_records: Sequence[Dict[str, Any]],
    claims_by_path: Mapping[str, Sequence[Dict[str, Any]]],
    evidence: Mapping[Tuple[str, str, str], str],
    run_id: str,
    created_at: str,
) -> Tuple[List[Dict[str, Any]], List[Tuple[str, Sequence[Dict[str, Any]]]]]:
    records = []
    conflicts = []
    active_claims = [
        claim
        for claims in claims_by_path.values()
        for claim in claims
        if claim["status"] == "ACTIVE_MAINLINE"
    ]
    conflicting_active_paths = {
        claim["repository_relative_path"] for claim in active_claims
    }
    has_active_entry_conflict = len(conflicting_active_paths) > 1
    for record in inventory_records:
        if record["object_type"] != "REGULAR_FILE":
            continue
        path = record["repository_relative_path"]
        claims = claims_by_path.get(path, [])
        statuses = {claim["status"] for claim in claims}
        conflicting = len(statuses) > 1 or (
            has_active_entry_conflict and "ACTIVE_MAINLINE" in statuses
        )
        conflicting_claims = active_claims if (
            has_active_entry_conflict and "ACTIVE_MAINLINE" in statuses
        ) else claims
        if conflicting:
            status = "UNRESOLVED"
            conflicts.append((path, conflicting_claims))
        elif statuses:
            status = next(iter(statuses))
        else:
            status = "UNRESOLVED"
        support = [
            evidence[
                (
                    claim["source_path"],
                    claim["repository_relative_path"],
                    claim["status"],
                )
            ]
            for claim in (conflicting_claims if conflicting else claims)
        ]
        records.append(
            {
                "artifact_id": record["artifact_id"],
                "counter_evidence_ids": support if conflicting else [],
                "created_at": created_at,
                "mainline_id": f"mainline_{run_id}_{len(records) + 1:08d}",
                "repository_relative_path": path,
                "retention": "REQUIRED",
                "run_id": run_id,
                "schema_version": MAINLINE_SCHEMA_VERSION,
                "scope": "REPOSITORY",
                "status": status,
                "supporting_evidence_ids": support,
                "uncertainty": (
                    ["CONFLICTING_INTENT_EVIDENCE"]
                    if conflicting
                    else ["NO_MAINLINE_EVIDENCE"]
                    if not claims
                    else []
                ),
            }
        )
    return records, conflicts


def _conflict_records(
    conflict_specs: Sequence[Tuple[str, Sequence[Dict[str, Any]]]],
    evidence: Mapping[Tuple[str, str, str], str],
    run_id: str,
    created_at: str,
) -> List[Dict[str, Any]]:
    records = []
    for path, claims in conflict_specs:
        evidence_ids = [
            evidence[
                (
                    claim["source_path"],
                    claim["repository_relative_path"],
                    claim["status"],
                )
            ]
            for claim in claims
        ]
        records.append(
            {
                "conflict_id": f"intent_conflict_{run_id}_{len(records) + 1:08d}",
                "counter_evidence_ids": evidence_ids,
                "created_at": created_at,
                "repository_relative_path": path,
                "run_id": run_id,
                "schema_version": CONFLICT_SCHEMA_VERSION,
                "scope": "REPOSITORY",
                "source_claims": [
                    {
                        "source_artifact_id": claim["artifact_id"],
                        "source_path": claim["source_path"],
                        "source_type": claim["source_type"],
                        "status": claim["status"],
                    }
                    for claim in claims
                ],
                "supporting_evidence_ids": evidence_ids,
                "uncertainty": ["CONFLICTING_INTENT_EVIDENCE"],
            }
        )
    return records


def _project_intent(
    claims: Sequence[Dict[str, Any]],
    conflicts: Sequence[Tuple[str, Sequence[Dict[str, Any]]]],
    evidence: Mapping[Tuple[str, str, str], str],
    run_id: str,
    created_at: str,
) -> Dict[str, Any]:
    active_claims = [claim for claim in claims if claim["status"] == "ACTIVE_MAINLINE"]
    evidence_ids = [
        evidence[(claim["source_path"], claim["repository_relative_path"], claim["status"])]
        for claim in active_claims
    ]
    return {
        "counter_evidence_ids": [
            evidence[
                (
                    claim["source_path"],
                    claim["repository_relative_path"],
                    claim["status"],
                )
            ]
            for path, claims_for_path in conflicts
            for claim in claims_for_path
        ],
        "created_at": created_at,
        "entry_points": sorted({claim["repository_relative_path"] for claim in active_claims}),
        "limitations": ["INTENT_EXPLICIT_LABEL_PARSER_ONLY"],
        "project_intent_id": f"project_intent_{run_id}",
        "run_id": run_id,
        "schema_version": INTENT_SCHEMA_VERSION,
        "scope": "REPOSITORY",
        "source_artifact_ids": sorted({claim["artifact_id"] for claim in claims}),
        "status": "UNRESOLVED" if conflicts or not active_claims else "SUPPORTED",
        "supporting_evidence_ids": evidence_ids,
        "uncertainty": (
            ["CONFLICTING_INTENT_EVIDENCE"]
            if conflicts
            else ["NO_ACTIVE_DELIVERY_OR_ENTRY_POINT_EVIDENCE"]
            if not active_claims
            else []
        ),
    }


def _retention_policy(
    claims: Sequence[Dict[str, Any]],
    evidence: Mapping[Tuple[str, str, str], str],
    run_id: str,
    created_at: str,
) -> Dict[str, Any]:
    return {
        "created_at": created_at,
        "default_retention": "REQUIRED",
        "retention_policy_id": f"retention_policy_{run_id}",
        "limitations": ["INTENT_EXPLICIT_LABEL_PARSER_ONLY"],
        "rules": [
            {
                "evidence_id": evidence[(claim["source_path"], claim["repository_relative_path"], claim["status"])],
                "repository_relative_path": claim["repository_relative_path"],
                "source_artifact_id": claim["artifact_id"],
                "source_path": claim["source_path"],
                "status": claim["status"],
            }
            for claim in sorted(
                claims,
                key=lambda item: (
                    item["repository_relative_path"], item["source_path"], item["status"]
                ),
            )
        ],
        "run_id": run_id,
        "schema_version": RETENTION_SCHEMA_VERSION,
        "scope": "REPOSITORY",
        "uncertainty": ["UNLISTED_ARTIFACTS_REMAIN_REQUIRED"],
    }


def _read_text(root_fd: int, path: str) -> Tuple[str, bool]:
    descriptor = _open_regular_file(root_fd, path)
    try:
        payload = os.read(descriptor, _READ_LIMIT + 1)
    finally:
        os.close(descriptor)
    return payload[:_READ_LIMIT].decode("utf-8", "replace"), len(payload) > _READ_LIMIT


def _open_regular_file(root_fd: int, path: str) -> int:
    current_fd = os.dup(root_fd)
    try:
        parts = os.fsencode(path).split(b"/")
        for part in parts[:-1]:
            next_fd = os.open(
                part,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
                dir_fd=current_fd,
            )
            os.close(current_fd)
            current_fd = next_fd
        descriptor = os.open(
            parts[-1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=current_fd
        )
    finally:
        os.close(current_fd)
    if not stat.S_ISREG(os.fstat(descriptor).st_mode):
        os.close(descriptor)
        raise OSError("intent source changed type")
    return descriptor
