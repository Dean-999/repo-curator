import ctypes
import errno
import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from repo_curator import __version__
from repo_curator.budgets import AuditBudgets
from repo_curator.brief import (
    bind_curation_brief,
    build_curation_brief,
    render_shadow_plan_markdown,
)
from repo_curator.archives import inspect_archives
from repo_curator.declarations import SYNTAX_LIMITATIONS, detect_declarations
from repo_curator.decisions import build_decision_questions
from repo_curator.documents import compare_documents
from repo_curator.evidence import (
    build_declared_experiment_relationships,
    build_evidence_graph,
)
from repo_curator.experiments import reconstruct_experiments
from repo_curator.git_evidence import collect_git_evidence
from repo_curator.intent import discover_intent
from repo_curator.profiles import profile_artifacts
from repo_curator.prior_runs import compare_with_prior_run
from repo_curator.relationships import build_relationship_candidates
from repo_curator.shadow import build_shadow_mode
from repo_curator.identity import (
    content_identity,
    location_identity,
    repository_state_identity,
)
from repo_curator.scanner import scan_root
from repo_curator.structural import observe_python_structure
from repo_curator.supplied_exports import detect_supplied_exports


RUN_ID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
RUN_SCHEMA_VERSION = "repo-curator.run.v1"
INVENTORY_SCHEMA_VERSION = "repo-curator.inventory.v1"
CONTROL_DIRECTORY_NAME = ".repo-curator"


