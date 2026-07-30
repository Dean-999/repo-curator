"""Bounded, redacted profiles for untrusted regular-file content."""

import csv
import io
import json
import os
import re
import stat
from typing import Any, Dict, Iterable, List

from repo_curator.notebook_envelope import observe_notebook_envelope
from repo_curator.research_metadata import is_sensitive_research_metadata_path
from repo_curator.secret_redaction import redact_text as _redact


PROFILE_SCHEMA_VERSION = "repo-curator.profile.v2"
TEXT_LIMIT = 2 * 1024 * 1024
SAMPLE_LIMIT = 512
_MARKDOWN = re.compile(r"(?m)^#{1,6}\s+\S+")
_LOG = re.compile(r"(?m)^(?:\d{4}-\d\d-\d\d|\[[A-Z]+\]|(?:INFO|WARN|ERROR|DEBUG)\b)")


def profile_artifacts(
    root_fd: int, records: Iterable[Dict[str, Any]], run_id: str, created_at: str
) -> List[Dict[str, Any]]:
    profiles = []
    for record in records:
        if record["object_type"] != "REGULAR_FILE":
            continue
        profiles.append(_profile(root_fd, record, run_id, created_at, len(profiles) + 1))
    return profiles


def _profile(root_fd: int, record: Dict[str, Any], run_id: str, created_at: str, sequence: int) -> Dict[str, Any]:
    limitations: List[str] = []
    redactions: List[str] = []
    content = b""
    if is_sensitive_research_metadata_path(record["repository_relative_path"]):
        limitations.append("RESEARCH_METADATA_CONTENT_NOT_PERSISTED")
    elif record["profile_eligibility"] != "ELIGIBLE":
        limitations.append("PROFILE_SKIPPED_SIZE_LIMIT")
    else:
        try:
            content, truncated = _read_file(root_fd, record["repository_relative_path"], TEXT_LIMIT)
            if truncated:
                limitations.append("PROFILE_TRUNCATED")
        except OSError:
            limitations.append("PROFILE_UNREADABLE")
    format_name, metadata, sample, detected_limits = _detect(
        content,
        record["repository_relative_path"],
        truncated="PROFILE_TRUNCATED" in limitations,
        available=not bool(
            {"PROFILE_SKIPPED_SIZE_LIMIT", "PROFILE_UNREADABLE"} & set(limitations)
        ),
    )
    limitations.extend(detected_limits)
    metadata, metadata_redactions = _redact_metadata(metadata)
    sample, sample_redactions = _redact(sample)
    sample = _redaction_safe_prefix(sample, SAMPLE_LIMIT)
    redactions = sorted(set(metadata_redactions + sample_redactions))
    return {
        "artifact_id": record["artifact_id"], "created_at": created_at,
        "format": format_name, "limitations": sorted(set(limitations)), "metadata": metadata,
        "profile_id": f"profile_{run_id}_{sequence:08d}", "redactions": redactions,
        "repository_relative_path": record["repository_relative_path"], "run_id": run_id,
        "inspected_ranges": ([{"start": 0, "end": len(content)}] if content else []),
        "persisted_sample_ranges": ([{"start": 0, "end": len(sample.encode("utf-8"))}] if sample else []),
        "sample": sample,
        "schema_version": PROFILE_SCHEMA_VERSION, "truncated": "PROFILE_TRUNCATED" in limitations,
    }


def _read_file(root_fd: int, path: str, limit: int) -> tuple[bytes, bool]:
    current_fd = os.dup(root_fd)
    try:
        components = os.fsencode(path).split(b"/")
        for component in components[:-1]:
            next_fd = os.open(component, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=current_fd)
            os.close(current_fd); current_fd = next_fd
        file_fd = os.open(components[-1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0), dir_fd=current_fd)
        try:
            if not stat.S_ISREG(os.fstat(file_fd).st_mode):
                raise OSError("profile target changed type")
            content = os.read(file_fd, limit + 1)
        finally:
            os.close(file_fd)
    finally:
        os.close(current_fd)
    return content[:limit], len(content) > limit


