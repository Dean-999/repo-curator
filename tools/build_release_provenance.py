#!/usr/bin/env python3
"""Build a create-once local SLSA statement for one release artifact."""

import argparse
import hashlib
import os
import stat
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from repo_curator.corpus import read_json_object, write_new_json
from repo_curator.release_provenance import build_release_provenance


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--bundle-manifest", required=True, type=Path)
    parser.add_argument("--release-check", required=True, type=Path)
    parser.add_argument("--builder-id", required=True)
    parser.add_argument("--invocation-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    manifest = read_json_object(args.bundle_manifest, "bundle manifest")
    release_check = read_json_object(args.release_check, "release check")
    if manifest.get("schema_version") != "repo-curator.skill-bundle.v4":
        raise ValueError("bundle manifest schema is unsupported")
    if (
        release_check.get("schema_version") != "repo-curator.release-check.v2"
        or release_check.get("status") != "PASSED"
    ):
        raise ValueError("release check is not passed")
    source_git = manifest.get("source_git")
    if not isinstance(source_git, dict):
        raise ValueError("bundle source identity is malformed")
    statement = build_release_provenance(
        artifact_name=args.artifact.name,
        artifact_sha256=_hash_regular(args.artifact),
        builder_id=args.builder_id,
        invocation_id=args.invocation_id,
        source_commit=source_git["head_commit"],
        source_tree=source_git["head_tree"],
        bundle_manifest_sha256=_hash_regular(args.bundle_manifest),
        release_check_sha256=_hash_regular(args.release_check),
    )
    write_new_json(args.output, statement)
    return 0


def _hash_regular(path: Path) -> str:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    digest = hashlib.sha256()
    total = 0
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode):
            raise ValueError("release input must be a regular file")
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                return digest.hexdigest()
            total += len(chunk)
            if total > 2 * 1024 * 1024 * 1024:
                raise ValueError("release input exceeds byte limit")
            digest.update(chunk)
    finally:
        os.close(descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
