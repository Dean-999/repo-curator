# Release Checklist

This checklist defines the truthful release boundary for the packaged
repo-curator Skill. `tools/check_release.py` verifies the fixed contract markers
below before it emits a passing release receipt.

## Product Boundary

- [x] Current Skill release mode: READ_ONLY
- [x] Mutation workflows exposed: NO
- [x] Formal calibrated accuracy claim: NOT_PUBLISHED
- [x] Target repository execution: FORBIDDEN

The Skill may audit, produce a curation brief, compare prior runs, and export a
non-executable RO-Crate view. It does not advertise archive, quarantine,
recovery, rollback, merge, deletion, history rewriting, or experiment
reproduction as user-facing Skill workflows.

## Contracts And Supply Chain

- [x] Schema compatibility: EXACT_VERSION_ONLY
- [x] Unknown schema versions: REJECT
- [x] Third-party source lock: REQUIRED
- [x] Third-party notices: REQUIRED
- [x] Upstream changes: SHADOW_REVIEW_BEFORE_ADOPTION

The bundle must bind its schema registry, compatibility guidance, source lock,
third-party notices, distributed license texts, launcher, Skill instructions,
and the explicit read-only runtime closure. It must not distribute approval,
transaction, recovery, archive-apply, or quarantine-apply modules, and its CLI
must advertise only workflows whose runtime modules are present.
`tools/check_upstreams.py` is advisory: source or
license drift creates a review candidate and never edits the lock or adopts a
new upstream revision. It retries only transient network, rate-limit, timeout,
and selected server failures twice with fixed bounded delays. Exhaustion is
classified explicitly and remains unavailable coverage; the tool never lowers
the coverage floor or invents cached metadata.

## Safety And Limitations

- [x] Known limitations: DOCUMENTED
- [x] Recovery primitives: INTERNAL_NOT_EXPOSED
- [x] Rollback primitives: INTERNAL_NOT_EXPOSED
- [x] Permanent deletion: UNAVAILABLE
- [x] Cross-filesystem copy-then-delete: UNAVAILABLE
- [x] Global inventory artifact, depth, directory-width, and hash-byte budgets: REQUIRED
- [x] Reached budgets finalize with explicit limitations: REQUIRED
- [x] Verified-run input byte and entity budgets: REQUIRED
- [x] RO-Crate descriptor-relative durable publication: REQUIRED
- [x] Bundle source Git and distributed-input identity: REQUIRED
- [x] Upstream source-metadata coverage floor: 80_PERCENT
- [x] Local release provenance: EXACT_IN_TOTO_STATEMENT_AND_SLSA_V1_PREDICATE
- [x] Hosted release attestation action: AVAILABILITY_GATED_IMMUTABLE_COMMIT_PIN
- [x] Evidence RO-Crate validation: BOUNDED_LOCAL_SHACL_SUBSET
- [x] Adapter adversarial matrix: REQUIRED
- [x] Corpus transparency card: DESCRIPTIVE_NOT_ADMISSION
- [x] Selective calibration publication: DESCRIPTIVE_NOT_ADMISSION
- [x] Human corpus admission: NOT_ADMITTED

Every release must retain no-execution, no-overwrite, path-boundary, secret
redaction, bounded parsing, exact approval, journal, recovery, and rollback
tests. The run record and curation brief must serialize every applied scan
budget. Passing lower-level mutation tests does not expose mutation through the
Skill. Human-labelled corpus admission remains optional unless the project
publishes calibrated semantic-accuracy or mutation-safety claims.

Prior-run comparison and RO-Crate export cap the run record, each declared
output, cumulative verified bytes, declared output count, and parsed JSONL
entities before constructing comparison indexes or JSON-LD graphs. RO-Crate
publication retries short writes, creates the absent output relative to a
descriptor-opened canonical parent, fsyncs the file and parent directory, and
rejects parent identity drift. Bundle manifest v4 records the Git HEAD/tree
baseline, exact distributed-input digest, and whether those inputs match HEAD;
every distributed source is a bounded no-follow regular-file read.

## Verification

Run:

```bash
python3 -m unittest discover -q
python3 -m compileall -q repo_curator tests tools
git diff --check
python3 tools/check_upstreams.py --output /absolute/new/path/upstream-review.json
python3 tools/check_release.py \
  --upstream-review /absolute/new/path/upstream-review.json \
  --output /absolute/new/path/release-check.json
```

Set `GITHUB_TOKEN` in the review process environment when checking the complete
source lock. Anonymous GitHub API exhaustion is retained as unavailable
metadata and may correctly fail the 80 percent coverage gate; tokens must not
be passed as CLI arguments or persisted in either receipt.

A release receipt must be `PASSED` and binds a matching upstream receipt no
older than 90 days. An upstream receipt may contain review candidates or
limitations; those states block silent adoption, not ordinary read-only use of
the already locked release.

After creating the archive and a passing release receipt, generate a
create-once local provenance statement and verify it offline:

```bash
python3 tools/build_release_provenance.py \
  --artifact /absolute/repo-curator-skill-VERSION.tar.gz \
  --bundle-manifest /absolute/bundle-manifest.json \
  --release-check /absolute/release-check.json \
  --builder-id https://github.com/Dean-999/repo-curator/actions/workflows/attest-release.yml \
  --invocation-id https://github.com/Dean-999/repo-curator/actions/runs/RUN_ID \
  --output /absolute/new/path/release-provenance.json
python3 tools/verify_release_provenance.py \
  --statement /absolute/new/path/release-provenance.json \
  --artifact /absolute/repo-curator-skill-VERSION.tar.gz \
  --builder-id https://github.com/Dean-999/repo-curator/actions/workflows/attest-release.yml \
  --source-commit COMMIT \
  --source-tree TREE
```

The local verifier validates the exact artifact, builder, source commit/tree,
and the fixed three resolved dependencies. It does not verify a hosted
signature. After release publication, manually dispatch `Attest Release` for
the immutable tag; the workflow verifies `SHA256SUMS` before invoking the
commit-pinned official GitHub attestation action when the repository is
eligible. GitHub does not offer artifact attestations for user-owned private
repositories; that state must be recorded as
`HOSTED_ATTESTATION_UNAVAILABLE_PRIVATE_REPOSITORY`, never presented as a
successful hosted attestation.
