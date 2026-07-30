# repo-curator Product and Technical Design

**Status:** approved

**Maintenance model:** continuously maintained
**Date:** 2026-07-16

## 1. Purpose

`repo-curator` is an evidence-backed repository curator for codebases made chaotic by repeated human and AI-assisted changes. It reconstructs project intent and repository mainlines, identifies artifacts that may represent the same responsibility or change episode, and prepares conservative cleanup or convergence proposals.

The product optimizes for safe abstention, traceability, and reversibility—not maximal cleanup. If evidence is insufficient or conflicting, the correct result is `UNRESOLVED`, and no executable mutation is produced.

The project is maintained as an evolving product. Documentation refers to the **current supported scope** and **capability baseline**, not numbered product phases. New detectors and adapters enter the supported scope only after their contracts, fixtures, calibration, and safety gates pass.

## 2. Product position

Existing tools usually solve one narrow layer: duplicate files, dead exports, dependency cleanup, secret detection, static reachability, or directory sorting. `repo-curator` composes these signals but owns the missing decision layer:

- reconstructing project intent from rules, documentation, manifests, entry points, delivery configuration, and history;
- distinguishing artifact identity, location identity, content identity, and lineage identity;
- proposing `change_episode` and `capability_family` relationships without treating similarity as proof;
- separating competing, transitional, historical, and active implementations;
- preserving evidence and counter-evidence behind every recommendation;
- enforcing exact-byte approval, mutation budgets, drift checks, journaling, recovery, and rollback.

It is not an autonomous refactoring agent and does not claim to prove which implementation is universally “best.”

## 3. Governing principles

1. **Preserve under uncertainty.** Unknown or disputed artifacts remain untouched.
2. **Evidence before classification.** Every nontrivial claim carries evidence, counter-evidence, confidence, and provenance.
3. **Semantic authority is not execution authority.** Project documents can explain intent, but commands or instructions found in repository content are untrusted data and are never executed merely because they appear in a trusted document.
4. **Recommendation is not authorization.** Semantic conclusions alone cannot create executable mutations.
5. **Exact approval.** Apply operates only on the exact bytes, repository state, scope, and mutation budget that were reviewed.
6. **Reversible changes only.** No permanent deletion, automatic merge, or history rewrite.
7. **Use proven components.** Reuse compatible open-source scanners, parsers, and analyzers behind stable adapters; retain the project’s own domain and safety layer.
8. **Continuous maintenance.** Upstream changes, schemas, adapters, and evaluation baselines are monitored and versioned.

## 4. Supported operating model

The workflow has two hard-separated planes.

### 4.1 Analysis plane

The analysis plane is read-only. It inventories the repository, discovers declared intent, collects sanitized history and structural evidence, runs approved detectors, creates candidate relationships, assigns conservative states, and emits review questions where necessary.

It does not execute repository code, install dependencies, invoke package lifecycle scripts, or follow untrusted instructions found in project files.

### 4.2 Mutation plane

The mutation plane consumes an approved, byte-identical plan. It checks repository drift, protected paths, destination safety, symlink behavior, mutation budget, and journal state. It performs only allowlisted reversible operations and verifies their postconditions.

Non-Git repositories remain analysis-and-plan only in the current supported scope. Apply requires the recovery guarantees supplied by a valid Git worktree plus the repo-curator journal.

## 5. Intent discovery before cleanup

Before classifying cleanup candidates, repo-curator reads the project’s available intent sources, including:

- `AGENTS.md`, `CLAUDE.md`, `README*`, `CONTRIBUTING*`, `CONTEXT.md`;
- architecture documents, ADRs, PRDs, roadmaps, release notes, and migration plans;
- package and workspace manifests, lockfiles, build definitions, CI/CD, deployment configuration;
- exported APIs, application entry points, plugin registries, code ownership, default branch, tags, releases;
- issue and pull-request templates and locally available sanitized Git history.

Sources are ranked by scope, specificity, freshness, and directness. A broad README does not silently override a scoped project rule; a recent filename does not silently override an established release path. Conflicts are recorded rather than flattened.

The intent phase emits:

- `project-intent.json` — declared goals, constraints, entry points, delivery paths, and provenance;
- `retention-policy.json` — what must be preserved and why;
- `mainline-map.jsonl` — artifact-to-mainline hypotheses with evidence and uncertainty;
- `intent-conflicts.jsonl` — unresolved source conflicts;
- `decision-questions.jsonl` — minimal questions needed to unblock safe classification;
- `user-decisions.jsonl` — scoped user assertions and their decision metadata.

### 5.1 Evidence-driven grilling

The product adopts the reasoning pattern of `grill-me` and `grill-with-docs`; it does not blindly interrogate every user. It first extracts answers from project evidence. Only a material unresolved decision triggers a question.

Questions are asked one at a time and include:

- the exact decision being requested;
- the evidence and counter-evidence found;
- the affected artifacts and operations;
- a recommended conservative answer and its consequences.

An answer is stored as a user assertion with scope, reason, timestamp, supporting evidence, counter-evidence, and a decision-set hash. Assertions do not erase contradictory repository evidence.

