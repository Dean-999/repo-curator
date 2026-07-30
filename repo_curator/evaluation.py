"""Score independently reviewed corpus records and conservative admission gates."""

from collections import defaultdict
import hashlib
import json
import math
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence


EVALUATION_SCHEMA_VERSION = "repo-curator.evaluation-report.v1"
GOLD_CASE_SCHEMA_VERSION = "repo-curator.gold-case.v1"
GOLD_CASE_SCHEMA_VERSION_V2 = "repo-curator.gold-case.v2"
CORPUS_MANIFEST_SCHEMA_VERSION = "repo-curator.evaluation-corpus-manifest.v1"
EVALUATION_PROFILE_URI = "https://github.com/Dean-999/repo-curator/tree/main/docs/profiles/evaluation-v1"
_CLAIM_TYPES = {
    "inventory_artifact",
    "exact_byte_duplicate",
    "capability_family",
    "change_episode",
    "intent",
    "mainline",
    "document",
    "experiment_lineage",
}
_PREDICTIONS = {"ASSERTED", "ABSTAINED", "UNRESOLVED"}
_REVIEW_LABELS = {"SUPPORTED", "UNSUPPORTED"}
_MUTATION_SAMPLE_MINIMUM = 3_000
_MUTATION_OPERATION_CLASSES = {"ARCHIVE", "QUARANTINE"}
_SEMANTIC_GATE_REQUIREMENTS = {
    "inventory-recall": {"minimum": 1_000, "minimum_unsupported": 100, "repositories": 5, "families": 3},
    "exact-byte-duplicate-precision": {"minimum": 1_000, "minimum_unsupported": 100, "repositories": 5, "families": 3},
    "capability-family-high-precision": {"minimum": 100, "minimum_unsupported": 50, "repositories": 5, "families": 3},
    "change-episode-strong-precision": {"minimum": 100, "minimum_unsupported": 50, "repositories": 5, "families": 3},
}


class AdmissionError(ValueError):
    """Stable rejection for malformed evaluation records."""


