#!/usr/bin/env python3
"""Verify an exact local repo-curator provenance statement."""

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from repo_curator.corpus import read_json_object
from repo_curator.release_provenance import verify_release_provenance
from tools.build_release_provenance import _hash_regular


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--statement", required=True, type=Path)
    parser.add_argument("--artifact", required=True, type=Path)
    parser.add_argument("--builder-id", required=True)
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--source-tree", required=True)
    args = parser.parse_args()
    verify_release_provenance(
        read_json_object(args.statement, "provenance statement"),
        args.artifact.name,
        _hash_regular(args.artifact),
        args.builder_id,
        args.source_commit,
        args.source_tree,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
