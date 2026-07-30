"""Conservative declared change-episode and capability-family candidates."""

import json
import os
import stat
from typing import Any, Dict, List, Mapping, Sequence, Tuple


EPISODE_SCHEMA_VERSION = "repo-curator.change-episode.v1"
FAMILY_SCHEMA_VERSION = "repo-curator.capability-family.v1"
ROLE_SCHEMA_VERSION = "repo-curator.implementation-role.v1"
MANIFEST_NAME = "relationship-manifest.json"
_READ_LIMIT = 1024 * 1024
MAX_GIT_CHANGE_EPISODE_MEMBERS = 64
_ROLES = {"ACTIVE_MAINLINE", "REQUIRED_COMPATIBILITY", "HISTORICAL_EVIDENCE", "EXPERIMENTAL_ACTIVE"}


def build_relationship_candidates(
    root_fd: int,
    inventory_records: Sequence[Dict[str, Any]],
    run_id: str,
    created_at: str,
    git_observations: Sequence[Dict[str, Any]] = (),
    structural_observations: Sequence[Dict[str, Any]] = (),
    mainline: Sequence[Dict[str, Any]] = (),
    evidence_by_source_id: Mapping[str, str] = (),
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    Dict[str, Dict[str, Any]],
    List[str],
]:
    inventory = {record["repository_relative_path"]: record for record in inventory_records}
    git_history_available = any(
        observation.get("observation_type") == "GIT_COMMIT"
        for observation in git_observations
    )
    git_history_limitations = sorted(
        {
            limitation
            for observation in git_observations
            if observation.get("observation_type") == "GIT_WORKTREE"
            for limitation in observation.get("limitations", [])
            if limitation.startswith("GIT_SHALLOW_")
        }
    )
    git_episodes = _git_episodes(
        git_observations,
        inventory,
        run_id,
        created_at,
        evidence_by_source_id=evidence_by_source_id,
    )
    oversized_git_cochange = _has_oversized_git_cochange(
        git_observations, inventory
    )
    declared = []
    manifest_available = MANIFEST_NAME in inventory
    if not manifest_available:
        roles = _roles(
            inventory_records,
            [],
            run_id,
            created_at,
            structural_observations,
            mainline,
            evidence_by_source_id,
        )
        coverage = _coverage_without_manifest(
            roles,
            len(git_episodes),
            git_history_available,
            oversized_git_cochange,
            structural_observations,
        )
        _extend_git_history_limitations(coverage, git_history_limitations)
        return (
            git_episodes,
            [],
            roles,
            coverage,
            _coverage_warnings(coverage),
        )
    try:
        manifest = _read_manifest(root_fd)
    except ValueError as error:
        roles = _roles(
            inventory_records,
            [],
            run_id,
            created_at,
            structural_observations,
            mainline,
            evidence_by_source_id,
        )
        coverage = _coverage_without_manifest(
            roles,
            len(git_episodes),
            git_history_available,
            oversized_git_cochange,
            structural_observations,
            str(error),
        )
        _extend_git_history_limitations(coverage, git_history_limitations)
        return git_episodes, [], roles, coverage, _coverage_warnings(coverage)
    declarations = manifest.get("artifacts")
    if not isinstance(declarations, list):
        roles = _roles(
            inventory_records,
            [],
            run_id,
            created_at,
            structural_observations,
            mainline,
            evidence_by_source_id,
        )
        coverage = _coverage_without_manifest(
            roles,
            len(git_episodes),
            git_history_available,
            oversized_git_cochange,
            structural_observations,
            "RELATIONSHIP_MANIFEST_MALFORMED",
        )
        _extend_git_history_limitations(coverage, git_history_limitations)
        return git_episodes, [], roles, coverage, _coverage_warnings(coverage)
    for item in declarations:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or item["path"] not in inventory:
            continue
        declared.append(item)
    episodes = _episodes(
        declared, inventory, run_id, created_at, evidence_by_source_id
    )
    episodes.extend(
        _git_episodes(
            git_observations,
            inventory,
            run_id,
            created_at,
            start_sequence=len(episodes),
            evidence_by_source_id=evidence_by_source_id,
        )
    )
    families = _families(
        declared, inventory, run_id, created_at, evidence_by_source_id
    )
    roles = _roles(
        inventory_records,
        declared,
        run_id,
        created_at,
        structural_observations,
        mainline,
        evidence_by_source_id,
    )
    coverage = _declared_coverage(
        episodes,
        families,
        roles,
        git_history_available,
        oversized_git_cochange,
        structural_observations,
    )
    _extend_git_history_limitations(coverage, git_history_limitations)
    return episodes, families, roles, coverage, _coverage_warnings(coverage)


