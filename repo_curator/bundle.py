"""Build a self-contained repo-curator Skill bundle from one source tree."""

import errno
import hashlib
import json
import os
import shutil
import subprocess
import stat
from pathlib import Path
from typing import Dict

from repo_curator import __version__


BUNDLE_SCHEMA_VERSION = "repo-curator.skill-bundle.v4"
SOURCE_LOCK_SCHEMA_VERSION = "repo-curator.third-party-sources-lock.v1"
SCHEMA_REGISTRY_SCHEMA_VERSION = "repo-curator.schema-registry.v1"
_SKILL_PATH = Path(".agents") / "skills" / "repo-curator"
_SOURCE_LOCK_PATH = Path("third_party") / "sources.lock.yaml"
_LICENSES_PATH = Path("third_party") / "licenses"
_NOTICES_SOURCE_PATH = Path("docs") / "THIRD_PARTY_NOTICES.md"
_NOTICES_BUNDLE_PATH = Path("THIRD_PARTY_NOTICES.md")
_SCHEMA_REGISTRY_PATH = Path("schemas") / "registry.json"
_SCHEMA_GUIDANCE_PATH = Path("schemas") / "README.md"
_RO_CRATE_SHAPE_PATH = Path("schemas") / "ro-crate-evidence-profile.shacl.ttl"
_MAX_BUNDLE_SOURCE_FILE_BYTES = 67_108_864
_LICENSE_TEXT_MARKERS = {
    "Apache-2.0": ("Apache License", "Version 2.0, January 2004"),
    "BSD-3-Clause": (
        "Redistribution and use in source and binary forms",
        "Neither the name of the copyright holder",
    ),
}

# Explicit runtime closure for the published read-only Skill. Evaluation tooling and
# every mutation-capable module remain source-tree-only.
_READ_ONLY_RUNTIME_MODULES = frozenset({
    "__init__.py",
    "__main__.py",
    "advanced.py",
    "archives.py",
    "brief.py",
    "budgets.py",
    "cli.py",
    "data_package.py",
    "decisions.py",
    "declarations.py",
    "documents.py",
    "environment_declarations.py",
    "evidence.py",
    "experiments.py",
    "git_evidence.py",
    "git_repository_size.py",
    "identity.py",
    "intent.py",
    "interchange.py",
    "inventory.py",
    "notebook_envelope.py",
    "prior_runs.py",
    "profiles.py",
    "report_html.py",
    "relationships.py",
    "repository_hygiene.py",
    "research_metadata.py",
    "ro_crate_graph.py",
    "ro_crate_validation.py",
    "scanner.py",
    "secret_redaction.py",
    "shadow.py",
    "structural.py",
    "supplied_exports.py",
    "workflow_run_crate.py",
})

_REQUIRED_SCHEMA_IDS = frozenset({
    "repo-curator.adapter-observation.v1", "repo-curator.apply-journal.v2",
    "repo-curator.semantic-adapter-observation.v1",
    "repo-curator.dvc-observation.v1", "repo-curator.mlflow-observation.v1",
    "repo-curator.datalad-observation.v1", "repo-curator.bagit-observation.v1",
    "repo-curator.near-duplicate-candidate.v1", "repo-curator.evidence-coverage.v1",
    "repo-curator.approval.v1", "repo-curator.archive-observation.v1",
    "repo-curator.archive-plan.v1", "repo-curator.canonical-entry-point.v1",
    "repo-curator.canonical-result-candidate.v1",
    "repo-curator.canonical-result-candidate.v2", "repo-curator.capability-family.v1",
    "repo-curator.change-episode.v1", "repo-curator.classification.v1",
    "repo-curator.classification.v2",
    "repo-curator.corpus-artifact-ledger.v1", "repo-curator.corpus-artifact-verification.v1",
    "repo-curator.curation-brief.v1", "repo-curator.curation-brief.v2",
    "repo-curator.curation-brief.v3",
    "repo-curator.decision-question.v1",
    "repo-curator.decision-question.v2",
    "repo-curator.document-comparison.v1", "repo-curator.evaluation-corpus-manifest.v1",
    "repo-curator.evaluation-report.v1", "repo-curator.evidence.v1",
    "repo-curator.experiment-attempt.v1", "repo-curator.experiment-attempt.v2",
    "repo-curator.experiment-bundle.v1", "repo-curator.experiment-bundle.v2",
    "repo-curator.git-observation.v1", "repo-curator.gold-case.v1",
    "repo-curator.gold-case.v2", "repo-curator.implementation-role.v1",
    "repo-curator.intent-conflict.v1", "repo-curator.inventory.v1",
    "repo-curator.mainline-map.v1", "repo-curator.mutation-risk-case.v1",
    "repo-curator.mutation-risk-case.v2", "repo-curator.profile.v2",
    "repo-curator.project-intent.v1", "repo-curator.python-structure.v1",
    "repo-curator.prior-run-comparison.v1",
    "repo-curator.quarantine-plan.v1", "repo-curator.recommendation.v1",
    "repo-curator.relationship.v1", "repo-curator.relationship.v2",
    "repo-curator.reproducibility-gap.v1",
    "repo-curator.reproducibility-gap.v2",
    "repo-curator.release-check.v2", "repo-curator.release-provenance.v1",
    "repo-curator.retention-policy.v1", "repo-curator.rollback-plan.v2",
    "repo-curator.rollback-receipt.v1", "repo-curator.run.v1",
    "repo-curator.ro-crate-export.v1",
    "repo-curator.ro-crate-validation-report.v1",
    "repo-curator.schema-registry.v1", "repo-curator.shadow-plan.v1",
    "repo-curator.skill-bundle.v4", "repo-curator.third-party-sources-lock.v1",
    "repo-curator.upstream-review.v1",
    "repo-curator.supplied-adapter-export-manifest.v1",
    "repo-curator.workflow-run-ro-crate-export-manifest.v1",
    "repo-curator.user-decision.v1", "repo-curator.wave3-expected-label.v1",
    "repo-curator.wave3-pre-review.v1", "repo-curator.wave3-prediction.v1",
})


