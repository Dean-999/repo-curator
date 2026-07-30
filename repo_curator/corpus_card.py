"""Deterministic transparency cards for evaluation repository registries."""

from collections import Counter
import re
from typing import Any, Dict, Mapping


CORPUS_CARD_SCHEMA_VERSION = "repo-curator.corpus-card.v1"
_REGISTRY_SCHEMA_VERSION = "repo-curator.pilot-snapshot-registry.v1"
_HEX = re.compile(r"[0-9a-f]+")
_SWHID = re.compile(r"swh:1:(rev|dir|cnt|snp):[0-9a-f]{40}")


class CorpusCardError(ValueError):
    """Stable rejection for malformed corpus-card inputs."""


def build_corpus_card(
    snapshot_registry: Mapping[str, Any], corpus_id: str, created_at: str
) -> Dict[str, Any]:
    """Build one descriptive card with no semantic or mutation authority."""
    if not isinstance(corpus_id, str) or not corpus_id:
        raise CorpusCardError("corpus ID must be a nonempty string")
    if not isinstance(created_at, str) or not created_at:
        raise CorpusCardError("created at must be a nonempty string")
    if (
        not isinstance(snapshot_registry, Mapping)
        or set(snapshot_registry) != {"purpose", "repositories", "schema_version"}
        or snapshot_registry.get("schema_version") != _REGISTRY_SCHEMA_VERSION
    ):
        raise CorpusCardError("snapshot registry schema is unsupported")
    repositories = snapshot_registry.get("repositories")
    if not isinstance(repositories, list):
        raise CorpusCardError("snapshot registry repositories are malformed")
    normalized = [_repository(record) for record in repositories]
    identifiers = [record["repository_id"] for record in normalized]
    if len(set(identifiers)) != len(identifiers):
        raise CorpusCardError("snapshot registry repository IDs are duplicated")
    normalized.sort(key=lambda record: record["repository_id"])
    public = [record for record in normalized if record["access"].startswith("public-")]
    return {
        "admission_authority": "NONE",
        "corpus_id": corpus_id,
        "created_at": created_at,
        "intended_use": [
            "READ_ONLY_REGRESSION",
            "REPRESENTATIVE_REPOSITORY_SCOPE_DOCUMENTATION",
        ],
        "limitations": [
            "CORPUS_CARD_DOES_NOT_ESTABLISH_REPRESENTATIVENESS",
            "CORPUS_CARD_DOES_NOT_ESTABLISH_REVIEWER_INDEPENDENCE",
            "CORPUS_CARD_DOES_NOT_AUTHORIZE_MUTATION",
            "MISSING_SWHID_DOES_NOT_MEAN_SOURCE_IS_UNARCHIVED",
        ],
        "private_repository_count": len(normalized) - len(public),
        "public_repository_count": len(public),
        "repositories": normalized,
        "repository_count": len(normalized),
        "repository_family_counts": dict(
            sorted(Counter(record["repository_family"] for record in normalized).items())
        ),
        "repository_type_counts": dict(
            sorted(Counter(record["repository_type"] for record in normalized).items())
        ),
        "schema_version": CORPUS_CARD_SCHEMA_VERSION,
        "source_identity_coverage": {
            "git_commit_count": len(normalized),
            "public_archival_identifier_count": sum(
                "swhid" in record for record in public
            ),
            "swhid_count": sum("swhid" in record for record in normalized),
        },
        "source_registry_schema_version": _REGISTRY_SCHEMA_VERSION,
    }


def _repository(value: Any) -> Dict[str, str]:
    required = {
        "access",
        "commit_sha",
        "repository_family",
        "repository_id",
        "repository_type",
        "snapshot_descriptor_path",
        "snapshot_descriptor_sha256",
        "source_url",
    }
    if not isinstance(value, Mapping) or set(value) not in (
        required,
        required | {"swhid"},
    ):
        raise CorpusCardError("snapshot registry repository is malformed")
    for field in required:
        if not isinstance(value[field], str) or not value[field]:
            raise CorpusCardError("snapshot registry repository is malformed")
    commit = value["commit_sha"]
    if len(commit) not in {40, 64} or _HEX.fullmatch(commit) is None:
        raise CorpusCardError("repository commit is malformed")
    descriptor_hash = value["snapshot_descriptor_sha256"]
    if (
        len(descriptor_hash) != 71
        or not descriptor_hash.startswith("sha256:")
        or _HEX.fullmatch(descriptor_hash[7:]) is None
    ):
        raise CorpusCardError("snapshot descriptor hash is malformed")
    if (
        value["snapshot_descriptor_path"].startswith(("/", "\\"))
        or ".." in value["snapshot_descriptor_path"].split("/")
        or "\\" in value["snapshot_descriptor_path"]
    ):
        raise CorpusCardError("snapshot descriptor path is unsafe")
    result = {field: value[field] for field in sorted(required)}
    if "swhid" in value:
        if not isinstance(value["swhid"], str) or _SWHID.fullmatch(value["swhid"]) is None:
            raise CorpusCardError("repository SWHID is malformed")
        result["swhid"] = value["swhid"]
    return result