def _unavailable_coverage(
    roles: Sequence[Dict[str, Any]], extra_limitation: str = ""
) -> Dict[str, Dict[str, Any]]:
    extra = [extra_limitation] if extra_limitation else []
    return {
        "capability_family": {
            "candidate_count": 0,
            "limitations": sorted(
                set(["CAPABILITY_FAMILY_EVIDENCE_UNAVAILABLE", *extra])
            ),
            "status": "UNAVAILABLE",
        },
        "change_episode": {
            "candidate_count": 0,
            "limitations": sorted(
                set(["CHANGE_EPISODE_EVIDENCE_UNAVAILABLE", *extra])
            ),
            "status": "UNAVAILABLE",
        },
        "implementation_role": {
            "limitations": sorted(
                set(["IMPLEMENTATION_ROLE_EVIDENCE_UNAVAILABLE", *extra])
            ),
            "resolved_artifact_count": 0,
            "status": "UNAVAILABLE",
            "total_artifact_count": len(roles),
        },
    }


def _extend_git_history_limitations(
    coverage: Dict[str, Dict[str, Any]], limitations: Sequence[str]
) -> None:
    if limitations:
        change_episode = coverage["change_episode"]
        change_episode["limitations"] = sorted(
            set(change_episode["limitations"] + list(limitations))
        )


def _declared_coverage(
    episodes: Sequence[Dict[str, Any]],
    families: Sequence[Dict[str, Any]],
    roles: Sequence[Dict[str, Any]],
    git_history_available: bool = False,
    oversized_git_cochange: bool = False,
    structural_observations: Sequence[Dict[str, Any]] = (),
) -> Dict[str, Dict[str, Any]]:
    resolved_roles = sum(role["role"] != "UNRESOLVED" for role in roles)
    return {
        "capability_family": {
            "candidate_count": len(families),
            "limitations": (
                ["CAPABILITY_FAMILY_DECLARED_ONLY"]
                if families
                else [
                    "CAPABILITY_FAMILY_SYNTAX_ONLY_NO_EQUIVALENCE",
                    "PYTHON_SYNTAX_NOT_RUNTIME_BEHAVIOR",
                ]
                if structural_observations
                else ["CAPABILITY_FAMILY_EVIDENCE_UNAVAILABLE"]
            ),
            "status": "AVAILABLE_DECLARED_ONLY" if families else (
                "PARTIAL_SYNTAX_ONLY" if structural_observations else "UNAVAILABLE"
            ),
        },
        "change_episode": _change_episode_coverage(
            episodes, git_history_available, oversized_git_cochange
        ),
        "implementation_role": {
            "limitations": (
                ["IMPLEMENTATION_ROLE_DECLARED_ONLY"]
                if resolved_roles
                else ["PYTHON_SYNTAX_NOT_RUNTIME_BEHAVIOR"]
                if structural_observations
                else ["IMPLEMENTATION_ROLE_EVIDENCE_UNAVAILABLE"]
            ),
            "resolved_artifact_count": resolved_roles,
            "status": "PARTIAL_DECLARED_ONLY" if resolved_roles else (
                "PARTIAL_SYNTAX_ONLY" if structural_observations else "UNAVAILABLE"
            ),
            "total_artifact_count": len(roles),
        },
}


