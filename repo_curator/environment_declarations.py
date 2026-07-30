"""Observe repo2docker-style environment declarations without building them.

Marker selection and ``binder``/``.binder`` scope precedence are adapted from
JupyterHub/repo2docker at commit f90d7e9b2f9bc8fb9fbccf916afa512a460eac3d,
primarily ``repo2docker/buildpacks/base.py`` and its language buildpacks.
Copyright 2017-2026 Project Jupyter Contributors. Licensed under BSD-3-Clause;
see THIRD_PARTY_NOTICES.md. Parsing, dependency resolution, and execution are
intentionally excluded from this port.
"""

from typing import Any, Dict, Mapping, Optional, Tuple


MARKER_KINDS = {
    "DESCRIPTION": "R_PACKAGE",
    "Dockerfile": "CONTAINER",
    "JuliaProject.toml": "JULIA",
    "Manifest.toml": "JULIA_LOCK",
    "Pipfile": "PIPENV",
    "Pipfile.lock": "PIPENV_LOCK",
    "Project.toml": "JULIA",
    "REQUIRE": "JULIA_LEGACY",
    "apt.txt": "SYSTEM_PACKAGES",
    "default.nix": "NIX",
    "environment.yaml": "CONDA",
    "environment.yml": "CONDA",
    "install.R": "R_INSTALL_SCRIPT",
    "postBuild": "POST_BUILD_SCRIPT",
    "pyproject.toml": "PYTHON_PROJECT",
    "requirements.txt": "PIP",
    "requirements3.txt": "PIP_SERVER",
    "runtime.txt": "RUNTIME",
    "start": "START_SCRIPT",
}

_BUILD_INSTRUCTION_MARKERS = {
    "Dockerfile",
    "default.nix",
    "install.R",
    "postBuild",
    "start",
}
_ROOT_ONLY_MARKERS = {"DESCRIPTION", "pyproject.toml"}


def environment_declaration_candidate(
    all_records: Mapping[str, Dict[str, Any]],
) -> Optional[
    Tuple[
        Dict[str, Any],
        Tuple[Dict[str, Any], ...],
        Tuple[str, ...],
        Dict[str, Any],
    ]
]:
    """Return one lossless declaration candidate or ``None`` when absent."""
    marker_records = tuple(
        sorted(
            (
                record
                for path, record in all_records.items()
                if record.get("object_type") == "REGULAR_FILE"
                and _marker_name(path) in MARKER_KINDS
                and _scope(path) is not None
                and (
                    _marker_name(path) not in _ROOT_ONLY_MARKERS
                    or _scope(path) == "ROOT"
                )
            ),
            key=lambda record: _path_bytes(record["repository_relative_path"]),
        )
    )
    if not marker_records:
        return None

    has_binder = _directory_present(all_records, "binder")
    has_dot_binder = _directory_present(all_records, ".binder")
    all_paths = tuple(record["repository_relative_path"] for record in marker_records)
    limitations = {
        "ENVIRONMENT_DECLARATION_CONTENT_NOT_PARSED",
        "ENVIRONMENT_DECLARATION_NOT_ENVIRONMENT_AVAILABILITY",
    }

    if has_binder and has_dot_binder:
        environment_scope = "CONFLICT"
        active_paths: Tuple[str, ...] = ()
        shadowed_paths = all_paths
        limitations.add("ENVIRONMENT_BINDER_SCOPE_CONFLICT")
    else:
        environment_scope = "BINDER" if has_binder else "DOT_BINDER" if has_dot_binder else "ROOT"
        scope_prefix = (
            "binder/"
            if environment_scope == "BINDER"
            else ".binder/"
            if environment_scope == "DOT_BINDER"
            else ""
        )
        active_paths = tuple(
            path
            for path in all_paths
            if _scope(path) == environment_scope and path.startswith(scope_prefix)
        )
        shadowed_paths = tuple(path for path in all_paths if path not in active_paths)
        if shadowed_paths:
            limitations.add("ENVIRONMENT_ROOT_MARKERS_SHADOWED")
        if not active_paths:
            limitations.add("ENVIRONMENT_ACTIVE_SCOPE_HAS_NO_RECOGNIZED_MARKER")

    if any(_marker_name(path) in _BUILD_INSTRUCTION_MARKERS for path in all_paths):
        limitations.add("ENVIRONMENT_BUILD_INSTRUCTIONS_NOT_EXECUTED")
    if any(_marker_name(path) == "REQUIRE" for path in all_paths):
        limitations.add("ENVIRONMENT_DECLARATION_DEPRECATED_UPSTREAM")

    declarations = []
    for path in all_paths:
        if environment_scope == "CONFLICT":
            scope_status = "UNRESOLVED"
        elif path in active_paths:
            scope_status = "ACTIVE"
        else:
            scope_status = "SHADOWED"
        declarations.append(
            {
                "kind": MARKER_KINDS[_marker_name(path)],
                "path": path,
                "scope_status": scope_status,
            }
        )

    details = {
        "active_environment_marker_paths": list(active_paths),
        "environment_declarations": declarations,
        "environment_scope": environment_scope,
        "shadowed_environment_marker_paths": list(shadowed_paths),
    }
    return marker_records[0], marker_records, tuple(sorted(limitations)), details


def _directory_present(
    all_records: Mapping[str, Dict[str, Any]], path: str
) -> bool:
    record = all_records.get(path)
    if record is not None and record.get("object_type") == "DIRECTORY":
        return True
    prefix = f"{path}/"
    return any(candidate.startswith(prefix) for candidate in all_records)


def _scope(path: str) -> Optional[str]:
    if "/" not in path:
        return "ROOT"
    parent, _, remainder = path.partition("/")
    if "/" in remainder:
        return None
    if parent == "binder":
        return "BINDER"
    if parent == ".binder":
        return "DOT_BINDER"
    return None


def _marker_name(path: str) -> str:
    return path.rsplit("/", 1)[-1]


def _path_bytes(path: str) -> bytes:
    return path.encode("utf-8", errors="surrogateescape")
