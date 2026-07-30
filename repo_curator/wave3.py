"""Deterministically materialize preregistered Wave 3 review artifacts."""

import hashlib
import json
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple


_MAX_INPUT_BYTES = 64 * 1024 * 1024
_SELECTION_SCHEMA_VERSION = "repo-curator.wave3-pre-review.v1"
_PREDICTION_SCHEMA_VERSION = "repo-curator.wave3-prediction.v1"
_EXPECTED_LABEL_SCHEMA_VERSION = "repo-curator.wave3-expected-label.v1"
_DEFAULT_REPOSITORY_IDS = (
    "climlab", "deepmd-kit", "deepvariant", "deepxde", "multiphysics-bench",
    "nf-core-rnaseq", "nipreps-fmriprep", "psi4", "scanpy",
    "sciml-benchmarks",
)


class Wave3MaterializationError(ValueError):
    """Raised when the frozen Wave 3 inputs cannot be safely materialized."""


@dataclass(frozen=True)
class Wave3SelectionConfig:
    """Preregistered candidate counts and source order for a Wave 3 release."""

    repository_ids: Tuple[str, ...] = _DEFAULT_REPOSITORY_IDS
    inventory_assertions_per_repository: int = 81
    inventory_extra_repository_count: int = 9
    controls_per_repository: int = 10

    def validate(self) -> None:
        if not self.repository_ids or len(set(self.repository_ids)) != len(self.repository_ids):
            raise Wave3MaterializationError("repository IDs must be nonempty and distinct")
        if any(not isinstance(repository_id, str) or not repository_id for repository_id in self.repository_ids):
            raise Wave3MaterializationError("repository IDs must be nonempty and distinct")
        if self.inventory_assertions_per_repository < 1:
            raise Wave3MaterializationError("inventory assertions per repository must be positive")
        if not 0 <= self.inventory_extra_repository_count <= len(self.repository_ids):
            raise Wave3MaterializationError("inventory extra repository count is invalid")
        if self.controls_per_repository < 1:
            raise Wave3MaterializationError("controls per repository must be positive")


def materialize_wave3(
    snapshot_registry: Path,
    audit_run_registry: Path,
    corpus_root: Path,
    output: Path,
    created_at: str,
    config: Wave3SelectionConfig = Wave3SelectionConfig(),
) -> Path:
    """Create one reviewer-ready Wave 3 evidence package without labels."""
    if not isinstance(created_at, str) or not created_at:
        raise Wave3MaterializationError("created at must be a nonempty string")
    config.validate()
    corpus_root = _validated_directory(corpus_root, "corpus root")
    output = _validated_output_path(output)
    snapshots = _read_json_object(snapshot_registry, "snapshot registry")
    audit_runs = _read_json_object(audit_run_registry, "audit run registry")
    sources = _load_sources(corpus_root, snapshots, audit_runs, config)
    cases = _select_cases(sources, config, created_at)
    _publish(output, cases, config, created_at, _hash_file(snapshot_registry), _hash_file(audit_run_registry))
    return output


