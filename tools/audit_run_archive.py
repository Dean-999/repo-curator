#!/usr/bin/env python3
"""Build, verify, and restore a deterministic pilot audit-run archive."""

import argparse
import gzip
import hashlib
import json
import os
import re
import stat
import tarfile
from pathlib import Path, PurePosixPath
from typing import Dict, Iterable, List


SCHEMA_VERSION = "repo-curator.audit-run-archive.v1"
MAX_MEMBERS = 512
MAX_MEMBER_BYTES = 16 * 1024 * 1024
MAX_TOTAL_BYTES = 64 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")


class AuditRunArchiveError(ValueError):
    """Raised when archive inputs or contents violate the frozen contract."""


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build")
    build.add_argument("--corpus-root", required=True, type=Path)
    build.add_argument("--source-git-commit", required=True)
    build.add_argument("--release-tag", required=True)
    build.add_argument("--asset-name", required=True)
    build.add_argument("--repository", required=True)
    build.add_argument("--output-archive", required=True, type=Path)
    build.add_argument("--output-manifest", required=True, type=Path)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--archive", required=True, type=Path)
    verify.add_argument("--manifest", required=True, type=Path)
    verify.add_argument("--restore-to", type=Path)

    args = parser.parse_args()
    try:
        if args.command == "build":
            build_archive(
                corpus_root=args.corpus_root,
                source_git_commit=args.source_git_commit,
                release_tag=args.release_tag,
                asset_name=args.asset_name,
                repository=args.repository,
                output_archive=args.output_archive,
                output_manifest=args.output_manifest,
            )
        else:
            verify_archive(args.archive, args.manifest, args.restore_to)
    except (AuditRunArchiveError, OSError, tarfile.TarError, json.JSONDecodeError) as error:
        parser.error(str(error))
    return 0


def build_archive(
    *,
    corpus_root: Path,
    source_git_commit: str,
    release_tag: str,
    asset_name: str,
    repository: str,
    output_archive: Path,
    output_manifest: Path,
) -> Dict[str, object]:
    if not COMMIT_PATTERN.fullmatch(source_git_commit):
        raise AuditRunArchiveError("source Git commit must be a full lowercase SHA-1")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", release_tag):
        raise AuditRunArchiveError("release tag contains unsupported characters")
    if not re.fullmatch(r"[A-Za-z0-9._-]+\.tar\.gz", asset_name):
        raise AuditRunArchiveError("asset name must be a portable .tar.gz filename")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repository):
        raise AuditRunArchiveError("repository must be an owner/name pair")
    _require_new_output(output_archive)
    _require_new_output(output_manifest)

    corpus_root = corpus_root.resolve(strict=True)
    audit_root = corpus_root / "artifacts" / "audit-runs"
    members = _collect_members(corpus_root, audit_root)
    registry_path = corpus_root / "audit-run-registry.json"
    snapshot_path = corpus_root / "snapshot-registry.json"
    registry = _read_json(registry_path)
    snapshots = _read_json(snapshot_path)
    repositories = _repository_bindings(registry, snapshots)

    output_archive.parent.mkdir(parents=True, exist_ok=True)
    with output_archive.open("xb") as raw_output:
        with gzip.GzipFile(
            filename="", mode="wb", fileobj=raw_output, mtime=0
        ) as compressed:
            with tarfile.open(
                fileobj=compressed, mode="w", format=tarfile.PAX_FORMAT
            ) as archive:
                for member in members:
                    source = corpus_root / member["path"]
                    info = tarfile.TarInfo(member["path"])
                    info.size = member["size_bytes"]
                    info.mode = 0o644
                    info.uid = 0
                    info.gid = 0
                    info.uname = ""
                    info.gname = ""
                    info.mtime = 0
                    with source.open("rb") as stream:
                        archive.addfile(info, stream)

    archive_sha256 = _hash_regular(output_archive)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "archive": {
            "asset_name": asset_name,
            "download_url": (
                "https://github.com/{}/releases/download/{}/{}".format(
                    repository, release_tag, asset_name
                )
            ),
            "format": "tar+gzip",
            "member_count": len(members),
            "member_root": "artifacts/audit-runs",
            "sha256": "sha256:" + archive_sha256,
            "size_bytes": output_archive.stat().st_size,
            "uncompressed_bytes": sum(item["size_bytes"] for item in members),
        },
        "source": {
            "audit_run_registry_path": "audit-run-registry.json",
            "audit_run_registry_sha256": "sha256:" + _hash_regular(registry_path),
            "git_commit": source_git_commit,
            "release_tag": release_tag,
            "snapshot_registry_path": "snapshot-registry.json",
            "snapshot_registry_sha256": "sha256:" + _hash_regular(snapshot_path),
        },
        "repositories": repositories,
        "members": members,
        "restore": {
            "policy": "NEW_EMPTY_DIRECTORY_ONLY",
            "tool": "tools/audit_run_archive.py verify --restore-to",
        },
    }
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    with output_manifest.open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2, sort_keys=True)
        stream.write("\n")
    return manifest


