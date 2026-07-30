"""Deterministic human and machine curation briefs for shadow-mode audits."""

import hashlib
import json
from collections import Counter
from typing import Any, Dict, Mapping, Sequence, Tuple


BRIEF_SCHEMA_VERSION = "repo-curator.curation-brief.v3"
_ATTENTION_LIMIT = 25
_CANONICAL_CANDIDATE_LIMIT = 25
_DECLARED_CHAIN_LIMIT = 25
_DECLARED_EDGE_LIMIT_PER_CHAIN = 64
_REPRODUCIBILITY_GAP_LIMIT = 25
_REPRODUCIBILITY_GAP_ITEM_LIMIT = 64
_UNRESOLVED_DEPENDENCY_LIMIT_PER_CHAIN = 64
_RECOMMENDATION_PRIORITY = {
    "ARCHIVE": 1,
    "MERGE": 2,
    "REVIEW_EXACT_DUPLICATE": 3,
    "MANUAL_REVIEW": 4,
    "KEEP": 5,
}


def build_curation_brief(
    *,
    artifact_count: int,
    budgets: Mapping[str, Any],
    bundles: Sequence[Mapping[str, Any]],
    canonical_candidates: Sequence[Mapping[str, Any]],
    classifications: Sequence[Mapping[str, Any]],
    created_at: str,
    decision_questions: Sequence[Mapping[str, Any]],
    declaration_observations: Sequence[Mapping[str, Any]],
    git_head: Any,
    mainline: Sequence[Mapping[str, Any]],
    project_intent: Mapping[str, Any],
    recommendations: Sequence[Mapping[str, Any]],
    relationships: Sequence[Mapping[str, Any]],
    repository_mode: str,
    repository_root: str,
    reproducibility_gaps: Sequence[Mapping[str, Any]],
    run_id: str,
    structural_observations: Sequence[Mapping[str, Any]],
    structural_coverage: Mapping[str, Mapping[str, Any]],
    warnings: Sequence[str],
) -> Tuple[Dict[str, Any], str]:
    recommendation_counts = _counts(
        item["recommendation_type"] for item in recommendations
    )
    classification_counts = _counts(item["state"] for item in classifications)
    mainline_counts = _counts(item["status"] for item in mainline)
    attention_items = _attention_items(recommendations, classifications)
    canonical_result_review = _canonical_result_review(canonical_candidates)
    declared_experiment_chains = _declared_experiment_chains(
        bundles, relationships
    )
    reproducibility_gap_review = _reproducibility_gap_review(
        reproducibility_gaps
    )
    questions = [
        {
            "affected_artifacts": list(item["affected_artifacts"]),
            "exact_decision": item["exact_decision"],
            "question_id": item["question_id"],
            "status": item["status"],
        }
        for item in sorted(decision_questions, key=lambda item: item["question_id"])
    ]
    brief = {
        "audit_scope": {
            "artifact_count": artifact_count,
            "git_head": git_head,
            "repository_mode": repository_mode,
            "repository_root_realpath": repository_root,
            "resource_budgets": dict(sorted(budgets.items())),
        },
        "classification_counts": classification_counts,
        "canonical_result_review": canonical_result_review,
        "created_at": created_at,
        "decision_questions": questions,
        "declared_experiment_chains": declared_experiment_chains,
        "execution_authorized": False,
        "next_safe_action": _next_safe_action(questions, attention_items),
        "observed_evidence": {
            "declaration_observation_count": len(declaration_observations),
            "exact_byte_duplicate_group_count": sum(
                item["relationship_type"] == "EXACT_BYTE_DUPLICATE"
                for item in relationships
            ),
            "python_structure_observation_count": len(structural_observations),
        },
        "preservation_risks": {
            "canonical_result_candidate_count": len(canonical_candidates),
            "incomplete_experiment_bundle_count": sum(
                item.get("completeness") != "COMPLETE_IN_ANALYZED_SCOPE"
                for item in bundles
            ),
            "reproducibility_gap_count": len(reproducibility_gaps),
            "unresolved_artifact_count": classification_counts.get("UNRESOLVED", 0),
            "warnings": sorted(set(warnings)),
        },
        "project_intent": {
            "mainline_status_counts": mainline_counts,
            "status": project_intent["status"],
            "uncertainty": sorted(set(project_intent["uncertainty"])),
        },
        "recommendation_counts": recommendation_counts,
        "reproducibility_gap_review": reproducibility_gap_review,
        "review_attention_items": attention_items,
        "run_id": run_id,
        "schema_version": BRIEF_SCHEMA_VERSION,
        "structural_coverage": {
            key: dict(value) for key, value in sorted(structural_coverage.items())
        },
    }
    return brief, render_curation_brief_markdown(brief)


