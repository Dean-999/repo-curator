<p align="center">
  <img
    src="docs/assets/repo-curator-banner.png"
    alt="Repo Curator — evidence-backed curation for messy research repositories"
    width="100%"
  >
</p>

# repo-curator

`repo-curator` provides retrospective evidence reconstruction and safe curation for computational research repositories made chaotic by repeated human and AI-assisted changes. It reconstructs project intent and scientific mainlines, identifies related or competing artifacts, and prepares conservative, reviewable convergence proposals.

The product optimizes for safe abstention, traceability, and reversibility. Evidence that is missing or in material conflict results in `UNRESOLVED`: preserve the artifact and produce no executable mutation.

## Project status

The product design is approved and the portable Skill is usable for read-only
audit, evidence-linked curation briefs, verified prior-run comparison, and
non-executable RO-Crate export plus bounded local evidence-profile validation.
Lower-level mutation primitives remain internal and are not distributed in the
Skill bundle. The published corpus card and selective calibration reports are
descriptive evidence only: independent human corpus admission is not complete,
and no formal semantic-accuracy or mutation-safety claim is published.

## Use the Skill

The product entry is the explicitly invoked
[`$repo-curator`](.agents/skills/repo-curator/SKILL.md) Skill. From Codex in this
checkout, invoke it with a target computational research repository, for
example:

```text
$repo-curator audit /absolute/path/to/research-repository and explain the safest curation decisions
```

The current Skill runs a read-only audit, validates the finalized control
artifacts, and returns an evidence-linked curation brief. The deterministic
`curation-brief.json` and `curation-brief.md` are SHA-256-bound by `plan.json`;
the Skill explains those records instead of inventing a separate recommendation
set. It writes only below the target's `.repo-curator/` control area. Apply,
rollback, automatic cleanup, target-code execution, dependency installation,
and experiment reproduction remain unavailable through this Skill version.

To create a portable release bundle from this checkout without maintaining a
second kernel copy, run:

```console
python3 tools/build_skill_bundle.py --output /path/to/repo-curator-skill
```

The bundle contains the Skill, its launcher, an explicit read-only runtime
dependency closure, and a SHA-256 manifest. Manifest v4 binds the Git HEAD and
tree baseline, the exact distributed-input digest, and whether those inputs
match HEAD; a dirty source tree is disclosed rather than presented as a clean
commit. It does not contain approval,
transaction, recovery, archive-apply, or quarantine-apply modules. The output
path must not already exist.

Before release, run the independent bundle smoke check:

```console
python3 tools/check_upstreams.py --output /absolute/path/to/upstream-review.json
python3 tools/check_release.py \
  --upstream-review /absolute/path/to/upstream-review.json \
  --output /absolute/path/to/release-check.json
```

Release-check v2 binds the complete upstream-review summary and requires current
source metadata for at least 80 percent of the exact locked source set. Missing
metadata remains visible; drift and license changes enter manual shadow review
and are never adopted automatically.
Transient network failures and GitHub 408/429/5xx responses receive two short,
bounded retries. Exhaustion is classified explicitly in the receipt and still
counts as unavailable metadata; retries never reduce the 80% release threshold
or substitute cached results.
For the full locked source set, provide a read-only GitHub token through the
`GITHUB_TOKEN` process environment; anonymous API rate limits may otherwise
produce an honestly incomplete receipt that the release gate rejects. Never
pass the token as a command-line argument or persist it in a review artifact.

To review locked upstream source and license metadata separately without
adopting changes:

```bash
python3 tools/check_upstreams.py --output /absolute/path/to/upstream-review.json
```

The release contract is listed in
[the release checklist](docs/release-checklist.md). Upstream changes produce
review candidates and enter shadow review before any source-lock update; the
check never downloads or executes upstream code and never rewrites the lock.

