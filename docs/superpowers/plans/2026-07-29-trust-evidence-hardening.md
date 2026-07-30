# Trust and Evidence Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Strengthen repo-curator with metamorphic and fuzz regression gates, corpus transparency, claim-specific calibration, signed-release provenance inputs, and bounded RO-Crate validation while preserving READ_ONLY behavior.

**Architecture:** Each improvement is a separate exact-version artifact or test gate. Existing audit, evaluation, curation-brief, and mutation schemas remain unchanged. New validators consume only explicit bounded local inputs and publish create-once reports; none may execute target content or authorize mutation.

**Tech Stack:** Python 3.9 standard library, unittest, JSON/JSONL, GitHub Actions, RO-Crate JSON-LD, SHACL Core shape documents, in-toto/SLSA provenance statements.

## Global Constraints

- Current Skill release mode remains `READ_ONLY`.
- `execution_authorized` remains `false`.
- No target code, workflow, hook, notebook, package manager, container, or remote project operation is executed.
- Unknown schema versions fail closed and historical records are not migrated implicitly.
- New copied, adapted, or behaviorally derived upstream work is fixed and attributed.
- Human reviewer independence and the 3,000-candidate mutation corpus are never synthesized.
- Curation brief v3 fields remain frozen.
- Repowise risk tools are unavailable; blast radius is checked through callers, tests, schema registry, and Git history.

---

### Task 1: Metamorphic and parser-boundary hardening

**Files:**
- Create: `tests/fixtures/adapter-adversarial-matrix.json`
- Create: `tests/test_metamorphic_scenario.py`
- Create: `tests/test_parser_fuzz_scenario.py`
- Modify: `.github/workflows/test.yml`
- Modify: `docs/release-checklist.md`

**Interfaces:**
- Consumes: public audit CLI and bounded parser entry points.
- Produces: a matrix mapping every read-only adapter family to required adversarial cases, plus deterministic metamorphic and byte-mutation regressions.

- [ ] **Step 1: Write failing coverage tests**

  Assert that every registered adapter family is represented in the matrix and that the matrix contains malformed, oversized, unsupported-version, stale, inconsistent, missing-reference, secret-bearing, path-escape, symlink-replacement, and global-budget cases.

- [ ] **Step 2: Run focused tests and confirm RED**

  Run `python3 -m unittest tests.test_metamorphic_scenario tests.test_parser_fuzz_scenario -v`.
  Expected: failure because the matrix and fuzz scenarios do not exist.

- [ ] **Step 3: Add the minimal matrix and real behavior scenarios**

  Exercise actual audit and parser functions. Required metamorphic relations include JSON key reordering, unrelated-file addition, timestamp-only changes, missing evidence, prompt-injection text, and regular-file-to-symlink replacement. Seed byte mutations with fixed bytes and assert bounded exceptions or typed limitations, never secret echo or authority increase.

- [ ] **Step 4: Add the hardening tests to CI and verify GREEN**

  Run the focused tests twice and compare deterministic artifacts where applicable.

### Task 2: Corpus cards and archival identifiers

**Files:**
- Create: `repo_curator/corpus_card.py`
- Create: `tests/test_corpus_card.py`
- Modify: `repo_curator/cli.py`
- Modify: `schemas/registry.json`
- Modify: `schemas/README.md`
- Modify: `evaluation-corpus/pilot-2026-07-25/snapshot-registry.json`
- Create: `evaluation-corpus/pilot-2026-07-25/corpus-card.json`
- Modify: `docs/evaluation-corpus-governance.md`

**Interfaces:**
- Consumes: an explicit snapshot registry and explicit corpus metadata.
- Produces: `repo-curator.corpus-card.v1` with immutable source identities, sampling scope, exclusions, intended use, limitations, and optional validated SWHIDs.

- [ ] **Step 1: Write failing corpus-card tests**

  Test deterministic repository/family counts, exact commit validation, optional SWHID syntax, private-source exclusion from public archival claims, create-once output, no-follow input, and unknown-version rejection.

- [ ] **Step 2: Run focused test and confirm RED**

  Run `python3 -m unittest tests.test_corpus_card -v`.

- [ ] **Step 3: Implement bounded card generation and CLI**

  Add `corpus-card --snapshot-registry --corpus-id --created-at --output`. Derive only counts and fixed identities from the registry; require the caller to provide intended-use and limitation constants defined by the v1 profile.

- [ ] **Step 4: Generate the pilot card and verify GREEN**

  Publish a deterministic card for the existing pilot without fetching repositories or inventing SWHIDs.

### Task 3: Claim-specific selective calibration

**Files:**
- Create: `repo_curator/calibration.py`
- Create: `tests/test_calibration_scenario.py`
- Modify: `repo_curator/cli.py`
- Modify: `schemas/registry.json`
- Modify: `schemas/README.md`
- Modify: `docs/evaluation-protocol.md`
- Modify: `.github/workflows/evaluate-corpus.yml`

**Interfaces:**
- Consumes: manifest-bound v2 gold cases.
- Produces: `repo-curator.calibration-report.v1`, separate from admission, with per-claim and per-stratum precision, recall, coverage, abstention, unresolved rate, selective risk, and risk-coverage points.

- [ ] **Step 1: Write failing calibration tests**

  Use hand-calculated supported and unsupported cases. Assert separate claim types, repository families, languages and repository types; deterministic thresholds; reviewer disagreement retention; and `NOT_CALIBRATED` when independent consensus is insufficient.

- [ ] **Step 2: Run focused test and confirm RED**

  Run `python3 -m unittest tests.test_calibration_scenario -v`.

