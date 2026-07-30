"""Build and black-box verify a portable repo-curator release candidate."""

import argparse
import datetime
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPOSITORY_ROOT))

from repo_curator.bundle import build_skill_bundle
from repo_curator.hardening import REQUIRED_ADVERSARIAL_CASES, load_adversarial_matrix


RELEASE_CHECK_SCHEMA_VERSION = "repo-curator.release-check.v2"
RELEASE_CHECKLIST_PATH = Path("docs") / "release-checklist.md"
UPSTREAM_REVIEW_SCHEMA_VERSION = "repo-curator.upstream-review.v1"
UPSTREAM_REVIEW_BYTE_LIMIT = 4 * 1024 * 1024
UPSTREAM_REVIEW_MAX_AGE_DAYS = 90
UPSTREAM_REVIEW_MIN_SOURCE_COVERAGE_PERCENT = 80


def main(arguments: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="build and black-box verify a repo-curator Skill release candidate"
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--upstream-review", required=True, type=Path)
    parser.add_argument("--release-at", default=_utc_now())
    parsed = parser.parse_args(arguments)
    try:
        report = check_release(
            REPOSITORY_ROOT,
            parsed.output,
            parsed.upstream_review,
            parsed.release_at,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"repo-curator: release check failed: {error}", file=sys.stderr)
        return 2
    _write_new_json(parsed.output, report)
    return 0


def check_release(
    source_root: Path,
    output: Path,
    upstream_review: Path,
    release_at: str,
) -> Dict[str, Any]:
    """Return a release receipt after exercising a new bundle outside its checkout."""
    source_root = source_root.resolve(strict=True)
    output = output.absolute()
    if output.exists() or output.is_symlink():
        raise ValueError(f"release check output already exists: {output}")
    if not output.parent.is_dir():
        raise ValueError(f"release check output parent is not a directory: {output.parent}")
    _verify_release_checklist(source_root)
    hardening = _verify_hardening_artifacts(source_root)
    upstream_review_binding = _verify_upstream_review(
        source_root, upstream_review, release_at
    )
    with tempfile.TemporaryDirectory(prefix="repo-curator-release-check-") as temporary_directory:
        temporary_path = Path(temporary_directory)
        bundle = build_skill_bundle(source_root, temporary_path / "bundle")
        manifest = _verify_bundle_manifest(bundle)
        target = temporary_path / "research-repository"
        target.mkdir()
        marker = target / "target-code-executed"
        build_marker = temporary_path / "target-build-instruction-executed"
        notebook_marker = temporary_path / "target-notebook-code-executed"
        notebook_secret = "release-check-notebook-output-secret"
        provider_secret = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        history_secret = "gho_ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        data_package_uri_secret = "release-check-uri-password"
        data_package_inline_value = "release-check-inline-value-not-persisted"
        git = shutil.which("git", path=os.defpath)
        if git is None:
            raise ValueError("system Git is required for release history-secret verification")
        _run([git, "init"], target)
        (target / "retired-credential.txt").write_text(
            history_secret + "\n", encoding="utf-8"
        )
        _run([git, "add", "retired-credential.txt"], target)
        _run(
            [
                git,
                "-c",
                "user.email=release-check@example.test",
                "-c",
                "user.name=Release Check",
                "commit",
                "-m",
                "add retired credential fixture",
            ],
            target,
        )
        history_secret_commit = _run([git, "rev-parse", "HEAD"], target).stdout.strip()
        (target / "retired-credential.txt").unlink()
        (target / "README.md").write_text("mainline: analysis.py\n", encoding="utf-8")
        (target / "preserved-link").symlink_to("README.md")
        (target / "analysis.py").write_text("print('not executed')\n", encoding="utf-8")
        (target / "provider-secret.txt").write_text(
            provider_secret + "\n", encoding="utf-8"
        )
        (target / "datapackage.json").write_text(
            json.dumps(
                {
                    "name": "release-check-data",
                    "resources": [
                        {
                            "format": "py",
                            "name": "analysis",
                            "path": "analysis.py",
                        },
                        {
                            "name": "remote",
                            "path": (
                                "https://fixture-user:"
                                + data_package_uri_secret
                                + "@example.test/data.csv"
                            ),
                        },
                        {
                            "data": [["value"], [data_package_inline_value]],
                            "name": "inline",
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        (target / "danger.py").write_text(
            "from pathlib import Path\n"
            f"Path({str(marker)!r}).write_text('executed')\n",
            encoding="utf-8",
        )
        binder = target / "binder"
        binder.mkdir()
        (binder / "environment.yml").write_text("name: release-check\n", encoding="utf-8")
        (binder / "postBuild").write_text(
            "#!/bin/sh\n" f"touch {str(build_marker)!r}\n",
            encoding="utf-8",
        )
        (target / "analysis.ipynb").write_text(
            json.dumps(
                {
                    "cells": [
                        {
                            "cell_type": "code",
                            "execution_count": 1,
                            "metadata": {},
                            "outputs": [
                                {
                                    "name": "stdout",
                                    "output_type": "stream",
                                    "text": notebook_secret,
                                }
                            ],
                            "source": [
                                "from pathlib import Path\n",
                                f"Path({str(notebook_marker)!r}).write_text('executed')\n",
                            ],
                        }
                    ],
                    "metadata": {
                        "kernelspec": {
                            "display_name": "Python 3",
                            "language": "python",
                            "name": "python3",
                        }
                    },
                    "nbformat": 4,
                    "nbformat_minor": 5,
                }
            ),
            encoding="utf-8",
        )
        _run([git, "add", "-A"], target)
        _run(
            [
                git,
                "-c",
                "user.email=release-check@example.test",
                "-c",
                "user.name=Release Check",
                "commit",
                "-m",
                "remove retired credential fixture",
            ],
            target,
        )
        (target / "preserved-link").unlink()
        (target / "preserved-link").write_text("README.md", encoding="utf-8")
        (target / "large-staged-result.bin").write_bytes(b"x" * (500 * 1024 + 1))
        (target / "broken-link").symlink_to("missing-target")
        _run([git, "add", "preserved-link", "large-staged-result.bin"], target)
        runner = bundle / "scripts" / "run_audit.py"
        _run(
            [
                sys.executable,
                str(runner),
                "audit",
                "--root",
                str(target),
                "--run-id",
                "release-check-run",
                "--created-at",
                "2026-07-27T00:00:00Z",
            ],
            temporary_path,
        )
        run_directory = target / ".repo-curator" / "runs" / "release-check-run"
        _verify_run_hashes(run_directory)
        _verify_environment_declaration(run_directory)
        _verify_notebook_profile(run_directory, notebook_secret)
        _verify_secret_redaction(run_directory, provider_secret)
        _verify_git_history_secret(
            run_directory, history_secret, history_secret_commit
        )
        _verify_repository_hygiene(run_directory)
        _verify_data_package(
            run_directory,
            data_package_uri_secret,
            data_package_inline_value,
        )
        export_path = temporary_path / "ro-crate-metadata.json"
        _run(
            [
                sys.executable,
                str(runner),
                "export-ro-crate",
                "--run-directory",
                str(run_directory),
                "--output",
                str(export_path),
            ],
            temporary_path,
        )
        export = _read_json(export_path, "RO-Crate export")
        root = next(
            (
                record
                for record in export.get("@graph", [])
                if isinstance(record, dict) and record.get("@id") == "./"
            ),
            None,
        )
        if not isinstance(root, dict) or root.get("repo-curator:executionAuthorized") is not False:
            raise ValueError("RO-Crate export is not explicitly non-executable")
        validation_path = temporary_path / "ro-crate-validation.json"
        _run(
            [
                sys.executable,
                str(runner),
                "validate-ro-crate",
                "--input",
                str(export_path),
                "--output",
                str(validation_path),
            ],
            temporary_path,
        )
        validation = _read_json(validation_path, "RO-Crate validation")
        if (
            validation.get("schema_version")
            != "repo-curator.ro-crate-validation-report.v1"
            or validation.get("status") != "BOUNDED_PROFILE_CONFORMANT"
            or validation.get("full_shacl_conformance_claimed") is not False
            or validation.get("admission_authority") is not False
            or validation.get("execution_authority") != "NONE"
        ):
            raise ValueError("RO-Crate validation report is not safely bounded")
        if marker.exists() or build_marker.exists() or notebook_marker.exists():
            raise ValueError("release smoke target code was executed")
        return {
            **hardening,
            "audit_output_hashes_verified": True,
            "bundle_manifest_sha256": hashlib.sha256(
                (bundle / "manifest.json").read_bytes()
            ).hexdigest(),
            "bundle_schema_version": manifest["schema_version"],
            "bundle_source_git": manifest["source_git"],
            "data_package_observer_verified": True,
            "environment_declaration_verified": True,
            "git_history_secret_scan_verified": True,
            "human_admission_status": "NOT_ADMITTED",
            "notebook_profile_verified": True,
            "repository_hygiene_verified": True,
            "release_checklist_markers_verified": True,
            "ro_crate_export_verified": True,
            "ro_crate_validation_verified": True,
            "schema_version": RELEASE_CHECK_SCHEMA_VERSION,
            "secret_redaction_verified": True,
            "status": "PASSED",
            "target_execution_prevented": True,
            "mutation_workflow_status": "NOT_EXPOSED",
            "upstream_review": upstream_review_binding,
        }


def _verify_bundle_manifest(bundle: Path) -> Dict[str, Any]:
    manifest = _read_json(bundle / "manifest.json", "bundle manifest")
    files = manifest.get("files")
    if manifest.get("schema_version") != "repo-curator.skill-bundle.v4" or not isinstance(files, dict):
        raise ValueError("bundle manifest is unsupported")
    source_git = manifest.get("source_git")
    if (
        not isinstance(source_git, dict)
        or set(source_git)
        != {
            "distributed_inputs_sha256",
            "distributed_inputs_state",
            "head_commit",
            "head_tree",
        }
        or source_git.get("distributed_inputs_state")
        not in {"MATCHES_HEAD", "DIFFERS_FROM_HEAD"}
        or not _hex_identifier(source_git.get("distributed_inputs_sha256"), {64})
        or not _hex_identifier(source_git.get("head_commit"), {40, 64})
        or not _hex_identifier(source_git.get("head_tree"), {40, 64})
    ):
        raise ValueError("bundle manifest source Git identity is invalid")
    for relative_path, expected_hash in files.items():
        if not isinstance(relative_path, str) or not isinstance(expected_hash, str):
            raise ValueError("bundle manifest entry is invalid")
        path = bundle / relative_path
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f"bundle manifest hash mismatch: {relative_path}")
    return manifest


def _hex_identifier(value: Any, lengths: set[int]) -> bool:
    return (
        isinstance(value, str)
        and len(value) in lengths
        and all(character in "0123456789abcdef" for character in value)
    )


def _verify_release_checklist(source_root: Path) -> None:
    required_lines = (
        "- [x] Current Skill release mode: READ_ONLY",
        "- [x] Mutation workflows exposed: NO",
        "- [x] Formal calibrated accuracy claim: NOT_PUBLISHED",
        "- [x] Schema compatibility: EXACT_VERSION_ONLY",
        "- [x] Unknown schema versions: REJECT",
        "- [x] Third-party source lock: REQUIRED",
        "- [x] Third-party notices: REQUIRED",
        "- [x] Upstream changes: SHADOW_REVIEW_BEFORE_ADOPTION",
        "- [x] Known limitations: DOCUMENTED",
        "- [x] Verified-run input byte and entity budgets: REQUIRED",
        "- [x] RO-Crate descriptor-relative durable publication: REQUIRED",
        "- [x] Bundle source Git and distributed-input identity: REQUIRED",
        "- [x] Upstream source-metadata coverage floor: 80_PERCENT",
        "- [x] Adapter adversarial matrix: REQUIRED",
        "- [x] Corpus transparency card: DESCRIPTIVE_NOT_ADMISSION",
        "- [x] Selective calibration publication: DESCRIPTIVE_NOT_ADMISSION",
        "- [x] Human corpus admission: NOT_ADMITTED",
        "- [x] Local release provenance: EXACT_IN_TOTO_STATEMENT_AND_SLSA_V1_PREDICATE",
        "- [x] Hosted release attestation action: AVAILABILITY_GATED_IMMUTABLE_COMMIT_PIN",
        "- [x] Evidence RO-Crate validation: BOUNDED_LOCAL_SHACL_SUBSET",
        "- [x] Recovery primitives: INTERNAL_NOT_EXPOSED",
        "- [x] Rollback primitives: INTERNAL_NOT_EXPOSED",
    )
    try:
        checklist = (source_root / RELEASE_CHECKLIST_PATH).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ValueError("release checklist is unavailable") from error
    lines = checklist.splitlines()
    if any(lines.count(required_line) != 1 for required_line in required_lines):
        raise ValueError("release checklist is incomplete")


def _verify_hardening_artifacts(source_root: Path) -> Dict[str, bool]:
    """Verify required trust artifacts without granting semantic admission."""
    try:
        matrix = load_adversarial_matrix(
            source_root / "tests" / "fixtures" / "adapter-adversarial-matrix.json"
        )
        card = _read_json(
            source_root
            / "evaluation-corpus"
            / "pilot-2026-07-25"
            / "corpus-card.json",
            "corpus card",
        )
        registry = _read_json(
            source_root / "schemas" / "registry.json", "schema registry"
        )
    except (OSError, ValueError) as error:
        raise ValueError("required hardening artifact is unavailable") from error
    schema_ids = {
        item.get("schema_id")
        for item in registry.get("schemas", [])
        if isinstance(item, dict)
    }
    required_schema_ids = {
        "repo-curator.calibration-report.v1",
        "repo-curator.corpus-card.v1",
        "repo-curator.release-provenance.v1",
        "repo-curator.ro-crate-validation-report.v1",
    }
    required_paths = (
        "repo_curator/release_provenance.py",
        "tools/build_release_provenance.py",
        "tools/verify_release_provenance.py",
        ".github/workflows/attest-release.yml",
        "schemas/ro-crate-evidence-profile.shacl.ttl",
    )
    if (
        len(matrix) < 7
        or any(set(cases) != set(REQUIRED_ADVERSARIAL_CASES) for cases in matrix.values())
        or card.get("schema_version") != "repo-curator.corpus-card.v1"
        or card.get("admission_authority") != "NONE"
        or card.get("corpus_id") != "pilot-2026-07-25"
        or not required_schema_ids.issubset(schema_ids)
        or any(not (source_root / path).is_file() for path in required_paths)
    ):
        raise ValueError("required hardening artifact contract is incomplete")
    return {
        "adapter_adversarial_matrix_verified": True,
        "calibration_contract_verified": True,
        "corpus_card_contract_verified": True,
        "release_provenance_tooling_verified": True,
    }


def _verify_upstream_review(
    source_root: Path, review_path: Path, release_at: str
) -> Dict[str, Any]:
    release_time = _parse_timestamp(release_at, "release-at")
    payload = _read_bounded_regular_file(review_path, UPSTREAM_REVIEW_BYTE_LIMIT)
    try:
        review = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
        lock_bytes = (source_root / "third_party" / "sources.lock.yaml").read_bytes()
        lock = json.loads(lock_bytes.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("upstream review receipt is malformed") from error
    if not isinstance(review, dict) or not isinstance(lock, dict):
        raise ValueError("upstream review receipt is malformed")
    checked_at = review.get("checked_at")
    if not isinstance(checked_at, str):
        raise ValueError("upstream review receipt timestamp is missing")
    review_time = _parse_timestamp(checked_at, "upstream review checked-at")
    age = release_time - review_time
    policy = review.get("review_policy")
    entries = review.get("entries")
    lock_entries = lock.get("entries")
    if not isinstance(lock_entries, list) or not lock_entries or not all(
        isinstance(entry, dict) and isinstance(entry.get("id"), str)
        for entry in lock_entries
    ):
        raise ValueError("source lock entries are malformed")
    locked_by_id = {entry["id"]: entry for entry in lock_entries}
    expected_ids = sorted(locked_by_id)
    if not isinstance(entries, list) or not all(
        isinstance(entry, dict) and isinstance(entry.get("source_id"), str)
        for entry in entries
    ):
        raise ValueError("upstream review receipt entries are malformed")
    observed_ids = sorted(entry.get("source_id") for entry in entries)
    if len(observed_ids) != len(set(observed_ids)):
        raise ValueError("upstream review receipt source IDs are duplicated")
    _verify_upstream_entries(entries, locked_by_id)
    source_observed_count = sum(
        entry["source_status"] != "UNAVAILABLE" for entry in entries
    )
    if (
        source_observed_count * 100
        < len(entries) * UPSTREAM_REVIEW_MIN_SOURCE_COVERAGE_PERCENT
    ):
        raise ValueError("upstream review source coverage is below release policy")
    expected_summary = {
        "entry_count": len(entries),
        "license_review_count": sum(
            entry["license_status"] == "REVIEW_REQUIRED" for entry in entries
        ),
        "limitation_count": sum(bool(entry["limitations"]) for entry in entries),
        "review_required_count": sum(
            bool(entry["review_required"]) for entry in entries
        ),
        "source_drift_count": sum(
            entry["source_status"] == "DEFAULT_HEAD_DIFFERS_FROM_LOCK"
            for entry in entries
        ),
    }
    expected_status = (
        "COMPLETED_WITH_LIMITATIONS"
        if expected_summary["limitation_count"]
        else "COMPLETED_WITH_REVIEW_CANDIDATES"
        if expected_summary["review_required_count"]
        else "COMPLETED"
    )
    if (
        review.get("schema_version") != UPSTREAM_REVIEW_SCHEMA_VERSION
        or review.get("source_lock_sha256")
        != hashlib.sha256(lock_bytes).hexdigest()
        or review.get("status") != expected_status
        or review.get("summary") != expected_summary
        or age < datetime.timedelta(0)
        or age > datetime.timedelta(days=UPSTREAM_REVIEW_MAX_AGE_DAYS)
        or not isinstance(policy, dict)
        or policy.get("adoption") != "MANUAL_REVIEW_ONLY"
        or policy.get("cadence") != lock.get("review_policy", {}).get("cadence")
        or policy.get("upstream_changes_enter_shadow_first") is not True
        or observed_ids != expected_ids
        or any(
            entry.get("adoption_effect")
            not in {"NO_CHANGE", "NO_CHANGE_REVIEW_REQUIRED"}
            for entry in entries
        )
    ):
        raise ValueError("upstream review receipt does not satisfy release policy")
    return {
        "checked_at": checked_at,
        "receipt_sha256": hashlib.sha256(payload).hexdigest(),
        "source_lock_sha256": review["source_lock_sha256"],
        "source_observed_count": source_observed_count,
        "source_total_count": len(entries),
        "source_coverage_percent": round(
            source_observed_count * 100 / len(entries), 2
        ),
        "status": review["status"],
        "summary": expected_summary,
    }


def _verify_upstream_entries(
    entries: List[Dict[str, Any]], locked_by_id: Dict[str, Dict[str, Any]]
) -> None:
    required_fields = {
        "adoption_effect",
        "distributed_code",
        "integration_mode",
        "license_status",
        "limitations",
        "locked_commit",
        "locked_license_spdx",
        "observed_default_branch",
        "observed_head_commit",
        "observed_license_spdx",
        "repository",
        "review_required",
        "source_id",
        "source_status",
    }
    allowed_limitations = {
        "UPSTREAM_HOST_UNSUPPORTED",
        "UPSTREAM_HTTP_CLIENT_ERROR",
        "UPSTREAM_HTTP_RATE_LIMITED",
        "UPSTREAM_HTTP_SERVER_ERROR",
        "UPSTREAM_LICENSE_METADATA_UNAVAILABLE",
        "UPSTREAM_METADATA_UNAVAILABLE",
        "UPSTREAM_NETWORK_UNAVAILABLE",
        "UPSTREAM_RESPONSE_INVALID",
    }
    for entry in entries:
        locked = locked_by_id.get(entry["source_id"])
        if locked is None or set(entry) != required_fields:
            raise ValueError("upstream review receipt entry is incomplete")
        limitations = entry["limitations"]
        source_status = entry["source_status"]
        license_status = entry["license_status"]
        if (
            entry["distributed_code"] is not locked["distributed_code"]
            or entry["integration_mode"] != locked["integration_mode"]
            or entry["locked_commit"] != locked["commit"]
            or entry["locked_license_spdx"] != locked["license"]["spdx"]
            or entry["repository"] != locked["repository"]
            or source_status
            not in {
                "DEFAULT_HEAD_DIFFERS_FROM_LOCK",
                "LOCKED_COMMIT_IS_DEFAULT_HEAD",
                "UNAVAILABLE",
            }
            or license_status
            not in {"MATCH", "NOT_COMPARABLE", "REVIEW_REQUIRED", "UNAVAILABLE"}
            or not isinstance(limitations, list)
            or len(limitations) != len(set(limitations))
            or any(limitation not in allowed_limitations for limitation in limitations)
            or not isinstance(entry["review_required"], bool)
        ):
            raise ValueError("upstream review receipt entry is inconsistent")
        observed_head = entry["observed_head_commit"]
        observed_branch = entry["observed_default_branch"]
        if source_status == "UNAVAILABLE":
            if observed_head is not None or observed_branch is not None or not limitations:
                raise ValueError("upstream review unavailable entry is inconsistent")
        elif (
            not isinstance(observed_branch, str)
            or not observed_branch
            or not isinstance(observed_head, str)
            or len(observed_head) != 40
            or any(character not in "0123456789abcdef" for character in observed_head)
            or (
                source_status == "LOCKED_COMMIT_IS_DEFAULT_HEAD"
                and observed_head != locked["commit"]
            )
            or (
                source_status == "DEFAULT_HEAD_DIFFERS_FROM_LOCK"
                and observed_head == locked["commit"]
            )
        ):
            raise ValueError("upstream review source observation is inconsistent")
        expected_review_required = (
            source_status == "DEFAULT_HEAD_DIFFERS_FROM_LOCK"
            or license_status == "REVIEW_REQUIRED"
        )
        observed_license = entry["observed_license_spdx"]
        locked_license = locked["license"]["spdx"]
        if (
            (license_status == "MATCH" and observed_license != locked_license)
            or (
                license_status == "REVIEW_REQUIRED"
                and (
                    not isinstance(observed_license, str)
                    or observed_license in {"", "NOASSERTION", locked_license}
                )
            )
            or (license_status == "NOT_COMPARABLE" and locked_license != "NOASSERTION")
            or (license_status == "UNAVAILABLE" and not limitations)
        ):
            raise ValueError("upstream review license observation is inconsistent")
        expected_effect = (
            "NO_CHANGE_REVIEW_REQUIRED"
            if expected_review_required or limitations
            else "NO_CHANGE"
        )
        if (
            entry["review_required"] is not expected_review_required
            or entry["adoption_effect"] != expected_effect
        ):
            raise ValueError("upstream review adoption state is inconsistent")


def _parse_timestamp(value: str, label: str) -> datetime.datetime:
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from error
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed


def _read_bounded_regular_file(path: Path, limit: int) -> bytes:
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > limit:
            raise ValueError("upstream review receipt is not a bounded regular file")
        chunks = []
        remaining = limit + 1
        while remaining:
            chunk = os.read(descriptor, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
    finally:
        os.close(descriptor)
    payload = b"".join(chunks)
    if len(payload) > limit:
        raise ValueError("upstream review receipt exceeds byte limit")
    return payload


def _unique_object(pairs: List[tuple[str, Any]]) -> Dict[str, Any]:
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _utc_now() -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _verify_run_hashes(run_directory: Path) -> None:
    run = _read_json(run_directory / "run.json", "audit run")
    hashes = run.get("output_file_hashes")
    if run.get("final_status") not in {"COMPLETED", "COMPLETED_WITH_LIMITATIONS"} or not isinstance(hashes, dict):
        raise ValueError("audit run is not finalized")
    for name, expected_hash in hashes.items():
        if not isinstance(name, str) or "/" in name or not isinstance(expected_hash, str):
            raise ValueError("audit output hash declaration is invalid")
        path = run_directory / name
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise ValueError(f"audit output hash mismatch: {name}")


def _verify_environment_declaration(run_directory: Path) -> None:
    path = run_directory / "adapter-observations.jsonl"
    try:
        observations = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("adapter observations are not valid JSONL") from error
    observation = next(
        (
            item
            for item in observations
            if isinstance(item, dict)
            and item.get("declaration_family") == "COMPUTATIONAL_ENVIRONMENT"
        ),
        None,
    )
    if (
        observation is None
        or observation.get("environment_scope") != "BINDER"
        or observation.get("active_environment_marker_paths")
        != ["binder/environment.yml", "binder/postBuild"]
        or "ENVIRONMENT_BUILD_INSTRUCTIONS_NOT_EXECUTED"
        not in observation.get("limitations", [])
    ):
        raise ValueError("bundled environment declaration observer is unavailable")


def _verify_notebook_profile(run_directory: Path, secret: str) -> None:
    path = run_directory / "profiles.jsonl"
    try:
        payload = path.read_bytes()
        profiles = [json.loads(line) for line in payload.splitlines()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("profiles are not valid JSONL") from error
    profile = next(
        (
            item
            for item in profiles
            if isinstance(item, dict)
            and item.get("repository_relative_path") == "analysis.ipynb"
        ),
        None,
    )
    if (
        profile is None
        or profile.get("format") != "NOTEBOOK"
        or profile.get("sample") != ""
        or profile.get("metadata", {}).get("cell_count") != 1
        or profile.get("metadata", {}).get("output_count") != 1
        or profile.get("metadata", {}).get("kernel", {}).get("name") != "python3"
        or "NOTEBOOK_OUTPUTS_UNTRUSTED_NOT_PERSISTED"
        not in profile.get("limitations", [])
        or secret.encode("utf-8") in payload
    ):
        raise ValueError("bundled notebook envelope observer is unavailable or unsafe")


def _verify_secret_redaction(run_directory: Path, secret: str) -> None:
    path = run_directory / "profiles.jsonl"
    try:
        payload = path.read_bytes()
        profiles = [json.loads(line) for line in payload.splitlines()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("profiles are not valid JSONL") from error
    profile = next(
        (
            item
            for item in profiles
            if isinstance(item, dict)
            and item.get("repository_relative_path") == "provider-secret.txt"
        ),
        None,
    )
    if (
        profile is None
        or profile.get("sample") != "[REDACTED:GITHUB_TOKEN]\n"
        or profile.get("redactions") != ["GITHUB_TOKEN"]
        or secret.encode("utf-8") in payload
    ):
        raise ValueError("bundled high-confidence secret redaction is unavailable")


def _verify_git_history_secret(
    run_directory: Path, secret: str, commit_id: str
) -> None:
    path = run_directory / "git-observations.jsonl"
    try:
        payload = path.read_bytes()
        observations = [json.loads(line) for line in payload.splitlines()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Git observations are not valid JSONL") from error
    summary = next(
        (
            item
            for item in observations
            if isinstance(item, dict)
            and item.get("observation_type") == "GIT_SECRET_HISTORY_SUMMARY"
        ),
        None,
    )
    expected_finding = {
        "category": "GITHUB_TOKEN",
        "commit_id": commit_id,
        "repository_relative_path": "retired-credential.txt",
    }
    if (
        summary is None
        or summary.get("status") != "OBSERVED"
        or summary.get("credential_validation") != "NOT_PERFORMED"
        or expected_finding not in summary.get("findings", [])
        or secret.encode("utf-8") in payload
    ):
        raise ValueError("bundled Git history secret scan is unavailable or unsafe")


def _verify_repository_hygiene(run_directory: Path) -> None:
    try:
        git_observations = [
            json.loads(line)
            for line in (run_directory / "git-observations.jsonl").read_bytes().splitlines()
        ]
        inventory = [
            json.loads(line)
            for line in (run_directory / "inventory.jsonl").read_bytes().splitlines()
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("repository hygiene evidence is not valid JSONL") from error
    summary = next(
        (
            item
            for item in git_observations
            if isinstance(item, dict)
            and item.get("observation_type") == "GIT_REPOSITORY_HYGIENE_SUMMARY"
        ),
        None,
    )
    broken_link = next(
        (
            item
            for item in inventory
            if isinstance(item, dict)
            and item.get("repository_relative_path") == "broken-link"
        ),
        None,
    )
    if (
        summary is None
        or summary.get("status") != "OBSERVED"
        or summary.get("staged_large_file_count") != 1
        or [
            item.get("repository_relative_path")
            for item in summary.get("staged_large_files", [])
        ]
        != ["large-staged-result.bin"]
        or summary.get("destroyed_symlink_count") != 1
        or summary.get("destroyed_symlinks")
        != [
            {
                "index_mode": "100644",
                "match_status": "CONTENT_ID_EQUAL",
                "repository_relative_path": "preserved-link",
            }
        ]
        or "GIT_REPOSITORY_HYGIENE_NOT_CLEANUP_AUTHORITY"
        not in summary.get("limitations", [])
        or broken_link is None
        or "SYMLINK_TARGET_MISSING" not in broken_link.get("warnings", [])
    ):
        raise ValueError("bundled repository hygiene observer is unavailable or unsafe")


def _verify_data_package(
    run_directory: Path, uri_secret: str, inline_value: str
) -> None:
    path = run_directory / "adapter-observations.jsonl"
    try:
        observations = [json.loads(line) for line in path.read_bytes().splitlines()]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("adapter observations are not valid JSONL") from error
    observation = next(
        (
            item
            for item in observations
            if isinstance(item, dict)
            and item.get("declaration_family") == "DATA_PACKAGE"
        ),
        None,
    )
    resources = (
        observation.get("data_package", {}).get("resources", [])
        if isinstance(observation, dict)
        else []
    )
    local = next(
        (item for item in resources if item.get("name") == "analysis"), None
    )
    remote = next(
        (item for item in resources if item.get("name") == "remote"), None
    )
    inline = next(
        (item for item in resources if item.get("name") == "inline"), None
    )
    if (
        observation is None
        or observation.get("validation_status") != "SYNTAX_VALIDATED"
        or local is None
        or local.get("local_paths")
        != [
            {
                "inventory_status": "PRESENT",
                "repository_relative_path": "analysis.py",
            }
        ]
        or remote is None
        or remote.get("source_kind") != "REMOTE_PATH"
        or "local_paths" in remote
        or inline is None
        or inline.get("source_kind") != "INLINE_DATA"
    ):
        raise ValueError("bundled Data Package observer is unavailable or unsafe")
    for output in run_directory.iterdir():
        if output.is_file():
            payload = output.read_bytes()
            if uri_secret.encode("utf-8") in payload or inline_value.encode("utf-8") in payload:
                raise ValueError("Data Package values leaked into audit output")


def _run(arguments: List[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(arguments, cwd=cwd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise ValueError(result.stderr.strip() or "release smoke command failed")
    return result


def _read_json(path: Path, label: str) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError(f"{label} is not valid JSON") from error
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _write_new_json(path: Path, value: Dict[str, Any]) -> None:
    encoded = (json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True) + "\n").encode("utf-8")
    path = path.absolute()
    parent = path.parent.resolve(strict=True)
    parent_descriptor = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    descriptor = None
    created_identity = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path.name, flags, 0o600, dir_fd=parent_descriptor)
        created = os.fstat(descriptor)
        created_identity = (created.st_dev, created.st_ino)
        offset = 0
        while offset < len(encoded):
            written = os.write(descriptor, encoded[offset:])
            if written <= 0:
                raise OSError("release receipt write made no progress")
            offset += written
        os.fsync(descriptor)
        os.fsync(parent_descriptor)
    except BaseException:
        if descriptor is not None:
            os.close(descriptor)
            descriptor = None
        if created_identity is not None:
            try:
                current = os.stat(
                    path.name, dir_fd=parent_descriptor, follow_symlinks=False
                )
                if (current.st_dev, current.st_ino) == created_identity:
                    os.unlink(path.name, dir_fd=parent_descriptor)
                    os.fsync(parent_descriptor)
            except OSError:
                pass
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_descriptor)


if __name__ == "__main__":
    raise SystemExit(main())