It creates a temporary bundle, verifies its manifest hashes, audits an isolated
synthetic research repository without executing its code, verifies every audit
output hash, exports a non-executable RO-Crate, and validates it against the
bundled bounded structural profile. It also requires the adversarial adapter
matrix, corpus card, calibration contract, local release-provenance tools, and
availability-gated, commit-pinned hosted-attestation workflow. GitHub hosted
attestations depend on the repository and workflow permissions available to the
release run; unavailability is recorded explicitly while the local
offline-verifiable provenance remains available. The report records human admission
as `NOT_ADMITTED` and mutation exposure as `NOT_EXPOSED`; it is written once
and never overwritten.

Verified prior-run and RO-Crate input reads are bounded by control-record,
per-output, cumulative-byte, declared-output, and JSONL-entity limits. RO-Crate
output is created once relative to an opened canonical parent, retries short
writes, fsyncs both file and parent, and rejects parent identity drift.

Representative public-repository validation, exact commits, and retained
limitations are recorded in [docs/release-validation.md](docs/release-validation.md).

## Internal audit kernel

Contributors can exercise the deterministic kernel directly from the repository
checkout:

```console
python3 -m repo_curator audit \
  --root /path/to/research-repository \
  --run-id audit-20260719 \
  --created-at 2026-07-19T00:00:00Z \
  --max-file-bytes 33554432 \
  --max-artifacts 100000 \
  --max-depth 128 \
  --max-directory-entries 50000 \
  --max-total-hash-bytes 1073741824 \
  --compare-to-run audit-20260718 \
  --adapter-export-manifest /absolute/path/to/reprozip-export.json
```

The command writes versioned `run.json`, `inventory.jsonl`, `git-observations.jsonl`, `structural-observations.jsonl`, `profiles.jsonl`, `archive-observations.jsonl`, `adapter-observations.jsonl`, `evidence.jsonl`, and `relationships.jsonl` files below `.repo-curator/runs/<run-id>/` in the selected repository. Fixed inputs and run metadata produce deterministic inventory bytes. The five applied scan budgets are recorded in `run.json` and the curation brief. Directory-width overflow scans none of that directory's children; artifact and depth limits stop deterministic traversal; cumulative hash exhaustion retains metadata while omitting content identity. Every case finalizes with an explicit limitation. Each record keeps independent per-run artifact, exact-content, filesystem-location, and unresolved-lineage identities: equal bytes (including hard links) do not establish artifact or lineage sameness. Directory content IDs are location-free Merkle identities, while location IDs include the root realpath, object type, and raw repository-relative path bytes. It inventories regular files, directories, symbolic links, and special filesystem objects using descriptor-relative operations. Links are recorded by their raw target text and are never followed; external, missing, or symlink-mediated targets receive structured boundary warnings. FIFOs, sockets, devices, and other special filesystem objects are retained without being opened. Root Git control data and nested repository roots are recorded as protected boundaries and are not descended into. Unicode-normalized case collisions are retained and flagged on every affected record.

To create a non-executable RO-Crate view from a completed audit, use a new
absolute output path outside the target repository:

```console
python3 -m repo_curator export-ro-crate \
  --run-directory /absolute/path/to/research-repository/.repo-curator/runs/audit-20260719 \
  --output /absolute/path/to/export/ro-crate-metadata.json
```

The exporter verifies every SHA-256 named by `run.json` before it reads the
required evidence records. It never overwrites an output or an existing crate.
The export preserves observed assertion origin, limitations, counter-evidence,
and the absence of an assigned confidence; its mainline entries remain claims.
It explicitly records `executionAuthorized: false` and does not create a
Workflow Run, declare a successful reproduction, or change the target.

To validate that export against repo-curator's bounded local evidence profile:

```console
python3 -m repo_curator validate-ro-crate \
  --input /absolute/path/to/export/ro-crate-metadata.json \
  --output /absolute/path/to/new/validation-report.json
```

The result is create-once and no-follow. `BOUNDED_PROFILE_CONFORMANT` is not a
claim of complete SHACL conformance, scientific validity, successful
reproduction, or execution authority; a reached traversal budget produces
`INCOMPLETE`.

