"""Minimal, evidence-specific questions and scoped user assertions."""

import hashlib
import json
from typing import Any, Dict, Iterable, List


QUESTION_SCHEMA_VERSION = "repo-curator.decision-question.v1"
USER_DECISION_SCHEMA_VERSION = "repo-curator.user-decision.v1"


def build_decision_questions(
    conflicts: Iterable[Dict[str, Any]], run_id: str, created_at: str
) -> List[Dict[str, Any]]:
    """Return at most one question for the first material retained conflict."""
    ordered_conflicts = sorted(conflicts, key=lambda item: item["repository_relative_path"])
    if not ordered_conflicts:
        return []
    conflict = ordered_conflicts[0]
    path = conflict["repository_relative_path"]
    return [
        {
            "affected_artifacts": [path],
            "consequences": [
                "The affected artifact remains UNRESOLVED and preserved.",
                "No recommendation or mutation is authorized by this question.",
            ],
            "conservative_recommendation": "PRESERVE_UNRESOLVED",
            "counter_evidence_ids": conflict["counter_evidence_ids"],
            "created_at": created_at,
            "exact_decision": f"Which scoped intent claim governs {path}?",
            "question_id": f"question_{run_id}_00000001",
            "question_type": "INTENT_CONFLICT",
            "run_id": run_id,
            "schema_version": QUESTION_SCHEMA_VERSION,
            "scope": conflict["scope"],
            "source_conflict_id": conflict["conflict_id"],
            "status": "OPEN",
            "supporting_evidence_ids": conflict["supporting_evidence_ids"],
        }
    ]


def record_user_decision(
    question: Dict[str, Any], answer: str, reason: str, created_at: str
) -> Dict[str, Any]:
    """Build a scoped assertion without altering conflicting repository evidence."""
    if not answer or not reason:
        raise ValueError("a user decision requires an answer and reason")
    decision_payload = {
        "answer": answer,
        "counter_evidence_ids": question["counter_evidence_ids"],
        "question_id": question["question_id"],
        "reason": reason,
        "scope": question["scope"],
        "supporting_evidence_ids": question["supporting_evidence_ids"],
    }
    encoded = json.dumps(
        decision_payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True
    ).encode("utf-8")
    return {
        "answer": answer,
        "counter_evidence_ids": question["counter_evidence_ids"],
        "created_at": created_at,
        "decision_id": f"decision_{question['question_id']}",
        "decision_set_hash": f"sha256:{hashlib.sha256(encoded).hexdigest()}",
        "question_id": question["question_id"],
        "reason": reason,
        "run_id": question["run_id"],
        "schema_version": USER_DECISION_SCHEMA_VERSION,
        "scope": question["scope"],
        "supporting_evidence_ids": question["supporting_evidence_ids"],
    }