def _load_sources(
    corpus_root: Path,
    snapshots: Mapping[str, Any],
    audit_runs: Mapping[str, Any],
    config: Wave3SelectionConfig,
) -> List[Dict[str, Any]]:
    repositories = _indexed_records(snapshots, "repositories", "repository_id", "snapshot registry")
    runs = _indexed_records(audit_runs, "audit_runs", "repository_id", "audit run registry")
    sources = []
    for repository_id in config.repository_ids:
        if repository_id not in repositories or repository_id not in runs:
            raise Wave3MaterializationError("missing frozen source for {}".format(repository_id))
        repository = repositories[repository_id]
        run_entry = runs[repository_id]
        descriptor_path = _relative_file(corpus_root, repository.get("snapshot_descriptor_path"), "snapshot descriptor")
        descriptor_hash = _hash_file(descriptor_path)
        if descriptor_hash != repository.get("snapshot_descriptor_sha256"):
            raise Wave3MaterializationError("snapshot descriptor hash mismatch for {}".format(repository_id))
        if descriptor_hash != run_entry.get("snapshot_descriptor_sha256"):
            raise Wave3MaterializationError("audit snapshot binding mismatch for {}".format(repository_id))
        descriptor = _read_json_object(descriptor_path, "snapshot descriptor")
        if descriptor.get("repository_id") != repository_id:
            raise Wave3MaterializationError("snapshot descriptor repository mismatch for {}".format(repository_id))
        if descriptor.get("git_commit_sha") != repository.get("commit_sha"):
            raise Wave3MaterializationError("snapshot descriptor commit mismatch for {}".format(repository_id))
        run_path = _relative_file(corpus_root, run_entry.get("run_path"), "audit run")
        if _hash_file(run_path) != run_entry.get("run_sha256"):
            raise Wave3MaterializationError("audit run hash mismatch for {}".format(repository_id))
        run = _read_json_object(run_path, "audit run")
        if run.get("run_id") != run_entry.get("run_id"):
            raise Wave3MaterializationError("audit run ID mismatch for {}".format(repository_id))
        if run.get("git_head") != descriptor.get("git_commit_sha"):
            raise Wave3MaterializationError("audit run head mismatch for {}".format(repository_id))
        run_directory = run_path.parent
        inventory_path = run_directory / "inventory.jsonl"
        relationships_path = run_directory / "relationships.jsonl"
        output_hashes = run.get("output_file_hashes")
        if not isinstance(output_hashes, Mapping):
            raise Wave3MaterializationError("audit output hashes are malformed for {}".format(repository_id))
        if _bare_hash_file(inventory_path) != output_hashes.get("inventory.jsonl"):
            raise Wave3MaterializationError("inventory hash mismatch for {}".format(repository_id))
        if _bare_hash_file(relationships_path) != output_hashes.get("relationships.jsonl"):
            raise Wave3MaterializationError("relationship hash mismatch for {}".format(repository_id))
        inventory = _read_json_lines(inventory_path, "inventory")
        relationships = _read_json_lines(relationships_path, "relationships")
        for record in inventory:
            if record.get("run_id") != run_entry["run_id"]:
                raise Wave3MaterializationError("inventory run binding mismatch for {}".format(repository_id))
        for record in relationships:
            if record.get("run_id") != run_entry["run_id"]:
                raise Wave3MaterializationError("relationship run binding mismatch for {}".format(repository_id))
        eligible = sorted(
            (
                record for record in inventory
                if record.get("object_type") == "REGULAR_FILE"
                and record.get("profile_eligibility") == "ELIGIBLE"
                and isinstance(record.get("artifact_id"), str)
                and isinstance(record.get("content_id"), str)
                and not record.get("warnings")
            ),
            key=lambda record: record["artifact_id"],
        )
        if len({record["artifact_id"] for record in eligible}) != len(eligible):
            raise Wave3MaterializationError("eligible inventory IDs are not unique for {}".format(repository_id))
        sources.append({
            "descriptor_hash": descriptor_hash,
            "descriptor_path": str(descriptor_path.relative_to(corpus_root)),
            "inventory": inventory,
            "inventory_hash": "sha256:" + _bare_hash_file(inventory_path),
            "eligible": eligible,
            "relationships": relationships,
            "relationships_hash": "sha256:" + _bare_hash_file(relationships_path),
            "repository": repository,
            "run": run,
            "run_entry": run_entry,
        })
    return sources