def bind_curation_brief(
    plan: Mapping[str, Any], json_bytes: bytes, markdown_bytes: bytes
) -> Dict[str, Any]:
    bound = dict(plan)
    bound["curation_brief"] = {
        "json_file": "curation-brief.json",
        "json_sha256": hashlib.sha256(json_bytes).hexdigest(),
        "markdown_file": "curation-brief.md",
        "markdown_sha256": hashlib.sha256(markdown_bytes).hexdigest(),
    }
    return bound


def render_shadow_plan_markdown(
    plan: Mapping[str, Any], brief_markdown: str
) -> str:
    binding = plan["curation_brief"]
    lines = [
        "# Shadow-mode curation plan",
        "",
        "This report is explanatory only. It authorizes no repository action.",
        "",
        f"Plan ID: {_code(plan['plan_id'])}",
        f"Analysis run: {_code(plan['analysis_run_id'])}",
        f"Executable actions: {_code(len(plan['action_candidates']))}",
        "",
        "## Bound curation brief",
        "",
        f"- JSON: {_code(binding['json_file'])} ({_code(binding['json_sha256'])})",
        f"- Markdown: {_code(binding['markdown_file'])} ({_code(binding['markdown_sha256'])})",
        "",
        brief_markdown.rstrip(),
        "",
    ]
    return "\n".join(lines)