def verify_archive(
    archive_path: Path, manifest_path: Path, restore_to: Path = None
) -> Dict[str, object]:
    manifest = _read_json(manifest_path)
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise AuditRunArchiveError("archive manifest version is unsupported")
    archive_record = manifest.get("archive")
    members = manifest.get("members")
    if not isinstance(archive_record, dict) or not isinstance(members, list):
        raise AuditRunArchiveError("archive manifest is malformed")
    expected_digest = _bare_sha256(archive_record.get("sha256"))
    if _hash_regular(archive_path) != expected_digest:
        raise AuditRunArchiveError("archive SHA-256 does not match the manifest")
    expected = _validate_manifest_members(members)
    if archive_record.get("member_count") != len(expected):
        raise AuditRunArchiveError("archive member count does not match the manifest")

    restore_root = None
    if restore_to is not None:
        if restore_to.exists() or restore_to.is_symlink():
            raise AuditRunArchiveError("restore destination already exists")
        restore_to.mkdir(parents=True)
        restore_root = restore_to.resolve(strict=True)

    observed = {}
    total = 0
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            for info in archive:
                path = _safe_member_path(info.name)
                if not info.isfile():
                    raise AuditRunArchiveError("archive contains a non-regular member")
                if path in observed:
                    raise AuditRunArchiveError("archive contains a duplicate member")
                if path not in expected:
                    raise AuditRunArchiveError("archive contains an unregistered member")
                if info.size != expected[path]["size_bytes"]:
                    raise AuditRunArchiveError("archive member size does not match")
                total += info.size
                if info.size > MAX_MEMBER_BYTES or total > MAX_TOTAL_BYTES:
                    raise AuditRunArchiveError("archive exceeds the restore byte limit")
                source = archive.extractfile(info)
                if source is None:
                    raise AuditRunArchiveError("archive member is unreadable")
                digest = hashlib.sha256()
                destination = restore_root / path if restore_root is not None else None
                if destination is not None:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    output = destination.open("xb")
                else:
                    output = None
                try:
                    remaining = info.size
                    while remaining:
                        chunk = source.read(min(CHUNK_BYTES, remaining))
                        if not chunk:
                            raise AuditRunArchiveError("archive member is truncated")
                        remaining -= len(chunk)
                        digest.update(chunk)
                        if output is not None:
                            output.write(chunk)
                    if source.read(1):
                        raise AuditRunArchiveError("archive member exceeds declared size")
                finally:
                    source.close()
                    if output is not None:
                        output.close()
                if digest.hexdigest() != expected[path]["sha256"]:
                    raise AuditRunArchiveError("archive member SHA-256 does not match")
                observed[path] = True
    except Exception:
        if restore_root is not None:
            _remove_restored_files(restore_root)
        raise
    if set(observed) != set(expected):
        raise AuditRunArchiveError("archive is missing registered members")
    return {
        "archive_sha256": expected_digest,
        "member_count": len(observed),
        "restored": restore_root is not None,
        "status": "VERIFIED",
    }


def _collect_members(corpus_root: Path, audit_root: Path) -> List[Dict[str, object]]:
    if not audit_root.is_dir() or audit_root.is_symlink():
        raise AuditRunArchiveError("audit-run root must be a real directory")
    members = []
    total = 0
    for directory, directory_names, filenames in os.walk(audit_root, followlinks=False):
        directory_names.sort()
        filenames.sort()
        current = Path(directory)
        if current.is_symlink():
            raise AuditRunArchiveError("audit-run tree contains a symbolic link")
        for name in directory_names:
            if (current / name).is_symlink():
                raise AuditRunArchiveError(
                    "audit-run tree contains a symbolic link"
                )
        for name in filenames:
            path = current / name
            details = path.lstat()
            if not stat.S_ISREG(details.st_mode):
                raise AuditRunArchiveError("audit-run tree contains a non-regular file")
            if details.st_size > MAX_MEMBER_BYTES:
                raise AuditRunArchiveError("audit-run member exceeds the byte limit")
            total += details.st_size
            if total > MAX_TOTAL_BYTES:
                raise AuditRunArchiveError("audit-run tree exceeds the byte limit")
            relative = path.relative_to(corpus_root).as_posix()
            members.append(
                {
                    "path": relative,
                    "sha256": _hash_regular(path),
                    "size_bytes": details.st_size,
                }
            )
            if len(members) > MAX_MEMBERS:
                raise AuditRunArchiveError("audit-run tree exceeds the member limit")
    if not members:
        raise AuditRunArchiveError("audit-run tree is empty")
    return members


