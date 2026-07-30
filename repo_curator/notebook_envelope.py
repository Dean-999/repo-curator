"""Bounded notebook-envelope observations without execution or output trust.

JSON parsing and explicit notebook-version observation are adapted from
Jupyter/nbformat ``nbformat/reader.py`` and ``nbformat/v4/nbjson.py`` at commit
4421827289087d37e57ee770e115a13db9a45dd5. Copyright 2001-2015 the IPython
Development Team and 2015-2026 the Jupyter Development Team. Licensed under
BSD-3-Clause; see THIRD_PARTY_NOTICES.md. Schema validation, version conversion,
NotebookNode construction, source persistence, output persistence, widgets,
and kernel execution are intentionally excluded.
"""

import json
from typing import Any, Dict, List, Tuple


CELL_LIMIT = 10_000
OUTPUT_LIMIT = 10_000
METADATA_STRING_LIMIT = 256
_CELL_TYPES = {"code", "markdown", "raw"}
_OUTPUT_TYPES = {
    "display_data",
    "error",
    "execute_result",
    "stream",
    "update_display_data",
}


def observe_notebook_envelope(
    content: bytes, truncated: bool = False
) -> Tuple[Dict[str, Any], Tuple[str, ...]]:
    """Return a controlled notebook summary without retaining cell content."""
    if truncated:
        return {}, ("NOTEBOOK_ENVELOPE_TRUNCATED",)
    try:
        parsed = json.loads(
            content.decode("utf-8"), parse_constant=_reject_json_constant
        )
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError, RecursionError):
        return {}, ("NOTEBOOK_ENVELOPE_MALFORMED",)
    if not isinstance(parsed, dict):
        return {}, ("NOTEBOOK_ENVELOPE_NOT_OBJECT",)

    major = parsed.get("nbformat")
    minor = parsed.get("nbformat_minor")
    if (
        not isinstance(major, int)
        or isinstance(major, bool)
        or major < 1
        or not isinstance(minor, int)
        or isinstance(minor, bool)
        or minor < 0
    ):
        return {}, ("NOTEBOOK_VERSION_MALFORMED",)

    metadata: Dict[str, Any] = {"nbformat": major, "nbformat_minor": minor}
    limitations = {
        "NOTEBOOK_EXECUTION_NOT_VERIFIED",
        "NOTEBOOK_SCHEMA_NOT_VALIDATED",
    }
    if major != 4:
        limitations.add("NOTEBOOK_VERSION_UNSUPPORTED_FOR_CELL_SUMMARY")
        return metadata, tuple(sorted(limitations))

    cells = parsed.get("cells")
    if not isinstance(cells, list):
        limitations.add("NOTEBOOK_CELLS_MALFORMED")
        return metadata, tuple(sorted(limitations))
    if len(cells) > CELL_LIMIT:
        limitations.add("NOTEBOOK_CELL_LIMIT")
    cells = cells[:CELL_LIMIT]

    declared_metadata = parsed.get("metadata")
    if not isinstance(declared_metadata, dict):
        declared_metadata = {}
        limitations.add("NOTEBOOK_METADATA_MALFORMED")
    kernel = _selected_strings(
        declared_metadata.get("kernelspec"),
        ("display_name", "language", "name"),
        limitations,
    )
    language_info = _selected_strings(
        declared_metadata.get("language_info"),
        ("name", "version"),
        limitations,
    )

    cell_type_counts = {"code": 0, "markdown": 0, "raw": 0, "unknown": 0}
    output_type_counts = {
        "display_data": 0,
        "error": 0,
        "execute_result": 0,
        "stream": 0,
        "update_display_data": 0,
        "unknown": 0,
    }
    cells_with_execution_count = 0
    cells_with_outputs = 0
    output_count = 0
    source_present = False
    for cell in cells:
        if not isinstance(cell, dict):
            cell_type_counts["unknown"] += 1
            limitations.add("NOTEBOOK_CELL_MALFORMED")
            continue
        cell_type = cell.get("cell_type")
        cell_type_counts[cell_type if cell_type in _CELL_TYPES else "unknown"] += 1
        if "source" in cell:
            source_present = True
        execution_count = cell.get("execution_count")
        if execution_count is not None:
            if isinstance(execution_count, int) and not isinstance(execution_count, bool):
                cells_with_execution_count += 1
            else:
                limitations.add("NOTEBOOK_EXECUTION_COUNT_MALFORMED")
        outputs = cell.get("outputs")
        if outputs is None:
            continue
        if not isinstance(outputs, list):
            limitations.add("NOTEBOOK_OUTPUTS_MALFORMED")
            continue
        if outputs:
            cells_with_outputs += 1
        for output in outputs:
            if output_count >= OUTPUT_LIMIT:
                limitations.add("NOTEBOOK_OUTPUT_LIMIT")
                break
            output_count += 1
            output_type = output.get("output_type") if isinstance(output, dict) else None
            key = output_type if output_type in _OUTPUT_TYPES else "unknown"
            output_type_counts[key] += 1
            if not isinstance(output, dict):
                limitations.add("NOTEBOOK_OUTPUT_MALFORMED")

    if source_present:
        limitations.add("NOTEBOOK_SOURCE_NOT_PERSISTED")
    if output_count:
        limitations.add("NOTEBOOK_OUTPUTS_UNTRUSTED_NOT_PERSISTED")
    metadata.update(
        {
            "cell_count": len(cells),
            "cell_type_counts": _nonzero(cell_type_counts),
            "cells_with_execution_count": cells_with_execution_count,
            "cells_with_outputs": cells_with_outputs,
            "kernel": kernel,
            "language_info": language_info,
            "output_count": output_count,
            "output_type_counts": _nonzero(output_type_counts),
        }
    )
    return metadata, tuple(sorted(limitations))


def _selected_strings(
    value: Any, keys: Tuple[str, ...], limitations: set
) -> Dict[str, str]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        limitations.add("NOTEBOOK_METADATA_MALFORMED")
        return {}
    selected = {}
    for key in keys:
        declared = value.get(key)
        if declared is None:
            continue
        if not isinstance(declared, str):
            limitations.add("NOTEBOOK_METADATA_MALFORMED")
        elif len(declared.encode("utf-8")) > METADATA_STRING_LIMIT:
            limitations.add("NOTEBOOK_METADATA_STRING_LIMIT")
        else:
            selected[key] = declared
    return selected


def _nonzero(values: Dict[str, int]) -> Dict[str, int]:
    return {key: value for key, value in values.items() if value}


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant: {value}")