def audit_repository(
    root: Path,
    run_id: str,
    created_at: str,
    budgets: AuditBudgets = AuditBudgets(),
    adapter_export_manifests: Iterable[Path] = (),
    compare_to_run_id: Optional[str] = None,
) -> Path:
    budgets.validate()
    resolved_root = root.resolve(strict=True)
    if not resolved_root.is_dir():
        raise ValueError(f"audit root is not a directory: {root}")
    if RUN_ID_PATTERN.fullmatch(run_id) is None:
        raise ValueError(
            "invalid run ID: use only letters, numbers, dot, underscore, or hyphen"
        )
    root_fd = os.open(resolved_root, _directory_open_flags())
    try:
        root_stat = os.fstat(root_fd)
        inventory_records = _inventory_records(
            resolved_root, run_id, created_at, root_fd, budgets
        )
        git_evidence = collect_git_evidence(
            resolved_root, root_fd, inventory_records, run_id, created_at
        )
        inventory_bytes = _json_lines(inventory_records)
        inventory_hash = hashlib.sha256(inventory_bytes).hexdigest()
        git_observations_bytes = _json_lines(git_evidence.observations)
        git_observations_hash = hashlib.sha256(git_observations_bytes).hexdigest()
        profiles = profile_artifacts(root_fd, inventory_records, run_id, created_at)
        profiles_bytes = _json_lines(profiles)
        profiles_hash = hashlib.sha256(profiles_bytes).hexdigest()
        structural_observations = observe_python_structure(
            root_fd, inventory_records, run_id, created_at
        )
        structural_bytes = _json_lines(structural_observations)
        structural_hash = hashlib.sha256(structural_bytes).hexdigest()
        archive_observations = inspect_archives(root_fd, inventory_records, run_id, created_at)
        archive_bytes = _json_lines(archive_observations)
        archive_hash = hashlib.sha256(archive_bytes).hexdigest()
        local_declaration_observations = detect_declarations(
            root_fd, inventory_records, run_id, created_at
        )
        observations = list(local_declaration_observations)
        observations.extend(
            detect_supplied_exports(
                tuple(adapter_export_manifests),
                run_id,
                created_at,
                start_sequence=len(observations),
            )
        )
        observations_bytes = _json_lines(observations)
        observations_hash = hashlib.sha256(observations_bytes).hexdigest()
        intent = discover_intent(root_fd, inventory_records, run_id, created_at)
        evidence, relationships = build_evidence_graph(
            inventory_records,
            observations,
            git_evidence.observations,
            profiles,
            archive_observations,
            structural_observations,
            run_id,
            created_at,
        )
        evidence.extend(intent.evidence)
        evidence_bytes = _json_lines(evidence)
        evidence_hash = hashlib.sha256(evidence_bytes).hexdigest()
        evidence_by_source_id = {
            record["source_record_id"]: record["evidence_id"] for record in evidence
        }
        declaration_evidence_by_artifact = _declaration_evidence_by_artifact(
            local_declaration_observations,
            evidence_by_source_id,
            inventory_records,
        )
        project_intent_bytes = _json_bytes(intent.project_intent)
        project_intent_hash = hashlib.sha256(project_intent_bytes).hexdigest()
        retention_policy_bytes = _json_bytes(intent.retention_policy)
        retention_policy_hash = hashlib.sha256(retention_policy_bytes).hexdigest()
        mainline_bytes = _json_lines(intent.mainline)
        mainline_hash = hashlib.sha256(mainline_bytes).hexdigest()
        intent_conflicts_bytes = _json_lines(intent.conflicts)
        intent_conflicts_hash = hashlib.sha256(intent_conflicts_bytes).hexdigest()
        decision_questions = build_decision_questions(intent.conflicts, run_id, created_at)
        decision_questions_bytes = _json_lines(decision_questions)
        decision_questions_hash = hashlib.sha256(decision_questions_bytes).hexdigest()
        user_decisions_bytes = _json_lines([])
        user_decisions_hash = hashlib.sha256(user_decisions_bytes).hexdigest()
        attempts, bundles, candidates, gaps, experiment_warnings = reconstruct_experiments(
            root_fd,
            inventory_records,
            evidence_by_source_id,
            run_id,
            created_at,
        )
        attempts_bytes = _json_lines(attempts)
        bundles_bytes = _json_lines(bundles)
        candidates_bytes = _json_lines(candidates)
        gaps_bytes = _json_lines(gaps)
        attempts_hash = hashlib.sha256(attempts_bytes).hexdigest()
        bundles_hash = hashlib.sha256(bundles_bytes).hexdigest()
        candidates_hash = hashlib.sha256(candidates_bytes).hexdigest()
        gaps_hash = hashlib.sha256(gaps_bytes).hexdigest()
        relationships.extend(
            build_declared_experiment_relationships(bundles, run_id, created_at)
        )
        relationships.sort(key=lambda item: item["relationship_id"])
        relationships_bytes = _json_lines(relationships)
        relationships_hash = hashlib.sha256(relationships_bytes).hexdigest()
        (
            episodes,
            families,
            implementation_roles,
            relationship_coverage,
            relationship_warnings,
        ) = build_relationship_candidates(
            root_fd,
            inventory_records,
            run_id,
            created_at,
            git_observations=git_evidence.observations,
            structural_observations=structural_observations,
            mainline=intent.mainline,
            evidence_by_source_id=evidence_by_source_id,
        )
        episodes_bytes = _json_lines(episodes)
        families_bytes = _json_lines(families)
        roles_bytes = _json_lines(implementation_roles)
        episodes_hash = hashlib.sha256(episodes_bytes).hexdigest()
        families_hash = hashlib.sha256(families_bytes).hexdigest()
        roles_hash = hashlib.sha256(roles_bytes).hexdigest()
        document_comparisons, canonical_entries, document_warnings = compare_documents(
            root_fd, inventory_records, run_id, created_at
        )
        document_comparisons_bytes = _json_lines(document_comparisons)
        canonical_entries_bytes = _json_lines(canonical_entries)
        document_comparisons_hash = hashlib.sha256(document_comparisons_bytes).hexdigest()
        canonical_entries_hash = hashlib.sha256(canonical_entries_bytes).hexdigest()
        prior_run_comparison = (
            compare_with_prior_run(
                root_fd,
                compare_to_run_id,
                inventory_records,
                intent.mainline,
                run_id,
                created_at,
            )
            if compare_to_run_id is not None
            else None
        )
        prior_run_comparison_bytes = (
            _json_bytes(prior_run_comparison) if prior_run_comparison is not None else None
        )
        prior_run_comparison_hash = (
            hashlib.sha256(prior_run_comparison_bytes).hexdigest()
            if prior_run_comparison_bytes is not None
            else None
        )
        repository_state_hash = repository_state_identity(str(resolved_root), inventory_records)
        classifications, recommendations, shadow_plan, shadow_plan_markdown = build_shadow_mode(
            inventory_records,
            intent.mainline,
            implementation_roles,
            relationships,
            attempts,
            bundles,
            candidates,
            document_comparisons,
            declaration_evidence_by_artifact,
            run_id,
            created_at,
            repository_state_hash,
        )
        classifications_bytes = _json_lines(classifications)
        recommendations_bytes = _json_lines(recommendations)
        classifications_hash = hashlib.sha256(classifications_bytes).hexdigest()
        recommendations_hash = hashlib.sha256(recommendations_bytes).hexdigest()
        intent_warnings = sorted(
            set(intent.warnings)
            | (
                {"INTENT_UNRESOLVED"}
                if intent.project_intent["status"] == "UNRESOLVED"
                else set()
            )
        )
        inventory_warnings = _aggregate_warnings(inventory_records)
        declaration_warnings = _aggregate_warnings(
            observations, field="limitations", excluded=SYNTAX_LIMITATIONS
        )
        profile_warnings = _aggregate_warnings(profiles, field="limitations")
        structural_warnings = _aggregate_warnings(
            structural_observations, field="limitations"
        )
        archive_warnings = _aggregate_warnings(archive_observations, field="limitations")
        warnings = sorted(
            set(inventory_warnings)
            | set(declaration_warnings)
            | set(git_evidence.warnings)
            | set(profile_warnings)
            | set(structural_warnings)
            | set(archive_warnings)
            | set(intent_warnings)
            | ({"DECISION_QUESTION_OPEN"} if decision_questions else set())
            | set(experiment_warnings)
            | set(relationship_warnings)
            | set(document_warnings)
        )
        curation_brief, curation_brief_markdown = build_curation_brief(
            artifact_count=len(inventory_records),
            budgets=budgets.as_dict(),
            bundles=bundles,
            canonical_candidates=candidates,
            classifications=classifications,
            created_at=created_at,
            decision_questions=decision_questions,
            declaration_observations=observations,
            git_head=git_evidence.head,
            mainline=intent.mainline,
            project_intent=intent.project_intent,
            recommendations=recommendations,
            relationships=relationships,
            repository_mode=git_evidence.repository_mode,
            repository_root=str(resolved_root),
            reproducibility_gaps=gaps,
            run_id=run_id,
            structural_observations=structural_observations,
            structural_coverage=relationship_coverage,
            warnings=warnings,
        )
        curation_brief_bytes = _json_bytes(curation_brief)
        curation_brief_markdown_bytes = curation_brief_markdown.encode("utf-8")
        shadow_plan = bind_curation_brief(
            shadow_plan, curation_brief_bytes, curation_brief_markdown_bytes
        )
        shadow_plan_bytes = _json_bytes(shadow_plan)
        shadow_plan_markdown_bytes = render_shadow_plan_markdown(
            shadow_plan, curation_brief_markdown
        ).encode("utf-8")
        run_record = {
            "artifact_count": len(inventory_records),
            "component_states": {
                "declarations": {
                    "status": (
                        "COMPLETED_WITH_LIMITATIONS"
                        if declaration_warnings
                        else "COMPLETED"
                    ),
                    "warnings": declaration_warnings,
                },
                "inventory": {
                    "status": (
                        "COMPLETED_WITH_LIMITATIONS" if inventory_warnings else "COMPLETED"
                    ),
                    "warnings": inventory_warnings,
                },
                "git": {
                    "status": (
                        "COMPLETED_WITH_LIMITATIONS"
                        if git_evidence.warnings
                        else "COMPLETED"
                    ),
                    "warnings": git_evidence.warnings,
                },
                "profiles": {
                    "status": (
                        "COMPLETED_WITH_LIMITATIONS"
                        if profile_warnings
                        else "COMPLETED"
                    ),
                    "warnings": profile_warnings,
                },
                "python_structure": {
                    "status": (
                        "COMPLETED_WITH_LIMITATIONS"
                        if structural_warnings
                        else "COMPLETED"
                    ),
                    "warnings": structural_warnings,
                },
                "archives": {
                    "status": (
                        "COMPLETED_WITH_LIMITATIONS"
                        if archive_warnings
                        else "COMPLETED"
                    ),
                    "warnings": archive_warnings,
                },
                "intent": {
                    "status": (
                        "COMPLETED_WITH_LIMITATIONS"
                        if intent_warnings
                        else "COMPLETED"
                    ),
                    "warnings": intent_warnings,
                },
                "decision_questions": {
                    "status": (
                        "COMPLETED_WITH_LIMITATIONS"
                        if decision_questions
                        else "COMPLETED"
                    ),
                    "warnings": ["DECISION_QUESTION_OPEN"] if decision_questions else [],
                },
                "experiments": {
                    "status": "COMPLETED_WITH_LIMITATIONS" if experiment_warnings or gaps else "COMPLETED",
                    "warnings": sorted(
                        set(experiment_warnings)
                        | ({"LINEAGE_UNRESOLVED"} if gaps else set())
                    ),
                },
                "relationship_candidates": {
                    "status": "COMPLETED_WITH_LIMITATIONS" if relationship_warnings else "COMPLETED",
                    "warnings": relationship_warnings,
                },
                "documents": {
                    "status": "COMPLETED_WITH_LIMITATIONS" if document_warnings else "COMPLETED",
                    "warnings": document_warnings,
                },
                "shadow_mode": {
                    "status": "COMPLETED_WITH_LIMITATIONS",
                    "warnings": ["SHADOW_MODE_NOT_EXECUTION_AUTHORITY"],
                },
            },
            "effective_config_hash": (
                f"sha256-config-v1:{hashlib.sha256(b'').hexdigest()}"
            ),
            "ended_at": created_at,
            "exclusions": [
                {
                    "path": f"{CONTROL_DIRECTORY_NAME}/",
                    "reason": "TOOL_CONTROL_AREA",
                }
            ],
            "execution_mode": "AUDIT",
            "final_status": "COMPLETED_WITH_LIMITATIONS" if warnings else "COMPLETED",
            "git_head": git_evidence.head,
            "inventory_file": "inventory.jsonl",
            "inventory_schema_version": INVENTORY_SCHEMA_VERSION,
            "output_file_hashes": {
                "adapter-observations.jsonl": observations_hash,
                "git-observations.jsonl": git_observations_hash,
                "archive-observations.jsonl": archive_hash,
                "decision-questions.jsonl": decision_questions_hash,
                "experiment-attempts.jsonl": attempts_hash,
                "experiment-bundles.jsonl": bundles_hash,
                "canonical-result-candidates.jsonl": candidates_hash,
                "capability-families.jsonl": families_hash,
                "change-episodes.jsonl": episodes_hash,
                "classifications.jsonl": classifications_hash,
                "document-comparisons.jsonl": document_comparisons_hash,
                "evidence.jsonl": evidence_hash,
                "inventory.jsonl": inventory_hash,
                "intent-conflicts.jsonl": intent_conflicts_hash,
                "mainline-map.jsonl": mainline_hash,
                "project-intent.json": project_intent_hash,
                "profiles.jsonl": profiles_hash,
                "structural-observations.jsonl": structural_hash,
                "retention-policy.json": retention_policy_hash,
                "relationships.jsonl": relationships_hash,
                "recommendations.jsonl": recommendations_hash,
                "reproducibility-gaps.jsonl": gaps_hash,
                "implementation-roles.jsonl": roles_hash,
                "canonical-entry-points.jsonl": canonical_entries_hash,
                "user-decisions.jsonl": user_decisions_hash,
            },
            "previous_run_id": compare_to_run_id,
            "relationship_coverage": relationship_coverage,
            "repository_mode": git_evidence.repository_mode,
            "repository_root_realpath": str(resolved_root),
            "repository_state_hash": repository_state_hash,
            "resource_budgets": budgets.as_dict(),
            "run_id": run_id,
            "schema_version": RUN_SCHEMA_VERSION,
            "shadow_plan_directory": f"{CONTROL_DIRECTORY_NAME}/plans/{run_id}",
            "started_at": created_at,
            "tool_versions": {"repo-curator": __version__},
            "warnings": warnings,
        }
        if prior_run_comparison_hash is not None:
            run_record["output_file_hashes"]["prior-run-comparison.json"] = prior_run_comparison_hash

        _require_root_path_unchanged(resolved_root, root_stat)
        run_directory_fd = None
        runs_directory_fd = None
        shadow_plan_identity = None
        try:
            (
                run_directory,
                staging_name,
                run_directory_fd,
                runs_directory_fd,
                staging_identity,
            ) = _create_staging_run_directory(resolved_root, root_fd, run_id)
            active_directory_name = staging_name
            _write_bytes(run_directory_fd, "inventory.jsonl", inventory_bytes)
            _write_bytes(
                run_directory_fd, "adapter-observations.jsonl", observations_bytes
            )
            _write_bytes(
                run_directory_fd, "git-observations.jsonl", git_observations_bytes
            )
            _write_bytes(run_directory_fd, "profiles.jsonl", profiles_bytes)
            _write_bytes(
                run_directory_fd,
                "structural-observations.jsonl",
                structural_bytes,
            )
            _write_bytes(run_directory_fd, "archive-observations.jsonl", archive_bytes)
            _write_bytes(run_directory_fd, "evidence.jsonl", evidence_bytes)
            _write_bytes(run_directory_fd, "relationships.jsonl", relationships_bytes)
            _write_bytes(run_directory_fd, "project-intent.json", project_intent_bytes)
            _write_bytes(run_directory_fd, "retention-policy.json", retention_policy_bytes)
            _write_bytes(run_directory_fd, "mainline-map.jsonl", mainline_bytes)
            _write_bytes(run_directory_fd, "intent-conflicts.jsonl", intent_conflicts_bytes)
            _write_bytes(run_directory_fd, "decision-questions.jsonl", decision_questions_bytes)
            _write_bytes(run_directory_fd, "user-decisions.jsonl", user_decisions_bytes)
            _write_bytes(run_directory_fd, "experiment-attempts.jsonl", attempts_bytes)
            _write_bytes(run_directory_fd, "experiment-bundles.jsonl", bundles_bytes)
            _write_bytes(run_directory_fd, "canonical-result-candidates.jsonl", candidates_bytes)
            _write_bytes(run_directory_fd, "reproducibility-gaps.jsonl", gaps_bytes)
            _write_bytes(run_directory_fd, "change-episodes.jsonl", episodes_bytes)
            _write_bytes(run_directory_fd, "capability-families.jsonl", families_bytes)
            _write_bytes(run_directory_fd, "implementation-roles.jsonl", roles_bytes)
            _write_bytes(run_directory_fd, "document-comparisons.jsonl", document_comparisons_bytes)
            _write_bytes(run_directory_fd, "canonical-entry-points.jsonl", canonical_entries_bytes)
            if prior_run_comparison_bytes is not None:
                _write_bytes(
                    run_directory_fd,
                    "prior-run-comparison.json",
                    prior_run_comparison_bytes,
                )
            _write_bytes(run_directory_fd, "classifications.jsonl", classifications_bytes)
            _write_bytes(run_directory_fd, "recommendations.jsonl", recommendations_bytes)
            _write_bytes(run_directory_fd, "run.json", _json_bytes(run_record))
            os.fsync(run_directory_fd)
            shadow_plan_identity = _publish_shadow_plan(
                root_fd,
                run_id,
                shadow_plan_bytes,
                shadow_plan_markdown_bytes,
                curation_brief_bytes,
                curation_brief_markdown_bytes,
            )
            _require_named_directory_identity(
                runs_directory_fd, staging_name, staging_identity
            )
            _rename_directory_without_replacing(
                runs_directory_fd, staging_name, run_id
            )
            active_directory_name = run_id
            published_stat = os.stat(
                run_id, dir_fd=runs_directory_fd, follow_symlinks=False
            )
            if not _same_object(published_stat, staging_identity):
                active_directory_name = None
                raise ValueError("published run directory changed during publication")
            os.fsync(runs_directory_fd)
        except BaseException:
            if run_directory_fd is not None and runs_directory_fd is not None:
                try:
                    _cleanup_incomplete_run(
                        run_directory_fd,
                        runs_directory_fd,
                        active_directory_name,
                        staging_identity,
                    )
                finally:
                    run_directory_fd = None
                    runs_directory_fd = None
            if shadow_plan_identity is not None and active_directory_name != run_id:
                try:
                    _cleanup_published_shadow_plan(root_fd, run_id, shadow_plan_identity)
                except (OSError, ValueError):
                    pass
            raise
        try:
            return run_directory
        finally:
            if run_directory_fd is not None:
                os.close(run_directory_fd)
            if runs_directory_fd is not None:
                os.close(runs_directory_fd)
    finally:
        os.close(root_fd)