def _coverage_without_manifest(
    roles: Sequence[Dict[str, Any]],
    git_episode_count: int,
    git_history_available: bool,
    oversized_git_cochange: bool,
    structural_observations: Sequence[Dict[str, Any]],
    extra_limitation: str = "",
) -> Dict[str, Dict[str, Any]]:
    coverage = _unavailable_coverage(roles)
    if git_history_available:
        limitations = []
        if git_episode_count:
            limitations.append("GIT_COCHANGE_NOT_COMMON_PURPOSE")
        if oversized_git_cochange:
            limitations.append("GIT_COCHANGE_MEMBER_LIMIT")
        if not limitations:
            limitations.append("NO_MULTI_ARTIFACT_CURRENT_COCHANGE")
        coverage["change_episode"] = {
            "candidate_count": git_episode_count,
            "limitations": sorted(set(limitations)),
            "status": "AVAILABLE_GIT_COCHANGE_ONLY",
        }
    if structural_observations:
        resolved_roles = sum(role["role"] != "UNRESOLVED" for role in roles)
        coverage["capability_family"] = {
            "candidate_count": 0,
            "limitations": [
                "CAPABILITY_FAMILY_SYNTAX_ONLY_NO_EQUIVALENCE",
                "PYTHON_SYNTAX_NOT_RUNTIME_BEHAVIOR",
            ],
            "status": "PARTIAL_SYNTAX_ONLY",
        }
        coverage["implementation_role"] = {
            "limitations": ["PYTHON_SYNTAX_NOT_RUNTIME_BEHAVIOR"],
            "resolved_artifact_count": resolved_roles,
            "status": "PARTIAL_SYNTAX_ONLY",
            "total_artifact_count": len(roles),
        }
    if extra_limitation:
        for state in coverage.values():
            state["limitations"] = sorted(
                set([*state["limitations"], extra_limitation])
            )
    return coverage


def _coverage_warnings(coverage: Dict[str, Dict[str, Any]]) -> List[str]:
    return sorted(
        {
            limitation
            for state in coverage.values()
            for limitation in state["limitations"]
        }
    )


def _episodes(
    declared: List[Dict[str, Any]],
    inventory: Dict[str, Dict[str, Any]],
    run_id: str,
    created_at: str,
    evidence_by_source_id: Mapping[str, str],
) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for item in declared:
        if isinstance(item.get("episode"), str) and item["episode"]:
            groups.setdefault(item["episode"], []).append(item)
    records = []
    for event, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        records.append({
            "candidate_status": "CANDIDATE", "counter_evidence_ids": [], "created_at": created_at,
            "episode_id": f"episode_{run_id}_{len(records) + 1:08d}", "event_evidence": event,
            "limitations": ["DECLARED_EVENT_NOT_INDEPENDENTLY_VERIFIED"],
            "member_artifact_ids": [inventory[item["path"]]["artifact_id"] for item in members],
            "member_paths": sorted(item["path"] for item in members), "relationship_type": "CHANGE_EPISODE_CANDIDATE",
            "run_id": run_id, "schema_version": EPISODE_SCHEMA_VERSION,
            "supporting_evidence_ids": _artifact_evidence_ids(
                [inventory[item["path"]]["artifact_id"] for item in members],
                evidence_by_source_id,
            ),
        })
    return records


def _git_episodes(
    observations: Sequence[Dict[str, Any]],
    inventory: Dict[str, Dict[str, Any]],
    run_id: str,
    created_at: str,
    start_sequence: int = 0,
    evidence_by_source_id: Mapping[str, str] = (),
) -> List[Dict[str, Any]]:
    records = []
    for observation in observations:
        if observation.get("observation_type") != "GIT_COMMIT":
            continue
        members = _git_current_regular_members(observation, inventory)
        if len(members) < 2 or len(members) > MAX_GIT_CHANGE_EPISODE_MEMBERS:
            continue
        artifact_ids = [inventory[path]["artifact_id"] for path in members]
        records.append(
            {
                "candidate_status": "CANDIDATE",
                "counter_evidence_ids": [],
                "created_at": created_at,
                "episode_id": f"episode_{run_id}_{start_sequence + len(records) + 1:08d}",
                "event_evidence": observation["commit_id"],
                "limitations": ["GIT_COCHANGE_NOT_COMMON_PURPOSE"],
                "member_artifact_ids": artifact_ids,
                "member_paths": members,
                "relationship_type": "CHANGE_EPISODE_CANDIDATE",
                "run_id": run_id,
                "schema_version": EPISODE_SCHEMA_VERSION,
                "supporting_evidence_ids": _evidence_ids(
                    [observation["observation_id"], *artifact_ids],
                    evidence_by_source_id,
                ),
            }
        )
    return records