When the selected root is a Git worktree, audit collects HEAD, index and working-tree status, explicitly included ignored paths, the newest 100 commit identities and their file-level changed paths, Git LFS pointer metadata, git-annex presence, gitlinks, and linked-worktree status. Commit paths come from one sanitized `git diff-tree --stdin` plumbing call over already validated commit IDs. Co-changed current inventory files may form a `change_episode` candidate only when the commit has 2 through 64 current regular-file members. Larger commits remain observed but produce `GIT_COCHANGE_MEMBER_LIMIT`; this avoids treating imports or broad rewrites as one meaningful episode. Every candidate retains `GIT_COCHANGE_NOT_COMMON_PURPOSE`; one commit does not prove shared responsibility or lineage. LFS payloads are never downloaded; submodules, annex data, and linked-worktree administration are never recursed into.

The same recent-commit scope is checked for pattern-matched credential remnants in changed regular-file blobs. The scan is local and read-only, uses literal paths plus validated commit and object IDs, and stops at 1,024 paths, 512 unique blobs, 1 MiB per blob, 16 MiB total, or 256 findings. `GIT_SECRET_HISTORY_SUMMARY` persists only category, commit ID, and repository-relative path; it never persists a value, snippet, line, fingerprint, entropy score, or provider response. A match is a rotation and disclosure-review signal, not proof that a credential is valid. Credential validity is always `NOT_PERFORMED`: online validation would disclose a suspected credential to a provider and is outside the local-first Skill boundary.

Git collection invokes only the system Git executable with fixed read-only arguments, a fresh sanitized environment, all transport protocols disabled, literal pathspecs, replacement-object and lazy-fetch suppression, pager and prompt suppression, and fsmonitor disabled. Every subprocess is incrementally read under a 10-second timeout, 64 KiB stdin cap, 32 MiB stdout cap, and 64 KiB stderr cap; history-tree batches use a tighter 512 KiB stdout cap and blob reads cannot exceed their validated declared size. An over-limit process is terminated and its truncated output is never parsed. Git collection never invokes a repository alias, hook, pager, filter, text conversion, credential helper, LFS process, remote, or submodule command; missing, malformed, unavailable, budget-limited, or shallow history becomes an explicit coverage limitation while filesystem inventory continues. A shallow repository is never automatically deepened or fetched.

An MIT-attributed git-sizer port adds a bounded
`GIT_REPOSITORY_SIZE_SUMMARY`. It reports compact object-database counts,
reference and reachable-commit counts, current-checkout file totals, the largest
inventoried regular file, and git-sizer-style concern ratios. Reference names
are not emitted to repo-curator, and historical file/blob contents are never
read by this observer. Object-database
figures may include unreachable objects or alternates, and concern ratios are
review context only: they never classify scientific value, recommend history
rewriting, or authorize cleanup.

An MIT-attributed pre-commit-hooks port adds
`GIT_REPOSITORY_HYGIENE_SUMMARY`. It reports staged additions larger than the
upstream default 500 KiB and HEAD-symlink-to-index-nonlink mode changes, capped
at 256 retained findings. Existing inventory warnings continue to report broken
symlinks without following them. The observer does not run hooks, compare Git
blob content, evaluate `.gitattributes`/LFS filters, repair the index, reject a
commit, or authorize cleanup; differing blob IDs remain candidates rather than
confirmed destroyed links. Unexpected rename, conflict, untracked, or ignored
porcelain records make the hygiene observation explicitly partial rather than
being silently treated as complete coverage.

`profiles.jsonl` contains bounded, format-evidenced profiles for regular files. `inspected_ranges` reports bytes actually inspected, while `persisted_sample_ranges` reports only the redacted sample retained in the output. Text, Markdown, JSON, CSV, logs, and PDF metadata are recognized from their contents; malformed, binary, unreadable, and truncated inputs retain explicit limitations. A BSD-3-Clause-attributed nbformat port treats `.ipynb` as a dedicated `NOTEBOOK` envelope: it records explicit format version, bounded v4 cell/output counts, and selected kernel/language declarations, while persisting no cell source, output data, widget state, or arbitrary metadata. Notebook outputs remain explicitly untrusted and no kernel is started. Other persisted samples are redacted before writing, so credential, token, private-key, cookie, and high-confidence token values are never copied into audit outputs.