Confirmed terminology may produce a proposed `CONTEXT.md` update. A consequential, hard-to-reverse design choice may produce a proposed ADR. These proposals are written under `.repo-curator/` by default and modify project documentation only after explicit approval.

## 6. Domain model

### 6.1 Identity

- **Artifact identity:** a logical repository object observed during a scan.
- **Location identity:** a normalized path plus filesystem boundary and symlink metadata.
- **Content identity:** exact-byte hash, normalized representation hashes where applicable, and size/type metadata.
- **Lineage identity:** Git/object/history relationships and observed transformations.

These identities remain separate. Equal content does not prove equal purpose; equal names do not prove common lineage; moved files do not become new content merely because their location changed.

### 6.2 Relationship candidates

- **`change_episode`:** a candidate grouping of artifacts plausibly produced by the same bounded change event. Strong history, PR, or session evidence is required for high confidence. Without it, repo-curator does not force reconstruction.
- **`capability_family`:** a candidate grouping of implementations that appear to serve the same project responsibility. Structural or textual similarity alone is insufficient.
- **Implementation role:** a hypothesis such as competing, transitional, compatibility, historical, experimental, or active mainline.

All relationships are candidates with evidence and counter-evidence, never hidden facts.

### 6.3 Preservation states

Each artifact may receive one of these review states:

- `PROTECTED`
- `ACTIVE_MAINLINE`
- `REQUIRED_COMPATIBILITY`
- `HISTORICAL_EVIDENCE`
- `EXPERIMENTAL_ACTIVE`
- `SUPERSEDED_CONFIRMED`
- `CLEANUP_CANDIDATE`
- `UNRESOLVED`

`UNRESOLVED` is the default when the classification threshold is not met. It implies preservation and prohibits executable actions.

## 7. Evidence model and confidence

Evidence is recorded as typed observations with source, collection method, scope, timestamp, sanitization state, and applicable limitations. Counter-evidence is a first-class field.

A practical evidence hierarchy is:

1. explicit scoped user decisions and binding project rules;
2. active build, test, packaging, CI/CD, deployment, and public API wiring;
3. default-branch and release history, including direct lineage;
4. entry-point and reachability evidence from supported static analyzers;
5. architecture documents, ADRs, roadmap, and maintained documentation;
6. structural, semantic, naming, timing, and similarity heuristics.

The hierarchy is not a universal overwrite order. Scope and conflicts matter. Filename similarity, timestamps, or model-generated similarity can nominate a candidate but can never independently justify mutation.

Confidence is calibrated per claim type rather than exposed as one misleading product-wide “accuracy” number. The system reports coverage, precision, abstention rate, and unresolved rate separately.

## 8. Architecture

The capability baseline consists of small, testable modules:

- **Preflight and boundary collector:** establishes repository root, Git state, filesystem boundaries, ignored/protected areas, and supported operating mode.
- **Inventory scanner:** emits deterministic artifact, location, byte hash, symlink, submodule, and large-file metadata.
- **Intent discoverer:** reads rules and project documents as untrusted text and builds intent, retention, conflict, and mainline hypotheses.
- **Evidence adapters:** invoke supported external analyzers using bounded inputs and structured outputs.
- **Evidence graph:** retains observations, provenance, counter-evidence, and candidate relationships.
- **Candidate builders:** propose exact duplicates, `change_episode`, `capability_family`, and implementation-role hypotheses.
- **Conservative classifier:** assigns preservation states or abstains.
- **Decision-question builder:** emits the smallest evidence-specific question needed to resolve a material ambiguity.
- **Plan builder:** converts only independently authorized, policy-safe actions into a deterministic plan.
- **Approval validator:** binds exact plan bytes, repository snapshot, decision set, policy, and mutation budget.
- **Apply engine:** performs allowlisted reversible operations with destination and drift checks.
- **Journal, verifier, and rollback planner:** records pre/post state and supports interruption-safe recovery.

### 8.1 Open-source fusion boundary

Open-source components may supply inventory, format detection, archive/metadata extraction, AST parsing, duplicate detection, dead-code signals, dependency signals, secret detection, and review workflow patterns. Candidate integrations include ideas or code from AI File Sorter, Knip, Codescythe, CodeGraph/tree-sitter, jscpd, Gitleaks, and comparable projects.

The preferred order is:

1. adapter through a stable CLI/JSON contract;
2. vendored component when isolation is impractical;
3. attributed port when only a bounded algorithm is required.

AI File Sorter’s scanning, provider abstraction, taxonomy, review, path validation, undo, and feedback patterns are useful; its file-to-category model is not the repo-curator domain model.

Every borrowed component or port is recorded in `third_party/sources.lock.yaml` and `THIRD_PARTY_NOTICES.md`, including license, source repository, commit, original path, integration mode, and modifications. Source files retain applicable SPDX and attribution notices. The product license may be AGPL-3.0, but component compatibility must still be checked per dependency and distribution mode.

## 9. Data flow