def _select_cases(sources: Sequence[Mapping[str, Any]], config: Wave3SelectionConfig, created_at: str) -> List[Dict[str, Any]]:
    cases = []
    for source_index, source in enumerate(sources):
        repository_id = source["repository"]["repository_id"]
        assertion_count = config.inventory_assertions_per_repository + (
            1 if source_index < config.inventory_extra_repository_count else 0
        )
        if len(source["eligible"]) < assertion_count:
            raise Wave3MaterializationError("insufficient eligible inventory for {}".format(repository_id))
        for index, record in enumerate(source["eligible"][:assertion_count], start=1):
            cases.append(_inventory_case(source, record, index, "ASSERTED", "SUPPORTED", created_at))
        inventory_paths = {record.get("repository_relative_path") for record in source["inventory"]}
        for index in range(1, config.controls_per_repository + 1):
            control_path = "__repo_curator_negative_control__/case-{:03d}".format(index)
            if control_path in inventory_paths:
                raise Wave3MaterializationError("negative inventory control exists for {}".format(repository_id))
            cases.append(_inventory_case(source, {"repository_relative_path": control_path}, index, "ABSTAINED", "UNSUPPORTED", created_at, control=True))
    relationship_sources = []
    for source in sources:
        for relationship in source["relationships"]:
            if relationship.get("relationship_type") != "EXACT_BYTE_DUPLICATE":
                continue
            member_ids = relationship.get("member_artifact_ids")
            if (
                not isinstance(member_ids, list)
                or len(member_ids) < 2
                or len(set(member_ids)) != len(member_ids)
                or not all(isinstance(value, str) for value in member_ids)
            ):
                raise Wave3MaterializationError("duplicate relationship is malformed")
            relationship_sources.append((relationship["relationship_id"], source, relationship))
    if len({item[0] for item in relationship_sources}) != len(relationship_sources):
        raise Wave3MaterializationError("duplicate relationship IDs are not unique")
    for _, source, relationship in sorted(relationship_sources, key=lambda item: item[0]):
        cases.append(_duplicate_case(source, relationship, "ASSERTED", "SUPPORTED", created_at))
    for source in sources:
        controls = _nonmatch_controls(source, config.controls_per_repository)
        if len(controls) != config.controls_per_repository:
            raise Wave3MaterializationError("insufficient nonmatch controls for {}".format(source["repository"]["repository_id"]))
        for index, pair in enumerate(controls, start=1):
            cases.append(_duplicate_case(source, {"member_artifact_ids": pair, "relationship_id": None}, "ABSTAINED", "UNSUPPORTED", created_at, control_index=index))
    if len({case["case_id"] for case in cases}) != len(cases):
        raise Wave3MaterializationError("selected case IDs are not unique")
    return cases


def _inventory_case(source: Mapping[str, Any], record: Mapping[str, Any], index: int, prediction: str, expected_truth: str, created_at: str, control: bool = False) -> Dict[str, Any]:
    repository_id = source["repository"]["repository_id"]
    suffix = "control-{:03d}".format(index) if control else "{:03d}".format(index)
    path = record["repository_relative_path"]
    claim = "The frozen inventory identifies `{}` as a regular-file artifact.".format(path)
    evidence = {"inventory_artifact_id": record.get("artifact_id"), "repository_relative_path": path}
    return _base_case(source, "wave3-inventory-{}-{}".format(repository_id, suffix), "inventory_artifact", prediction, expected_truth, claim, evidence, created_at)


def _duplicate_case(source: Mapping[str, Any], relationship: Mapping[str, Any], prediction: str, expected_truth: str, created_at: str, control_index: int = 0) -> Dict[str, Any]:
    repository_id = source["repository"]["repository_id"]
    member_ids = list(relationship["member_artifact_ids"])
    if control_index:
        suffix = "control-{:03d}".format(control_index)
    else:
        suffix = relationship["relationship_id"].rsplit("_", 1)[-1]
    members = ", ".join("`{}`".format(member_id) for member_id in member_ids)
    claim = "The frozen evidence identifies {} as one exact-byte duplicate group; this does not establish common lineage or purpose.".format(members)
    evidence = {"member_artifact_ids": member_ids, "relationship_id": relationship.get("relationship_id")}
    return _base_case(source, "wave3-duplicate-{}-{}".format(repository_id, suffix), "exact_byte_duplicate", prediction, expected_truth, claim, evidence, created_at)


def _base_case(source: Mapping[str, Any], case_id: str, claim_type: str, prediction: str, expected_truth: str, claim: str, evidence: Mapping[str, Any], created_at: str) -> Dict[str, Any]:
    return {
        "case_id": case_id,
        "claim": claim,
        "claim_type": claim_type,
        "confidence": "DETERMINISTIC",
        "created_at": created_at,
        "evidence": dict(evidence),
        "expected_truth": expected_truth,
        "prediction": prediction,
        "repository_family": source["repository"]["repository_family"],
        "repository_id": source["repository"]["repository_id"],
        "repository_snapshot_hash": source["descriptor_hash"],
        "repository_type": source["repository"]["repository_type"],
        "run_id": source["run_entry"]["run_id"],
        "run_sha256": source["run_entry"]["run_sha256"],
        "source_evidence": {
            "inventory_hash": source["inventory_hash"],
            "relationships_hash": source["relationships_hash"],
            "snapshot_descriptor_path": source["descriptor_path"],
        },
    }


