"""Bounded observations of research-software metadata declarations.

The signac filename constants below are adapted from ``signac/project.py``,
``signac/job.py``, and ``signac/_config.py`` at upstream commit
9419e3c71900bbbd6a4a177ac91ae895d1290b2d (BSD-3-Clause).  This module keeps
only the stable filesystem contract; it does not import signac, parse its
metadata, discover projects by walking outside the selected root, or execute
target code.
"""

import bisect
from typing import Any, Dict, Mapping, Optional, Tuple


SIGNAC_PROJECT_CONFIG = ".signac/config"
SIGNAC_PROJECT_DOCUMENT = "signac_project_document.json"
SIGNAC_STATEPOINT_CACHE = ".signac/statepoint_cache.json.gz"
SIGNAC_STATEPOINT = "signac_statepoint.json"
SIGNAC_JOB_DOCUMENT = "signac_job_document.json"
SIGNAC_MARKER_LIMIT = 256
CITATION_CFF = "CITATION.cff"
CODEMETA_JSON = "codemeta.json"

# CodeMeta vocabulary terms are used only as a disclosure-resistant allowlist.
# Values and unknown keys are intentionally never copied into an observation.
CODEMETA_DECLARATION_FIELDS = frozenset(
    {
        "@context",
        "@id",
        "@type",
        "applicationCategory",
        "author",
        "citation",
        "codeRepository",
        "codemeta:contIntegration",
        "contributor",
        "copyrightHolder",
        "copyrightYear",
        "dateCreated",
        "dateModified",
        "datePublished",
        "description",
        "developmentStatus",
        "downloadUrl",
        "editor",
        "email",
        "embargoDate",
        "funder",
        "funding",
        "hasPart",
        "identifier",
        "isAccessibleForFree",
        "isPartOf",
        "keywords",
        "license",
        "maintainer",
        "memoryRequirements",
        "name",
        "operatingSystem",
        "permissions",
        "position",
        "processorRequirements",
        "producer",
        "programmingLanguage",
        "provider",
        "publisher",
        "readme",
        "referencePublication",
        "releaseNotes",
        "review",
        "runtimePlatform",
        "sameAs",
        "softwareHelp",
        "softwareRequirements",
        "softwareSuggestions",
        "softwareVersion",
        "sponsor",
        "storageRequirements",
        "supportingData",
        "targetProduct",
        "url",
        "version",
    }
)


def signac_candidate(
    all_records: Mapping[str, Dict[str, Any]],
) -> Optional[
    Tuple[
        Dict[str, Any],
        Tuple[Dict[str, Any], ...],
        Tuple[str, ...],
        Dict[str, Any],
    ]
]:
    """Return a capped, inventory-only signac declaration candidate."""
    counts = {
        "project_config": 0,
        "project_document": 0,
        "statepoint_cache": 0,
        "statepoint": 0,
        "job_document": 0,
    }
    retained = []
    total = 0
    for path, record in all_records.items():
        if record["object_type"] != "REGULAR_FILE":
            continue
        category = _signac_category(path)
        if category is None:
            continue
        counts[category] += 1
        total += 1
        item = (_path_bytes(record), record)
        if len(retained) < SIGNAC_MARKER_LIMIT:
            bisect.insort(retained, item)
        elif item[0] < retained[-1][0]:
            bisect.insort(retained, item)
            retained.pop()

    if not retained:
        return None

    limitations = ["SIGNAC_METADATA_CONTENT_NOT_PARSED"]
    if total > SIGNAC_MARKER_LIMIT:
        limitations.append("SIGNAC_MARKER_LIMIT")
    marker_records = tuple(record for _, record in retained)
    details = {
        "signac": {
            "job_document_count": counts["job_document"],
            "project_config_present": bool(counts["project_config"]),
            "project_document_count": counts["project_document"],
            "statepoint_cache_present": bool(counts["statepoint_cache"]),
            "statepoint_count": counts["statepoint"],
        }
    }
    return marker_records[0], marker_records, tuple(limitations), details


def is_sensitive_research_metadata_path(path: str) -> bool:
    """Return whether generic profiling must defer to a controlled observer."""
    return path in {CITATION_CFF, CODEMETA_JSON} or _signac_category(path) is not None


def observe_codemeta(parsed: Any) -> Tuple[Dict[str, Any], Tuple[str, ...]]:
    """Summarize a syntax-valid CodeMeta object without retaining values."""
    limitations = (
        "CODEMETA_CONTEXT_NOT_RESOLVED",
        "CODEMETA_SCHEMA_NOT_VALIDATED",
        "CODEMETA_VALUES_NOT_PERSISTED",
    )
    if not isinstance(parsed, dict):
        return {}, (*limitations, "CODEMETA_ROOT_NOT_OBJECT")
    return {
        "codemeta": {
            "author_count_declared": _declared_count(parsed.get("author")),
            "declared_fields": sorted(
                key
                for key in parsed
                if isinstance(key, str) and key in CODEMETA_DECLARATION_FIELDS
            ),
            "programming_language_count_declared": _declared_count(
                parsed.get("programmingLanguage")
            ),
        }
    }, limitations


def _declared_count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    return 0 if value is None else 1


def _signac_category(path: str) -> Optional[str]:
    basename = path.rsplit("/", 1)[-1]
    if path == SIGNAC_PROJECT_CONFIG or path.endswith(f"/{SIGNAC_PROJECT_CONFIG}"):
        return "project_config"
    if path == SIGNAC_STATEPOINT_CACHE or path.endswith(f"/{SIGNAC_STATEPOINT_CACHE}"):
        return "statepoint_cache"
    if basename == SIGNAC_PROJECT_DOCUMENT:
        return "project_document"
    if basename == SIGNAC_STATEPOINT:
        return "statepoint"
    if basename == SIGNAC_JOB_DOCUMENT:
        return "job_document"
    return None


def _path_bytes(record: Dict[str, Any]) -> bytes:
    return record["repository_relative_path"].encode(
        "utf-8", errors="surrogateescape"
    )