`structural-observations.jsonl` contains standard-library Python AST syntax observations for regular `.py` files no larger than 256 KiB, with a 20,000-node post-parse budget. It records module names, imports, top-level function and class names, and literal `if __name__ == "__main__"` guards. It never imports modules, executes target code, installs dependencies, or persists source snippets. Imports do not prove runtime reachability, main guards do not prove a canonical entry point, and matching definitions do not establish a capability family; parse, size, memory, recursion, read, and node-limit failures remain per-file limitations.

`archive-observations.jsonl` records ZIP member metadata without extracting members. ZIP end records, central-directory size, and member count are bounded before `zipfile` parses the directory. Unsafe, oversized, or malformed ZIPs retain explicit limitations; TAR, 7z, and RAR inputs remain opaque with unsupported-format evidence.

`evidence.jsonl` turns inventory and read-only observations into records with explicit origin, source, extractor, scope, limitations, and counter-evidence. New audits emit `repo-curator.relationship.v2` records in `relationships.jsonl`. Exact-byte duplicates use an `ARTIFACT_GROUP` shape that preserves separate artifact and location identities without inferring common purpose or lineage. Inventory-resolved experiment-manifest members use `DIRECTED_EDGE` plus `DECLARED_OUTPUT`, `DECLARED_INPUT`, `DECLARED_CONFIGURATION`, `DECLARED_GENERATOR`, `DECLARED_VALIDATION`, or `DECLARED_REVIEWER_RECORD`; every edge cites the manifest evidence and retains `DECLARED_LINEAGE_NOT_EXECUTION_VERIFIED`. Missing paths emit gaps, not edges. Declared change-episode and capability-family candidates remain separate coverage-limited outputs. The minimal [PROV/RO-Crate mapping](docs/evidence-standards-mapping.md) is descriptive only and is not an export format.

`project-intent.json`, `retention-policy.json`, `mainline-map.jsonl`, and `intent-conflicts.jsonl` record limited, evidence-linked intent hypotheses from explicit document labels and delivery wiring. Rules and examples are treated as untrusted text; repo-curator never executes them. Conflicting or insufficient claims remain `UNRESOLVED` and retain the affected material.

`decision-questions.jsonl` contains at most one evidence-specific question for a material intent conflict. Its conservative outcome is preservation; an unanswered question does not block unrelated analysis. `user-decisions.jsonl` is initially empty and reserved for later scoped decision assertions, which retain all counter-evidence and do not edit project documents.

`run.json.relationship_coverage` reports change-episode, capability-family, and
implementation-role coverage independently. A supplied
`relationship-manifest.json` can produce declared-only candidates, but it does
not establish structural equivalence or verified history. Missing evidence for
Git co-change and Python syntax observations therefore report separate
`AVAILABLE_GIT_COCHANGE_ONLY` or `PARTIAL_SYNTAX_ONLY` states rather than being
promoted to semantic verification.

`classifications.jsonl` and `recommendations.jsonl` are shadow-mode review projections. They classify artifacts from the existing evidence as `KEEP`, `ARCHIVE`, `REVIEW_EXACT_DUPLICATE`, `MERGE`, or `MANUAL_REVIEW`, with evidence coverage, counter-evidence, expected loss, limitations, and a retention closure. An exact-byte duplicate is a preserved review item, not a cleanup or quarantine instruction: it has `expected_loss: NONE` and `NO_MOVE_OR_DELETE_AUTHORIZED`. Insufficient coverage, material conflict, and incomplete bundles remain `UNRESOLVED` and preserved. A separate `.repo-curator/plans/<run-id>/plan.json`, `plan.md`, `curation-brief.json`, and `curation-brief.md` cross-link those projections, but contain no executable action candidates in the current shadow-only mode. `plan.json` binds the exact brief bytes by SHA-256, while `plan.md` embeds the same deterministic brief for human review.