def render_curation_brief_markdown(brief: Mapping[str, Any]) -> str:
    scope = brief["audit_scope"]
    intent = brief["project_intent"]
    risks = brief["preservation_risks"]
    lines = [
        "# Repo-curator curation brief",
        "",
        "This report is evidence-linked shadow guidance. It authorizes no repository action.",
        "",
        "## Audit scope",
        "",
        f"- Run: {_code(brief['run_id'])}",
        f"- Repository: {_code(scope['repository_root_realpath'])}",
        f"- Mode: {_code(scope['repository_mode'])}",
        f"- Git HEAD: {_code(scope['git_head'] if scope['git_head'] is not None else 'UNAVAILABLE')}",
        f"- Artifacts: {_code(scope['artifact_count'])}",
        "",
        "## Observed evidence",
        "",
        f"- Exact-byte duplicate groups: {_code(brief['observed_evidence']['exact_byte_duplicate_group_count'])}",
        f"- Research declaration observations: {_code(brief['observed_evidence']['declaration_observation_count'])}",
        f"- Python structure observations: {_code(brief['observed_evidence']['python_structure_observation_count'])}",
        "",
        "## Declared experiment chains",
        "",
        "These links are declaration-only; execution was not verified.",
        "",
        f"- Declared attempts: {_code(brief['declared_experiment_chains']['attempt_count'])}",
        f"- Inventory-resolved directed edges: {_code(brief['declared_experiment_chains']['directed_edge_count'])}",
        f"- Complete bundles in analyzed scope: {_code(brief['declared_experiment_chains']['complete_bundle_count'])}",
        f"- Incomplete bundles: {_code(brief['declared_experiment_chains']['incomplete_bundle_count'])}",
        f"- Relationship types: {_format_counts(brief['declared_experiment_chains']['relationship_type_counts'])}",
        "",
    ]
    chains = brief["declared_experiment_chains"]
    if chains["chains"]:
        for chain in chains["chains"]:
            lines.append(
                f"- Attempt {_code(chain['attempt_id'])}: "
                f"{_code(chain['completeness'])}; "
                f"resolved edges {_code(chain['declared_edge_count'])}; "
                f"unresolved {_format_values(chain['unresolved_dependencies'])}"
            )
            for edge in chain["declared_edges"]:
                lines.append(
                    f"  - {_code(edge['relationship_type'])}: "
                    f"{_code(edge['declared_path'])}; artifact "
                    f"{_code(edge['artifact_id'])}; evidence "
                    f"{_format_values(edge['supporting_evidence_ids'])}"
                )
            if chain["omitted_declared_edge_count"]:
                lines.append(
                    "  - Additional declared edges omitted by report limit: "
                    f"{_code(chain['omitted_declared_edge_count'])}"
                )
            if chain["omitted_unresolved_dependency_count"]:
                lines.append(
                    "  - Additional unresolved dependencies omitted by report limit: "
                    f"{_code(chain['omitted_unresolved_dependency_count'])}"
                )
    else:
        lines.append("- No declared experiment chain was emitted.")
    if chains["omitted_chain_count"]:
        lines.append(
            "- Additional chains omitted by report limit: "
            f"{_code(chains['omitted_chain_count'])}"
        )
    candidates = brief["canonical_result_review"]
    lines.extend(
        [
            "",
            "## Canonical-result candidates",
            "",
            "Candidates require project-governance review; none is canonical by declaration alone.",
            "",
            f"- Candidate count: {_code(candidates['candidate_count'])}",
            "",
        ]
    )
    if candidates["candidates"]:
        for candidate in candidates["candidates"]:
            lines.append(
                f"- {_code(candidate['candidate_id'])}: attempt "
                f"{_code(candidate['attempt_id'])}; output "
                f"{_code(candidate['output_path'])}; governance "
                f"{_code(candidate['governance_state'])}; evidence "
                f"{_format_values(candidate['supporting_evidence_ids'])}; "
                f"limitations {_format_values(candidate['limitations'])}"
            )
    else:
        lines.append("- No canonical-result candidate was emitted.")
    if candidates["omitted_candidate_count"]:
        lines.append(
            "- Additional candidates omitted by report limit: "
            f"{_code(candidates['omitted_candidate_count'])}"
        )
    gaps = brief["reproducibility_gap_review"]
    lines.extend(
        [
            "",
            "## Reproducibility-evidence gaps",
            "",
            "A gap records missing or unresolved evidence; it is not a reproduction verdict.",
            "",
            f"- Gap count: {_code(gaps['gap_count'])}",
            "",
        ]
    )
    if gaps["gaps"]:
        for gap in gaps["gaps"]:
            lines.append(
                f"- {_code(gap['gap_id'])}: attempt {_code(gap['attempt_id'])}; "
                f"status {_code(gap['status'])}; missing or unresolved "
                f"{_format_values(gap['missing_or_unresolved'])}; evidence "
                f"{_format_values(gap['supporting_evidence_ids'])}"
            )
            if gap["omitted_unresolved_item_count"]:
                lines.append(
                    "  - Additional unresolved items omitted by report limit: "
                    f"{_code(gap['omitted_unresolved_item_count'])}"
                )
    else:
        lines.append("- No reproducibility-evidence gap was emitted.")
    if gaps["omitted_gap_count"]:
        lines.append(
            "- Additional gaps omitted by report limit: "
            f"{_code(gaps['omitted_gap_count'])}"
        )
    lines.extend(
        [
            "",
            "## Project intent and scientific mainline",
            "",
            f"- Intent status: {_code(intent['status'])}",
            f"- Mainline states: {_format_counts(intent['mainline_status_counts'])}",
            f"- Uncertainty: {_format_values(intent['uncertainty'])}",
            "",
            "## Preservation risks",
            "",
            f"- Unresolved artifacts: {_code(risks['unresolved_artifact_count'])}",
            f"- Incomplete experiment bundles: {_code(risks['incomplete_experiment_bundle_count'])}",
            f"- Canonical-result candidates: {_code(risks['canonical_result_candidate_count'])}",
            f"- Reproducibility-evidence gaps: {_code(risks['reproducibility_gap_count'])}",
            f"- Coverage limitations: {_format_values(risks['warnings'])}",
            f"- Structural coverage: {_format_structural_coverage(brief['structural_coverage'])}",
            "",
            "## Conservative recommendations",
            "",
            f"Recommendation counts: {_format_counts(brief['recommendation_counts'])}",
            "",
        ]
    )
    if brief["review_attention_items"]:
        for item in brief["review_attention_items"]:
            paths = ", ".join(_code(path) for path in item["repository_relative_paths"])
            lines.append(
                f"- {_code(item['recommendation_type'])}: {paths}; "
                f"expected loss {_code(item['expected_loss'])}; "
                f"limitations {_format_values(item['limitations'])}"
            )
    else:
        lines.append("- No non-KEEP review item was emitted.")
    lines.extend(["", "## Decision questions", ""])
    if brief["decision_questions"]:
        for question in brief["decision_questions"]:
            lines.append(
                f"- {_code(question['question_id'])}: {_code(question['exact_decision'])} "
                f"Affected: {_format_values(question['affected_artifacts'])}"
            )
    else:
        lines.append("- No evidence-specific decision question was emitted.")
    next_action = brief["next_safe_action"]
    lines.extend(
        [
            "",
            "## Next safe action",
            "",
            f"- Action: {_code(next_action['action'])}",
            f"- Reason: {next_action['reason']}",
            "- No cleanup or mutation is authorized.",
            "",
        ]
    )
    return "\n".join(lines)


