"""Claim-specific selective-risk reports with no admission authority."""

from collections import defaultdict
from typing import Any, Dict, List, Mapping, Optional, Sequence

from repo_curator.evaluation import evaluate_admission


CALIBRATION_REPORT_SCHEMA_VERSION = "repo-curator.calibration-report.v1"
_CONFIDENCE_ORDER = {
    "DETERMINISTIC": 5,
    "STRONG": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
}


def build_calibration_report(
    cases: Sequence[Mapping[str, Any]],
    risk_cases: Sequence[Mapping[str, Any]],
    manifest: Optional[Mapping[str, Any]],
    created_at: str,
) -> Dict[str, Any]:
    """Return descriptive risk-coverage slices after evaluator validation."""
    evaluation = evaluate_admission(cases, risk_cases, created_at, manifest)
    normalized = [_normalized_case(case) for case in cases]
    slices: Dict[tuple, List[Mapping[str, Any]]] = defaultdict(list)
    for case in normalized:
        key = (
            case["claim_type"],
            case["language"],
            case["repository_type"],
            case["repository_family"],
        )
        slices[key].append(case)
    reports = [
        _slice(group, key)
        for key, group in sorted(
            slices.items(),
            key=lambda item: tuple("" if value is None else value for value in item[0]),
        )
    ]
    v2_only = bool(normalized) and all(
        case["schema_version"] == "repo-curator.gold-case.v2"
        for case in normalized
    )
    return {
        "admission_authority": False,
        "corpus_manifest_id": evaluation["corpus_manifest_id"],
        "created_at": created_at,
        "limitations": [
            "CALIBRATION_REPORT_IS_DESCRIPTIVE_ONLY",
            "DISTRIBUTION_SHIFT_NOT_RULED_OUT",
            "MUTATION_AUTHORITY_NOT_GRANTED",
        ],
        "schema_version": CALIBRATION_REPORT_SCHEMA_VERSION,
        "slices": reports,
        "status": (
            "EVIDENCE_AVAILABLE_NOT_ADMITTED" if v2_only else "NOT_CALIBRATED"
        ),
    }


def _normalized_case(case: Mapping[str, Any]) -> Dict[str, Any]:
    labels = case["review_labels"]
    label_values = {label["label"] for label in labels}
    truth = (
        next(iter(label_values))
        if len(labels) >= 2 and len(label_values) == 1
        else "DISAGREED"
        if len(labels) >= 2
        else None
    )
    return {
        "claim_type": case["claim_type"],
        "confidence": case["confidence"],
        "language": case["language"],
        "prediction": case["prediction"],
        "repository_family": case.get("repository_family"),
        "repository_type": case["repository_type"],
        "schema_version": case["schema_version"],
        "truth": truth,
    }


def _slice(cases: Sequence[Mapping[str, Any]], key: tuple) -> Dict[str, Any]:
    consensus = [case for case in cases if case["truth"] in {"SUPPORTED", "UNSUPPORTED"}]
    thresholds = sorted(
        {
            case["confidence"]
            for case in consensus
            if case["confidence"] in _CONFIDENCE_ORDER
        },
        key=lambda value: -_CONFIDENCE_ORDER[value],
    )
    return {
        "candidate_count": len(cases),
        "claim_type": key[0],
        "consensus_count": len(consensus),
        "disagreement_count": sum(case["truth"] == "DISAGREED" for case in cases),
        "language": key[1],
        "repository_family": key[3],
        "repository_type": key[2],
        "risk_coverage_points": [
            _risk_point(consensus, threshold) for threshold in thresholds
        ],
        "unreviewed_count": sum(case["truth"] is None for case in cases),
    }


def _risk_point(
    consensus: Sequence[Mapping[str, Any]], threshold: str
) -> Dict[str, Any]:
    minimum = _CONFIDENCE_ORDER[threshold]
    accepted = [
        case
        for case in consensus
        if case["prediction"] == "ASSERTED"
        and case["confidence"] in _CONFIDENCE_ORDER
        and _CONFIDENCE_ORDER[case["confidence"]] >= minimum
    ]
    false_count = sum(case["truth"] == "UNSUPPORTED" for case in accepted)
    return {
        "accepted_count": len(accepted),
        "coverage": _ratio(len(accepted), len(consensus)),
        "selective_risk": _ratio(false_count, len(accepted)),
        "threshold": threshold,
    }


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator / denominator, 12) if denominator else None