`repo-curator.curation-brief.v2` introduced a bounded declared-chain
projection that reports experiment-attempt and inventory-resolved edge counts, role
counts, bundle completeness, unresolved dependencies, artifact identities, and
supporting evidence IDs. It reports incomplete chains first, then stable IDs,
and caps output at 25 chains, 64 edges per chain, and 64 unresolved dependencies
per chain, with explicit omitted counts. This projection does not re-infer lineage from
paths and does not claim execution, generation, use, validation, or review.
Historical v1 brief bytes are retained and are never migrated in place.

New audits emit `repo-curator.curation-brief.v3`. V3 retains the v2 declared
chains and adds bounded canonical-result candidate and reproducibility-gap
review projections. Candidate entries retain attempt, output, governance state,
limitations, and evidence IDs; a candidate is never presented as canonical
confirmation. Gaps retain attempt, missing-or-unresolved items, limitations,
and manifest evidence IDs; a gap is not a reproduction verdict. Each projection
reports at most 25 records, each gap expands at most 64 unresolved items, and
all omitted counts remain explicit. Historical v1 and v2 bytes are unchanged.

Ordinary directories are deterministically preserved as non-executable `KEEP`
recommendations instead of consuming the `MANUAL_REVIEW` queue. Their
`PROTECTED`, preservation, and non-regular-object limitations remain recorded.
Symlinks, special objects, Git-control boundaries, and other limited or
unresolved artifacts remain conservative manual-review items.

An ordinary regular file that is unresolved only because both mainline and role
evidence are absent is also preserved as non-executable `KEEP` instead of being
placed in the review-attention queue. Its `UNRESOLVED` classification,
`NO_MAINLINE_EVIDENCE`, `NO_ROLE_EVIDENCE`, `PRESERVE_UNRESOLVED`, and
human-review metadata remain explicit. Any additional limitation or conflict
keeps the recommendation at `MANUAL_REVIEW`; absence-only `KEEP` does not claim
that the file has a known research role or is scientifically dispensable.

New audits emit `repo-curator.classification.v2`. A local inventory-bound marker
used by the declaration adapter receives `DECLARATION_EVIDENCE` and references
the exact `DECLARED` evidence record plus all observation limitations. This
state establishes only that the artifact is a preserved source of declaration
evidence; it does not validate declaration semantics, environment availability,
execution, reproducibility, or scientific role. Supplied exports cannot assign
the state. Material conflict, inventory limitations, and bundle guards remain
conservative overrides; exact-byte duplicate review keeps precedence while
retaining the declaration evidence IDs. Historical v1 classifications remain
immutable and are not semantically migrated.

Experiment attempts, bundles, and canonical-result candidates use their v2
schemas in new audits. Every `supporting_evidence_ids` value resolves to an
actual `evidence.jsonl` record for the local experiment manifest; artifact IDs
are never substituted for evidence IDs. If that internal evidence link is
unavailable, audit fails before publishing a run. Historical v1 records remain
unchanged and receive no inferred migration.

New audits also emit `repo-curator.reproducibility-gap.v2`. Every gap caused by
the bounded local experiment manifest cites that manifest's inventory evidence
ID, including malformed and duplicate attempt declarations. The link proves
only where the missing-or-unresolved assertion came from; it does not prove the
declared artifact existed or that an experiment ran. Historical gap v1 bytes
remain unchanged.