def _canonical_result_review(
    canonical_candidates: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    ordered = sorted(
        canonical_candidates, key=lambda item: item["candidate_id"]
    )
    reported = ordered[:_CANONICAL_CANDIDATE_LIMIT]
    return {
        "candidate_count": len(ordered),
        "candidates": [
            {
                "attempt_id": item["attempt_id"],
                "candidate_id": item["candidate_id"],
                "counter_evidence_ids": list(item["counter_evidence_ids"]),
                "executable_in_supported_scope": item[
                    "executable_in_supported_scope"
                ],
                "governance_state": item["governance_state"],
                "limitations": list(item["limitations"]),
                "output_path": item["output_path"],
                "supporting_evidence_ids": list(item["supporting_evidence_ids"]),
            }
            for item in reported
        ],
        "omitted_candidate_count": len(ordered) - len(reported),
    }


def _reproducibility_gap_review(
    reproducibility_gaps: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    ordered = sorted(
        reproducibility_gaps,
        key=lambda item: (-len(item["missing_or_unresolved"]), item["gap_id"]),
    )
    reported = ordered[:_REPRODUCIBILITY_GAP_LIMIT]
    gaps = []
    for item in reported:
        unresolved = list(item["missing_or_unresolved"])
        reported_unresolved = unresolved[:_REPRODUCIBILITY_GAP_ITEM_LIMIT]
        gaps.append(
            {
                "attempt_id": item["attempt_id"],
                "counter_evidence_ids": list(item["counter_evidence_ids"]),
                "gap_id": item["gap_id"],
                "limitations": list(item["limitations"]),
                "missing_or_unresolved": reported_unresolved,
                "omitted_unresolved_item_count": (
                    len(unresolved) - len(reported_unresolved)
                ),
                "status": item["status"],
                "supporting_evidence_ids": list(item["supporting_evidence_ids"]),
                "unresolved_item_count": len(unresolved),
            }
        )
    return {
        "gap_count": len(ordered),
        "gaps": gaps,
        "omitted_gap_count": len(ordered) - len(reported),
    }


def _declared_experiment_chains(
    bundles: Sequence[Mapping[str, Any]],
    relationships: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    declared_edges = [
        item
        for item in relationships
        if item.get("assertion_origin") == "DECLARED"
        and item.get("relationship_shape") == "DIRECTED_EDGE"
        and item.get("source", {}).get("entity_type") == "EXPERIMENT_ATTEMPT"
        and item.get("target", {}).get("entity_type") == "ARTIFACT"
    ]
    edges_by_attempt: Dict[str, list[Mapping[str, Any]]] = {}
    for edge in declared_edges:
        edges_by_attempt.setdefault(edge["source"]["entity_id"], []).append(edge)

    ordered_bundles = sorted(
        bundles,
        key=lambda item: (
            item["completeness"] == "COMPLETE_IN_ANALYZED_SCOPE",
            item["bundle_id"],
        ),
    )
    chains = []
    for bundle in ordered_bundles[:_DECLARED_CHAIN_LIMIT]:
        edges = sorted(
            edges_by_attempt.get(bundle["attempt_id"], []),
            key=lambda item: item["relationship_id"],
        )
        reported_edges = edges[:_DECLARED_EDGE_LIMIT_PER_CHAIN]
        unresolved_dependencies = list(bundle["unresolved_dependencies"])
        reported_dependencies = unresolved_dependencies[
            :_UNRESOLVED_DEPENDENCY_LIMIT_PER_CHAIN
        ]
        chains.append(
            {
                "attempt_id": bundle["attempt_id"],
                "bundle_id": bundle["bundle_id"],
                "completeness": bundle["completeness"],
                "declared_edge_count": len(edges),
                "declared_edges": [
                    {
                        "artifact_id": edge["target"]["entity_id"],
                        "counter_evidence_ids": list(edge["counter_evidence_ids"]),
                        "declared_path": edge["declared_path"],
                        "limitations": list(edge["limitations"]),
                        "relationship_id": edge["relationship_id"],
                        "relationship_type": edge["relationship_type"],
                        "supporting_evidence_ids": list(
                            edge["supporting_evidence_ids"]
                        ),
                    }
                    for edge in reported_edges
                ],
                "omitted_declared_edge_count": len(edges) - len(reported_edges),
                "omitted_unresolved_dependency_count": (
                    len(unresolved_dependencies) - len(reported_dependencies)
                ),
                "supporting_evidence_ids": list(bundle["supporting_evidence_ids"]),
                "unresolved_dependencies": reported_dependencies,
                "unresolved_dependency_count": len(unresolved_dependencies),
            }
        )
    return {
        "attempt_count": len(ordered_bundles),
        "chains": chains,
        "complete_bundle_count": sum(
            item["completeness"] == "COMPLETE_IN_ANALYZED_SCOPE"
            for item in ordered_bundles
        ),
        "directed_edge_count": len(declared_edges),
        "incomplete_bundle_count": sum(
            item["completeness"] != "COMPLETE_IN_ANALYZED_SCOPE"
            for item in ordered_bundles
        ),
        "omitted_chain_count": len(ordered_bundles) - len(chains),
        "relationship_type_counts": _counts(
            item["relationship_type"] for item in declared_edges
        ),
    }


def _attention_items(
    recommendations: Sequence[Mapping[str, Any]],
    classifications: Sequence[Mapping[str, Any]],
) -> list[Dict[str, Any]]:
    state_by_classification = {
        item["classification_id"]: item["state"] for item in classifications
    }
    eligible = []
    for item in recommendations:
        if item["recommendation_type"] == "KEEP":
            continue
        classification_ids = item["classification_ids"]
        if classification_ids and all(
            state_by_classification.get(identifier) == "PROTECTED"
            for identifier in classification_ids
        ):
            continue
        eligible.append(item)
    ordered = sorted(
        eligible,
        key=lambda item: (
            _attention_priority(item),
            item["recommendation_id"],
        ),
    )
    return [
        {
            "counter_evidence_ids": list(item["counter_evidence_ids"]),
            "expected_loss": item["expected_loss"],
            "limitations": list(item["limitations"]),
            "recommendation_id": item["recommendation_id"],
            "recommendation_type": item["recommendation_type"],
            "repository_relative_paths": list(item["repository_relative_paths"]),
            "supporting_evidence_ids": list(item["supporting_evidence_ids"]),
        }
        for item in ordered[:_ATTENTION_LIMIT]
    ]


def _attention_priority(item: Mapping[str, Any]) -> int:
    if item["recommendation_type"] == "MANUAL_REVIEW" and (
        item["counter_evidence_ids"]
        or any(
            limitation.startswith(("MATERIAL_", "BUNDLE_"))
            for limitation in item["limitations"]
        )
    ):
        return 0
    return _RECOMMENDATION_PRIORITY.get(item["recommendation_type"], 99)


def _next_safe_action(
    questions: Sequence[Mapping[str, Any]],
    attention_items: Sequence[Mapping[str, Any]],
) -> Dict[str, str]:
    if questions:
        return {
            "action": "REVIEW_DECISION_QUESTION",
            "reason": "A material evidence conflict has an open scoped question.",
        }
    if attention_items:
        return {
            "action": "REVIEW_HIGHEST_PRIORITY_ITEM",
            "reason": (
                "Review the first deterministically ordered non-KEEP recommendation "
                f"{attention_items[0]['recommendation_id']}."
            ),
        }
    return {
        "action": "RETAIN_SHADOW_REPORT",
        "reason": "No non-KEEP review item or material decision question was emitted.",
    }


def _counts(values: Sequence[str]) -> Dict[str, int]:
    return dict(sorted(Counter(values).items()))


def _format_counts(counts: Mapping[str, int]) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{_code(key)}={_code(value)}" for key, value in counts.items())


def _format_values(values: Sequence[Any]) -> str:
    if not values:
        return "none"
    return ", ".join(_code(value) for value in values)


def _format_structural_coverage(
    coverage: Mapping[str, Mapping[str, Any]],
) -> str:
    return ", ".join(
        f"{_code(name)}={_code(state['status'])}"
        for name, state in coverage.items()
    )


def _code(value: Any) -> str:
    text = json.dumps(str(value), ensure_ascii=True)[1:-1]
    longest = 0
    current = 0
    for character in text:
        if character == "`":
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    fence = "`" * max(1, longest + 1)
    padding = " " if text.startswith("`") or text.endswith("`") else ""
    return f"{fence}{padding}{text}{padding}{fence}"