- [ ] **Step 3: Implement the report without changing admission**

  Validate cases through the existing evaluator contracts. For each ordered confidence tier, compute accepted count, selective risk, precision and coverage. Never turn the report into `ADMISSION_READY`; only existing gates may do that.

- [ ] **Step 4: Add CLI and CI artifact retention, then verify GREEN**

  Add `calibrate --cases --manifest --created-at --output` and retain the report in the manual corpus workflow.

### Task 4: Verifiable release provenance

**Files:**
- Create: `repo_curator/release_provenance.py`
- Create: `tools/build_release_provenance.py`
- Create: `tools/verify_release_provenance.py`
- Create: `tests/test_release_provenance.py`
- Create: `.github/workflows/attest-release.yml`
- Modify: `schemas/registry.json`
- Modify: `schemas/README.md`
- Modify: `docs/release-checklist.md`
- Modify: `docs/release-validation.md`
- Modify: `third_party/sources.lock.yaml`
- Modify: `THIRD_PARTY_NOTICES.md`

**Interfaces:**
- Consumes: bundle manifest, release-check receipt, source commit/tree, and artifact digest.
- Produces: an exact in-toto Statement with SLSA provenance predicate and a local fail-closed verifier. GitHub release workflow adds platform attestation/signature using a commit-pinned official action.

- [ ] **Step 1: Write failing build and verification tests**

  Assert exact subject digest, builder identity, source commit/tree, manifest and release-check digests, rejected unknown predicate versions, rejected tampering, create-once output, and no network requirement for local verification.

- [ ] **Step 2: Run focused test and confirm RED**

  Run `python3 -m unittest tests.test_release_provenance -v`.

- [ ] **Step 3: Implement minimal statement builder and verifier**

  Emit `_type=https://in-toto.io/Statement/v1` and `predicateType=https://slsa.dev/provenance/v1`; treat external parameters as untrusted and bind all resolved inputs by digest.

- [ ] **Step 4: Add the pinned GitHub attestation workflow and attribution**

  Resolve the official action commit through the GitHub API, grant only required permissions, and keep local release checks independent of hosted signing availability.

- [ ] **Step 5: Verify GREEN**

  Build, tamper, and verify fixtures locally; validate workflow YAML as text plus behaviorally significant release inputs.

### Task 5: Bounded RO-Crate profile validation

**Files:**
- Create: `repo_curator/ro_crate_validation.py`
- Create: `schemas/ro-crate-evidence-profile.shacl.ttl`
- Create: `tests/test_ro_crate_validation.py`
- Modify: `repo_curator/cli.py`
- Modify: `repo_curator/interchange.py`
- Modify: `schemas/registry.json`
- Modify: `schemas/README.md`
- Modify: `docs/evidence-standards-mapping.md`
- Modify: `third_party/sources.lock.yaml`
- Modify: `THIRD_PARTY_NOTICES.md`

**Interfaces:**
- Consumes: one bounded local RO-Crate JSON-LD document.
- Produces: `repo-curator.ro-crate-validation-report.v1` with structural violations and limitations; the bundled SHACL file is an interoperability profile, while the dependency-free validator explicitly does not claim full SHACL processor conformance.

- [ ] **Step 1: Write failing validation tests**

  Test valid non-executable exports, missing descriptor/root, duplicate IDs, unresolved local references, execution authorization, malformed and oversized input, output collision, and source immutability.

- [ ] **Step 2: Run focused test and confirm RED**

  Run `python3 -m unittest tests.test_ro_crate_validation -v`.

- [ ] **Step 3: Implement bounded validation and CLI**

  Add `validate-ro-crate --input --output`; reuse bounded graph observation, add evidence-profile rules, and publish a separate create-once report. A conforming graph is structurally valid only and never proves execution or reproduction.

- [ ] **Step 4: Package the shape and validator, then verify GREEN**

  Ensure the read-only Skill bundle includes the validator and SHACL profile without including mutation modules.

### Task 6: Governance, release gates, and handoff

**Files:**
- Modify: `README.md`
- Modify: `docs/product-requirements.md`
- Modify: `docs/release-checklist.md`
- Modify: `tools/check_release.py`
- Modify: `tests/test_release_check.py`
- Modify: `tests/test_skill_bundle.py`
- Modify: GitHub Issues `#16`, `#32`, `#33`, and a new release-provenance/RO-Crate-validation issue if required.

**Interfaces:**
- Consumes: all prior task artifacts.
- Produces: release gates and documentation that distinguish implemented infrastructure from unfulfilled human admission.

- [ ] **Step 1: Add failing release-gate tests**

  Require matrix coverage, corpus-card presence, calibration schema registration, release provenance tooling, and RO-Crate validation profile while preserving `READ_ONLY`, `NOT_PUBLISHED` calibrated accuracy, and internal-only mutation markers.

- [ ] **Step 2: Run focused release tests and confirm RED**

  Run `python3 -m unittest tests.test_release_check tests.test_skill_bundle -v`.

- [ ] **Step 3: Update release gates and product documentation**

  Document that #16 remains blocked on independent human corpus size and that no new artifact authorizes mutation.

- [ ] **Step 4: Run complete verification**

  Run unit tests, coverage gate, compileall, JSON/source-lock validation, `git diff --check`, bundle build, release check, and checkout-external smoke.

- [ ] **Step 5: Commit in reviewable slices and update GitHub**

  Commit each independently verified task, push the branch, open a ready PR, monitor CI, and update issues only with verified evidence.