The declaration adapter recognizes DVC, DataLad, MLflow, Sacred, Data Package, RO-Crate, BagIt, Snakemake, Nextflow, Renku, noWorkflow, showyourwork, Citation File Format, CodeMeta, and signac markers without importing or launching their tools. It emits typed, coverage-limited observations only. `CITATION.cff` is presence-only and its YAML is never opened by either the declaration adapter or generic profiler. A bounded `codemeta.json` syntax check retains only allowlisted field names and selected declared cardinalities, never values or resolved JSON-LD. The BSD-3-Clause-attributed signac observer counts project, cache, statepoint, and document markers from inventory only, caps persisted markers at 256, and never reads signac metadata. A BSD-3-Clause-attributed repo2docker port additionally recognizes Conda, pip, Pipenv, R, Julia, Nix, Docker, and Binder environment markers from inventory paths. It preserves root markers shadowed by `binder/` or `.binder/` and reports conflicting Binder directories without choosing one; it never parses a dependency file or executes a build instruction. Recognized JSON declarations are read through descriptor-relative no-follow opens and are bounded to 1 MiB for UTF-8 JSON validation. The MIT-attributed Frictionless Data Package port observes every root or nested `datapackage.json`, capped at 128 resources and 16 paths per resource. It retains only safe structural tokens and normalized repository-relative local-path presence; remote URLs, inline values, schemas, dialects, descriptions, and arbitrary metadata are not persisted, and no resource is opened or fetched. Generic profiles for admitted research metadata descriptors are content-free so descriptor values cannot bypass this boundary. The RO-Crate adapter additionally performs an Apache-2.0-attributed, local-only bounded port of entity indexing and metadata-descriptor-to-Dataset-root checking: it records at most 256 entities and 512 `@id` references, never resolves a remote context or payload, and retains malformed, duplicate, external, and unresolved references as limitations. Workflow Run RO-Crate remains a declaration-only subtype, and `dvc.lock` receives only a bounded lexical stage-key count. Oversized, malformed, unavailable, or changed declarations remain observable with explicit limitations.

An explicit repeatable `--adapter-export-manifest` may additionally import one
ReproZip metadata JSON export. The absolute manifest is strict
`repo-curator.supplied-adapter-export-manifest.v1` JSON: it declares `REPROZIP`,
source tool/version, snapshot scope, payload type `REPROZIP_METADATA_JSON`, a
relative payload path, and the payload's lowercase SHA-256. The manifest and
payload are regular files read without following links; the manifest is limited
to 64 KiB and its payload to 1 MiB. A mismatch, symbolic link, invalid JSON,
unsupported field/version, or escaping payload path fails the audit before a
run is published. A valid payload yields metadata-only evidence and does not
unpack a package, invoke ReproZip, install an environment, trace a run, fetch
content, or establish reproducibility.

The same option accepts an exact
`repo-curator.workflow-run-ro-crate-export-manifest.v1` manifest for one already
generated Workflow Run RO-Crate JSON payload. The manifest declares
`WORKFLOW_RUN_RO_CRATE`, source tool/version, snapshot scope, payload type
`WORKFLOW_RUN_RO_CRATE_JSON`, a contained relative payload path, and its
lowercase SHA-256. An audit accepts at most 16 explicitly supplied export
manifests in total. The bounded observer retains at most 128 declared
`CreateAction` records, 64 input and output references plus 8 instruments per
action, and the shared RO-Crate graph limits of 256 entities and 512 references.
Malformed action references are counted and retained as limitations rather than
silently disappearing.
Completed, failed, active, and potential values are always labelled
`*_DECLARED`; they are not execution-verified. The adapter does not generate a
crate, resolve JSON-LD contexts or URLs, retrieve payloads, copy referenced
files, load a workflow plugin, or execute a target workflow.

`--compare-to-run` is optional and names one earlier finalized run under the
same target's `.repo-curator/runs/` directory. Before publishing the new run,
repo-curator validates every output hash from that earlier `run.json`; a
missing, linked, or changed output fails closed. A verified comparison adds
`prior-run-comparison.json`, listing non-directory artifact additions,
removals, content changes, unambiguous moves, newly linked mainline paths,
newly conflicting paths, and paths unresolved in both runs. It does not infer
that a same-byte move preserves semantic role or scientific equivalence.

`--max-file-bytes` defaults to 33,554,432 bytes and accepts values from 1 through 268,435,456. Files observed above the applied budget remain in inventory but are not opened for content hashing; they retain null content fields and a `CONTENT_HASH_SKIPPED_SIZE_LIMIT` warning. A file-system failure confined to one artifact is retained with a deterministic warning and does not stop sibling inventory. Such a run is finalized as `COMPLETED_WITH_LIMITATIONS`; inability to open the selected audit root remains an error.

