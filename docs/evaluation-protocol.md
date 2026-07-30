# Evaluation Protocol

This protocol governs admission of semantic claims and mutation operation
classes beyond `SHADOW_ONLY`. It is a preregistered corpus contract, not a
claim that the fixture suite establishes production accuracy.

## Corpus Scope

The corpus includes computational research repositories across supported
languages and repository types. It retains supported, unsupported, poorly
organized, missing-tool, negative-result, failed-reproduction, and
unsupported-language cases. Exclusions are recorded as corpus records rather
than removed after an outcome is known.

Supported claim types are `inventory_artifact`, `exact_byte_duplicate`,
`intent`, `mainline`, `document`, `experiment_lineage`, `change_episode`, and
`capability_family`. Metrics are emitted separately for each claim type,
language, and repository type. No aggregate product-wide accuracy is used for
admission.

## Manifest and record versions

Only `repo-curator.gold-case.v2` and `repo-curator.mutation-risk-case.v2`
records bound by `repo-curator.evaluation-corpus-manifest.v1` can contribute to
a positive gate. The manifest hashes the exact ordered case arrays, fixes the
evaluator version, and binds reviewer IDs to provenance-artifact hashes. Every
v2 record identifies a repository, repository family, exact snapshot, and run
or test run. One repository ID cannot refer to conflicting snapshots or
families inside a corpus. V1 records remain reportable but are admission-inert.

## Independent Labels

Every gold-case review label contains a reviewer ID, a label artifact hash,
and `SUPPORTED` or `UNSUPPORTED`. Prediction and expected-label artifacts are
also hash-bound to the case.

At least two distinct reviewers label a case before it has a consensus truth.
Matching labels form the consensus truth. Conflicting labels remain
`DISAGREED`; one or zero labels remain unreviewed. Neither condition is
silently converted into a consensus or removed from coverage, abstention, or
unresolved reporting.

## Metrics

For each slice, the evaluator reports candidate count, consensus count,
disagreement count, unreviewed count, precision, recall, coverage, abstention
rate, and unresolved rate. Precision and recall use only the independent
reviewer consensus. Coverage is the share of all candidates with a consensus;
disagreement and unreviewed cases remain visible as separate counts.

An `ASSERTED` prediction is positive. `ABSTAINED` and `UNRESOLVED` predictions
are non-assertions. High-confidence and strong-evidence filters are applied
only to their corresponding gate; lower-confidence candidates remain in the
general reporting slices.

## Gates

`repo_curator.evaluation.evaluate_admission` emits one deterministic gate
record per requirement. A missing or non-consensus sample blocks that gate.

| Gate | Requirement |
| --- | --- |
| Inventory recall | At least 1,000 reviewed v2 cases, five repositories, three families, and at least 99.9% observed recall |
| Exact-byte duplicates | At least 1,000 reviewed v2 cases, five repositories, three families, and 100% observed precision |
| Capability family | At least 100 reviewed v2 cases, five repositories, three families, and a 95% Wilson lower precision bound of at least 95% for `HIGH` claims |
| Change episode | At least 100 reviewed v2 cases, five repositories, three families, and a 95% Wilson lower precision bound of at least 90% for `STRONG` claims |
| Mutation operation | At least 3,000 unique v2 candidates across five repositories and three families, all named invariants passing, fault-injection and evidence artifacts present, and zero unsafe false positives per operation class |

Each semantic population must also include both supported and unsupported
labels: inventory and exact-duplicate corpora require at least 100 unsupported
cases, while capability-family and change-episode populations require at least
50. Reports expose reviewer `label_coverage` separately from
`supported_scope_coverage`, the share of reviewed population inside the
confidence-filtered gate.

Risk records carry individual named invariant results, a fault-injection report
hash, evidence-artifact hashes, repository snapshot identity, evaluator
version, and a controlled `SAFE` or `UNSAFE_FALSE_POSITIVE` outcome. The gate
derives its aggregate result from those records rather than trusting one coarse
`invariants_passed` field.

The only positive verdict is `ADMISSION_READY`. Any missing corpus, malformed
record, insufficient independent review, unmet threshold, failed invariant, or
unsafe false positive yields `SHADOW_ONLY`. Fixture records verify the gate
logic but cannot be used to represent the required empirical corpus.

The separate `calibrate` command emits
`repo-curator.calibration-report.v1`. It retains reviewer disagreement and
reports selective risk versus coverage for each observed confidence threshold,
split by claim type, language, repository type, and repository family. This
artifact is descriptive, has no admission authority, and must not be presented
as evidence that a confidence label transfers to a new repository population.

## Artifact pipeline

Corpus maintainers retain the ordered `gold-cases.json` and
`mutation-risk-cases.json` record arrays, repository snapshot references,
prediction and expected-label artifacts, reviewer label artifacts, and
fault-injection reports in durable reviewable storage. Reviewer provenance is
recorded separately as a JSON object mapping reviewer IDs to the SHA-256 hashes
of their retained provenance artifacts. The hashes are evidence locators; they
are not cryptographic reviewer authentication.

The deterministic local pipeline is:

```console
python3 -m repo_curator corpus-manifest \
  --cases gold-cases.json \
  --risk-cases mutation-risk-cases.json \
  --reviewer-registry reviewer-provenance.json \
  --corpus-id <immutable-corpus-id> \
  --evaluator-version <evaluator-version> \
  --output corpus-manifest.json

python3 -m repo_curator corpus-verify \
  --cases gold-cases.json \
  --risk-cases mutation-risk-cases.json \
  --reviewer-registry reviewer-provenance.json \
  --artifact-ledger artifact-ledger.json \
  --artifact-root immutable-artifacts \
  --output artifact-verification.json

python3 -m repo_curator evaluate \
  --cases gold-cases.json \
  --risk-cases mutation-risk-cases.json \
  --manifest corpus-manifest.json \
  --artifact-ledger artifact-ledger.json \
  --artifact-root immutable-artifacts \
  --created-at <RFC3339-timestamp> \
  --output admission-report.json
```

The record arrays and registry must be regular UTF-8 JSON files at most 64 MiB
each. The commands reject symbolic links and never overwrite an output file.
This preserves the bytes that the manifest and resulting report describe;
corrected labels or predictions require a new file, a new manifest, and a new
report. CI retains the corpus inputs, manifest, artifact-verification receipt,
and admission report as immutable build artifacts and publishes the
claim-specific gates and slices. It must not interpret a fixture report as
production admission or use `ADMISSION_READY` as an authorization to apply a
mutation.

### Artifact ledger

Before evaluating a v2 corpus, CI runs `corpus-verify`. Its artifact ledger is
an exact JSON object with schema version
`repo-curator.corpus-artifact-ledger.v1` and an `artifacts` array. Each array
entry has only `artifact_hash` (`sha256:<64 lowercase hex characters>`) and
`path` (a nonempty forward-slash relative path). The ledger contains exactly
the hashes referenced by v2 prediction, expected-label, reviewer-label,
repository-snapshot, fault-injection, mutation-evidence, and reviewer
provenance fields. It has no duplicate hashes or paths.

The verifier opens each path descriptor-relatively under `--artifact-root`,
rejects path traversal, symbolic links, directories, nonregular files, and
artifacts above 512 MiB, then hashes the observed bytes. It emits
`repo-curator.corpus-artifact-verification.v1` only when every ledger entry and
every required evidence reference matches. The receipt proves byte closure at
the verification time; its ledger hash and verified-hash set are retained with
the corpus manifest and admission report. The `evaluate` command repeats this
verification for v2 records from the ledger and artifact root; it does not
trust a separately supplied receipt.
