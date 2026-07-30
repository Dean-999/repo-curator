"""Create a portable repo-curator Skill bundle from this checkout."""

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from repo_curator.bundle import build_skill_bundle


def main() -> int:
    parser = argparse.ArgumentParser(
        description="build a self-contained repo-curator Skill bundle"
    )
    parser.add_argument("--output", required=True, type=Path)
    arguments = parser.parse_args()
    build_skill_bundle(REPOSITORY_ROOT, arguments.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