def _nonmatch_controls(source: Mapping[str, Any], count: int) -> List[List[str]]:
    relationship_pairs = set()
    for relationship in source["relationships"]:
        member_ids = relationship.get("member_artifact_ids")
        if relationship.get("relationship_type") != "EXACT_BYTE_DUPLICATE" or not isinstance(member_ids, list):
            continue
        for left_index, left in enumerate(member_ids):
            for right in member_ids[left_index + 1:]:
                relationship_pairs.add(frozenset((left, right)))
    selected = []
    used = set()
    eligible = source["eligible"]
    for left_index, left in enumerate(eligible):
        for right in eligible[left_index + 1:]:
            pair = frozenset((left["artifact_id"], right["artifact_id"]))
            if left["artifact_id"] in used or right["artifact_id"] in used:
                continue
            if left["content_id"] == right["content_id"] or pair in relationship_pairs:
                continue
            selected.append(sorted(pair))
            used.update(pair)
            if len(selected) == count:
                return selected
    return selected


def _publish(output: Path, cases: Sequence[Mapping[str, Any]], config: Wave3SelectionConfig, created_at: str, snapshot_registry_hash: str, audit_registry_hash: str) -> None:
    try:
        os.mkdir(output, 0o700)
    except FileExistsError as error:
        raise Wave3MaterializationError("output already exists") from error
    predictions = output / "predictions"
    expected_labels = output / "expected-labels"
    case_cards = output / "case-cards"
    for directory in (predictions, expected_labels, case_cards):
        directory.mkdir(mode=0o700)
    selection_cases = []
    for case in cases:
        case_id = case["case_id"]
        prediction_path = predictions / "{}.json".format(case_id)
        expected_path = expected_labels / "{}.json".format(case_id)
        card_path = case_cards / "{}.md".format(case_id)
        _write_json(prediction_path, {
            "case_id": case_id,
            "claim": case["claim"],
            "claim_type": case["claim_type"],
            "confidence": case["confidence"],
            "evidence": case["evidence"],
            "prediction": case["prediction"],
            "repository_id": case["repository_id"],
            "run_id": case["run_id"],
            "schema_version": _PREDICTION_SCHEMA_VERSION,
        })
        _write_json(expected_path, {
            "case_id": case_id,
            "claim_type": case["claim_type"],
            "expected_truth": case["expected_truth"],
            "schema_version": _EXPECTED_LABEL_SCHEMA_VERSION,
        })
        _write_text(card_path, _case_card(case))
        selection_cases.append({
            **case,
            "case_card_path": "case-cards/{}.md".format(case_id),
            "case_card_sha256": _hash_file(card_path),
            "expected_label_path": "expected-labels/{}.json".format(case_id),
            "expected_label_sha256": _hash_file(expected_path),
            "prediction_path": "predictions/{}.json".format(case_id),
            "prediction_sha256": _hash_file(prediction_path),
        })
    claim_counts = {
        claim_type: sum(case["claim_type"] == claim_type for case in selection_cases)
        for claim_type in sorted({case["claim_type"] for case in selection_cases})
    }
    _write_json(output / "selection.json", {
        "case_count": len(selection_cases),
        "cases": selection_cases,
        "claim_counts": claim_counts,
        "created_at": created_at,
        "input_hashes": {
            "audit_run_registry": audit_registry_hash,
            "snapshot_registry": snapshot_registry_hash,
        },
        "schema_version": _SELECTION_SCHEMA_VERSION,
        "selection_config": {
            "controls_per_repository": config.controls_per_repository,
            "inventory_assertions_per_repository": config.inventory_assertions_per_repository,
            "inventory_extra_repository_count": config.inventory_extra_repository_count,
            "repository_ids": list(config.repository_ids),
        },
    })
    _write_text(output / "README.md", "# Wave 3 Pre-Review Package\n\nThis package contains frozen predictions, expected labels, and reviewer-visible case cards. It contains no reviewer labels and does not authorize mutation.\n")