def evaluate_admission(
    cases: Sequence[Mapping[str, Any]],
    risk_cases: Sequence[Mapping[str, Any]],
    created_at: str,
    corpus_manifest: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Return deterministic metrics and a fail-closed admission verdict."""
    v2_present = (
        any(isinstance(case, Mapping) and case.get("schema_version") == GOLD_CASE_SCHEMA_VERSION_V2 for case in cases)
        or any(isinstance(case, Mapping) and case.get("schema_version") == "repo-curator.mutation-risk-case.v2" for case in risk_cases)
    )
    if v2_present and corpus_manifest is None:
        raise AdmissionError("EVALUATION_MANIFEST_REQUIRED")
    if corpus_manifest is not None:
        _validate_manifest(cases, risk_cases, corpus_manifest)
    validated_cases = [_case(case, corpus_manifest) for case in cases]
    if len({case["case_id"] for case in validated_cases}) != len(validated_cases):
        raise AdmissionError("EVALUATION_CASE_DUPLICATE")
    validated_risk_cases = [_risk_case(case) for case in risk_cases]
    metrics = _sliced_metrics(validated_cases)
    gates = _semantic_gates(validated_cases)
    gates.extend(_mutation_gates(validated_risk_cases))
    return {
        "created_at": created_at,
        "gates": gates,
        "metrics": metrics,
        "corpus_manifest_id": corpus_manifest.get("corpus_id") if corpus_manifest else None,
        "conforms_to": [EVALUATION_PROFILE_URI],
        "schema_version": EVALUATION_SCHEMA_VERSION,
        "verdict": "ADMISSION_READY" if gates and all(gate["status"] == "PASSED" for gate in gates) else "SHADOW_ONLY",
    }


def _case(value: Mapping[str, Any], corpus_manifest: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    required_v1 = {
        "case_id", "claim_type", "confidence", "language", "prediction", "repository_type",
        "review_labels", "schema_version",
    }
    required_v2 = required_v1 | {
        "evaluator_version", "expected_label_artifact_hash", "prediction_artifact_hash",
        "repository_family", "repository_id", "repository_snapshot_hash", "run_id",
    }
    if not isinstance(value, Mapping) or value.get("schema_version") not in {GOLD_CASE_SCHEMA_VERSION, GOLD_CASE_SCHEMA_VERSION_V2}:
        raise AdmissionError("EVALUATION_CASE_MALFORMED")
    is_v2 = value["schema_version"] == GOLD_CASE_SCHEMA_VERSION_V2
    if set(value) != (required_v2 if is_v2 else required_v1):
        raise AdmissionError("EVALUATION_CASE_MALFORMED")
    for field in ("case_id", "language", "repository_type"):
        if not isinstance(value[field], str) or not value[field]:
            raise AdmissionError("EVALUATION_CASE_MALFORMED")
    if value["claim_type"] not in _CLAIM_TYPES or value["prediction"] not in _PREDICTIONS:
        raise AdmissionError("EVALUATION_CASE_MALFORMED")
    if value["confidence"] is not None and (not isinstance(value["confidence"], str) or not value["confidence"]):
        raise AdmissionError("EVALUATION_CASE_MALFORMED")
    labels = value["review_labels"]
    if not isinstance(labels, list):
        raise AdmissionError("EVALUATION_LABEL_MALFORMED")
    reviewers = set()
    normalized = []
    for label in labels:
        label_fields = {"label", "reviewer_id", "label_artifact_hash"} if is_v2 else {"label", "reviewer_id"}
        if not isinstance(label, Mapping) or set(label) != label_fields:
            raise AdmissionError("EVALUATION_LABEL_MALFORMED")
        if label["label"] not in _REVIEW_LABELS or not isinstance(label["reviewer_id"], str) or not label["reviewer_id"]:
            raise AdmissionError("EVALUATION_LABEL_MALFORMED")
        if label["reviewer_id"] in reviewers:
            raise AdmissionError("EVALUATION_REVIEWER_INDEPENDENCE")
        reviewers.add(label["reviewer_id"])
        if is_v2 and (
            not _sha256(label["label_artifact_hash"])
            or label["reviewer_id"] not in corpus_manifest.get("reviewer_registry", {})
        ):
            raise AdmissionError("EVALUATION_REVIEWER_PROVENANCE")
        normalized.append(dict(label))
    if is_v2:
        for field in ("evaluator_version", "repository_family", "repository_id", "run_id"):
            if not isinstance(value[field], str) or not value[field]:
                raise AdmissionError("EVALUATION_CASE_MALFORMED")
        for field in ("expected_label_artifact_hash", "prediction_artifact_hash", "repository_snapshot_hash"):
            if not _sha256(value[field]):
                raise AdmissionError("EVALUATION_CASE_MALFORMED")
    return {
        "case_id": value["case_id"],
        "claim_type": value["claim_type"],
        "confidence": value["confidence"],
        "language": value["language"],
        "prediction": value["prediction"],
        "repository_type": value["repository_type"],
        "review_labels": normalized,
        "repository_family": value.get("repository_family"),
        "repository_id": value.get("repository_id"),
        "schema_version": value["schema_version"],
        "truth": _truth(normalized),
    }


def _truth(labels: Sequence[Mapping[str, str]]) -> Optional[str]:
    if len(labels) < 2:
        return None
    values = {label["label"] for label in labels}
    return next(iter(values)) if len(values) == 1 else "DISAGREED"


def _risk_case(value: Mapping[str, Any]) -> Dict[str, Any]:
    required_v1 = {"candidate_id", "invariants_passed", "operation_class", "unsafe_false_positive"}
    required_v2 = {
        "candidate_id", "evaluator_version", "evidence_artifact_hashes", "fault_injection_report_hash",
        "invariant_results", "operation_class", "outcome", "repository_family", "repository_id",
        "repository_snapshot_hash", "schema_version", "test_run_id",
    }
    if not isinstance(value, Mapping):
        raise AdmissionError("EVALUATION_RISK_CASE_MALFORMED")
    is_v2 = value.get("schema_version") == "repo-curator.mutation-risk-case.v2"
    if set(value) != (required_v2 if is_v2 else required_v1):
        raise AdmissionError("EVALUATION_RISK_CASE_MALFORMED")
    if (
        not isinstance(value["candidate_id"], str)
        or not value["candidate_id"]
        or value["operation_class"] not in _MUTATION_OPERATION_CLASSES
    ):
        raise AdmissionError("EVALUATION_RISK_CASE_MALFORMED")
    if not is_v2 and (not isinstance(value["invariants_passed"], bool) or not isinstance(value["unsafe_false_positive"], bool)):
        raise AdmissionError("EVALUATION_RISK_CASE_MALFORMED")
    if not is_v2:
        return {**value, "repository_family": None, "repository_id": None, "schema_version": "repo-curator.mutation-risk-case.v1"}
    for field in ("evaluator_version", "repository_family", "repository_id", "test_run_id"):
        if not isinstance(value[field], str) or not value[field]:
            raise AdmissionError("EVALUATION_RISK_CASE_MALFORMED")
    if not _sha256(value["fault_injection_report_hash"]) or not _sha256(value["repository_snapshot_hash"]):
        raise AdmissionError("EVALUATION_RISK_CASE_MALFORMED")
    artifacts = value["evidence_artifact_hashes"]
    invariants = value["invariant_results"]
    if not isinstance(artifacts, list) or not artifacts or not all(_sha256(item) for item in artifacts):
        raise AdmissionError("EVALUATION_RISK_CASE_MALFORMED")
    if (
        not isinstance(invariants, list) or not invariants
        or not all(isinstance(item, Mapping) and set(item) == {"invariant_id", "status"} and isinstance(item["invariant_id"], str) and item["invariant_id"] and item["status"] in {"PASSED", "FAILED"} for item in invariants)
    ):
        raise AdmissionError("EVALUATION_RISK_CASE_MALFORMED")
    if value["outcome"] not in {"SAFE", "UNSAFE_FALSE_POSITIVE"}:
        raise AdmissionError("EVALUATION_RISK_CASE_MALFORMED")
    return {
        **value,
        "invariants_passed": all(item["status"] == "PASSED" for item in invariants),
        "unsafe_false_positive": value["outcome"] == "UNSAFE_FALSE_POSITIVE",
    }


def _sliced_metrics(cases: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    slices: Dict[tuple[str, str, str], List[Mapping[str, Any]]] = defaultdict(list)
    for case in cases:
        slices[(case["claim_type"], case["language"], case["repository_type"])].append(case)
    return [
        _metrics(group, claim_type, language, repository_type)
        for (claim_type, language, repository_type), group in sorted(slices.items())
    ]


def _metrics(
    cases: Sequence[Mapping[str, Any]], claim_type: str, language: str, repository_type: str
) -> Dict[str, Any]:
    candidate_count = len(cases)
    consensus = [case for case in cases if case["truth"] in _REVIEW_LABELS]
    asserted = [case for case in consensus if case["prediction"] == "ASSERTED"]
    true_positive = sum(case["truth"] == "SUPPORTED" for case in asserted)
    false_positive = sum(case["truth"] == "UNSUPPORTED" for case in asserted)
    false_negative = sum(
        case["truth"] == "SUPPORTED" and case["prediction"] != "ASSERTED" for case in consensus
    )
    return {
        "abstention_rate": _ratio(sum(case["prediction"] == "ABSTAINED" for case in cases), candidate_count),
        "candidate_count": candidate_count,
        "claim_type": claim_type,
        "consensus_count": len(consensus),
        "coverage": _ratio(len(consensus), candidate_count),
        "disagreement_count": sum(case["truth"] == "DISAGREED" for case in cases),
        "false_negative_count": false_negative,
        "false_positive_count": false_positive,
        "language": language,
        "precision": _ratio(true_positive, true_positive + false_positive),
        "recall": _ratio(true_positive, true_positive + false_negative),
        "repository_type": repository_type,
        "true_positive_count": true_positive,
        "unresolved_rate": _ratio(sum(case["prediction"] == "UNRESOLVED" for case in cases), candidate_count),
        "unreviewed_count": sum(case["truth"] is None for case in cases),
    }


def _semantic_gates(cases: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    return [
        _metric_gate("inventory-recall", cases, lambda case: case["claim_type"] == "inventory_artifact", lambda case: case["claim_type"] == "inventory_artifact", "recall", 0.999, False),
        _metric_gate("exact-byte-duplicate-precision", cases, lambda case: case["claim_type"] == "exact_byte_duplicate", lambda case: case["claim_type"] == "exact_byte_duplicate", "precision", 1.0, False),
        _metric_gate("capability-family-high-precision", cases, lambda case: case["claim_type"] == "capability_family" and case["confidence"] == "HIGH", lambda case: case["claim_type"] == "capability_family", "precision", 0.95, True),
        _metric_gate("change-episode-strong-precision", cases, lambda case: case["claim_type"] == "change_episode" and case["confidence"] == "STRONG", lambda case: case["claim_type"] == "change_episode", "precision", 0.9, True),
    ]


def _metric_gate(
    gate_id: str,
    cases: Sequence[Mapping[str, Any]],
    selector: Callable[[Mapping[str, Any]], bool],
    population_selector: Callable[[Mapping[str, Any]], bool],
    metric: str,
    threshold: float,
    confidence_bound: bool,
) -> Dict[str, Any]:
    selected = [case for case in cases if selector(case)]
    if not selected:
        return _blocked_gate(gate_id, {"reason": "NO_REVIEWED_CASES", "required": threshold})
    measured = _metrics(selected, "ALL", "ALL", "ALL")
    if measured["consensus_count"] == 0:
        return _blocked_gate(gate_id, {"reason": "NO_REVIEWED_CASES", "required": threshold, "observed": measured})
    requirement = _SEMANTIC_GATE_REQUIREMENTS[gate_id]
    v2_consensus = [case for case in selected if case["schema_version"] == GOLD_CASE_SCHEMA_VERSION_V2 and case["truth"] in _REVIEW_LABELS]
    population = [case for case in cases if population_selector(case) and case["schema_version"] == GOLD_CASE_SCHEMA_VERSION_V2]
    population_consensus = [case for case in population if case["truth"] in _REVIEW_LABELS]
    unsupported_count = sum(case["truth"] == "UNSUPPORTED" for case in population_consensus)
    repositories = {case["repository_id"] for case in v2_consensus}
    families = {case["repository_family"] for case in v2_consensus}
    if len(repositories) < requirement["repositories"] or len(families) < requirement["families"]:
        return _blocked_gate(gate_id, {"reason": "INSUFFICIENT_REPOSITORY_DIVERSITY", "repositories": len(repositories), "families": len(families)})
    if len(v2_consensus) < requirement["minimum"]:
        return _blocked_gate(gate_id, {"reason": "INSUFFICIENT_REVIEWED_CASES", "minimum": requirement["minimum"], "observed": len(v2_consensus)})
    if unsupported_count < requirement["minimum_unsupported"]:
        return _blocked_gate(gate_id, {"reason": "INSUFFICIENT_LABEL_DISTRIBUTION", "unsupported": unsupported_count})
    measured = _metrics(v2_consensus, "ALL", "ALL", "ALL")
    observed = measured[metric]
    successes, total = _metric_counts(v2_consensus, metric)
    lower_bound = _wilson_lower_bound(successes, total) if confidence_bound else observed
    return {
        "gate_id": gate_id,
        "observed": {"metric": metric, "value": observed, "lower_confidence_bound": lower_bound, "reviewed_case_count": measured["consensus_count"], "repository_count": len(repositories), "repository_family_count": len(families), "label_coverage": _ratio(len(population_consensus), len(population)), "supported_scope_coverage": _ratio(len(v2_consensus), len(population_consensus))},
        "required": threshold,
        "status": "PASSED" if lower_bound is not None and lower_bound >= threshold else "BLOCKED",
    }


def _mutation_gates(risk_cases: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    by_operation: Dict[str, List[Mapping[str, Any]]] = defaultdict(list)
    for case in risk_cases:
        by_operation[case["operation_class"]].append(case)
    gates = []
    for operation_class in sorted(_MUTATION_OPERATION_CLASSES):
        group = by_operation[operation_class]
        if not group:
            gates.append(_blocked_gate(
                "mutation-risk-corpus:{}".format(operation_class),
                {"reason": "NO_RISK_CASES", "required": {"minimum_relevant_candidates": _MUTATION_SAMPLE_MINIMUM}},
            ))
            continue
        candidate_ids = {case["candidate_id"] for case in group}
        if len(candidate_ids) != len(group):
            raise AdmissionError("EVALUATION_RISK_CASE_DUPLICATE")
        v2_group = [case for case in group if case["schema_version"] == "repo-curator.mutation-risk-case.v2"]
        repositories = {case["repository_id"] for case in v2_group}
        families = {case["repository_family"] for case in v2_group}
        if len(repositories) < 5 or len(families) < 3:
            gates.append(_blocked_gate(
                "mutation-risk-corpus:{}".format(operation_class),
                {"reason": "INSUFFICIENT_REPOSITORY_DIVERSITY", "repositories": len(repositories), "families": len(families)},
            ))
            continue
        observed = {
            "invariants_passed": all(case["invariants_passed"] for case in v2_group),
            "relevant_candidate_count": len(v2_group),
            "repository_count": len(repositories),
            "repository_family_count": len(families),
            "unsafe_false_positive_count": sum(case["unsafe_false_positive"] for case in v2_group),
        }
        gates.append({
            "gate_id": "mutation-risk-corpus:{}".format(operation_class),
            "observed": observed,
            "required": {"invariants_passed": True, "minimum_relevant_candidates": _MUTATION_SAMPLE_MINIMUM, "unsafe_false_positive_count": 0},
            "status": "PASSED" if observed["invariants_passed"] and observed["relevant_candidate_count"] >= _MUTATION_SAMPLE_MINIMUM and observed["unsafe_false_positive_count"] == 0 else "BLOCKED",
        })
    return gates


def _blocked_gate(gate_id: str, observed: Mapping[str, Any]) -> Dict[str, Any]:
    return {"gate_id": gate_id, "observed": dict(observed), "status": "BLOCKED"}


def _ratio(numerator: int, denominator: int) -> Optional[float]:
    return round(numerator / denominator, 12) if denominator else None


def _metric_counts(cases: Sequence[Mapping[str, Any]], metric: str) -> tuple[int, int]:
    asserted = [case for case in cases if case["prediction"] == "ASSERTED"]
    if metric == "precision":
        return sum(case["truth"] == "SUPPORTED" for case in asserted), len(asserted)
    supported = [case for case in cases if case["truth"] == "SUPPORTED"]
    return sum(case["prediction"] == "ASSERTED" for case in supported), len(supported)


def _wilson_lower_bound(successes: int, total: int, z: float = 1.959963984540054) -> Optional[float]:
    if total == 0:
        return None
    probability = successes / total
    denominator = 1 + z * z / total
    centre = probability + z * z / (2 * total)
    margin = z * math.sqrt((probability * (1 - probability) + z * z / (4 * total)) / total)
    return round((centre - margin) / denominator, 12)


def _validate_manifest(cases: Sequence[Mapping[str, Any]], risk_cases: Sequence[Mapping[str, Any]], manifest: Mapping[str, Any]) -> None:
    required = {"case_records_sha256", "corpus_id", "evaluator_version", "reviewer_registry", "risk_records_sha256", "schema_version"}
    if not isinstance(manifest, Mapping) or set(manifest) != required or manifest.get("schema_version") != CORPUS_MANIFEST_SCHEMA_VERSION:
        raise AdmissionError("EVALUATION_MANIFEST_MALFORMED")
    if not isinstance(manifest.get("corpus_id"), str) or not manifest["corpus_id"] or not isinstance(manifest.get("evaluator_version"), str):
        raise AdmissionError("EVALUATION_MANIFEST_MALFORMED")
    registry = manifest.get("reviewer_registry")
    if not isinstance(registry, Mapping) or not all(isinstance(key, str) and key and _sha256(value) for key, value in registry.items()):
        raise AdmissionError("EVALUATION_MANIFEST_MALFORMED")
    if manifest.get("case_records_sha256") != _digest(cases) or manifest.get("risk_records_sha256") != _digest(risk_cases):
        raise AdmissionError("EVALUATION_MANIFEST_HASH_MISMATCH")
    identities: Dict[str, tuple[Any, Any]] = {}
    for record in list(cases) + list(risk_cases):
        if not isinstance(record, Mapping) or record.get("schema_version") not in {GOLD_CASE_SCHEMA_VERSION_V2, "repo-curator.mutation-risk-case.v2"}:
            continue
        if record.get("evaluator_version") != manifest["evaluator_version"]:
            raise AdmissionError("EVALUATION_EVALUATOR_VERSION_MISMATCH")
        repository_id = record.get("repository_id")
        identity = (record.get("repository_family"), record.get("repository_snapshot_hash"))
        if repository_id in identities and identities[repository_id] != identity:
            raise AdmissionError("EVALUATION_REPOSITORY_IDENTITY_CONFLICT")
        identities[repository_id] = identity


def _digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 71 and value.startswith("sha256:") and all(character in "0123456789abcdef" for character in value[7:])
