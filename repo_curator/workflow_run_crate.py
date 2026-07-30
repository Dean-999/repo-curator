"""Bounded declared action summaries from supplied Workflow Run RO-Crates.

The field model is adapted from Workflow Run RO-Crate 0.5 at commit
4add9f64a49d8c6a79cb34f146b35b887a60852d and nf-prov's WrrocRenderer at
commit 97d350065f89d7a98aad8506586b54bce32f1acb. Both are Apache-2.0; see
THIRD_PARTY_NOTICES.md. This port never resolves a context or executes a run.
"""

from typing import Any, Dict, List, Tuple

from repo_curator.ro_crate_graph import ENTITY_LIMIT, observe_ro_crate_graph


ACTION_LIMIT = 128
ACTION_REFERENCE_LIMIT = 64
INSTRUMENT_LIMIT = 8
_STATUS_BY_VALUE = {
    "CompletedActionStatus": "COMPLETED_DECLARED",
    "http://schema.org/CompletedActionStatus": "COMPLETED_DECLARED",
    "https://schema.org/CompletedActionStatus": "COMPLETED_DECLARED",
    "FailedActionStatus": "FAILED_DECLARED",
    "http://schema.org/FailedActionStatus": "FAILED_DECLARED",
    "https://schema.org/FailedActionStatus": "FAILED_DECLARED",
    "ActiveActionStatus": "ACTIVE_DECLARED",
    "http://schema.org/ActiveActionStatus": "ACTIVE_DECLARED",
    "https://schema.org/ActiveActionStatus": "ACTIVE_DECLARED",
    "PotentialActionStatus": "POTENTIAL_DECLARED",
    "http://schema.org/PotentialActionStatus": "POTENTIAL_DECLARED",
    "https://schema.org/PotentialActionStatus": "POTENTIAL_DECLARED",
}
_CREATE_ACTION_TYPES = {
    "CreateAction",
    "http://schema.org/CreateAction",
    "https://schema.org/CreateAction",
}


def observe_workflow_run_crate(
    parsed: Any,
) -> Tuple[Dict[str, Any], Tuple[str, ...]]:
    """Return declaration-only action summaries from one bounded local graph."""
    graph, graph_limitations = observe_ro_crate_graph(parsed)
    limitations = set(graph_limitations)
    if graph["root_entity_id"] is None:
        return _empty(graph), tuple(sorted(limitations))

    entities = _entities(parsed)
    action_entities = [
        (identifier, entity)
        for identifier, entity in sorted(entities.items())
        if _CREATE_ACTION_TYPES.intersection(_types(entity))
    ]
    if len(action_entities) > ACTION_LIMIT:
        limitations.add("WORKFLOW_RUN_ACTION_LIMIT")
    actions = []
    for identifier, entity in action_entities[:ACTION_LIMIT]:
        inputs, omitted_inputs, malformed_inputs = _reference_ids(
            entity.get("object"), ACTION_REFERENCE_LIMIT
        )
        outputs, omitted_outputs, malformed_outputs = _reference_ids(
            entity.get("result"), ACTION_REFERENCE_LIMIT
        )
        instruments, omitted_instruments, malformed_instruments = _reference_ids(
            entity.get("instrument"), INSTRUMENT_LIMIT
        )
        if omitted_inputs:
            limitations.add("WORKFLOW_RUN_ACTION_INPUT_LIMIT")
        if omitted_outputs:
            limitations.add("WORKFLOW_RUN_ACTION_OUTPUT_LIMIT")
        if omitted_instruments:
            limitations.add("WORKFLOW_RUN_ACTION_INSTRUMENT_LIMIT")
        if malformed_inputs:
            limitations.add("WORKFLOW_RUN_ACTION_INPUT_MALFORMED")
        if malformed_outputs:
            limitations.add("WORKFLOW_RUN_ACTION_OUTPUT_MALFORMED")
        if malformed_instruments:
            limitations.add("WORKFLOW_RUN_ACTION_INSTRUMENT_MALFORMED")
        status = _normalize_status(entity.get("actionStatus"))
        if status == "UNRESOLVED":
            limitations.add("WORKFLOW_RUN_ACTION_STATUS_UNRESOLVED")
        actions.append(
            {
                "action_id": identifier,
                "input_ids": inputs,
                "instrument_ids": instruments,
                "malformed_input_count": malformed_inputs,
                "malformed_instrument_count": malformed_instruments,
                "malformed_output_count": malformed_outputs,
                "omitted_input_count": omitted_inputs,
                "omitted_instrument_count": omitted_instruments,
                "omitted_output_count": omitted_outputs,
                "output_ids": outputs,
                "status": status,
                "unresolved_input_ids": [
                    item for item in inputs if item not in entities
                ],
                "unresolved_instrument_ids": [
                    item for item in instruments if item not in entities
                ],
                "unresolved_output_ids": [
                    item for item in outputs if item not in entities
                ],
            }
        )
    return (
        {
            "action_count_in_scope": len(action_entities),
            "actions": actions,
            "graph": graph,
            "omitted_action_count": len(action_entities) - len(actions),
            "status": "OBSERVED_WITH_LIMITATIONS" if limitations else "OBSERVED",
        },
        tuple(sorted(limitations)),
    )


def _empty(graph: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "action_count_in_scope": 0,
        "actions": [],
        "graph": graph,
        "omitted_action_count": 0,
        "status": "UNAVAILABLE",
    }


def _entities(parsed: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    entities = {}
    for item in parsed.get("@graph", []):
        if len(entities) >= ENTITY_LIMIT:
            break
        if not isinstance(item, dict):
            continue
        identifier = item.get("@id")
        if isinstance(identifier, str) and identifier and identifier not in entities:
            entities[identifier] = item
    return entities


def _types(entity: Dict[str, Any]) -> List[str]:
    value = entity.get("@type")
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def _reference_ids(value: Any, limit: int) -> Tuple[List[str], int, int]:
    values = value if isinstance(value, list) else ([] if value is None else [value])
    malformed_count = sum(
        1
        for item in values
        if not (
            isinstance(item, dict)
            and isinstance(item.get("@id"), str)
            and item["@id"]
        )
    )
    identifiers = sorted(
        {
            item["@id"]
            for item in values
            if isinstance(item, dict)
            and isinstance(item.get("@id"), str)
            and item["@id"]
        }
    )
    return identifiers[:limit], max(0, len(identifiers) - limit), malformed_count


def _normalize_status(value: Any) -> str:
    if isinstance(value, dict):
        value = value.get("@id")
    if not isinstance(value, str):
        return "UNRESOLVED"
    return _STATUS_BY_VALUE.get(value, "UNRESOLVED")