def build_skill_bundle(source_root: Path, output: Path) -> Path:
    """Create a new portable Skill directory without overwriting an existing path."""
    source_root = Path(source_root)
    if source_root.is_symlink():
        raise ValueError("source root must not be a symbolic link")
    source_root = source_root.resolve(strict=True)
    skill_root = source_root / _SKILL_PATH
    package_root = source_root / "repo_curator"
    notices_source, _ = _resolve_notices_source(source_root)
    required_sources = (
        skill_root / "SKILL.md",
        skill_root / "agents" / "openai.yaml",
        skill_root / "scripts" / "run_audit.py",
        package_root / "cli.py",
        source_root / _SOURCE_LOCK_PATH,
        notices_source,
        source_root / _SCHEMA_REGISTRY_PATH,
        source_root / _SCHEMA_GUIDANCE_PATH,
        source_root / _RO_CRATE_SHAPE_PATH,
    )
    runtime_sources = tuple(
        package_root / module_name for module_name in sorted(_READ_ONLY_RUNTIME_MODULES)
    )
    license_sources = tuple(
        sorted((source_root / _LICENSES_PATH).glob("*.txt"))
    )
    distributed_sources = required_sources + runtime_sources + license_sources
    if any(not path.is_file() for path in distributed_sources):
        raise ValueError("source tree does not contain a complete repo-curator Skill")
    for source in distributed_sources:
        _require_unlinked_source_file(source_root, source)
    output = output.resolve(strict=False)
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"bundle output already exists: {output}")
    if not output.parent.is_dir():
        raise ValueError(f"bundle output parent is not a directory: {output.parent}")
    source_lock, notices = _validate_source_governance(source_root)
    schema_registry = _validate_schema_registry(source_root)
    source_git = _source_git_identity(source_root, distributed_sources)

    output.mkdir(mode=0o700)
    try:
        _copy_file(skill_root / "SKILL.md", output / "SKILL.md")
        _copy_file(
            skill_root / "agents" / "openai.yaml",
            output / "agents" / "openai.yaml",
        )
        _copy_file(
            skill_root / "scripts" / "run_audit.py",
            output / "scripts" / "run_audit.py",
        )
        for source in runtime_sources:
            module_name = source.name
            _copy_file(source, output / "scripts" / "repo_curator" / module_name)
        _copy_file(source_root / _SOURCE_LOCK_PATH, output / _SOURCE_LOCK_PATH)
        _copy_file(notices_source, output / _NOTICES_BUNDLE_PATH)
        for source in license_sources:
            _copy_file(source, output / _LICENSES_PATH / source.name)
        _copy_file(source_root / _SCHEMA_REGISTRY_PATH, output / _SCHEMA_REGISTRY_PATH)
        _copy_file(source_root / _SCHEMA_GUIDANCE_PATH, output / _SCHEMA_GUIDANCE_PATH)
        _copy_file(source_root / _RO_CRATE_SHAPE_PATH, output / _RO_CRATE_SHAPE_PATH)
        manifest = {
            "files": _hash_bundle_files(output),
            "governance": {
                "source_lock_path": _SOURCE_LOCK_PATH.as_posix(),
                "source_lock_sha256": hashlib.sha256(source_lock).hexdigest(),
                "third_party_notices_path": _NOTICES_BUNDLE_PATH.as_posix(),
                "third_party_notices_sha256": hashlib.sha256(notices).hexdigest(),
                "schema_registry_path": _SCHEMA_REGISTRY_PATH.as_posix(),
                "schema_registry_sha256": hashlib.sha256(schema_registry).hexdigest(),
                "schema_guidance_path": _SCHEMA_GUIDANCE_PATH.as_posix(),
                "schema_guidance_sha256": hashlib.sha256(
                    _read_source_bytes(source_root / _SCHEMA_GUIDANCE_PATH)
                ).hexdigest(),
                "ro_crate_shape_path": _RO_CRATE_SHAPE_PATH.as_posix(),
                "ro_crate_shape_sha256": hashlib.sha256(
                    _read_source_bytes(source_root / _RO_CRATE_SHAPE_PATH)
                ).hexdigest(),
            },
            "kernel_package": "scripts/repo_curator",
            "repo_curator_version": __version__,
            "schema_version": BUNDLE_SCHEMA_VERSION,
            "skill_name": "repo-curator",
            "source_git": source_git,
        }
        (output / "manifest.json").write_bytes(_canonical_json(manifest))
        return output
    except BaseException:
        shutil.rmtree(output)
        raise


