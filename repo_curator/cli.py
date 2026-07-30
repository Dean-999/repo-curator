import argparse
import importlib.util
import sys
from pathlib import Path
from typing import Optional, Sequence

from repo_curator.budgets import AuditBudgets
from repo_curator.inventory import audit_repository
from repo_curator.interchange import export_ro_crate


_DEFAULT_WAVE3_REPOSITORY_IDS = (
    "climlab", "deepmd-kit", "deepvariant", "deepxde", "multiphysics-bench",
    "nf-core-rnaseq", "nipreps-fmriprep", "psi4", "scanpy",
    "sciml-benchmarks",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="repo-curator")
    subparsers = parser.add_subparsers(dest="workflow", required=True)

    audit_parser = subparsers.add_parser(
        "audit", help="inventory a repository without executing its content"
    )
    audit_parser.add_argument("--root", required=True, type=Path)
    audit_parser.add_argument("--run-id", required=True)
    audit_parser.add_argument("--created-at", required=True)
    audit_parser.add_argument("--max-file-bytes", type=_max_file_bytes, default=33_554_432)
    audit_parser.add_argument("--max-artifacts", type=_max_artifacts, default=100_000)
    audit_parser.add_argument("--max-depth", type=_max_depth, default=128)
    audit_parser.add_argument(
        "--max-directory-entries", type=_max_directory_entries, default=50_000
    )
    audit_parser.add_argument(
        "--max-total-hash-bytes", type=_max_total_hash_bytes, default=1_073_741_824
    )
    audit_parser.add_argument("--compare-to-run", help="verified prior run ID in this target")
    audit_parser.add_argument(
        "--adapter-export-manifest",
        action="append",
        default=[],
        type=Path,
        help="absolute manifest-bound supplied adapter export (repeatable)",
    )

    export_parser = subparsers.add_parser(
        "export-ro-crate", help="export verified audit evidence as a non-executable RO-Crate"
    )
    export_parser.add_argument("--run-directory", required=True, type=Path)
    export_parser.add_argument("--output", required=True, type=Path)

    validation_parser = subparsers.add_parser(
        "validate-ro-crate",
        help="validate a repo-curator evidence RO-Crate under a bounded local profile",
    )
    validation_parser.add_argument("--input", required=True, type=Path)
    validation_parser.add_argument("--output", required=True, type=Path)

    if importlib.util.find_spec("repo_curator.corpus") is not None:
        manifest_parser = subparsers.add_parser(
            "corpus-manifest", help="bind explicit evaluation records to a v2 corpus manifest"
        )
        manifest_parser.add_argument("--cases", required=True, type=Path)
        manifest_parser.add_argument("--risk-cases", required=True, type=Path)
        manifest_parser.add_argument("--reviewer-registry", required=True, type=Path)
        manifest_parser.add_argument("--corpus-id", required=True)
        manifest_parser.add_argument("--evaluator-version", required=True)
        manifest_parser.add_argument("--output", required=True, type=Path)

        evaluate_parser = subparsers.add_parser(
            "evaluate", help="evaluate a manifest-bound corpus without executing repository content"
        )
        evaluate_parser.add_argument("--cases", required=True, type=Path)
        evaluate_parser.add_argument("--risk-cases", required=True, type=Path)
        evaluate_parser.add_argument("--manifest", required=True, type=Path)
        evaluate_parser.add_argument("--artifact-ledger", type=Path)
        evaluate_parser.add_argument("--artifact-root", type=Path)
        evaluate_parser.add_argument("--created-at", required=True)
        evaluate_parser.add_argument("--output", required=True, type=Path)

        verify_parser = subparsers.add_parser(
            "corpus-verify", help="verify every v2 evidence artifact before publishing a receipt"
        )
        verify_parser.add_argument("--cases", required=True, type=Path)
        verify_parser.add_argument("--risk-cases", required=True, type=Path)
        verify_parser.add_argument("--reviewer-registry", required=True, type=Path)
        verify_parser.add_argument("--artifact-ledger", required=True, type=Path)
        verify_parser.add_argument("--artifact-root", required=True, type=Path)
        verify_parser.add_argument("--output", required=True, type=Path)

        card_parser = subparsers.add_parser(
            "corpus-card", help="publish a descriptive card for a snapshot registry"
        )
        card_parser.add_argument("--snapshot-registry", required=True, type=Path)
        card_parser.add_argument("--corpus-id", required=True)
        card_parser.add_argument("--created-at", required=True)
        card_parser.add_argument("--output", required=True, type=Path)

        calibration_parser = subparsers.add_parser(
            "calibrate", help="publish claim-specific descriptive risk-coverage slices"
        )
        calibration_parser.add_argument("--cases", required=True, type=Path)
        calibration_parser.add_argument("--risk-cases", required=True, type=Path)
        calibration_parser.add_argument("--manifest", type=Path)
        calibration_parser.add_argument("--created-at", required=True)
        calibration_parser.add_argument("--output", required=True, type=Path)

    if importlib.util.find_spec("repo_curator.wave3") is not None:
        wave3_parser = subparsers.add_parser(
            "materialize-wave3", help="materialize preregistered Wave 3 review artifacts"
        )
        wave3_parser.add_argument("--snapshot-registry", required=True, type=Path)
        wave3_parser.add_argument("--audit-run-registry", required=True, type=Path)
        wave3_parser.add_argument("--corpus-root", required=True, type=Path)
        wave3_parser.add_argument("--output", required=True, type=Path)
        wave3_parser.add_argument("--created-at", required=True)
        wave3_parser.add_argument("--repository-ids", default=",".join(_DEFAULT_WAVE3_REPOSITORY_IDS))
        wave3_parser.add_argument("--inventory-assertions-per-repository", type=int, default=81)
        wave3_parser.add_argument("--inventory-extra-repository-count", type=int, default=9)
        wave3_parser.add_argument("--controls-per-repository", type=int, default=10)
    return parser