def _utf8_prefix(value: str, maximum_bytes: int) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= maximum_bytes:
        return value
    return encoded[:maximum_bytes].decode("utf-8", "ignore")


def _redaction_safe_prefix(value: str, maximum_bytes: int) -> str:
    prefix = _utf8_prefix(value, maximum_bytes)
    marker_start = prefix.rfind("[REDACTED:")
    if marker_start < 0 or "]" in prefix[marker_start:]:
        return prefix
    marker_end = value.find("]", marker_start)
    if marker_end < 0:
        return prefix
    marker = value[marker_start : marker_end + 1]
    marker_size = len(marker.encode("utf-8"))
    if marker_size > maximum_bytes:
        return "[REDACTED]"[:maximum_bytes]
    return _utf8_prefix(value[:marker_start], maximum_bytes - marker_size) + marker


def _detect(
    content: bytes, path: str = "", truncated: bool = False, available: bool = True
) -> tuple[str, Dict[str, Any], str, List[str]]:
    if is_sensitive_research_metadata_path(path):
        return (
            "RESEARCH_METADATA_DECLARATION",
            {},
            "",
            ["RESEARCH_METADATA_CONTENT_NOT_PERSISTED"],
        )
    if path.rsplit("/", 1)[-1].casefold() == "datapackage.json":
        return "DATA_PACKAGE", {}, "", ["DATA_PACKAGE_CONTENT_NOT_PERSISTED"]
    if path.casefold().endswith(".ipynb"):
        if not available:
            return "NOTEBOOK", {}, "", ["NOTEBOOK_ENVELOPE_UNAVAILABLE"]
        metadata, limitations = observe_notebook_envelope(content, truncated)
        return "NOTEBOOK", metadata, "", list(limitations)
    if content.startswith(b"%PDF-"):
        version = content[5:8].decode("ascii", "replace")
        text = b" ".join(re.findall(rb"\(([^()]*)\)\s*Tj", content)).decode("latin-1", "replace")
        return "PDF", {"page_markers": content.count(b"/Type /Page"), "version": version}, text, []
    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        return "BINARY", {}, "", ["UNSUPPORTED_FORMAT"]
    stripped = text.lstrip()
    if stripped.startswith(("{", "[")):
        try:
            value = json.loads(text)
            return "JSON", {"root_type": type(value).__name__}, text, []
        except json.JSONDecodeError:
            return "JSON", {}, text, ["PROFILE_MALFORMED_JSON"]
    lines = text.splitlines()
    if len(lines) >= 2 and "," in lines[0]:
        try:
            rows = list(csv.reader(io.StringIO("\n".join(lines[:1001]))))
            if rows and all(len(row) == len(rows[0]) for row in rows):
                return "CSV", {"columns": len(rows[0]), "sampled_rows": len(rows)}, text, []
        except csv.Error:
            return "CSV", {}, text, ["PROFILE_MALFORMED_CSV"]
    if _MARKDOWN.search(text):
        return "MARKDOWN", {"heading_count": len(_MARKDOWN.findall(text))}, text, []
    if _LOG.search(text):
        return "LOG", {"line_count": len(lines)}, text, []
    return "TEXT", {"line_count": len(lines)}, text, []
def _redact_metadata(value: Any) -> tuple[Any, List[str]]:
    if isinstance(value, str):
        return _redact(value)
    if isinstance(value, list):
        redacted = []
        categories = []
        for item in value:
            clean, item_categories = _redact_metadata(item)
            redacted.append(clean)
            categories.extend(item_categories)
        return redacted, sorted(set(categories))
    if isinstance(value, dict):
        redacted = {}
        categories = []
        for key, item in value.items():
            clean, item_categories = _redact_metadata(item)
            redacted[key] = clean
            categories.extend(item_categories)
        return redacted, sorted(set(categories))
    return value, []