A directory containing a regular `pyvenv.cfg` is retained as a single
`PYTHON_VIRTUAL_ENVIRONMENT_BOUNDARY_NOT_RECURSED` record. This prevents an
embedded Python environment's third-party packages from overwhelming research
evidence while preserving the boundary itself. Directory names alone never
trigger this behavior; an ordinary directory named `venv` is fully inventoried.

If a run fails after its private staging directory is created, repo-curator clears only its fixed, tool-owned output names through the held directory descriptor. It intentionally leaves an empty staging or published-run tombstone rather than deleting a pathname that may have been replaced concurrently. Tombstone inspection and recovery require a future explicit maintenance workflow; audit never deletes them automatically.

The boundary scenarios cover symlinks, FIFOs, Unix sockets, and Git boundaries on macOS and Linux. Device nodes receive the same special-object no-read policy when encountered, but ordinary CI does not create privileged device-node fixtures.

The supported continuous-verification platforms are macOS and Linux (the GitHub
Actions matrix uses `macos-latest` and `ubuntu-latest` with Python 3.9). FIFO,
Unix-socket, raw-filename, and Unicode case-collision fixtures are
used only when the host filesystem supports creating them; an unavailable
capability is a test-fixture limitation, not evidence about the audited
repository.

Run the black-box scenarios with:

```console
python3 -m unittest discover -v
python3 -m pip install "coverage>=7.10,<8"
COVERAGE_FILE=/tmp/repo-curator-coverage python3 -m coverage run -m unittest discover -v
COVERAGE_FILE=/tmp/repo-curator-coverage python3 -m coverage report --include='repo_curator/*' --fail-under=80
python3 -m compileall -q repo_curator tests
```

For a focused cross-platform parent acceptance check, run:

```console
python3 -m unittest -v tests/test_parent_issue_1_acceptance.py
```

The audit outputs are `inventory.jsonl`, `git-observations.jsonl`, `structural-observations.jsonl`, `profiles.jsonl`, `archive-observations.jsonl`, `adapter-observations.jsonl`, `evidence.jsonl`, `relationships.jsonl`, `project-intent.json`, `retention-policy.json`, `mainline-map.jsonl`, `intent-conflicts.jsonl`, `decision-questions.jsonl`, `user-decisions.jsonl`, `experiment-attempts.jsonl`, `experiment-bundles.jsonl`, `canonical-result-candidates.jsonl`, `reproducibility-gaps.jsonl`, `change-episodes.jsonl`, `capability-families.jsonl`, `implementation-roles.jsonl`, `document-comparisons.jsonl`, `canonical-entry-points.jsonl`, `classifications.jsonl`, `recommendations.jsonl`, and `run.json` below `.repo-curator/runs/<run-id>/`. The corresponding non-executable shadow plan lives below `.repo-curator/plans/<run-id>/`. They are forensic inventory and
declaration-presence evidence only: audit does not clean up a repository,
reproduce an experiment, prove semantic lineage, or execute external tools,
package managers, hooks, or target commands.

Failed publication leaves only an empty tool-owned staging or run-directory
tombstone, never an automatic cleanup action. Preserve and inspect such a
tombstone through a future explicit maintenance workflow; do not treat it as an
audit conclusion.

## Evaluation Corpus Workflow

Formal admission is an optional internal validation workflow, not the product's
main value proposition or a prerequisite for ordinary shadow-mode use.
`repo-curator` can audit a repository, reconstruct evidence, expose uncertainty,
and produce conservative reviewable plans while remaining `SHADOW_ONLY`.
Semantic claims and mutation operation classes are promoted beyond
`SHADOW_ONLY` only if an independently reviewed v2 corpus satisfies the
protocol in [docs/evaluation-protocol.md](docs/evaluation-protocol.md). The
local commands below only read explicit JSON corpus artifacts; they never open,
scan, or execute an evaluated repository.