def _max_file_bytes(value: str) -> int:
    try:
        return AuditBudgets(max_file_bytes=int(value)).max_file_bytes
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "max file bytes must be between 1 and 268435456"
        ) from error


def _max_artifacts(value: str) -> int:
    return _validated_budget_argument("max_artifacts", value)


def _max_depth(value: str) -> int:
    return _validated_budget_argument("max_depth", value)


def _max_directory_entries(value: str) -> int:
    return _validated_budget_argument("max_directory_entries", value)


def _max_total_hash_bytes(value: str) -> int:
    return _validated_budget_argument("max_total_hash_bytes", value)


def _validated_budget_argument(field: str, value: str) -> int:
    try:
        parsed = int(value)
        return getattr(AuditBudgets(**{field: parsed}), field)
    except (TypeError, ValueError) as error:
        label = field.replace("_", " ")
        raise argparse.ArgumentTypeError(f"invalid {label}: {error}") from error


def main(arguments: Optional[Sequence[str]] = None) -> int:
    parsed = build_parser().parse_args(arguments)
    if parsed.workflow == "audit":
        try:
            audit_repository(
                root=parsed.root,
                run_id=parsed.run_id,
                created_at=parsed.created_at,
                budgets=AuditBudgets(
                    max_file_bytes=parsed.max_file_bytes,
                    max_artifacts=parsed.max_artifacts,
                    max_depth=parsed.max_depth,
                    max_directory_entries=parsed.max_directory_entries,
                    max_total_hash_bytes=parsed.max_total_hash_bytes,
                ),
                adapter_export_manifests=tuple(parsed.adapter_export_manifest),
                compare_to_run_id=parsed.compare_to_run,
            )
        except (OSError, ValueError) as error:
            print(f"repo-curator: audit failed: {error}", file=sys.stderr)
            return 2
        return 0
    if parsed.workflow == "corpus-manifest":
        from repo_curator.corpus import (
            CorpusError, build_manifest, read_record_array, read_reviewer_registry,
            write_new_json,
        )

        try:
            manifest = build_manifest(
                cases=read_record_array(parsed.cases, "cases"),
                risk_cases=read_record_array(parsed.risk_cases, "risk cases"),
                reviewer_registry=read_reviewer_registry(parsed.reviewer_registry),
                corpus_id=parsed.corpus_id,
                evaluator_version=parsed.evaluator_version,
            )
            write_new_json(parsed.output, manifest)
        except (CorpusError, OSError, ValueError) as error:
            print(f"repo-curator: corpus manifest failed: {error}", file=sys.stderr)
            return 2
        return 0
    if parsed.workflow == "export-ro-crate":
        try:
            export_ro_crate(parsed.run_directory, parsed.output)
        except (OSError, ValueError) as error:
            print(f"repo-curator: RO-Crate export failed: {error}", file=sys.stderr)
            return 2
        return 0
    if parsed.workflow == "validate-ro-crate":
        from repo_curator.ro_crate_validation import (
            RoCrateValidationError,
            validate_evidence_crate_file,
        )

        try:
            validate_evidence_crate_file(parsed.input, parsed.output)
        except (OSError, RoCrateValidationError, ValueError) as error:
            print(f"repo-curator: RO-Crate validation failed: {error}", file=sys.stderr)
            return 2
        return 0
    if parsed.workflow == "evaluate":
        from repo_curator.corpus import (
            CorpusError, evaluate_corpus, read_artifact_ledger, read_json_object,
            read_record_array, write_new_json,
        )
        from repo_curator.evaluation import AdmissionError

        try:
            manifest = read_json_object(parsed.manifest, "manifest")
            if (parsed.artifact_ledger is None) != (parsed.artifact_root is None):
                raise CorpusError("artifact ledger and artifact root must be provided together")
            report = evaluate_corpus(
                cases=read_record_array(parsed.cases, "cases"),
                risk_cases=read_record_array(parsed.risk_cases, "risk cases"),
                manifest=manifest,
                created_at=parsed.created_at,
                artifact_ledger=read_artifact_ledger(parsed.artifact_ledger) if parsed.artifact_ledger else None,
                artifact_root=parsed.artifact_root,
            )
            write_new_json(parsed.output, report)
        except (AdmissionError, CorpusError, OSError, ValueError) as error:
            print(f"repo-curator: evaluation failed: {error}", file=sys.stderr)
            return 2
        return 0
    if parsed.workflow == "corpus-verify":
        from repo_curator.corpus import (
            CorpusError, read_artifact_ledger, read_record_array,
            read_reviewer_registry, verify_corpus_artifacts, write_new_json,
        )
        from repo_curator.evaluation import AdmissionError

        try:
            receipt = verify_corpus_artifacts(
                cases=read_record_array(parsed.cases, "cases"),
                risk_cases=read_record_array(parsed.risk_cases, "risk cases"),
                reviewer_registry=read_reviewer_registry(parsed.reviewer_registry),
                artifact_ledger=read_artifact_ledger(parsed.artifact_ledger),
                artifact_root=parsed.artifact_root,
            )
            write_new_json(parsed.output, receipt)
        except (AdmissionError, CorpusError, OSError, ValueError) as error:
            print(f"repo-curator: corpus verification failed: {error}", file=sys.stderr)
            return 2
        return 0
    if parsed.workflow == "corpus-card":
        from repo_curator.corpus import (
            CorpusError, read_json_object, write_new_json,
        )
        from repo_curator.corpus_card import CorpusCardError, build_corpus_card

        try:
            card = build_corpus_card(
                read_json_object(parsed.snapshot_registry, "snapshot registry"),
                parsed.corpus_id,
                parsed.created_at,
            )
            write_new_json(parsed.output, card)
        except (CorpusCardError, CorpusError, OSError, ValueError) as error:
            print(f"repo-curator: corpus card failed: {error}", file=sys.stderr)
            return 2
        return 0
    if parsed.workflow == "calibrate":
        from repo_curator.calibration import build_calibration_report
        from repo_curator.corpus import (
            CorpusError, read_json_object, read_record_array, write_new_json,
        )
        from repo_curator.evaluation import AdmissionError

        try:
            report = build_calibration_report(
                read_record_array(parsed.cases, "cases"),
                read_record_array(parsed.risk_cases, "risk cases"),
                read_json_object(parsed.manifest, "manifest")
                if parsed.manifest
                else None,
                parsed.created_at,
            )
            write_new_json(parsed.output, report)
        except (AdmissionError, CorpusError, OSError, ValueError) as error:
            print(f"repo-curator: calibration failed: {error}", file=sys.stderr)
            return 2
        return 0
    if parsed.workflow == "materialize-wave3":
        from repo_curator.wave3 import (
            Wave3MaterializationError, Wave3SelectionConfig, materialize_wave3,
        )

        try:
            repository_ids = tuple(identifier for identifier in parsed.repository_ids.split(",") if identifier)
            materialize_wave3(
                snapshot_registry=parsed.snapshot_registry,
                audit_run_registry=parsed.audit_run_registry,
                corpus_root=parsed.corpus_root,
                output=parsed.output,
                created_at=parsed.created_at,
                config=Wave3SelectionConfig(
                    repository_ids=repository_ids,
                    inventory_assertions_per_repository=parsed.inventory_assertions_per_repository,
                    inventory_extra_repository_count=parsed.inventory_extra_repository_count,
                    controls_per_repository=parsed.controls_per_repository,
                ),
            )
        except (Wave3MaterializationError, OSError, ValueError) as error:
            print(f"repo-curator: Wave 3 materialization failed: {error}", file=sys.stderr)
            return 2
        return 0
    raise AssertionError(f"unsupported workflow: {parsed.workflow}")