def _has_oversized_git_cochange(
    observations: Sequence[Dict[str, Any]], inventory: Dict[str, Dict[str, Any]]
) -> bool:
    return any(
        observation.get("observation_type") == "GIT_COMMIT"
        and len(_git_current_regular_members(observation, inventory))
        > MAX_GIT_CHANGE_EPISODE_MEMBERS
        for observation in observations
    )


def _git_current_regular_members(
    observation: Mapping[str, Any], inventory: Mapping[str, Dict[str, Any]]
) -> List[str]:
    return sorted(
        {
            path
            for path in observation.get("changed_paths", [])
            if path in inventory and inventory[path].get("object_type") == "REGULAR_FILE"
        }
    )


def _families(
    declared: List[Dict[str, Any]],
    inventory: Dict[str, Dict[str, Any]],
    run_id: str,
    created_at: str,
    evidence_by_source_id: Mapping[str, str],
) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}
    for item in declared:
        if isinstance(item.get("responsibility"), str) and item["responsibility"]:
            groups.setdefault(item["responsibility"], []).append(item)
    records = []
    for responsibility, members in sorted(groups.items()):
        if len(members) < 2:
            continue
        records.append({
            "candidate_status": "CANDIDATE", "counter_evidence_ids": [], "created_at": created_at,
            "family_id": f"family_{run_id}_{len(records) + 1:08d}",
            "limitations": ["DECLARED_RESPONSIBILITY_NOT_STRUCTURAL_EQUIVALENCE"],
            "member_artifact_ids": [inventory[item["path"]]["artifact_id"] for item in members],
            "member_paths": sorted(item["path"] for item in members), "relationship_type": "CAPABILITY_FAMILY_CANDIDATE",
            "responsibility": responsibility, "run_id": run_id, "schema_version": FAMILY_SCHEMA_VERSION,
            "supporting_evidence_ids": _artifact_evidence_ids(
                [inventory[item["path"]]["artifact_id"] for item in members],
                evidence_by_source_id,
            ),
        })
    return records


def _change_episode_coverage(
    episodes: Sequence[Dict[str, Any]],
    git_history_available: bool,
    oversized_git_cochange: bool,
) -> Dict[str, Any]:
    git_episode_count = sum(
        item.get("limitations") == ["GIT_COCHANGE_NOT_COMMON_PURPOSE"]
        for item in episodes
    )
    declared_episode_count = len(episodes) - git_episode_count
    if git_episode_count:
        limitations = ["GIT_COCHANGE_NOT_COMMON_PURPOSE"]
        if oversized_git_cochange:
            limitations.append("GIT_COCHANGE_MEMBER_LIMIT")
        if declared_episode_count:
            limitations.append("CHANGE_EPISODE_DECLARED_ONLY")
        return {
            "candidate_count": len(episodes),
            "limitations": sorted(set(limitations)),
            "status": (
                "AVAILABLE_GIT_COCHANGE_ONLY"
                if not declared_episode_count
                else "AVAILABLE_MIXED_EVIDENCE"
            ),
        }
    if declared_episode_count:
        limitations = ["CHANGE_EPISODE_DECLARED_ONLY"]
        if oversized_git_cochange:
            limitations.append("GIT_COCHANGE_MEMBER_LIMIT")
        return {
            "candidate_count": declared_episode_count,
            "limitations": limitations,
            "status": "AVAILABLE_DECLARED_ONLY",
        }
    if git_history_available:
        return {
            "candidate_count": 0,
            "limitations": (
                ["GIT_COCHANGE_MEMBER_LIMIT"]
                if oversized_git_cochange
                else ["NO_MULTI_ARTIFACT_CURRENT_COCHANGE"]
            ),
            "status": "AVAILABLE_GIT_COCHANGE_ONLY",
        }
    return {
        "candidate_count": 0,
        "limitations": ["CHANGE_EPISODE_EVIDENCE_UNAVAILABLE"],
        "status": "UNAVAILABLE",
    }