```console
python3 -m repo_curator corpus-manifest \
  --cases /path/to/gold-cases.json \
  --risk-cases /path/to/mutation-risk-cases.json \
  --reviewer-registry /path/to/reviewer-provenance.json \
  --corpus-id 2026-q3-review-set \
  --evaluator-version repo-curator-evaluator/1 \
  --output /path/to/corpus-manifest.json

python3 -m repo_curator corpus-verify \
  --cases /path/to/gold-cases.json \
  --risk-cases /path/to/mutation-risk-cases.json \
  --reviewer-registry /path/to/reviewer-provenance.json \
  --artifact-ledger /path/to/artifact-ledger.json \
  --artifact-root /path/to/immutable-artifacts \
  --output /path/to/artifact-verification.json

python3 -m repo_curator evaluate \
  --cases /path/to/gold-cases.json \
  --risk-cases /path/to/mutation-risk-cases.json \
  --manifest /path/to/corpus-manifest.json \
  --artifact-ledger /path/to/artifact-ledger.json \
  --artifact-root /path/to/immutable-artifacts \
  --created-at 2026-07-25T00:00:00Z \
  --output /path/to/admission-report.json
```

`gold-cases.json` and `mutation-risk-cases.json` are JSON arrays of the v2
records defined by the evaluation protocol. `reviewer-provenance.json` is a
JSON object mapping each reviewer ID to the SHA-256 hash of that reviewer's
retained provenance artifact. Record array order is significant because the
manifest hashes the exact canonical arrays. Inputs must be explicit regular
UTF-8 JSON files no larger than 64 MiB; symbolic links, directories, and other
filesystem objects are rejected. Output files are created once and are never
overwritten, so a correction requires a new artifact path and a new manifest.

`artifact-ledger.json` maps every v2 evidence hash referenced by the records
or reviewer registry to exactly one relative file below `--artifact-root`.
`corpus-verify` rejects missing, surplus, duplicated, oversized, symbolic-link,
or byte-mismatched artifacts and writes a verification receipt only after every
reference closes. `evaluate` repeats this check for v2 records and embeds the
result in its report, so it does not trust a separately supplied receipt. A
receipt proves observed local bytes, not reviewer identity or storage-provider
immutability.

The report is a deterministic CI artifact, not a certification. A positive
verdict still depends on the corpus actually representing independently
reviewed repositories and fault-injection evidence; this local tooling does
not authenticate reviewer identity or confer mutation authority.

## Design sources

Release bundles include the machine-readable
[`third_party/sources.lock.yaml`](third_party/sources.lock.yaml) and
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md), plus the compatible-reader
policy in [`schemas/registry.json`](schemas/registry.json) and
[`schemas/README.md`](schemas/README.md). The bundle manifest binds all four
files by SHA-256 and construction fails if their source entries, licenses,
fixtures, notice sections, or schema coverage are incomplete.

- [Product requirements](docs/product-requirements.md)
- [Product and technical design](docs/superpowers/specs/2026-07-16-repo-curator-design.md)
- [Evaluation corpus governance](docs/evaluation-corpus-governance.md)
- [Binding safety amendments](final-binding-amendments.md)
- [Reference design sources](docs/reference-design-sources.md)
- [Competitive and standards landscape](research/repo-curator-landscape-analysis.md)

## Safety boundaries

- Target repository content is untrusted data and is not executed.
- Missing evidence is not negative evidence.
- Semantic recommendations do not independently authorize mutation.
- Permanent deletion, automatic merge, and history rewriting are outside the supported scope.
- Approved mutations are exact-plan-bound, retention-closure-bound, budgeted, drift-checked, and reversible.
- One repository-scoped exclusive lock serializes archive, quarantine, and rollback transactions.
- Mutation journals are locally append-written, hash-chained, exact-plan/approval-bound, and explicitly committed; true append-only protection requires a separately authorized storage service.
- Namespace changes and provenance receipts use an explicit file-and-parent-directory fsync protocol.
