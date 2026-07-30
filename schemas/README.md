# Schema Registry

`registry.json` is the release-bound registry for every schema emitted by the
repo-curator package and each formally admitted external input contract. It is
JSON to keep validation dependency-free and is bundled with the Skill.

The default compatibility policy is deliberately fail-closed:

- a reader accepts only its exact schema version;
- an unknown version is rejected while the original record is preserved;
- an incompatible change receives a new schema ID or version and an explicit
  migration contract;
- a schema is not removed until its compatibility notice and read-only reader
  obligations have been met.

The bundle build rejects a registry missing a schema currently emitted by the
package. Fixture-only corpus schemas are included because their records are
also emitted by supported evaluation commands.

`repo-curator.classification.v2` replaces v1 for new audit classifications and
adds the `DECLARATION_EVIDENCE` preservation-review state. V1 run bytes remain
valid historical evidence and are never rewritten; hash-verified prior-run
comparison may preserve them as opaque non-required outputs, but no v1-to-v2
semantic state is inferred. New audits emit v2 directly. Unknown classification
versions remain unsupported rather than being silently reinterpreted. The new
state does not suppress exact-byte duplicate review; declaration evidence IDs
remain attached when `EXACT_DUPLICATE_REVIEW` takes precedence.

`repo-curator.experiment-attempt.v2`, `experiment-bundle.v2`, and
`canonical-result-candidate.v2` replace their v1 outputs so that every
`supporting_evidence_ids` entry is an actual `repo-curator.evidence.v1` identity
rather than an artifact identity. Historical v1 bytes remain immutable and are
not upgraded or relabelled. New audits resolve the manifest artifact to its
inventory evidence before emitting any experiment record and fail closed when
that internal evidence link is unavailable.

`repo-curator.reproducibility-gap.v2` replaces v1 for new audits and binds each
manifest-derived gap to the inventory evidence for the local experiment
manifest. This includes malformed and duplicate attempt declarations as well
as missing bundle members. The evidence link identifies the declaration source
only; it does not establish artifact existence or experiment execution.
Historical v1 gap bytes are not migrated or relabelled.

`repo-curator.relationship.v2` replaces v1 for new audits and adds an explicit
shape discriminator. Exact-byte duplicates use `ARTIFACT_GROUP`; local
experiment-manifest members use `DIRECTED_EDGE` with `DECLARED_*` relationship
types. Only inventory-resolved paths produce edges, every edge cites the
manifest evidence, and `DECLARED_LINEAGE_NOT_EXECUTION_VERIFIED` prevents a
declared path from becoming an execution or causal claim. Missing paths remain
reproducibility gaps. Historical v1 relationships are never rewritten.

`repo-curator.curation-brief.v2` added a bounded,
evidence-linked `declared_experiment_chains` projection. It summarizes current
experiment bundles and declaration-only directed edges without reconstructing
new relationships: each reported edge retains its artifact identity,
relationship type, limitations, and supporting evidence IDs. Incomplete chains
sort before complete chains. The report emits at most 25 chains, 64 edges per
chain, and 64 unresolved dependencies per chain and records omitted counts. Historical
v1 brief bytes remain immutable; no v1-to-v2 in-place migration, backup, or
rollback receipt exists because new audits emit a new derived report instead.

`repo-curator.curation-brief.v3` replaces v2 for new audits and retains the v2
declared-chain projection while adding `canonical_result_review` and
`reproducibility_gap_review`. Candidate and gap details retain their original
supporting/counter-evidence and limitations. Reports cap candidates and gaps at
25 each and unresolved gap items at 64, with explicit total and omitted counts.
V1 and v2 historical plan/brief bytes remain internally hash-bound and are not
migrated. Unknown brief versions remain unsupported.

`repo-curator.skill-bundle.v4` replaces v3 for new bundles. V4 requires the
`source_git` binding containing the Git HEAD commit and tree baseline, an exact
digest of distributed source inputs, and `MATCHES_HEAD` or
`DIFFERS_FROM_HEAD`. Readers that support only v3 must reject v4 rather than
silently dropping this provenance binding; no in-place migration is performed.

`repo-curator.release-check.v2` replaces v1 and binds the verified upstream
review summary plus observed/total source counts and coverage percentage. A v2
release requires at least 80 percent current source-metadata coverage. V1
readers must reject v2; no coverage value is inferred for an older receipt.

`repo-curator.release-provenance.v1` is carried in the SLSA predicate's
`internalParameters` and requires the external in-toto Statement v1 envelope
with SLSA provenance v1 predicate. The fail-closed verifier binds one
artifact subject, the repo-curator builder identity, source commit/tree, and
exactly three resolved inputs: source, bundle manifest, and passing
release-check receipt. This local statement is not proof of a hosted signature
or GitHub attestation.

`repo-curator.workflow-run-ro-crate-export-manifest.v1` is an exact-version,
fail-closed external input contract for one explicitly supplied Workflow Run
RO-Crate JSON payload. It binds the contained regular file by lowercase SHA-256
and fixes the family and payload type to `WORKFLOW_RUN_RO_CRATE` and
`WORKFLOW_RUN_RO_CRATE_JSON`. Unknown versions and schema/family/type mismatches
are rejected before a run is published. The accepted payload remains an
untrusted declaration graph; status values do not establish that any action
ran or completed. An audit accepts at most 16 supplied export manifests;
malformed graph roots and action references remain explicit unavailable or
limited observations rather than successful validation.

`repo-curator.corpus-card.v1` is a descriptive transparency artifact for one
fixed snapshot registry. It records repository and family composition, fixed
Git identities, optional Software Heritage identifiers, intended use, and
limitations. A corpus card has `admission_authority: NONE`; it cannot establish
representativeness, reviewer independence, semantic accuracy, or mutation
admission.

`repo-curator.calibration-report.v1` is a separate descriptive view over
validated evaluation cases. It reports claim-, language-, repository-type-,
and repository-family-specific selective risk and coverage at observed
confidence thresholds. It always has `admission_authority: false`; legacy
records remain `NOT_CALIBRATED`, and a v2 report does not replace the existing
admission gates or establish robustness under distribution shift.

`repo-curator.ro-crate-validation-report.v1` records validation against the
bundled `ro-crate-evidence-profile.shacl.ttl` constraints as a bounded local
structural subset. `BOUNDED_PROFILE_CONFORMANT` requires the exact evidence
profile and export schema, an explicit false execution-authority marker, and no
local structural violations. A reached traversal budget yields `INCOMPLETE`;
violations yield `NONCONFORMANT`. The implementation does not run a general
RDF/SHACL engine or resolve contexts and therefore always records
`full_shacl_conformance_claimed: false`, `shacl_engine_used: false`,
`admission_authority: false`, and `execution_authority: NONE`.

`tests/test_schema_migration_scenario.py` exercises the external read paths
where compatibility matters most: immutable historical v1 classifications,
v1/v2 curation briefs, a future supplied-export manifest, a future prior-run record,
and a future run presented to the RO-Crate exporter. Future versions are
rejected without rewriting original bytes or publishing a derived output.