def _roles(
    inventory_records: Sequence[Dict[str, Any]],
    declared: List[Dict[str, Any]],
    run_id: str,
    created_at: str,
    structural_observations: Sequence[Dict[str, Any]] = (),
    mainline: Sequence[Dict[str, Any]] = (),
    evidence_by_source_id: Mapping[str, str] = (),
) -> List[Dict[str, Any]]:
    by_path = {item["path"]: item for item in declared if item.get("role") in _ROLES}
    structure_by_path = {
        item["repository_relative_path"]: item for item in structural_observations
    }
    mainline_by_path = {
        item["repository_relative_path"]: item
        for item in mainline
        if item.get("status") == "ACTIVE_MAINLINE"
    }
    records = []
    for record in inventory_records:
        if record["object_type"] != "REGULAR_FILE":
            continue
        declaration = by_path.get(record["repository_relative_path"])
        structural = structure_by_path.get(record["repository_relative_path"])
        syntax_mainline = (
            declaration is None
            and structural is not None
            and structural.get("has_main_guard") is True
            and record["repository_relative_path"] in mainline_by_path
        )
        records.append({
            "artifact_id": record["artifact_id"], "counter_evidence_ids": [], "created_at": created_at,
            "limitations": (
                ["DECLARED_ROLE_NOT_EXECUTION_AUTHORITY"]
                if declaration
                else ["PYTHON_SYNTAX_NOT_RUNTIME_BEHAVIOR"]
                if syntax_mainline
                else ["NO_ROLE_EVIDENCE"]
            ),
            "repository_relative_path": record["repository_relative_path"],
            "role": declaration["role"] if declaration else "ACTIVE_MAINLINE" if syntax_mainline else "UNRESOLVED", "run_id": run_id,
            "schema_version": ROLE_SCHEMA_VERSION,
            "supporting_evidence_ids": (
                _evidence_ids(
                    [record["artifact_id"]], evidence_by_source_id
                )
                if declaration
                else sorted(
                    set(
                        [
                            *mainline_by_path[record["repository_relative_path"]][
                                "supporting_evidence_ids"
                            ],
                            *(_evidence_ids(
                                [structural["structure_id"]], evidence_by_source_id
                            )),
                        ]
                    )
                )
                if syntax_mainline
                else []
            ),
        })
    return records


def _unresolved_roles(inventory_records: Sequence[Dict[str, Any]], run_id: str, created_at: str) -> List[Dict[str, Any]]:
    return _roles(inventory_records, [], run_id, created_at)


def _artifact_evidence_ids(
    artifact_ids: Sequence[str], evidence_by_source_id: Mapping[str, str]
) -> List[str]:
    return _evidence_ids(artifact_ids, evidence_by_source_id)


def _evidence_ids(
    source_ids: Sequence[str], evidence_by_source_id: Mapping[str, str]
) -> List[str]:
    return sorted(
        {
            evidence_by_source_id[source_id]
            for source_id in source_ids
            if source_id in evidence_by_source_id
        }
    )


def _read_manifest(root_fd: int) -> Dict[str, Any]:
    descriptor = os.open(MANIFEST_NAME, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), dir_fd=root_fd)
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise ValueError("RELATIONSHIP_MANIFEST_UNAVAILABLE")
        payload = os.read(descriptor, _READ_LIMIT + 1)
    finally:
        os.close(descriptor)
    if len(payload) > _READ_LIMIT:
        raise ValueError("RELATIONSHIP_MANIFEST_SIZE_LIMIT")
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, json.JSONDecodeError):
        raise ValueError("RELATIONSHIP_MANIFEST_MALFORMED")
    if not isinstance(value, dict):
        raise ValueError("RELATIONSHIP_MANIFEST_MALFORMED")
    return value