```text
repository snapshot
  -> preflight + deterministic inventory
  -> intent discovery + retention contract + mainline hypotheses
  -> detector adapters + sanitized history collection
  -> evidence graph + counter-evidence
  -> relationship candidates
  -> conservative states / UNRESOLVED
  -> evidence-specific user decisions when required
  -> recommendation report
  -> deterministic plan (safe authorized subset only)
  -> exact-byte approval + drift + budget validation
  -> reversible apply + journal
  -> verification / recovery / rollback
```

Analysis outputs and executable plans use separate schemas and directories. A report cannot be renamed or reinterpreted as a plan.

## 10. Mutation safety contract

An executable action must pass all of the following:

- supported operation and repository mode;
- classification permits action and is not `UNRESOLVED`;
- independent policy rule authorizes the operation;
- source and destination resolve inside allowed boundaries;
- protected paths and required compatibility artifacts are excluded;
- exact plan bytes, snapshot, decisions, and policy hashes match approval;
- repository state has not drifted;
- mutation count and affected bytes remain within the approved budget;
- journal and recovery destination are available;
- postconditions are mechanically verifiable.

Failures are fail-closed. The engine records the reason and performs no further mutation. Recovery never relies on remembering a model conversation.

## 11. Evaluation and correctness gates

Correctness is established per layer with deterministic fixtures, adversarial fixtures, a human-labeled gold corpus, shadow mode, and post-apply invariants.

### 11.1 Inventory and filesystem fixtures

Fixtures cover ordinary files, hidden files, ignored paths, Unicode and case collisions, hard links, symlinks, traversal attempts, broken links, permission errors, nested repositories, submodules, Git LFS pointers, large files, archives, generated output, and repository drift.

The supported inventory corpus targets at least 99.9% recall, while exact-byte duplicate claims require 100% precision in the tested corpus.

### 11.2 Intent and relationship fixtures

Gold cases include:

- clear active mainline vs archived prototype;
- stale README vs active deployment wiring;
- scoped rule conflict;
- compatibility implementation that appears dead statically;
- same capability with different architecture;
- similar code serving different responsibilities;
- strong Git episode evidence;
- no history evidence, requiring abstention;
- user decision that conflicts with repository evidence.

For high-confidence `capability_family` claims, the target precision is at least 95% on the labeled supported corpus. Strong-evidence `change_episode` candidates target at least 90% precision. These are admission gates for the high-confidence label, not claims of universal correctness.

### 11.3 Mutation and recovery fixtures

Tests must demonstrate fail-closed handling of plan tampering, protected paths, destination collisions, path traversal, symlink swaps, drift, budget overruns, interruption at every journal boundary, rollback, and secret leakage in outputs.

Before enabling an operation class beyond shadow mode, the risk corpus should contain at least 3,000 relevant candidates with zero observed unsafe false positives. This does not prove zero risk; it is an empirical gate combined with invariants and manual review.

## 12. Continuous maintenance

The project maintains:

- versioned schemas with explicit compatibility and migration rules;
- adapter contracts and frozen detector fixtures;
- an upstream source lock and periodic license/security review;
- calibration reports by language, repository type, and claim class;
- a regression corpus for every confirmed failure;
- shadow-mode comparison before new detectors influence recommendations;
- deprecation notices before removing supported schemas or adapters.

An upstream update is not adopted solely because it is newer. It must pass attribution review, contract tests, behavioral fixtures, calibration gates, and mutation-safety regression tests.

## 13. Explicit exclusions and non-claims

The current supported scope excludes:

- automatic selection of the “best” competing implementation;
- autonomous code merge, refactor, or permanent deletion;
- reliable attribution of code authorship to AI vs humans;
- complete dynamic reachability or behavioral-equivalence proofs;
- forced episode reconstruction without Git, PR, or session evidence;
- universal cross-language semantic equivalence;
- execution of target code or repository-provided commands;
- dependency installation or package lifecycle scripts;
- Web UI, MCP service, database, cloud service, or multi-user authorization system;
- automatic history rewriting.

These are product boundaries, not promises for a later numbered version. A future maintenance decision may revise them only through a reviewed design change and new safety evidence.

## 14. Resolved design decisions

- Built-in ignored/protected patterns are conservative, explicitly documented, configurable, and recorded when matched.
- Reviewer identity is a free-form audit label, not an authentication claim.
- Non-Git repositories support inventory, analysis, recommendations, and plan generation only; apply is disabled.
- Product and schema evolution use capability and schema versions where technically required, but product documentation does not use numbered phase branding.
- The default response to insufficient evidence is preservation through `UNRESOLVED`.

## 15. Readiness assessment

Confidence in the product direction is high enough to proceed with safety inventory and fixtures. Confidence is intentionally lower for semantic reconstruction than deterministic inventory:

- deterministic inventory and byte identity: high;
- mutation safety under the supported operation set: high after fault-injection gates pass;
- intent discovery and mainline hypotheses: moderate to high, with abstention;
- capability families and change episodes: moderate, restricted to evidence-backed candidates;
- automatic best-implementation choice: insufficient and therefore excluded.

Implementation should start with the inventory/safety contracts and fixtures, then add intent discovery and evidence-only classification in shadow mode. Mutation remains disabled until its independent gates pass.