def _copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination.write_bytes(_read_source_bytes(source))


def _read_source_bytes(source: Path) -> bytes:
    try:
        descriptor = os.open(
            source, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        )
    except OSError as error:
        if error.errno == errno.ELOOP:
            raise ValueError(f"bundle source input is linked: {source}") from error
        raise
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"bundle source input is not a regular file: {source}")
        if before.st_size > _MAX_BUNDLE_SOURCE_FILE_BYTES:
            raise ValueError(f"bundle source input exceeds byte limit: {source}")
        chunks = []
        bytes_read = 0
        while True:
            chunk = os.read(
                descriptor,
                min(65_536, _MAX_BUNDLE_SOURCE_FILE_BYTES - bytes_read + 1),
            )
            if not chunk:
                break
            bytes_read += len(chunk)
            if bytes_read > _MAX_BUNDLE_SOURCE_FILE_BYTES:
                raise ValueError(f"bundle source input exceeds byte limit: {source}")
            chunks.append(chunk)
        after = os.fstat(descriptor)
        named = os.stat(source, follow_symlinks=False)
        before_state = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
        after_state = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
        named_state = (named.st_dev, named.st_ino, named.st_size, named.st_mtime_ns)
        if before_state != after_state or after_state != named_state:
            raise ValueError(f"bundle source input changed during read: {source}")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _require_unlinked_source_file(source_root: Path, source: Path) -> None:
    current = source_root
    for component in source.relative_to(source_root).parts:
        current = current / component
        if current.is_symlink():
            raise ValueError(f"bundle source input is linked: {source.relative_to(source_root)}")


def _source_git_identity(
    source_root: Path, distributed_sources: tuple[Path, ...]
) -> Dict[str, str]:
    relative_paths = sorted(
        {source.relative_to(source_root).as_posix() for source in distributed_sources}
    )
    head_commit = _git_output(
        source_root, "rev-parse", "--verify", "HEAD^{commit}"
    ).decode("ascii").strip()
    head_tree = _git_output(
        source_root, "rev-parse", "--verify", "HEAD^{tree}"
    ).decode("ascii").strip()
    tree_output = _git_output(source_root, "ls-tree", "-z", "HEAD", "--", *relative_paths)
    head_objects: Dict[str, str] = {}
    for entry in tree_output.split(b"\0"):
        if not entry:
            continue
        metadata, path_bytes = entry.split(b"\t", 1)
        object_id = metadata.split(b" ")[2].decode("ascii")
        head_objects[path_bytes.decode("utf-8")] = object_id

    source_records = []
    matches_head = True
    for relative_path in relative_paths:
        source = source_root / relative_path
        content = _read_source_bytes(source)
        current_object = _git_output(
            source_root, "hash-object", "--no-filters", "--", relative_path
        ).decode("ascii").strip()
        if head_objects.get(relative_path) != current_object:
            matches_head = False
        source_records.append(
            {"path": relative_path, "sha256": hashlib.sha256(content).hexdigest()}
        )
    return {
        "distributed_inputs_sha256": hashlib.sha256(
            _canonical_json({"files": source_records})
        ).hexdigest(),
        "distributed_inputs_state": (
            "MATCHES_HEAD" if matches_head else "DIFFERS_FROM_HEAD"
        ),
        "head_commit": head_commit,
        "head_tree": head_tree,
    }