def _inventory_records(
    root: Path,
    run_id: str,
    created_at: str,
    root_fd: int,
    budgets: AuditBudgets = AuditBudgets(),
) -> List[Dict[str, Any]]:
    observed_artifacts = scan_root(root_fd, budgets)
    records = []
    for sequence, artifact in enumerate(
        sorted(observed_artifacts, key=lambda item: item.path_bytes),
        start=1,
    ):
        repository_relative_path = artifact.path
        stat_result = artifact.stat_result
        fingerprint_scheme = artifact.fingerprint_scheme
        fingerprint = artifact.fingerprint
        object_type = artifact.object_type
        records.append(
            {
                "artifact_id": f"art_{run_id}_{sequence:08d}",
                "content_id": content_identity(artifact),
                "created_at": created_at,
                "executable": bool(stat_result and stat_result.st_mode & 0o111),
                "fingerprint": fingerprint,
                "fingerprint_scheme": fingerprint_scheme,
                "git_state": {
                    "ignored_included": False,
                    "index_status": None,
                    "modified": None,
                    "tracked": None,
                    "untracked": None,
                },
                "lineage_id": None,
                "lineage_status": "UNRESOLVED",
                "lfs_pointer": None,
                "location_id": location_identity(
                    str(root), object_type, artifact.path_bytes
                ),
                "mode": stat_result.st_mode & 0o7777 if stat_result else None,
                "mtime_ns": (
                    stat_result.st_mtime_ns
                    if object_type == "REGULAR_FILE"
                    else None
                ),
                "object_type": object_type,
                "profile_eligibility": artifact.profile_eligibility,
                "realpath": str(
                    root
                    if repository_relative_path == "."
                    else root / repository_relative_path
                ),
                "repository_relative_path": repository_relative_path,
                "run_id": run_id,
                "schema_version": INVENTORY_SCHEMA_VERSION,
                "size_bytes": (
                    stat_result.st_size
                    if object_type == "REGULAR_FILE"
                    else None
                ),
                "symlink_target_text": artifact.symlink_target_text,
                "warnings": list(artifact.warnings),
            }
        )
    return records