def _case_card(case: Mapping[str, Any]) -> str:
    return "\n".join((
        "# Review Case",
        "",
        "- Case ID: `{}`".format(case["case_id"]),
        "- Claim type: `{}`".format(case["claim_type"]),
        "- Repository: `{}`".format(case["repository_id"]),
        "- Snapshot descriptor hash: `{}`".format(case["repository_snapshot_hash"]),
        "- Audit run: `{}` ({})".format(case["run_id"], case["run_sha256"]),
        "",
        "## Claim",
        "",
        case["claim"],
        "",
        "## Frozen Evidence",
        "",
        "- Snapshot descriptor: `{}`".format(case["source_evidence"]["snapshot_descriptor_path"]),
        "- Inventory output SHA-256: `{}`".format(case["source_evidence"]["inventory_hash"]),
        "- Relationship output SHA-256: `{}`".format(case["source_evidence"]["relationships_hash"]),
        "- Evidence locator: `{}`".format(json.dumps(case["evidence"], ensure_ascii=True, sort_keys=True)),
        "",
    ))


def _indexed_records(value: Mapping[str, Any], key: str, identifier: str, name: str) -> Dict[str, Mapping[str, Any]]:
    records = value.get(key)
    if not isinstance(records, list):
        raise Wave3MaterializationError("{} is malformed".format(name))
    indexed = {}
    for record in records:
        if not isinstance(record, Mapping) or not isinstance(record.get(identifier), str) or not record[identifier]:
            raise Wave3MaterializationError("{} is malformed".format(name))
        if record[identifier] in indexed:
            raise Wave3MaterializationError("{} has duplicate identifiers".format(name))
        indexed[record[identifier]] = record
    return indexed


def _validated_directory(path: Path, name: str) -> Path:
    if path.is_symlink() or not path.is_dir():
        raise Wave3MaterializationError("{} must be a directory".format(name))
    return path.resolve(strict=True)


def _validated_output_path(path: Path) -> Path:
    if path.is_symlink() or path.exists():
        raise Wave3MaterializationError("output already exists")
    parent = path.parent
    if parent.is_symlink() or not parent.is_dir():
        raise Wave3MaterializationError("output parent directory does not exist")
    return path


def _relative_file(root: Path, relative_path: Any, name: str) -> Path:
    if not isinstance(relative_path, str) or not relative_path:
        raise Wave3MaterializationError("{} path is unsafe".format(name))
    parts = relative_path.split("/")
    if any(not part or part in {".", ".."} for part in parts) or relative_path.startswith("/"):
        raise Wave3MaterializationError("{} path is unsafe".format(name))
    path = root.joinpath(*parts)
    if path.is_symlink() or not path.is_file():
        raise Wave3MaterializationError("{} must be a regular file".format(name))
    return path


def _read_json_object(path: Path, name: str) -> Dict[str, Any]:
    value = _read_json(path, name)
    if not isinstance(value, Mapping):
        raise Wave3MaterializationError("{} is malformed".format(name))
    return dict(value)


def _read_json_lines(path: Path, name: str) -> List[Dict[str, Any]]:
    value = _read_bytes(path, name)
    records = []
    try:
        for line in value.decode("utf-8").splitlines():
            parsed = json.loads(line)
            if not isinstance(parsed, Mapping):
                raise Wave3MaterializationError("{} is malformed".format(name))
            records.append(dict(parsed))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise Wave3MaterializationError("{} is malformed".format(name)) from error
    return records


def _read_json(path: Path, name: str) -> Any:
    value = _read_bytes(path, name)
    try:
        return json.loads(value.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise Wave3MaterializationError("{} is malformed".format(name)) from error


def _read_bytes(path: Path, name: str) -> bytes:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags)
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_size > _MAX_INPUT_BYTES:
            raise Wave3MaterializationError("{} must be a bounded regular file".format(name))
        chunks = []
        while True:
            chunk = os.read(descriptor, 1_048_576)
            if not chunk:
                break
            chunks.append(chunk)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _hash_file(path: Path) -> str:
    return "sha256:" + _bare_hash_file(path)


def _bare_hash_file(path: Path) -> str:
    return hashlib.sha256(_read_bytes(path, "artifact")).hexdigest()


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n")


def _write_text(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(value)
        stream.flush()
        os.fsync(stream.fileno())