def _git_output(source_root: Path, *arguments: str) -> bytes:
    git = shutil.which("git")
    if git is None:
        raise ValueError("Git is required to bind the bundle source identity")
    environment = os.environ.copy()
    for name in (
        "GIT_CONFIG",
        "GIT_CONFIG_COUNT",
        "GIT_DIR",
        "GIT_WORK_TREE",
    ):
        environment.pop(name, None)
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_PAGER": "cat",
        }
    )
    result = subprocess.run(
        [
            git,
            "-c",
            "core.hooksPath=/dev/null",
            "-c",
            "core.fsmonitor=false",
            "-C",
            str(source_root),
            *arguments,
        ],
        check=False,
        capture_output=True,
        env=environment,
        timeout=10,
    )
    if result.returncode != 0:
        raise ValueError("unable to bind bundle source Git identity")
    if len(result.stdout) > 1_048_576:
        raise ValueError("bundle source Git identity output exceeds limit")
    return result.stdout


def _validate_source_governance(source_root: Path) -> tuple[bytes, bytes]:
    source_lock = _read_source_bytes(source_root / _SOURCE_LOCK_PATH)
    notices_source, _ = _resolve_notices_source(source_root)
    notices = _read_source_bytes(notices_source)
    try:
        lock = json.loads(
            source_lock.decode("utf-8"), object_pairs_hook=_unique_json_object
        )
        notices_text = notices.decode("utf-8")
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("third-party source governance is not valid UTF-8 JSON/Markdown") from error
    if not isinstance(lock, dict) or lock.get("schema_version") != SOURCE_LOCK_SCHEMA_VERSION:
        raise ValueError("third-party source lock schema is unsupported")
    if lock.get("serialization") != "JSON_SUBSET_OF_YAML_1_2":
        raise ValueError("third-party source lock serialization is unsupported")
    review_policy = lock.get("review_policy")
    if (
        not isinstance(review_policy, dict)
        or not isinstance(review_policy.get("cadence"), str)
        or not review_policy.get("cadence")
        or review_policy.get("upstream_changes_enter_shadow_first") is not True
    ):
        raise ValueError("third-party source lock review policy is incomplete")
    entries = lock.get("entries")
    if not isinstance(entries, list) or not entries:
        raise ValueError("third-party source lock has no entries")
    identifiers = set()
    required = {
        "adopted_boundary", "commit", "distributed_code", "excluded_authority",
        "fixtures", "id", "integration_mode", "license", "modification_summary",
        "name", "repository", "upstream_material",
    }
    for entry in entries:
        if not isinstance(entry, dict) or not required.issubset(entry):
            raise ValueError("third-party source lock entry is incomplete")
        if not isinstance(entry["distributed_code"], bool):
            raise ValueError("third-party source lock distributed-code flag is invalid")
        identifier = entry["id"]
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise ValueError("third-party source lock identifiers must be unique strings")
        identifiers.add(identifier)
        commit = entry["commit"]
        if not isinstance(commit, str) or len(commit) != 40 or any(
            character not in "0123456789abcdef" for character in commit
        ):
            raise ValueError("third-party source lock commit must be a full lowercase SHA-1")
        if entry["distributed_code"] is not False:
            distributed_files = entry.get("distributed_files")
            if not isinstance(distributed_files, list) or not distributed_files:
                raise ValueError("distributed third-party code requires explicit files")
            if not all(
                isinstance(path, str)
                and path
                and not Path(path).is_absolute()
                and ".." not in Path(path).parts
                and (source_root / path).is_file()
                for path in distributed_files
            ):
                raise ValueError("distributed third-party source file is invalid")
        license_record = entry["license"]
        if not isinstance(license_record, dict) or not isinstance(license_record.get("spdx"), str):
            raise ValueError("third-party source lock license is incomplete")
        if entry["distributed_code"] is not False and license_record["spdx"] in {"", "NOASSERTION"}:
            raise ValueError("distributed third-party source license is not verified")
        if entry["distributed_code"] is not False:
            license_path = license_record.get("text_path")
            if (
                not isinstance(license_path, str)
                or not license_path
                or Path(license_path).is_absolute()
                or ".." in Path(license_path).parts
                or not (source_root / license_path).is_file()
            ):
                raise ValueError("distributed third-party license text is missing")
            try:
                license_text = _read_source_bytes(
                    source_root / license_path
                ).decode("utf-8")
            except (OSError, UnicodeDecodeError) as error:
                raise ValueError("distributed third-party license text is invalid") from error
            required_markers = _LICENSE_TEXT_MARKERS.get(license_record["spdx"], ())
            if len(license_text) < 100 or any(
                marker not in license_text for marker in required_markers
            ):
                raise ValueError("distributed third-party license text is invalid")
        if not isinstance(entry["modification_summary"], str) or not entry["modification_summary"]:
            raise ValueError("third-party source lock modification summary is incomplete")
        fixtures = entry["fixtures"]
        if not isinstance(fixtures, list) or not fixtures or not all(
            isinstance(path, str) and (source_root / path).is_file() for path in fixtures
        ):
            raise ValueError("third-party source lock fixture is missing")
        if f"## {identifier}\n" not in notices_text:
            raise ValueError("third-party notice is missing a source-lock entry")
    return source_lock, notices


