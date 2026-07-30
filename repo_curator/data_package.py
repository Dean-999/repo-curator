"""Bounded Data Package descriptor observation for untrusted JSON values.

Package/resource field selection is adapted from Frictionless Framework at
commit 52ec5477f07612639b1505edc669128ce5e49a30. Copyright 2020 Open
Knowledge Foundation, MIT License; see THIRD_PARTY_NOTICES.md. Resource reads,
schema validation, inference, dereferencing, plugins, and network access are
intentionally excluded.
"""

import re
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple
from urllib.parse import urlsplit


RESOURCE_LIMIT = 128
PATHS_PER_RESOURCE_LIMIT = 16
PATH_BYTES_LIMIT = 4096
_NAME = re.compile(r"[a-z0-9._-]{1,100}")
_FORMAT = re.compile(r"[A-Za-z0-9.+_-]{1,64}")
_MEDIATYPE = re.compile(r"[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+")
_WINDOWS_DRIVE = re.compile(r"[A-Za-z]:")


def observe_data_package(
    parsed: Any,
    descriptor_path: str,
    inventory_records: Mapping[str, Dict[str, Any]],
) -> Tuple[Dict[str, Any], Tuple[str, ...]]:
    """Return content-free package/resource structure and explicit limitations."""
    limitations: Set[str] = {
        "DATA_PACKAGE_DIALECT_NOT_PARSED",
        "DATA_PACKAGE_RESOURCE_PAYLOADS_NOT_OPENED",
        "DATA_PACKAGE_TABLE_SCHEMA_NOT_PARSED",
    }
    package = {
        "declared_name": None,
        "descriptor_path": descriptor_path,
        "profile_declared": False,
        "resource_count_declared": None,
        "resources": [],
    }
    if not isinstance(parsed, dict):
        limitations.add("DATA_PACKAGE_ROOT_NOT_OBJECT")
        return {"data_package": package}, tuple(sorted(limitations))

    name = parsed.get("name")
    if isinstance(name, str) and _NAME.fullmatch(name):
        package["declared_name"] = name
    elif name is not None:
        limitations.add("DATA_PACKAGE_NAME_NOT_SAFE_TOKEN")
    package["profile_declared"] = any(
        isinstance(parsed.get(key), str) for key in ("profile", "$schema")
    )

    resources = parsed.get("resources")
    if resources is None:
        package["resource_count_declared"] = 0
        limitations.add("DATA_PACKAGE_RESOURCES_MISSING")
        return {"data_package": package}, tuple(sorted(limitations))
    if not isinstance(resources, list):
        limitations.add("DATA_PACKAGE_RESOURCES_NOT_LIST")
        return {"data_package": package}, tuple(sorted(limitations))

    package["resource_count_declared"] = len(resources)
    if len(resources) > RESOURCE_LIMIT:
        limitations.add("DATA_PACKAGE_RESOURCE_LIMIT")
    observed_resources: List[Dict[str, Any]] = []
    for index, resource in enumerate(resources[:RESOURCE_LIMIT]):
        summary, resource_limitations = _observe_resource(
            resource, index, descriptor_path, inventory_records
        )
        observed_resources.append(summary)
        limitations.update(resource_limitations)
    package["resources"] = observed_resources
    return {"data_package": package}, tuple(sorted(limitations))