def _repository_bindings(
    audit_registry: Dict[str, object], snapshot_registry: Dict[str, object]
) -> List[Dict[str, object]]:
    snapshots = {
        item.get("repository_id"): item
        for item in snapshot_registry.get("repositories", [])
        if isinstance(item, dict)
    }
    bindings = []
    for run in audit_registry.get("audit_runs", []):
        if not isinstance(run, dict):
            raise AuditRunArchiveError("audit-run registry entry is malformed")
        snapshot = snapshots.get(run.get("repository_id"))
        if not isinstance(snapshot, dict):
            raise AuditRunArchiveError("audit run has no snapshot binding")
        commit = snapshot.get("commit_sha")
        if not isinstance(commit, str) or not COMMIT_PATTERN.fullmatch(commit):
            raise AuditRunArchiveError("snapshot commit is malformed")
        _bare_sha256(run.get("run_sha256"))
        _bare_sha256(run.get("snapshot_descriptor_sha256"))
        bindings.append(
            {
                "access": snapshot.get("access"),
                "repository_id": run.get("repository_id"),
                "run_id": run.get("run_id"),
                "run_path": run.get("run_path"),
                "run_sha256": run.get("run_sha256"),
                "source_commit": commit,
                "source_url": snapshot.get("source_url"),
            }
        )
    if not bindings:
        raise AuditRunArchiveError("audit-run registry is empty")
    return bindings


def _validate_manifest_members(
    members: Iterable[object],
) -> Dict[str, Dict[str, object]]:
    expected = {}
    total = 0
    for item in members:
        if not isinstance(item, dict):
            raise AuditRunArchiveError("archive member manifest is malformed")
        path = _safe_member_path(item.get("path"))
        size = item.get("size_bytes")
        digest = item.get("sha256")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise AuditRunArchiveError("archive member size is malformed")
        if size > MAX_MEMBER_BYTES:
            raise AuditRunArchiveError("archive member exceeds the byte limit")
        if not isinstance(digest, str) or not SHA256_PATTERN.fullmatch(digest):
            raise AuditRunArchiveError("archive member SHA-256 is malformed")
        if path in expected:
            raise AuditRunArchiveError("archive manifest contains a duplicate member")
        expected[path] = {"sha256": digest, "size_bytes": size}
        total += size
        if len(expected) > MAX_MEMBERS or total > MAX_TOTAL_BYTES:
            raise AuditRunArchiveError("archive manifest exceeds resource limits")
    return expected


def _safe_member_path(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise AuditRunArchiveError("archive member path is malformed")
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise AuditRunArchiveError("archive member path escapes the restore root")
    normalized = path.as_posix()
    if (
        normalized != value
        or not normalized.startswith("artifacts/audit-runs/")
        or "\x00" in normalized
    ):
        raise AuditRunArchiveError("archive member path is outside the audit-run root")
    return normalized


def _read_json(path: Path) -> Dict[str, object]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise AuditRunArchiveError("JSON input must contain one object")
    return value


def _hash_regular(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    digest = hashlib.sha256()
    total = 0
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise AuditRunArchiveError("archive input must be a regular file")
        while True:
            chunk = os.read(descriptor, CHUNK_BYTES)
            if not chunk:
                return digest.hexdigest()
            total += len(chunk)
            if total > MAX_TOTAL_BYTES:
                raise AuditRunArchiveError("archive input exceeds the byte limit")
            digest.update(chunk)
    finally:
        os.close(descriptor)


def _bare_sha256(value: object) -> str:
    if not isinstance(value, str):
        raise AuditRunArchiveError("SHA-256 value is malformed")
    bare = value.removeprefix("sha256:")
    if not SHA256_PATTERN.fullmatch(bare):
        raise AuditRunArchiveError("SHA-256 value is malformed")
    return bare


def _require_new_output(path: Path) -> None:
    if path.exists() or path.is_symlink():
        raise AuditRunArchiveError("output already exists")


def _remove_restored_files(root: Path) -> None:
    for directory, directory_names, filenames in os.walk(root, topdown=False):
        for name in filenames:
            (Path(directory) / name).unlink()
        for name in directory_names:
            (Path(directory) / name).rmdir()
    root.rmdir()


if __name__ == "__main__":
    raise SystemExit(main())
