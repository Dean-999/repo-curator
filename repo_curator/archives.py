"""Bounded archive observations that never extract members."""

import hashlib
import json
import os
import re
import stat
import struct
import zipfile
from typing import Any, Dict, Iterable, List, Optional


ARCHIVE_SCHEMA_VERSION = "repo-curator.archive-observation.v1"
ZIP_MEMBER_LIMIT = 100_000
ZIP_RATIO_LIMIT = 100
ZIP_CENTRAL_DIRECTORY_LIMIT = 1024 * 1024
ZIP_EOCD_SEARCH_LIMIT = 65_557


def inspect_archives(root_fd: int, records: Iterable[Dict[str, Any]], run_id: str, created_at: str) -> List[Dict[str, Any]]:
    observations = []
    for record in records:
        if record["object_type"] != "REGULAR_FILE" or record["profile_eligibility"] != "ELIGIBLE":
            continue
        prefix = _read_prefix(root_fd, record["repository_relative_path"], 512)
        kind = _archive_kind(prefix)
        if kind is None:
            continue
        limitations: List[str] = []
        details: Dict[str, Any] = {}
        status = "OPAQUE"
        if kind == "ZIP":
            status, details, limitations = _zip_observation(root_fd, record["repository_relative_path"])
        else:
            limitations.append("UNSUPPORTED_FORMAT")
        observations.append({
            "archive_format": kind, "artifact_id": record["artifact_id"], "created_at": created_at,
            "limitations": sorted(set(limitations)), "observation_id": f"archive_{run_id}_{len(observations)+1:08d}",
            "repository_relative_path": record["repository_relative_path"], "run_id": run_id,
            "schema_version": ARCHIVE_SCHEMA_VERSION, "status": status, **details,
        })
    return observations


def _archive_kind(prefix: bytes) -> Optional[str]:
    if prefix.startswith(b"PK\x03\x04") or prefix.startswith(b"PK\x05\x06"):
        return "ZIP"
    if len(prefix) >= 262 and prefix[257:262] == b"ustar":
        return "TAR"
    if prefix.startswith(b"7z\xbc\xaf\x27\x1c"):
        return "7Z"
    if prefix.startswith(b"Rar!\x1a\x07"):
        return "RAR"
    return None


def _zip_observation(root_fd: int, path: str) -> tuple[str, Dict[str, Any], List[str]]:
    try:
        descriptor = _open_file(root_fd, path)
        with os.fdopen(descriptor, "rb") as source:
            limitation = _zip_directory_precheck(source)
            if limitation is not None:
                return "LIMITED", {}, [limitation]
            source.seek(0)
            with zipfile.ZipFile(source) as archive:
                infos = archive.infolist()
    except (OSError, zipfile.BadZipFile, zipfile.LargeZipFile):
        return "LIMITED", {}, ["ARCHIVE_MALFORMED"]
    if len(infos) > ZIP_MEMBER_LIMIT:
        return "LIMITED", {}, ["RESOURCE_LIMIT_REACHED"]
    names = set()
    manifest = []
    for info in infos:
        name = info.filename
        if not _safe_name(name):
            return "LIMITED", {}, ["ARCHIVE_PATH_UNSAFE"]
        key = name.casefold()
        if key in names:
            return "LIMITED", {}, ["ARCHIVE_DUPLICATE_MEMBER"]
        names.add(key)
        if info.flag_bits & 1:
            return "LIMITED", {}, ["ARCHIVE_ENCRYPTED"]
        if info.compress_size and info.file_size / info.compress_size > ZIP_RATIO_LIMIT:
            return "LIMITED", {}, ["RESOURCE_LIMIT_REACHED"]
        manifest.append({"crc": info.CRC, "name": name, "size": info.file_size})
    payload = json.dumps(sorted(manifest, key=lambda item: item["name"]), separators=(",", ":"), sort_keys=True).encode()
    return "INSPECTED", {"member_count": len(manifest), "member_manifest_id": "zip-manifest-v1:" + hashlib.sha256(payload).hexdigest()}, []


def _zip_directory_precheck(source: Any) -> Optional[str]:
    source.seek(0, os.SEEK_END)
    size = source.tell()
    if size < 22:
        return "ARCHIVE_MALFORMED"
    tail_size = min(size, ZIP_EOCD_SEARCH_LIMIT)
    source.seek(size - tail_size)
    tail = source.read(tail_size)
    offset = tail.rfind(b"PK\x05\x06")
    if offset < 0 or offset + 22 > len(tail):
        return "ARCHIVE_MALFORMED"
    try:
        _, disk, directory_disk, entries_on_disk, entries, directory_size, directory_offset, comment_size = struct.unpack_from(
            "<4s4H2LH", tail, offset
        )
    except struct.error:
        return "ARCHIVE_MALFORMED"
    eocd_offset = size - tail_size + offset
    if offset + 22 + comment_size != len(tail) or disk != 0 or directory_disk != 0 or entries_on_disk != entries:
        return "ARCHIVE_MALFORMED"
    if entries == 0xFFFF or directory_size == 0xFFFFFFFF or directory_offset == 0xFFFFFFFF:
        return "RESOURCE_LIMIT_REACHED"
    if entries > ZIP_MEMBER_LIMIT or directory_size > ZIP_CENTRAL_DIRECTORY_LIMIT:
        return "RESOURCE_LIMIT_REACHED"
    if directory_offset + directory_size > eocd_offset:
        return "ARCHIVE_MALFORMED"
    return None


def _safe_name(name: str) -> bool:
    normalized = name.replace("\\", "/").rstrip("/")
    return bool(normalized) and not normalized.startswith("/") and not re.match(r"^[A-Za-z]:", normalized) and all(part not in {"", ".", ".."} for part in normalized.split("/"))


def _read_prefix(root_fd: int, path: str, limit: int) -> bytes:
    try:
        descriptor = _open_file(root_fd, path)
        try:
            return os.read(descriptor, limit)
        finally:
            os.close(descriptor)
    except OSError:
        return b""


def _open_file(root_fd: int, path: str) -> int:
    current_fd = os.dup(root_fd)
    try:
        parts = os.fsencode(path).split(b"/")
        for part in parts[:-1]:
            next_fd = os.open(part, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0), dir_fd=current_fd)
            os.close(current_fd); current_fd = next_fd
        descriptor = os.open(parts[-1], os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=current_fd)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            os.close(descriptor); raise OSError("archive changed type")
        return descriptor
    finally:
        os.close(current_fd)