def _aggregate_warnings(
    records: Iterable[Dict[str, Any]],
    field: str = "warnings",
    excluded: Iterable[str] = (),
) -> List[str]:
    excluded_values = set(excluded)
    return sorted(
        {
            warning
            for record in records
            for warning in record.get(field, [])
            if warning not in excluded_values
        }
    )


def _directory_open_flags() -> int:
    return (
        os.O_RDONLY
        | getattr(os, "O_DIRECTORY", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )


def _json_lines(records: Iterable[Dict[str, Any]]) -> bytes:
    return b"".join(_json_bytes(record) for record in records)


def _json_bytes(value: Dict[str, Any]) -> bytes:
    return _canonical_json_bytes(value) + b"\n"


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")


def _create_staging_run_directory(
    root: Path, root_fd: int, run_id: str
) -> tuple[Path, str, int, int, os.stat_result]:
    directory_flags = os.O_RDONLY
    directory_flags |= getattr(os, "O_DIRECTORY", 0)
    directory_flags |= getattr(os, "O_NOFOLLOW", 0)
    control_fd = _open_or_create_directory(
        parent_fd=root_fd,
        name=CONTROL_DIRECTORY_NAME,
        label="control directory",
        flags=directory_flags,
    )
    try:
        runs_fd = _open_or_create_directory(
            parent_fd=control_fd,
            name="runs",
            label="runs directory",
            flags=directory_flags,
        )
    finally:
        os.close(control_fd)
    try:
        _require_path_absent(runs_fd, run_id)
        staging_name, run_fd = _create_private_staging_directory(
            runs_fd, directory_flags, run_id
        )
    except BaseException:
        os.close(runs_fd)
        raise
    return (
        root / CONTROL_DIRECTORY_NAME / "runs" / run_id,
        staging_name,
        run_fd,
        runs_fd,
        os.fstat(run_fd),
    )


def _publish_shadow_plan(
    root_fd: int,
    run_id: str,
    plan_bytes: bytes,
    markdown_bytes: bytes,
    brief_bytes: bytes,
    brief_markdown_bytes: bytes,
) -> os.stat_result:
    """Publish shadow-only plan bytes outside the immutable audit-report directory."""
    directory_flags = _directory_open_flags()
    control_fd = _open_or_create_directory(
        root_fd, CONTROL_DIRECTORY_NAME, "control directory", directory_flags
    )
    try:
        plans_fd = _open_or_create_directory(
            control_fd, "plans", "plans directory", directory_flags
        )
    finally:
        os.close(control_fd)
    plan_fd = None
    staging_name = None
    plan_identity = None
    try:
        _require_path_absent(plans_fd, run_id)
        staging_name, plan_fd = _create_private_staging_directory(
            plans_fd, directory_flags, run_id
        )
        plan_identity = os.fstat(plan_fd)
        _write_bytes(plan_fd, "plan.json", plan_bytes)
        _write_bytes(plan_fd, "plan.md", markdown_bytes)
        _write_bytes(plan_fd, "curation-brief.json", brief_bytes)
        _write_bytes(plan_fd, "curation-brief.md", brief_markdown_bytes)
        os.fsync(plan_fd)
        _require_named_directory_identity(plans_fd, staging_name, plan_identity)
        _rename_directory_without_replacing(plans_fd, staging_name, run_id)
        staging_name = None
        os.fsync(plans_fd)
        return plan_identity
    except BaseException:
        if plan_fd is not None and staging_name is not None:
            try:
                _cleanup_incomplete_plan(plan_fd, plans_fd, staging_name, plan_identity)
            finally:
                plan_fd = None
                plans_fd = None
        raise
    finally:
        if plan_fd is not None:
            os.close(plan_fd)
        if plans_fd is not None:
            os.close(plans_fd)


def _cleanup_incomplete_plan(
    plan_fd: int,
    plans_fd: int,
    staging_name: str,
    expected_identity: os.stat_result,
) -> None:
    first_error = None
    for name in (
        "plan.json",
        "plan.md",
        "curation-brief.json",
        "curation-brief.md",
        ".plan.json.tmp",
        ".plan.md.tmp",
        ".curation-brief.json.tmp",
        ".curation-brief.md.tmp",
    ):
        try:
            _unlink_if_exists(plan_fd, name)
        except OSError as error:
            if first_error is None:
                first_error = error
    try:
        _require_named_directory_identity(plans_fd, staging_name, expected_identity)
        os.fsync(plans_fd)
    except (OSError, ValueError) as error:
        if first_error is None:
            first_error = error
    finally:
        os.close(plan_fd)
        os.close(plans_fd)
    if first_error is not None:
        raise first_error


def _cleanup_published_shadow_plan(
    root_fd: int, run_id: str, expected_identity: os.stat_result
) -> None:
    directory_flags = _directory_open_flags()
    control_fd = _open_or_create_directory(
        root_fd, CONTROL_DIRECTORY_NAME, "control directory", directory_flags
    )
    try:
        plans_fd = _open_or_create_directory(
            control_fd, "plans", "plans directory", directory_flags
        )
    finally:
        os.close(control_fd)
    plan_fd = None
    try:
        _require_named_directory_identity(plans_fd, run_id, expected_identity)
        plan_fd = os.open(run_id, directory_flags, dir_fd=plans_fd)
        _cleanup_incomplete_plan(plan_fd, plans_fd, run_id, expected_identity)
        plan_fd = None
        plans_fd = None
    finally:
        if plan_fd is not None:
            os.close(plan_fd)
        if plans_fd is not None:
            os.close(plans_fd)


def _create_private_staging_directory(
    runs_fd: int, directory_flags: int, run_id: str
) -> tuple[str, int]:
    for _ in range(16):
        staging_name = f".{run_id}.{os.urandom(16).hex()}.tmp"
        try:
            os.mkdir(staging_name, mode=0o700, dir_fd=runs_fd)
        except FileExistsError:
            continue
        try:
            return staging_name, os.open(staging_name, directory_flags, dir_fd=runs_fd)
        except BaseException:
            os.rmdir(staging_name, dir_fd=runs_fd)
            raise
    raise FileExistsError("unable to allocate private staging directory")


def _require_root_path_unchanged(root: Path, expected: os.stat_result) -> None:
    try:
        observed = os.stat(root, follow_symlinks=False)
    except OSError as error:
        raise ValueError("audit root changed after inventory") from error
    if not stat.S_ISDIR(observed.st_mode) or (
        observed.st_dev,
        observed.st_ino,
    ) != (expected.st_dev, expected.st_ino):
        raise ValueError("audit root changed after inventory")


def _cleanup_incomplete_run(
    run_directory_fd: int,
    runs_directory_fd: int,
    run_id: Optional[str],
    expected_identity: os.stat_result,
) -> None:
    incomplete_names = (
        "adapter-observations.jsonl",
        "git-observations.jsonl",
        "inventory.jsonl",
        "run.json",
        ".adapter-observations.jsonl.tmp",
        ".git-observations.jsonl.tmp",
        "profiles.jsonl",
        ".profiles.jsonl.tmp",
        "structural-observations.jsonl",
        ".structural-observations.jsonl.tmp",
        "archive-observations.jsonl",
        "evidence.jsonl",
        "relationships.jsonl",
        "project-intent.json",
        "retention-policy.json",
        "mainline-map.jsonl",
        "intent-conflicts.jsonl",
        "decision-questions.jsonl",
        "user-decisions.jsonl",
        "experiment-attempts.jsonl",
        "experiment-bundles.jsonl",
        "canonical-result-candidates.jsonl",
        "reproducibility-gaps.jsonl",
        "change-episodes.jsonl",
        "capability-families.jsonl",
        "implementation-roles.jsonl",
        "document-comparisons.jsonl",
        "canonical-entry-points.jsonl",
        "classifications.jsonl",
        "recommendations.jsonl",
        ".archive-observations.jsonl.tmp",
        ".evidence.jsonl.tmp",
        ".relationships.jsonl.tmp",
        ".project-intent.json.tmp",
        ".retention-policy.json.tmp",
        ".mainline-map.jsonl.tmp",
        ".intent-conflicts.jsonl.tmp",
        ".decision-questions.jsonl.tmp",
        ".user-decisions.jsonl.tmp",
        ".experiment-attempts.jsonl.tmp",
        ".experiment-bundles.jsonl.tmp",
        ".canonical-result-candidates.jsonl.tmp",
        ".reproducibility-gaps.jsonl.tmp",
        ".change-episodes.jsonl.tmp",
        ".capability-families.jsonl.tmp",
        ".implementation-roles.jsonl.tmp",
        ".document-comparisons.jsonl.tmp",
        ".canonical-entry-points.jsonl.tmp",
        ".classifications.jsonl.tmp",
        ".recommendations.jsonl.tmp",
        ".inventory.jsonl.tmp",
        ".run.json.tmp",
    )
    first_error = None
    for name in incomplete_names:
        try:
            _unlink_if_exists(run_directory_fd, name)
        except OSError as error:
            if first_error is None:
                first_error = error
    try:
        if run_id is not None:
            try:
                _require_named_directory_identity(
                    runs_directory_fd, run_id, expected_identity
                )
            except ValueError:
                error = ValueError("cleanup directory identity mismatch")
                if first_error is None:
                    first_error = error
        try:
            os.fsync(runs_directory_fd)
        except OSError as error:
            if first_error is None:
                first_error = error
    finally:
        for descriptor in (run_directory_fd, runs_directory_fd):
            try:
                os.close(descriptor)
            except OSError as error:
                if first_error is None:
                    first_error = error
    if first_error is not None:
        raise first_error


def _same_object(observed: os.stat_result, expected: os.stat_result) -> bool:
    return (observed.st_dev, observed.st_ino) == (expected.st_dev, expected.st_ino)


def _declaration_evidence_by_artifact(
    observations: Iterable[Dict[str, Any]],
    evidence_by_source_id: Dict[str, str],
    inventory_records: Iterable[Dict[str, Any]],
) -> Dict[str, Dict[str, List[str]]]:
    inventory_ids = {record["artifact_id"] for record in inventory_records}
    result: Dict[str, Dict[str, List[str]]] = {}
    for observation in observations:
        evidence_id = evidence_by_source_id.get(observation.get("observation_id", ""))
        if evidence_id is None:
            continue
        marker_ids = observation.get("marker_artifact_ids", [])
        if not isinstance(marker_ids, list):
            continue
        for artifact_id in marker_ids:
            if artifact_id not in inventory_ids:
                continue
            record = result.setdefault(
                artifact_id,
                {"limitations": [], "supporting_evidence_ids": []},
            )
            record["limitations"].extend(observation.get("limitations", []))
            record["supporting_evidence_ids"].append(evidence_id)
    return {
        artifact_id: {
            "limitations": sorted(set(record["limitations"])),
            "supporting_evidence_ids": sorted(
                set(record["supporting_evidence_ids"])
            ),
        }
        for artifact_id, record in result.items()
    }


def _require_named_directory_identity(
    directory_fd: int, name: str, expected: os.stat_result
) -> None:
    try:
        observed = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError as error:
        raise ValueError("staging directory changed before publication") from error
    if not stat.S_ISDIR(observed.st_mode) or not _same_object(observed, expected):
        raise ValueError("staging directory changed before publication")


def _require_path_absent(directory_fd: int, name: str) -> None:
    try:
        os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
    except FileNotFoundError:
        return
    raise FileExistsError(f"run directory already exists: {name}")


def _rename_directory_without_replacing(
    directory_fd: int, source_name: str, destination_name: str
) -> None:
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = libc.renameatx_np
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(
            directory_fd,
            os.fsencode(source_name),
            directory_fd,
            os.fsencode(destination_name),
            0x00000004,  # RENAME_EXCL
        )
    else:
        rename = getattr(libc, "renameat2", None)
        if rename is None:
            raise OSError(errno.ENOTSUP, "no no-replace rename primitive")
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        result = rename(
            directory_fd,
            os.fsencode(source_name),
            directory_fd,
            os.fsencode(destination_name),
            1,  # RENAME_NOREPLACE
        )
    if result == 0:
        return
    error_code = ctypes.get_errno()
    if error_code == errno.EEXIST:
        raise FileExistsError(error_code, os.strerror(error_code), destination_name)
    raise OSError(error_code, os.strerror(error_code), destination_name)


def _open_or_create_directory(
    parent_fd: int, name: str, label: str, flags: int
) -> int:
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_fd)
    except FileExistsError:
        pass
    try:
        return os.open(name, flags, dir_fd=parent_fd)
    except OSError as error:
        raise ValueError(f"unsafe {label}: expected a real directory") from error


def _write_bytes(directory_fd: int, name: str, content: bytes) -> None:
    file_flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    file_flags |= getattr(os, "O_NOFOLLOW", 0)
    temporary_name = f".{name}.tmp"
    published = False
    try:
        file_descriptor = os.open(
            temporary_name, file_flags, 0o600, dir_fd=directory_fd
        )
        with os.fdopen(file_descriptor, "wb") as destination:
            destination.write(content)
            destination.flush()
            os.fsync(destination.fileno())
        os.link(
            temporary_name,
            name,
            src_dir_fd=directory_fd,
            dst_dir_fd=directory_fd,
            follow_symlinks=False,
        )
        published = True
        os.unlink(temporary_name, dir_fd=directory_fd)
        os.fsync(directory_fd)
    except BaseException:
        if published:
            _unlink_if_exists(directory_fd, name)
        _unlink_if_exists(directory_fd, temporary_name)
        raise


def _unlink_if_exists(directory_fd: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=directory_fd)
    except FileNotFoundError:
        pass
