"""Run the canonical local or bundled repo-curator audit kernel."""

import sys
from pathlib import Path


def _kernel_root() -> Path:
    scripts_directory = Path(__file__).resolve().parent
    bundled_package = scripts_directory / "repo_curator" / "cli.py"
    if bundled_package.is_file():
        return scripts_directory
    for ancestor in scripts_directory.parents:
        if (ancestor / "repo_curator" / "cli.py").is_file():
            return ancestor
    raise RuntimeError("repo-curator kernel is unavailable beside this Skill")


def main() -> int:
    sys.path.insert(0, str(_kernel_root()))
    from repo_curator.cli import main as audit_main

    return audit_main()


if __name__ == "__main__":
    raise SystemExit(main())