def _resolve_notices_source(source_root: Path) -> tuple[Path, Path]:
    """Resolve the source notice document while keeping bundle output stable.

    The canonical source location is under docs/. A root-level fallback keeps
    temporary fixtures and older checkouts readable during the path migration.
    """
    canonical = source_root / _NOTICES_SOURCE_PATH
    if canonical.is_file():
        return canonical, _NOTICES_SOURCE_PATH
    legacy = source_root / _NOTICES_BUNDLE_PATH
    if legacy.is_file():
        return legacy, _NOTICES_BUNDLE_PATH
    return canonical, _NOTICES_SOURCE_PATH


def _validate_schema_registry(source_root: Path) -> bytes:
    registry_bytes = _read_source_bytes(source_root / _SCHEMA_REGISTRY_PATH)
    try:
        registry = json.loads(
            registry_bytes.decode("utf-8"), object_pairs_hook=_unique_json_object
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise ValueError("schema registry is not valid UTF-8 JSON") from error
    if not isinstance(registry, dict) or registry.get("schema_version") != SCHEMA_REGISTRY_SCHEMA_VERSION:
        raise ValueError("schema registry version is unsupported")
    defaults = registry.get("defaults")
    if (
        not isinstance(defaults, dict)
        or defaults.get("compatibility") != "EXACT_VERSION_ONLY"
        or defaults.get("unknown_version_policy") != "REJECT"
        or defaults.get("migration") != "PRESERVE_AND_REQUIRE_EXPLICIT_MIGRATION"
    ):
        raise ValueError("schema registry defaults are incomplete")
    schemas = registry.get("schemas")
    if not isinstance(schemas, list) or not schemas:
        raise ValueError("schema registry has no schemas")
    identifiers = set()
    for schema in schemas:
        if not isinstance(schema, dict) or set(schema) != {"owner", "schema_id"}:
            raise ValueError("schema registry entry is malformed")
        identifier = schema["schema_id"]
        if not isinstance(identifier, str) or not identifier.startswith("repo-curator.") or identifier in identifiers:
            raise ValueError("schema registry identifiers must be unique repo-curator schemas")
        if not isinstance(schema["owner"], str) or not schema["owner"]:
            raise ValueError("schema registry owner is missing")
        identifiers.add(identifier)
    missing = _REQUIRED_SCHEMA_IDS - identifiers
    if missing:
        raise ValueError("schema registry is missing required schemas: " + ", ".join(sorted(missing)))
    return registry_bytes


def _unique_json_object(pairs: list[tuple[str, object]]) -> Dict[str, object]:
    value: Dict[str, object] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _hash_bundle_files(bundle_root: Path) -> Dict[str, str]:
    files = {}
    for path in sorted(
        item for item in bundle_root.rglob("*") if item.is_file() and item.name != "manifest.json"
    ):
        relative_path = path.relative_to(bundle_root).as_posix()
        files[relative_path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def _canonical_json(value: Dict[str, object]) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)
        + "\n"
    ).encode("utf-8")