def _observe_resource(
    resource: Any,
    index: int,
    descriptor_path: str,
    inventory_records: Mapping[str, Dict[str, Any]],
) -> Tuple[Dict[str, Any], Set[str]]:
    limitations: Set[str] = set()
    summary: Dict[str, Any] = {"index": index}
    if not isinstance(resource, dict):
        summary["source_kind"] = "INVALID_RESOURCE"
        limitations.add("DATA_PACKAGE_RESOURCE_ENTRY_NOT_OBJECT")
        return summary, limitations

    name = resource.get("name")
    if isinstance(name, str) and _NAME.fullmatch(name):
        summary["name"] = name
    elif name is not None:
        limitations.add("DATA_PACKAGE_RESOURCE_NAME_NOT_SAFE_TOKEN")
    _copy_safe_token(resource, summary, "format", "declared_format", _FORMAT, limitations)
    _copy_safe_token(
        resource, summary, "mediatype", "declared_mediatype", _MEDIATYPE, limitations
    )
    _copy_safe_token(
        resource, summary, "compression", "declared_compression", _FORMAT, limitations
    )
    summary["schema_kind"] = _schema_kind(resource.get("schema"))

    raw_paths = _resource_paths(resource, limitations)
    has_inline = "data" in resource and resource.get("data") is not None
    if has_inline:
        limitations.add("DATA_PACKAGE_INLINE_DATA_NOT_PERSISTED")
    local_paths = []
    remote_count = 0
    unsafe_count = 0
    for raw_path in raw_paths[:PATHS_PER_RESOURCE_LIMIT]:
        if _is_remote(raw_path):
            remote_count += 1
            limitations.add("DATA_PACKAGE_REMOTE_RESOURCES_NOT_ACCESSED")
            continue
        resolved = _resolve_local_path(descriptor_path, raw_path)
        if resolved is None:
            unsafe_count += 1
            limitations.add("DATA_PACKAGE_RESOURCE_PATH_UNSAFE")
            continue
        record = inventory_records.get(resolved)
        inventory_status = (
            "MISSING"
            if record is None
            else "PRESENT"
            if record.get("object_type") == "REGULAR_FILE"
            else "PRESENT_NON_REGULAR"
        )
        if inventory_status == "MISSING":
            limitations.add("DATA_PACKAGE_LOCAL_RESOURCE_MISSING")
        elif inventory_status == "PRESENT_NON_REGULAR":
            limitations.add("DATA_PACKAGE_LOCAL_RESOURCE_NON_REGULAR")
        local_paths.append(
            {
                "inventory_status": inventory_status,
                "repository_relative_path": resolved,
            }
        )
    if local_paths:
        summary["local_paths"] = local_paths
    summary["source_kind"] = _source_kind(
        has_inline, len(raw_paths), len(local_paths), remote_count, unsafe_count
    )
    return summary, limitations


def _resource_paths(resource: Dict[str, Any], limitations: Set[str]) -> List[str]:
    paths: List[str] = []
    path = resource.get("path")
    if isinstance(path, str):
        paths.append(path)
    elif path is not None:
        limitations.add("DATA_PACKAGE_RESOURCE_PATH_TYPE_UNSUPPORTED")
    extrapaths = resource.get("extrapaths")
    if isinstance(extrapaths, list):
        for item in extrapaths:
            if isinstance(item, str):
                paths.append(item)
            else:
                limitations.add("DATA_PACKAGE_RESOURCE_PATH_TYPE_UNSUPPORTED")
    elif extrapaths is not None:
        limitations.add("DATA_PACKAGE_RESOURCE_PATH_TYPE_UNSUPPORTED")
    if len(paths) > PATHS_PER_RESOURCE_LIMIT:
        limitations.add("DATA_PACKAGE_RESOURCE_PATH_LIMIT")
    return paths


def _resolve_local_path(descriptor_path: str, value: str) -> Optional[str]:
    if (
        not value
        or len(value.encode("utf-8", errors="surrogateescape")) > PATH_BYTES_LIMIT
        or any(ord(character) < 32 for character in value)
        or "\\" in value
        or "?" in value
        or "#" in value
        or value.startswith(("/", "//"))
        or _WINDOWS_DRIVE.match(value)
    ):
        return None
    components = descriptor_path.split("/")[:-1]
    for component in value.split("/"):
        if component in {"", "."}:
            continue
        if component == "..":
            if not components:
                return None
            components.pop()
            continue
        components.append(component)
    return "/".join(components) if components else None


def _is_remote(value: str) -> bool:
    if _WINDOWS_DRIVE.match(value):
        return False
    if value.startswith("//"):
        return True
    try:
        return bool(urlsplit(value).scheme)
    except ValueError:
        return True


def _source_kind(
    has_inline: bool,
    path_count: int,
    local_count: int,
    remote_count: int,
    unsafe_count: int,
) -> str:
    if has_inline and path_count:
        return "MULTIPLE_SOURCES"
    if has_inline:
        return "INLINE_DATA"
    if not path_count:
        return "MISSING_SOURCE"
    if remote_count and (local_count or unsafe_count):
        return "MIXED_PATHS"
    if remote_count:
        return "REMOTE_PATH"
    if unsafe_count and not local_count:
        return "UNSAFE_PATH"
    if path_count > 1:
        return "MULTIPART_LOCAL"
    return "LOCAL_PATH"


def _schema_kind(value: Any) -> str:
    if value is None:
        return "ABSENT"
    if isinstance(value, dict):
        return "INLINE_OBJECT"
    if isinstance(value, str):
        return "REFERENCE_STRING"
    return "UNSUPPORTED"


def _copy_safe_token(
    source: Dict[str, Any],
    target: Dict[str, Any],
    source_key: str,
    target_key: str,
    pattern: re.Pattern[str],
    limitations: Set[str],
) -> None:
    value = source.get(source_key)
    if isinstance(value, str) and pattern.fullmatch(value):
        target[target_key] = value
    elif value is not None:
        limitations.add("DATA_PACKAGE_RESOURCE_TOKEN_NOT_PERSISTED")
