"""Exact, offline-verifiable provenance for repo-curator release artifacts."""

from typing import Any, Dict, Mapping


STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://slsa.dev/provenance/v1"
BUILD_TYPE = (
    "https://github.com/Dean-999/repo-curator/"
    ".github/workflows/attest-release.yml@v1"
)


class ReleaseProvenanceError(ValueError):
    """Stable rejection for malformed or unexpected release provenance."""


def build_release_provenance(
    artifact_name: str,
    artifact_sha256: str,
    builder_id: str,
    invocation_id: str,
    source_commit: str,
    source_tree: str,
    bundle_manifest_sha256: str,
    release_check_sha256: str,
) -> Dict[str, Any]:
    """Build one SLSA v1 predicate without claiming hosted signature state."""
    for label, value in (
        ("artifact name", artifact_name),
        ("builder ID", builder_id),
        ("invocation ID", invocation_id),
    ):
        if not isinstance(value, str) or not value:
            raise ReleaseProvenanceError("{} is invalid".format(label))
    for label, value, lengths in (
        ("artifact digest", artifact_sha256, {64}),
        ("source commit", source_commit, {40, 64}),
        ("source tree", source_tree, {40, 64}),
        ("bundle manifest digest", bundle_manifest_sha256, {64}),
        ("release check digest", release_check_sha256, {64}),
    ):
        if not _hex(value, lengths):
            raise ReleaseProvenanceError("{} is invalid".format(label))
    source_uri = (
        "git+https://github.com/Dean-999/repo-curator@" + source_commit
    )
    return {
        "_type": STATEMENT_TYPE,
        "predicate": {
            "buildDefinition": {
                "buildType": BUILD_TYPE,
                "externalParameters": {
                    "executionMode": "READ_ONLY",
                    "mutationExposed": False,
                },
                "internalParameters": {
                    "schemaVersion": "repo-curator.release-provenance.v1"
                },
                "resolvedDependencies": [
                    {
                        "digest": {"gitCommit": source_commit},
                        "uri": source_uri,
                    },
                    {
                        "digest": {"sha256": bundle_manifest_sha256},
                        "uri": "repo-curator:bundle-manifest",
                    },
                    {
                        "digest": {"sha256": release_check_sha256},
                        "uri": "repo-curator:release-check",
                    },
                ],
            },
            "runDetails": {
                "builder": {
                    "id": builder_id,
                    "version": {"sourceTree": source_tree},
                },
                "metadata": {"invocationId": invocation_id},
            },
        },
        "predicateType": PREDICATE_TYPE,
        "subject": [
            {"digest": {"sha256": artifact_sha256}, "name": artifact_name}
        ],
    }


def verify_release_provenance(
    statement: Mapping[str, Any],
    expected_artifact_name: str,
    expected_artifact_sha256: str,
    expected_builder_id: str,
    expected_source_commit: str,
    expected_source_tree: str,
) -> Dict[str, Any]:
    """Verify the exact local statement contract; signature verification is separate."""
    if not isinstance(statement, Mapping) or statement.get("_type") != STATEMENT_TYPE:
        raise ReleaseProvenanceError("statement type is unsupported")
    if statement.get("predicateType") != PREDICATE_TYPE:
        raise ReleaseProvenanceError("provenance predicate is unsupported")
    subject = statement.get("subject")
    expected_subject = [
        {
            "digest": {"sha256": expected_artifact_sha256},
            "name": expected_artifact_name,
        }
    ]
    if subject != expected_subject:
        raise ReleaseProvenanceError("artifact subject does not match")
    predicate = statement.get("predicate")
    if not isinstance(predicate, Mapping):
        raise ReleaseProvenanceError("provenance predicate is malformed")
    definition = predicate.get("buildDefinition")
    details = predicate.get("runDetails")
    if (
        not isinstance(definition, Mapping)
        or definition.get("buildType") != BUILD_TYPE
        or definition.get("externalParameters")
        != {"executionMode": "READ_ONLY", "mutationExposed": False}
        or definition.get("internalParameters")
        != {"schemaVersion": "repo-curator.release-provenance.v1"}
        or not isinstance(details, Mapping)
        or not isinstance(details.get("builder"), Mapping)
        or details["builder"].get("id") != expected_builder_id
    ):
        raise ReleaseProvenanceError("builder contract does not match")
    dependencies = definition.get("resolvedDependencies")
    source_uri = (
        "git+https://github.com/Dean-999/repo-curator@" + expected_source_commit
    )
    expected_dependencies = [
        {
                "digest": {"gitCommit": expected_source_commit},
                "uri": source_uri,
        },
        dependencies[1] if isinstance(dependencies, list) and len(dependencies) == 3 else None,
        dependencies[2] if isinstance(dependencies, list) and len(dependencies) == 3 else None,
    ]
    if (
        not isinstance(dependencies, list)
        or len(dependencies) != 3
        or dependencies[0] != expected_dependencies[0]
        or not _digest_dependency(dependencies[1], "repo-curator:bundle-manifest")
        or not _digest_dependency(dependencies[2], "repo-curator:release-check")
    ):
        raise ReleaseProvenanceError("resolved dependencies do not match")
    builder = details["builder"]
    if builder.get("version") != {"sourceTree": expected_source_tree}:
        raise ReleaseProvenanceError("source tree does not match")
    metadata = details.get("metadata")
    if (
        not isinstance(metadata, Mapping)
        or set(metadata) != {"invocationId"}
        or not isinstance(metadata["invocationId"], str)
        or not metadata["invocationId"]
    ):
        raise ReleaseProvenanceError("invocation metadata is malformed")
    return {
        "artifact_sha256": expected_artifact_sha256,
        "builder_id": expected_builder_id,
        "source_commit": expected_source_commit,
        "verified": True,
    }


def _hex(value: Any, lengths: set) -> bool:
    return (
        isinstance(value, str)
        and len(value) in lengths
        and all(character in "0123456789abcdef" for character in value)
    )


def _digest_dependency(value: Any, expected_uri: str) -> bool:
    return (
        isinstance(value, Mapping)
        and set(value) == {"digest", "uri"}
        and value.get("uri") == expected_uri
        and isinstance(value.get("digest"), Mapping)
        and set(value["digest"]) == {"sha256"}
        and _hex(value["digest"]["sha256"], {64})
    )
