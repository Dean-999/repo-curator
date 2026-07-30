"""Bounded RO-Crate entity and reference observations from local JSON only.

Descriptor/root validation is adapted from ResearchObject/ro-crate-py
``rocrate/metadata.py`` at commit 05effe591443934e48e3fe59c53d7bc01a3334e0.
Copyright 2019-2026 the upstream RO-Crate Python contributors. Licensed under
Apache-2.0; see THIRD_PARTY_NOTICES.md. Network and mutable entity behavior are
intentionally excluded from this port.
"""

import re
from typing import Any, Dict, List, Tuple


ENTITY_LIMIT = 256
REFERENCE_LIMIT = 512
VALUE_NODE_LIMIT = 8192
TYPE_LIMIT = 32
EXTERNAL_ID_LIMIT = 64
UNRESOLVED_ID_LIMIT = 64
_DESCRIPTOR_IDS = ("ro-crate-metadata.json", "ro-crate-metadata.jsonld")
_URI_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")


def observe_ro_crate_graph(parsed: Any) -> Tuple[Dict[str, Any], Tuple[str, ...]]:
    """Return a bounded declaration graph without resolving any identifier."""
    empty = {
        "entities": [],
        "entity_count_in_scope": 0,
        "external_reference_ids": [],
        "metadata_descriptor_id": None,
        "reference_count_in_scope": 0,
        "references": [],
        "root_entity_id": None,
        "status": "UNAVAILABLE",
        "unresolved_reference_ids": [],
    }
    if not isinstance(parsed, dict) or "@context" not in parsed or not isinstance(
        parsed.get("@graph"), list
    ):
        return empty, ("RO_CRATE_GRAPH_SHAPE_INVALID",)

    limitations = set()
    entities: Dict[str, Dict[str, Any]] = {}
    for item in parsed["@graph"]:
        if len(entities) >= ENTITY_LIMIT:
            limitations.add("RO_CRATE_ENTITY_LIMIT")
            break
        if not isinstance(item, dict) or not isinstance(item.get("@id"), str) or not item["@id"]:
            limitations.add("RO_CRATE_ENTITY_MALFORMED")
            continue
        identifier = item["@id"]
        if identifier in entities:
            limitations.add("RO_CRATE_DUPLICATE_ENTITY_ID")
            continue
        entities[identifier] = item

    descriptor_id, root_id, root_limitations = _root_ids(entities)
    limitations.update(root_limitations)
    references, external_ids, unresolved_ids, reference_limitations = _references(
        entities
    )
    limitations.update(reference_limitations)
    summaries = [
        {"entity_id": identifier, "types": _types(entity)}
        for identifier, entity in sorted(entities.items())
    ]
    details = {
        "entities": summaries,
        "entity_count_in_scope": len(summaries),
        "external_reference_ids": external_ids[:EXTERNAL_ID_LIMIT],
        "metadata_descriptor_id": descriptor_id,
        "reference_count_in_scope": len(references),
        "references": references,
        "root_entity_id": root_id,
        "status": "OBSERVED_WITH_LIMITATIONS" if limitations else "OBSERVED",
        "unresolved_reference_ids": unresolved_ids[:UNRESOLVED_ID_LIMIT],
    }
    if len(external_ids) > EXTERNAL_ID_LIMIT:
        limitations.add("RO_CRATE_EXTERNAL_REFERENCE_LIMIT")
    if len(unresolved_ids) > UNRESOLVED_ID_LIMIT:
        limitations.add("RO_CRATE_UNRESOLVED_REFERENCE_LIMIT")
    return details, tuple(sorted(limitations))


def _root_ids(
    entities: Dict[str, Dict[str, Any]]
) -> Tuple[Any, Any, Tuple[str, ...]]:
    descriptor_id = next(
        (identifier for identifier in _DESCRIPTOR_IDS if identifier in entities), None
    )
    if descriptor_id is None:
        return None, None, ("RO_CRATE_DESCRIPTOR_MISSING",)
    descriptor = entities[descriptor_id]
    if "CreativeWork" not in _types(descriptor):
        return descriptor_id, None, ("RO_CRATE_DESCRIPTOR_INVALID",)
    about = descriptor.get("about")
    root_id = about.get("@id") if isinstance(about, dict) else None
    if not isinstance(root_id, str) or root_id not in entities:
        return descriptor_id, None, ("RO_CRATE_ROOT_MISSING",)
    if "Dataset" not in _types(entities[root_id]):
        return descriptor_id, None, ("RO_CRATE_ROOT_INVALID",)
    return descriptor_id, root_id, ()


def _types(entity: Dict[str, Any]) -> List[str]:
    value = entity.get("@type")
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return sorted({item for item in value if isinstance(item, str)})[:TYPE_LIMIT]
    return []


def _references(
    entities: Dict[str, Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], List[str], List[str], Tuple[str, ...]]:
    records = []
    external = set()
    unresolved = set()
    limitations = set()
    visited_nodes = 0
    for source_id, entity in sorted(entities.items()):
        for property_name, value in sorted(entity.items()):
            if property_name.startswith("@"):
                continue
            stack = [value]
            while stack:
                visited_nodes += 1
                if visited_nodes > VALUE_NODE_LIMIT:
                    limitations.add("RO_CRATE_VALUE_NODE_LIMIT")
                    stack.clear()
                    break
                current = stack.pop()
                if isinstance(current, list):
                    stack.extend(reversed(current))
                    continue
                if not isinstance(current, dict):
                    continue
                target_id = current.get("@id")
                if isinstance(target_id, str) and target_id:
                    target_present = target_id in entities
                    if len(records) < REFERENCE_LIMIT:
                        records.append(
                            {
                                "property": property_name,
                                "source_entity_id": source_id,
                                "target_entity_id": target_id,
                                "target_present": target_present,
                            }
                        )
                    else:
                        limitations.add("RO_CRATE_REFERENCE_LIMIT")
                    if not target_present:
                        if _URI_SCHEME.match(target_id):
                            external.add(target_id)
                        else:
                            unresolved.add(target_id)
                    continue
                stack.extend(reversed(list(current.values())))
    if external:
        limitations.add("RO_CRATE_EXTERNAL_REFERENCE_NOT_RETRIEVED")
    if unresolved:
        limitations.add("RO_CRATE_REFERENCE_UNRESOLVED")
    return (
        sorted(
            records,
            key=lambda item: (
                item["source_entity_id"],
                item["property"],
                item["target_entity_id"],
            ),
        ),
        sorted(external),
        sorted(unresolved),
        tuple(sorted(limitations)),
    )
