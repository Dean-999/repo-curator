---
title: repo-curator Computational Research Evidence Curation PRD
status: approved
label: approved
issue_tracker: github-issue-18
product: repo-curator
maintenance: continuously-maintained
date: 2026-07-29
---

# repo-curator Computational Research Evidence Curation PRD

> This document describes the current supported scope and is maintained continuously. It does not use numbered product-phase branding. The conservative intent-discovery, evidence, abstention, open-source integration, and maintenance rules in [`docs/superpowers/specs/2026-07-16-repo-curator-design.md`](superpowers/specs/2026-07-16-repo-curator-design.md) are binding where this earlier draft is silent or less conservative.

## 1. Executive summary

`repo-curator` is an explicitly invoked Codex Skill positioned as **retrospective evidence reconstruction and safe curation for computational research repositories** made chaotic by repeated human and AI-assisted changes. The positioning is defined by the repository problem and outcome rather than one persona or lifecycle event. Publication, review, handoff, revival, and archival are important use contexts, especially when code, data, configurations, environments, notebooks, figures, reports, accepted and failed experiments, and historical implementations are intermixed or incompletely recorded.

The current supported scope builds a bounded, auditable model of repository artifacts, their content, locations, research relationships, experiment attempts, canonical-result hypotheses, scientific mainlines, retention requirements, and proposed actions. Its primary review view follows a research evidence chain from a publication claim, figure, or table through a result and experiment attempt to the configuration, environment, code revision, and dataset snapshot that may support it. Missing and conflicting links remain visible rather than being completed by model invention.

The product assesses **reproducibility evidence completeness**; it does not execute experiments or verify scientific truth. It separates deterministic observations, declared provenance, semantic inferences, scoped user assertions, recommendations, approvals, and executable actions. Audit and planning never modify original repository artifacts. Apply executes only pre-approved, reversible, same-filesystem moves already present in the exact approved `plan.json`. Permanent deletion, automatic document merging, repository-code execution, dependency installation, and automatic Git operations are forbidden.

The product is successful when a reviewer can determine what should remain current, what should be archived or quarantined, what may warrant merging or deletion, what evidence supports each conclusion, what contradicts it, and what remains uncertain. Success is not measured by minimizing file count.

Independent large-corpus admission is an optional internal validation track, not
the product's primary market promise or a launch prerequisite. The primary
claim is that repo-curator produces local, auditable, conservative evidence
reconstruction and reviewable curation plans for computational research
repositories. Public positioning should emphasize evidence traceability,
uncertainty preservation, and safe shadow-mode recommendations rather than
formal benchmark certification.

## 2. Problem Statement and Product Differentiation

Computational research repositories accumulate manuscripts, preregistrations, plans, protocols, figures, tables, notebooks, exports, logs, copied archives, retries, accepted and failed experiments, audit records, dataset snapshots, environments, models, and artifacts named `final`, `old`, `fixed`, or `latest`. AI coding accelerates the creation of competing implementations and partially connected experiment materials. Conventional cleanup tools rely on age, filename, size, duplicate bytes, or static references. Those signals cannot establish scientific value, provenance, experiment lineage, publication support, or retention obligations.

Existing research tools usually capture provenance prospectively: DataLad, Renku, noWorkflow, ReproZip, DVC, MLflow, Sacred, Snakemake, Nextflow, showyourwork, Whole Tale, and RO-Crate are strongest when the project records or packages runs deliberately. `repo-curator` does not replace them. It imports their declarations as typed evidence and addresses the later condition in which adoption was partial, tools changed, metadata drifted, or historical material predates the current workflow.

`repo-curator` adds a retrospective curation layer above filesystem inventory, research metadata, workflow declarations, and code structure. RepoWise, CodeGraph, Understand Anything, Knip, and comparable analyzers may contribute architectural or reachability evidence, but `repo-curator` remains responsible for research evidence chains, experiment bundles, canonical-result and scientific-mainline hypotheses, counter-evidence, retention reasoning, recommendations, approval, and reversible application. Its governing principle is: scientific status, software reachability, and file action are separate decisions.

## Solution

The solution is an explicitly invoked, local-first Codex workflow backed by deterministic, resource-bounded scripts, versioned file contracts, and optional read-only adapters. It first inventories the repository and imports any declared provenance, then reconstructs project intent, scientific mainline, research evidence chains, experiment bundles, canonical-result candidates, conflicts, and reproducibility-evidence gaps without changing repository artifacts. It produces conservative recommendations and a reviewable plan only after evidence and counter-evidence are recorded. Only reversible actions in the exact approved plan can reach the apply engine.

Open-source fusion follows a strict order: standards mapping first, stable CLI/JSON adapters second, attributed ports for small independently testable algorithms third, and vendoring only when isolation is impractical. External tools provide observations, not semantic or execution authority. Their absence or failure lowers coverage and never causes weak evidence to be promoted.

## 3. Goals

The maintained capability baseline must produce a deterministic inventory, protected research bundles, bounded profiles, exact-duplicate groups, imported provenance observations, evidence and relationship records, research evidence chains, document and claim comparisons, experiment attempts, canonical-result and scientific-mainline hypotheses, reproducibility-evidence gaps, multidimensional classifications, a machine-readable plan, a human-readable plan, exact plan-bound approvals, reversible movements, a locally append-written hash-chained journal, rollback instructions, and post-apply verification. It must expose uncertainty and counter-evidence rather than converting weak signals into confident actions.

## Out of Scope

The current supported scope does not permanently delete content, rewrite or merge documents, refactor source code, run target code, execute notebooks or workflows, reproduce experiments, prepare an executable reproduction handoff, recompute statistics, judge causal validity, verify a publication claim, install dependencies, commit Git changes, download LFS objects, call external embedding services, run a vector database, provide an MCP server or Web UI, use cloud storage, or implement multi-user approval. It does not claim to prove that a file is unreferenced across all languages or runtime systems, that a research evidence chain is complete outside analyzed scopes, or that a scientifically significant result is canonical.

## 4. Personas and primary use cases

The product is role-flexible within the computational-research boundary. Likely operators include computational researchers, research software engineers, lab members, principal investigators, artifact evaluators, data curators, laboratory reviewers, ML engineers, robotics and numerical-computing teams, software maintainers, and auditors. No single persona defines the product; the shared condition is responsibility for understanding or safely curating a computational research repository whose current and historical evidence are intermixed.

Primary use cases are a read-only repository audit; reconstruction of scientific mainline and research evidence chains; identification of canonical-result, experiment-attempt, bundle, and publication-support candidates; reporting of reproducibility-evidence gaps; generation of a consolidation plan; review of merge and deletion candidates; approval of reversible actions; safe archive or quarantine movement; recovery from interrupted apply; and comparison with an earlier curation run.

## 5. User Stories

1. As a researcher, I want an inventory of every relevant artifact, so that hidden or untracked evidence is not omitted.
2. As a researcher, I want failed experiments separated from disposable outputs, so that negative results remain interpretable.
3. As a reviewer, I want deterministic evidence separated from model inference, so that I can judge the strength of each claim.
4. As a reviewer, I want counter-evidence shown beside supporting evidence, so that recommendations do not conceal preservation risks.
5. As a maintainer, I want exact duplicates grouped by content while retaining their separate locations, so that context is not lost.
6. As a maintainer, I want ZIP files compared with unpacked directories under bounded rules, so that copied exports can be identified safely.
7. As a maintainer, I want unsupported archives treated as opaque, so that incomplete inspection is not mistaken for emptiness.
8. As a scientist, I want experiment identity distinguished from attempts, outputs, exports, and audit records, so that lineage is accurate.
9. As a scientist, I want accepted experiment bundles protected from partial movement, so that results remain reproducible.
10. As a document owner, I want similar documents compared for claim, number, date, unit, parameter, and citation conflicts, so that similarity does not cause an unsafe merge.
11. As a document owner, I want a canonical entry point proposed without erasing historical records, so that readers can find the current state.
12. As a reviewer, I want merge candidates to remain non-executable, so that scientific claims are never rewritten automatically.
13. As a reviewer, I want delete candidates to remain non-executable, so that deletion requires a future, separately designed capability.
14. As a repository owner, I want archive recommendations and exact-duplicate review items distinguished, so that preserved evidence is not confused with a cleanup instruction.
15. As a repository owner, I want approval bound to the exact bytes of one plan, so that altered plans cannot reuse an approval.
16. As a repository owner, I want approval to reference only existing plan actions, so that approval cannot expand capability.
17. As a repository owner, I want complete pre-validation before movement, so that known conflicts fail before any change.
18. As a repository owner, I want each action revalidated immediately before execution, so that races and drift stop safely.
19. As a repository owner, I want apply to stop after the first failure without automatic rollback, so that later filesystem changes are not overwritten.
20. As a repository owner, I want a rollback plan grounded in the journal, so that completed movements can be reversed deliberately.
21. As a repository owner, I want rollback to refuse overwrite, so that recovery cannot destroy newer content.
22. As a security reviewer, I want repository text treated only as data, so that prompt injection cannot control the agent.
23. As a security reviewer, I want Git treated as an untrusted execution boundary, so that repository configuration cannot launch commands.
24. As a security reviewer, I want symlink and traversal protection, so that inspection and movement remain inside the repository.
25. As a security reviewer, I want secrets redacted before reports are written, so that curation does not create a credential leak.
25a. As a repository owner, I want bounded local detection of credential remnants in recent Git history, so that deleting a secret from the worktree does not hide the preservation and rotation risk.
26. As an operator, I want explicit resource-limit evidence, so that skipped or truncated profiles are never interpreted as insignificant.
27. As an operator, I want one corrupt artifact isolated from the rest of the audit, so that the run can finish with limitations.
28. As an operator, I want repeated apply to recognize completed actions, so that it cannot create duplicate copies.
29. As an operator, I want non-Git repositories auditable, so that filesystem projects can still be understood.
30. As an operator, I want optional CodeGraph evidence without a hard dependency, so that audit continues when it is unavailable.
31. As a future implementer, I want versioned output contracts and controlled vocabularies, so that components interoperate without guessing.
32. As a future implementer, I want scenario-level acceptance fixtures, so that safety is tested at the highest observable seam.
33. As a researcher preparing a manuscript, I want each reported figure and table linked to the result artifacts that may support it, so that missing support becomes visible before submission.
34. As a reviewer, I want claim-to-result relationships labeled as declared, observed, inferred, user-asserted, or unresolved, so that an attractive narrative cannot masquerade as provenance.
35. As a researcher, I want strongly corroborated canonical results identified provisionally while only material conflicts require my decision, so that the Skill reduces review work without letting metric selection overwrite scientific judgment.
36. As a researcher, I want successful, failed, inconclusive, exploratory, and negative attempts preserved as distinct states, so that publication and survivorship bias are not reinforced by cleanup.
37. As a research software engineer, I want the scientific mainline to include required data, configuration, environment, code, validation, and explanation materials, so that it is not confused with the Git default branch.
38. As a curator, I want a reproducibility-evidence gap report, so that I can distinguish absent material from material the tool could not inspect.
39. As a curator, I want existing RO-Crate and Workflow Run RO-Crate records imported and validated within bounded scopes, so that established research metadata is not replaced by new guesses.
40. As a DataLad, DVC, Renku, noWorkflow, MLflow, Sacred, Snakemake, Nextflow, or showyourwork user, I want existing declarations imported as typed observations, so that repo-curator composes rather than duplicates my tools.
41. As a security reviewer, I want external adapter outputs treated as untrusted and coverage-limited, so that a compromised or stale detector cannot authorize movement.
42. As a future implementer, I want each borrowed adapter, port, fixture, and vendored component locked to source, commit, path, license, modification, and tests, so that open-source fusion remains auditable.
43. As a researcher with sensitive or embargoed data, I want local analysis and redacted persisted evidence, so that curation does not create a new disclosure channel.
44. As a principal investigator receiving a departing member's repository, I want unresolved research intent converted into one evidence-specific question at a time, so that handoff does not depend on reconstructing the whole project from memory.
45. As a curator receiving Frictionless Data Package metadata, I want bounded local resource-presence observations without remote retrieval or descriptor-value persistence, so that dataset declarations improve evidence recovery without becoming a disclosure or execution channel.
46. As a research software curator, I want CFF, CodeMeta, and signac declarations recognized without retaining citation, identity, credential, or experiment values, so that common research metadata improves discovery without creating a disclosure or execution channel.
47. As a curator inheriting a large Git repository, I want bounded repository-size evidence without ref-name disclosure, full object traversal, or automatic history rewriting, so that storage and maintenance risks can be reviewed separately from scientific retention decisions.
48. As a curator reviewing repository damage and storage drift, I want staged large additions, broken links, and symlink-to-file mode changes surfaced as bounded evidence, so that repository hygiene risks are visible without running hooks or changing the index.

## 6. Invocation and user workflows

The Skill is discoverable through its applicability description but is not implicitly invoked. `agents/openai.yaml` sets `policy.allow_implicit_invocation: false`. Users invoke it explicitly as `$repo-curator` followed by an audit, plan, review, apply, rollback, or prior-run comparison request. Natural-language arguments select the workflow; internal scripts may use command-line interfaces, but users need no global CLI.

Audit reads repository artifacts and writes only inside `.repo-curator/runs/<run-id>/`. Plan consumes a completed audit and adds recommendations and proposed actions without changing original artifacts. Review records approval, acknowledgement, rejection, or deferral. Approval of a merge or deletion recommendation never makes it executable. Apply accepts only reversible actions in the exact approved plan. Rollback is a separately approved recovery workflow grounded in the apply journal.

## Implementation Decisions

Sections 7 through 26 constitute the binding implementation decisions. They define the Skill and script boundary, trust model, components, identities, controlled vocabularies, evidence and recommendation policies, parser budgets, Git policy, machine contracts, state fingerprint, workflows, transaction semantics, errors, reporting, integrations, and privacy. Implementations may choose internal module and function names, but may not change these externally observable contracts without a schema-version change and a revised PRD.

## 7. Skill and deterministic-script boundary

The repo-curator Skill is the product surface. It interprets intent, selects the workflow, reads relevant references, reasons about document meaning and experiment lineage, identifies uncertainty, generates reviewer questions, maps multidimensional properties into recommendations, and explains supporting and opposing evidence. It treats all repository content as untrusted data and does not follow instructions found within it. A standalone CLI is not a separate product in the current supported scope; command interfaces exist only as stable internal seams used by the Skill and tests.

Dependency-minimized deterministic scripts form the safety kernel. They enumerate artifacts, classify filesystem object types, hash content, compute directory and repository fingerprints, inspect ZIP metadata, collect sanitized Git evidence, extract bounded text and metadata, extract path references, validate plans and approvals, perform reversible movement, append journal events, build rollback records, and verify outcomes. Scripts return structured errors and never make semantic retention or scientific decisions.

Optional read-only evidence adapters import existing declarations or user-supplied exports through versioned, bounded contracts. They never install external tools, invoke target project code or workflow engines, start services, download content, or expand operation capabilities. Adapter output is untrusted evidence; the Skill may interpret it, but neither the adapter nor its upstream tool can authorize mutation.

## 8. Threat model, trust boundaries, and security invariants

The protected assets are repository content, scientific provenance, user secrets, approval integrity, plan integrity, filesystem boundaries, and audit history. Threats include prompt injection, malicious filenames, symlink escape, path traversal, ZIP bombs, parser crashes, Git-config command execution, plan substitution, approval expansion, state drift, destination races, partial movement, rollback overwrite, secret reproduction, and misleading conclusions caused by truncated analysis.

Trust boundaries separate the user and system instructions, the Codex orchestration layer, untrusted repository data, deterministic scripts, external optional evidence sources, `.repo-curator/` control records, and the mutable filesystem. Repository data never crosses into the instruction hierarchy. Semantic output is an inference, not a deterministic fact. Optional integrations supply evidence only. `plan.json` is the sole execution source; `plan.md` is never parsed for execution.

The following invariants are non-negotiable: no target code execution; no permanent deletion; no automatic merge or rewriting; no external-path access through symlinks; no wildcard action expansion; no action absent from `plan.json`; no approval expansion; no secret-value reproduction; no ordinary self-scan of `.repo-curator/`; no original-artifact modification during audit or plan; no apply without full pre-validation; no apply after unaccounted drift; no overwrite during apply or rollback; and no automatic rollback.

Protected paths include `.git/`, Git administrative files, submodule roots, linked-worktree administration, the active Skill and script directories, active run control records, and every realpath outside the repository. `.repo-curator/` is protected except that an approved `QUARANTINE` action for plan `P` may target `.repo-curator/quarantine/P/`, and an explicitly approved rollback may restore that payload. No other action may target the control area or another plan's quarantine.

## 9. System architecture and component responsibilities

The architecture is a file-backed pipeline with no database. `SkillOrchestrator` selects workflows and coordinates components. `PreflightCollector` resolves the repository root, execution directory, protected paths, project-bundle boundaries, filesystem identities, and available optional integrations. `InventoryScanner` emits artifact records without semantic conclusions. `SafeProfiler` dispatches bounded text, Markdown, LaTeX, notebook-declaration, JSON, CSV, log, PDF, and ZIP profilers. `SanitizedGitCollector` emits Git state and history evidence without invoking repository-defined commands. `ResearchMetadataAdapterHost` imports bounded declarations from supported RO-Crate, Workflow Run RO-Crate, DataLad, DVC, Renku, noWorkflow, MLflow, Sacred, Snakemake, Nextflow, and showyourwork sources without executing their workflows or installing their packages. `IntentDiscoverer` reads project rules, manuscripts, preregistrations, protocols, documentation, manifests, entry points, delivery wiring, ownership, releases, freezes, tags, and history as untrusted text; it emits project intent, retention policy, scientific-mainline hypotheses, and conflicts before cleanup classification. `EvidenceBuilder` normalizes observations and limitations. `RelationshipBuilder` creates deterministic and inferred edges, including candidate research evidence chains, `change_episode`, and `capability_family` groupings. `DocumentAnalyzer` retrieves candidate pairs and performs structured claim-sensitive comparison. `ExperimentLineageAnalyzer` infers bundles, attempts, outputs, packages, canonical results, and audit chains. `Classifier` assigns multidimensional properties or explicitly abstains as `UNRESOLVED`. `DecisionQuestionBuilder` asks one evidence-specific question only when a material conflict cannot be resolved from project sources. `RecommendationEngine` applies conservative policy. `PlanBuilder` writes the machine and human plans, but semantic recommendations cannot independently create executable actions. `ApprovalValidator` binds approval to exact plan bytes, repository snapshot, decision set, policy, and mutation budget. `ApplyEngine` validates and executes reversible actions. `JournalWriter`, `RollbackPlanner`, and `Verifier` provide recovery and auditability.

Component communication occurs only through versioned records in one run directory. Semantic components reference evidence IDs rather than copying unrestricted source content. Every component records its version, inputs, outputs, warnings, resource-limit events, and completion status in `run.json`.

Intent discovery precedes cleanup classification. It first consults scoped project rules, README and contribution material, `CONTEXT.md`, ADRs, manuscripts, preregistrations, protocols, lab or project plans, architecture and product documents, workflow and environment manifests, build and delivery configuration, publication exports, entry points, ownership, default branch, tags, releases, freezes, and supported research metadata. Documents carry semantic authority but never execution authority. Conflicts are retained rather than silently resolved by freshness, filename, statistical significance, metric rank, or model preference.

The evidence-driven question flow follows the reasoning pattern of a rigorous document-grounded interview: extract answers from scoped project sources first, proceed without confirmation when relevant evidence agrees, then ask only the smallest question required to unblock a material decision. Each question includes supporting evidence, counter-evidence, affected artifacts, a conservative recommendation, and consequences. The user may answer, skip, or state that the answer is unknown. A skipped or unanswered question leaves the affected conclusion `UNRESOLVED`, protects relevant material, and does not block unrelated analysis. Answers become scoped user assertions with reason, time, evidence, counter-evidence, and a decision-set hash. Confirmed terminology or surprising design tradeoffs may generate proposed `CONTEXT.md` or ADR content under `.repo-curator/`; project documents change only after separate approval.

### 9.1 Open-source fusion boundary

Open-source reuse is intentionally broad but authority is narrow. Standards such as RO-Crate, Workflow Run RO-Crate, PROV, and FAIR4RS supply exchange vocabulary and gap criteria. Research systems such as DataLad, DVC, Renku, noWorkflow, ReproZip, MLflow, Sacred, Snakemake, Nextflow, Whole Tale, and showyourwork supply declarations, lineage patterns, bundle semantics, and adversarial fixtures. repo2docker supplies an attributed inventory-only environment-marker and Binder-scope model without transferring any build or execution authority. RepoWise, CodeGraph, Understand Anything, Knip, and ecosystem analyzers supply typed structural observations. AI File Sorter and KonMari supply review, path-safety, undo, and decision-presentation patterns.

The preferred integration order is a frozen CLI or file-contract adapter, then a small attributed port with independent tests, then vendoring only when no stable isolation boundary exists. Whole platforms, databases, dashboards, servers, hooks, package lifecycle commands, and execution engines remain outside the safety core. Adapter absence, malformed output, version drift, or timeout emits a coverage limitation and cannot promote another observation or authorize an action.

Every copied, adapted, or behaviorally derived component is represented in `third_party/sources.lock.yaml` and `THIRD_PARTY_NOTICES.md` with source repository, fixed commit, original path, license, integration mode, modification summary, applicable SPDX notice, contract fixture, and upstream-review policy. The evidence-backed comparison supporting this policy is maintained in [`research/scientific-reference-fusion.md`](../research/scientific-reference-fusion.md).

## 10. Multidimensional artifact and identity model

An artifact has four distinct identities. `artifact_id` identifies one concrete object observed in one inventory run and is formatted `art_<run-id>_<sequence>`. `content_id` identifies content under a named fingerprint scheme, such as `sha256-file-v1:<hex>`, `merkle-dir-v1:<hex>`, or `zip-manifest-v1:<hex>`; different schemes are never directly equated. `location_id` identifies an observed repository-relative, archive-member, submodule, archive, or quarantine location using a type-tagged hash of its normalized representation. `lineage_id` identifies a logical artifact across runs when evidence supports continuity; its assertion carries confirmed, strongly inferred, weakly inferred, or unresolved confidence.

Regular-file content identity is SHA-256 over exact bytes. A directory fingerprint sorts child entries by normalized relative byte path and hashes each entry's type, name, content fingerprint, executable bit, and symlink target text without following the link. ZIP byte identity hashes the ZIP bytes; normalized ZIP identity separately hashes a sorted manifest of safe member names, uncompressed sizes, CRC values, and sampled or complete member hashes. Incomplete ZIP comparison is labeled incomplete and never establishes equivalence. Archive members have separate artifact and location IDs even when their bytes match unpacked files.

Controlled vocabularies are versioned in the plan schema:

| Dimension | Values |
|---|---|
| role | `SOURCE`, `SCRIPT`, `CONFIGURATION`, `ENVIRONMENT`, `DOCUMENT`, `MANUSCRIPT`, `RESEARCH_CLAIM`, `FIGURE`, `TABLE`, `PLAN`, `PREREGISTRATION`, `PROTOCOL`, `DECISION_RECORD`, `EXPERIMENT`, `EXPERIMENT_ATTEMPT`, `CANONICAL_RESULT`, `OUTPUT`, `AUDIT`, `MANIFEST`, `HASH_RECORD`, `FREEZE_RECORD`, `REVIEWER_RECORD`, `DATASET`, `DATASET_SNAPSHOT`, `MODEL`, `ARCHIVE`, `CACHE`, `TEMPORARY_ARTIFACT`, `UNKNOWN` |
| lifecycle | `CURRENT`, `ACTIVE`, `SUPERSEDED`, `ABANDONED`, `HISTORICAL`, `UNKNOWN` |
| result | `ACCEPTED`, `FAILED`, `INCONCLUSIVE`, `PARTIAL`, `NOT_APPLICABLE`, `UNKNOWN` |
| reproducibility | `REGENERABLE`, `PARTIALLY_REGENERABLE`, `IRREPLACEABLE`, `UNVERIFIED`, `UNKNOWN` |
| evidence completeness | `COMPLETE_IN_ANALYZED_SCOPE`, `PARTIAL`, `MISSING_REQUIRED_LINK`, `CONFLICTING`, `UNVERIFIED`, `UNKNOWN` |
| retention | `REQUIRED`, `RECOMMENDED`, `OPTIONAL`, `UNKNOWN` |
| confidence | `CONFIRMED`, `STRONGLY_INFERRED`, `WEAKLY_INFERRED`, `UNKNOWN` |
| risk | `LOW`, `MEDIUM`, `HIGH`, `CRITICAL` |

Relationships are independently evidenced records. The current v2 shapes include exact-byte `ARTIFACT_GROUP` records and declared attempt-to-artifact `DIRECTED_EDGE` records with types `DECLARED_OUTPUT`, `DECLARED_INPUT`, `DECLARED_CONFIGURATION`, `DECLARED_GENERATOR`, `DECLARED_VALIDATION`, and `DECLARED_REVIEWER_RECORD`. The broader controlled vocabulary reserves `DUPLICATE_OF`, `NEAR_DUPLICATE_OF`, `DERIVED_FROM`, `GENERATED_BY`, `SUPPORTS_CLAIM`, `REPORTED_IN`, `PRODUCED_FIGURE`, `USES_DATASET`, `PARAMETERIZED_BY`, `EXECUTED_IN_ENVIRONMENT`, `SUPERSEDES`, `SUPERSEDED_BY`, `RETRY_OF`, `VALIDATED_BY`, `PACKAGED_AS`, `UNPACKED_FROM`, `REFERENCES`, `REFERENCED_BY`, `MEMBER_OF_BUNDLE`, `CANONICAL_VERSION_OF`, `HISTORICAL_VERSION_OF`, `CHANGE_EPISODE_CANDIDATE`, `CAPABILITY_FAMILY_CANDIDATE`, and `CONFLICTS_WITH` for evidence that can support those stronger meanings. Inverse relationships are emitted explicitly when useful but reference the same evidence set.

A **research evidence chain** is a review projection, not a newly asserted causal graph. It may connect a manuscript claim, figure, or table to a canonical-result candidate, experiment attempt, configuration, environment, code revision, and dataset snapshot. Every link retains its own evidence and may be unresolved. A chain marked complete means complete only in the explicit analyzed scope and never proves that the scientific claim is true or reproducible.

The current read-only preservation-review states are `PROTECTED`, `DECLARATION_EVIDENCE`, `ACTIVE_MAINLINE`, `REQUIRED_COMPATIBILITY`, `HISTORICAL_EVIDENCE`, `EXPERIMENTAL_ACTIVE`, `EXACT_DUPLICATE_REVIEW`, and `UNRESOLVED`. `DECLARATION_EVIDENCE` means that a local, inventory-bound marker is the source of an admitted declaration-presence observation; it does not validate declaration semantics, environment availability, execution, reproducibility, or scientific role. Stronger role evidence may supersede this state, while material conflict, inventory limitation, or bundle guards downgrade it to `UNRESOLVED`. An exact-byte duplicate marker remains `EXACT_DUPLICATE_REVIEW` without losing its declaration supporting evidence. `EXACT_DUPLICATE_REVIEW` records an observed replacement by exact bytes but preserves both artifacts and grants no cleanup, move, or delete authority. Evidence below the applicable threshold or in material conflict yields `UNRESOLVED`, which means preserve and prohibit executable action.

## 11. Evidence model and semantic-inference policy

Every evidence record contains `evidence_id`, `subject_type`, `subject_id`, `evidence_type`, `source_artifact_id`, `source_location`, `observation`, `origin`, `assertion_class`, `strength`, `scope`, `limitations`, `extractor_version`, and `created_at`. `origin` is `DETERMINISTIC`, `ADAPTER`, `SEMANTIC`, or `USER`; `assertion_class` is `DECLARED`, `OBSERVED`, `INFERRED`, or `USER_ASSERTED`; `strength` is `STRONG`, `MODERATE`, or `WEAK`. Secret-bearing observations are reduced to type, location, and redaction marker before persistence.

Semantic inference records contain the proposed value, supporting evidence IDs, counter-evidence IDs, confidence, limitations, and reviewer questions. Missing evidence is never represented as negative evidence. A truncated, timed-out, encrypted, opaque, or unsupported artifact carries explicit limitation evidence and cannot be treated as empty, unreferenced, duplicate, or disposable.

Filenames, directory names, timestamps, and age are weak retrieval signals. No recommendation may depend on one weak signal. Exact byte hashes, signed or internally consistent manifests, direct references, verified generation chains, and reviewer records are stronger signals, but their meaning still depends on bundle and retention context.

Scientific restraint is part of the evidence policy. A publication statement is declared evidence that a claim was made, not proof that the claim is true. A workflow or RO-Crate relationship is declared provenance until its referenced objects and applicable snapshot are checked. A successful process exit is not proof of valid analysis; a statistically significant metric is not proof of canonical status; absence from a manuscript is not proof of irrelevance. The product reports these distinctions explicitly.

## 12. Recommendation policy

The current read-only recommendation vocabulary is `KEEP`, `ARCHIVE`, `REVIEW_EXACT_DUPLICATE`, `MERGE`, and `MANUAL_REVIEW`. Each recommendation contains identity, affected artifacts, multidimensional classifications, evidence and counter-evidence, expected loss, limitations, `human_review_required`, and `executable_in_supported_scope`.

`KEEP` is used when retention is required, an accepted bundle depends on the artifact, provenance or audit value exists, or uncertainty makes movement unsafe. `ARCHIVE` identifies historical material with continuing explanatory or provenance value, but remains non-executable in the packaged Skill. `REVIEW_EXACT_DUPLICATE` records an exact-byte replacement in the analyzed scope with `expected_loss: NONE`; it preserves the original location and carries `NO_MOVE_OR_DELETE_AUTHORIZED`. `MANUAL_REVIEW` is used when evidence conflicts, analysis is incomplete, or risk exceeds confidence.

Current Skill recommendations always set `human_review_required: true` and `executable_in_supported_scope: false`; their plans contain no action candidates. The separately tested archive and quarantine primitives are not exposed by the packaged Skill. Any future mutation workflow requires a new product-governance decision and a versioned action contract; recommendation approval and action approval remain separate.

## 13. Merge-candidate policy

Semantic similarity retrieves candidate pairs but never establishes mergeability. Structured comparison records intended audience, lifecycle order, canonical candidate, shared topics and claims, unique content, numerical, date, unit, parameter, status, conclusion, citation, link, attachment, decision-record, and audit differences.

The subtypes are `FULL_MERGE_CANDIDATE`, `PARTIAL_MERGE_CANDIDATE`, `CANONICALIZE_WITHOUT_MERGE`, and `DO_NOT_MERGE`. Full merge means most current material could be consolidated while originals remain preserved. Partial merge identifies specific compatible sections. Canonicalize-without-merge proposes a current entry point while retaining independent records. Do-not-merge records why similar documents serve distinct audiences, decisions, protocols, conclusions, or audit purposes. The maintained capability produces a proposed outline and reviewer questions, never replacement prose or edited files.

## 14. Delete-candidate policy

A deletion candidate must document role, lifecycle, result, reproducibility, retention, duplicate relationships, references, history, bundle membership, provenance, deterministic and semantic evidence, counter-evidence, regeneration procedure, generator, inputs, configuration, verification status, unresolved risk, blocking conditions, confidence, and risk. It is never executable.

A strong candidate normally requires exact redundancy, disposable-export status, cache status, or verified full regenerability; preservation of generator, inputs, configuration, and provenance; exclusion from accepted, audit, manifest, hash, freeze, reviewer, decision, and provenance chains; no known current reference in the explicitly analyzed scopes; and no loss of interpretability or reproducibility. Failure to establish any required condition downgrades the result to archive, quarantine, or manual review and records the exact reason. “No known reference in analyzed scopes” is the strongest permitted wording; repo-curator never claims universal unreferencedness.

## 15. Experiment-bundle and lineage model

The registry distinguishes `research_claim`, `figure`, `table`, `experiment`, `attempt`, `artifact`, `dataset_snapshot`, `environment`, `package`, `audit_record`, and `canonical_result`. Bundle inference considers shared parents, run IDs, timestamps, manifests, input and output hashes, configurations, environments, audit records, logs, ZIP members, reports, manuscripts, Git history, document links, and generated-by relationships. Each inferred membership stores supporting and opposing evidence and confidence.

An accepted bundle is the transitive closure of a canonical result through required inputs, configuration, generator, validation, manifest, hash, freeze, reviewer, and audit relationships. Planning blocks movement of one member when unresolved dependencies remain or when remaining references would break. Retry, supersession, packaging, unpacking, and validation are separate directed relationships; matching content alone does not prove common lineage.

A `canonical_result` is always a scoped project-governance hypothesis with one of four states: `CANDIDATE`, `PROVISIONALLY_CANONICAL`, `USER_CONFIRMED`, or `UNRESOLVED`. Evidence may include explicit manuscript references, signed or internally consistent freeze records, reviewer or author decisions, release artifacts, maintained workflow wiring, direct generation links, and current project rules. Latest timestamps, filenames containing `final`, best metrics, statistical significance, or model preference cannot establish canonical status alone.

The Skill may assign `PROVISIONALLY_CANONICAL` only when multiple independent evidence classes strongly agree, applicable semantic evaluation gates have passed, and no material counter-evidence exists. Minor gaps that do not change preservation or safety are collected into a batch-review recommendation. A material conflict triggers one evidence-specific question that explains the competing records and the consequence of each answer. An explicit scoped user or reviewer decision yields `USER_CONFIRMED`; it records project governance, not scientific truth, and never erases counter-evidence or grants movement authority. If the user cannot decide, the state is `UNRESOLVED` and all affected attempts and supporting material remain protected.

Negative, failed, inconclusive, partial, and exploratory attempts remain eligible for `HISTORICAL_EVIDENCE` when they document model selection, rejected hypotheses, safety findings, parameter boundaries, reviewer questions, or later decisions. Publication omission is not counter-evidence of value. This policy directly mitigates confirmation, publication, and survivorship bias during curation.

## 16. Resource budgets and parser safety

All configurable values may be lowered. They may be raised only up to the hard ceiling recorded below. Exceeding a limit retains the artifact in inventory and emits `PROFILE_SKIPPED_SIZE_LIMIT`, `PROFILE_TRUNCATED`, `PROFILE_TIMEOUT`, `UNSUPPORTED_FORMAT`, or `RESOURCE_LIMIT_REACHED`.

| Resource | Default | Hard ceiling |
|---|---:|---:|
| Individual file eligible for profiling | 32 MiB | 256 MiB |
| Text or Markdown bytes read | 2 MiB | 16 MiB |
| Log head plus tail | 1 MiB | 8 MiB |
| CSV bytes scanned | 16 MiB | 128 MiB |
| CSV sampled records | 1,000 | 10,000 |
| CSV field length | 1 MiB | 8 MiB |
| JSON bytes parsed | 16 MiB | 64 MiB |
| JSON nesting depth | 64 | 256 |
| PDF file size | 64 MiB | 256 MiB |
| PDF pages inspected | 100 | 500 |
| PDF extracted text | 4 MiB | 32 MiB |
| Per-file parse time | 10 s | 60 s |
| Total audit time | 30 min | 4 h |
| Generated run data | 100 MiB | 1 GiB |
| Inventory artifacts | 250,000 | 2,000,000 |
| Relationships | 2,000,000 | 10,000,000 |
| Candidate document pairs | 1,000 | 10,000 |
| Deep document comparisons | 200 | 2,000 |
| Data Package resources per descriptor | 128 | 128 |
| Data Package paths per resource | 16 | 16 |
| Data Package path length | 4,096 bytes | 4,096 bytes |
| Persisted signac marker records | 256 | 256 |
| Persisted repository-hygiene findings per category | 256 | 256 |

Every regular file whose basename is exactly `datapackage.json` is syntax-checked
under the 1 MiB declaration limit and receives its own `DATA_PACKAGE`
observation. A syntax-valid descriptor remains declared evidence rather than
schema conformance. The observer records safe names, formats, media types,
compression tokens, source classifications, schema kind, and normalized
repository-relative local-path presence only. It does not retain remote URLs,
inline data, schema or dialect contents, descriptions, or arbitrary metadata;
does not open resource payloads; and performs no network access, format
inference, dereferencing, plugin loading, or target execution. The generic file
profile for `datapackage.json` is content-free and reports format
`DATA_PACKAGE`, preventing descriptor values from entering `profiles.jsonl`.

A root `CITATION.cff` emits presence-only evidence without YAML or schema
parsing. A regular root `codemeta.json` is syntax-checked under the same 1 MiB
limit and emits only allowlisted top-level field names plus declared author and
programming-language cardinalities; all values and JSON-LD resolution are
omitted. The signac observer adapts five upstream filename constants and counts
regular project, cache, statepoint, and document markers from inventory only,
persisting at most 256 marker paths and IDs. Generic profiles for all admitted
CFF, CodeMeta, and signac descriptors are content-free and do not open them.

The current supported scope deeply inspects ZIP only. TAR, compressed TAR, 7z, RAR, and other containers remain opaque and receive `UNSUPPORTED_FORMAT`. ZIP inspection never extracts into the repository.

| ZIP resource | Default | Hard ceiling |
|---|---:|---:|
| ZIP file size | 512 MiB | 4 GiB |
| Members | 100,000 | 1,000,000 |
| Recursive nested depth | 0 | 2 |
| Declared uncompressed bytes | 10 GiB | 100 GiB |
| Actual member bytes read | 512 MiB | 4 GiB |
| Member-name length | 4,096 bytes | 32,768 bytes |
| Individual member size | 1 GiB | 8 GiB |
| Compression ratio | 100:1 | 1,000:1 |
| Parse time | 60 s | 300 s |
| Members sampled | 1,000 | 10,000 |

Absolute member paths, `..`, drive or UNC paths, escaping symlinks, malformed metadata, abnormal ratios, duplicate order-sensitive names, and exceeded bounds terminate inspection of that ZIP with structured evidence, not the audit. Encrypted ZIPs are not decrypted or brute-forced. Pickle, joblib, checkpoints, executable notebooks, and arbitrary serialized objects remain opaque. Parser failures are isolated per artifact.

## 17. Sanitized Git policy

Git-dependent analysis runs only after a sanitized environment is established. The implementation invokes the Git executable directly with an allowlist of `rev-parse`, fixed porcelain `status`, `ls-files`, `log` with fixed formatting, one `diff-tree --stdin --root --always --raw -r -z --no-renames` call over validated commit IDs, `ls-tree -z --long` over validated commit IDs and literal changed paths, and `cat-file blob` over validated object IDs. It never invokes aliases, shell-composed subcommands, checkout, reset, add, commit, merge, rebase, clean, hooks, credential operations, filters, LFS commands, remotes, or target-provided helpers. A Git-derived change episode has 2 through 64 current regular-file members; larger commits remain observed with `GIT_COCHANGE_MEMBER_LIMIT`, not grouped. File-level co-change is evidence that paths changed in one commit, not evidence of common purpose, semantic equivalence, or lineage.

Each invocation sets `GIT_ALLOW_PROTOCOL` to an empty allowlist, `GIT_PROTOCOL_FROM_USER=0`, `GIT_PAGER=cat`, `PAGER=cat`, `GIT_TERMINAL_PROMPT=0`, `GIT_CONFIG_NOSYSTEM=1`, `GIT_NO_LAZY_FETCH=1`, `GIT_NO_REPLACE_OBJECTS=1`, `GIT_LITERAL_PATHSPECS=1`, and a null global config, and supplies command-line overrides disabling `core.fsmonitor`, the untracked cache, the pager, and optional locks. Commands use NUL-delimited output where supported. If sanitized operation cannot be established, Git analysis stops; filesystem audit continues with an explicit limitation.

Git subprocess I/O is incremental and bounded independently from parser budgets: stdin is capped at 64 KiB, ordinary stdout at 32 MiB, stderr at 64 KiB, and wall time at 10 seconds. Each 64-path `ls-tree` history batch has a 512 KiB stdout cap; each `cat-file blob` read is capped at the validated size declared by `ls-tree`. Exceeding any output cap terminates the process, discards the command's semantic result, and records a command-specific limitation. Truncated stdout is never parsed.

A bounded git-sizer-derived observation invokes only `count-objects -v`,
`for-each-ref --format=x`, and `rev-list --count --all` through the same
sanitized runner. It retains object-database numeric fields, ref count, reachable
commit count, current-inventory file totals, largest regular-file identity/path,
and five `value / reference-scale` context ratios. Git emits one constant line
per ref, so repo-curator never receives ref names. It does not enumerate the
complete reachable object graph, read historical file/blob payloads, resolve
object paths, or recommend rewriting.
Historical commit traversal may occur for the reachable count, but historical
file/blob content is not read. Object-database figures explicitly may include unreachable objects or alternates;
ratios are advisory context and cannot authorize classification or mutation.

A pre-commit-hooks-derived hygiene observation reuses inventory warnings for
broken symlinks, selects staged-added regular files whose worktree size exceeds
500 KiB, and parses porcelain-v2 ordinary changed entries for a `120000` HEAD
mode changed to a non-link, non-deleted index mode. Each candidate category
retains at most 256 byte-order-sorted paths. Differing blob IDs are not compared
and remain `MODE_CHANGE_CANDIDATE`; `.gitattributes` and LFS filter attributes
are not evaluated. The observer never installs or runs hooks, prints executable
repair commands, mutates the index/filesystem, rejects commits, or authorizes
cleanup. Unknown or malformed status records fail closed; valid nonordinary
rename, conflict, untracked, or ignored records produce an explicit partial
coverage limitation instead of a complete zero-finding claim.

LFS pointers are recognized from pointer text in the worktree or Git object metadata. Repo-curator does not call Git LFS or download objects. Submodule and linked-worktree roots are inventoried and protected but not recursively curated unless the user explicitly starts a separate audit rooted there.

Recent-history secret detection considers only changed regular-file blobs in the newest 100 commits. It stops at 1,024 paths, 512 unique blobs, 1 MiB per blob, 16 MiB total, or 256 findings. Budget exhaustion, malformed tree output, unavailable objects, non-text blobs, and shallow or indeterminate repository history reduce coverage without aborting filesystem audit. A shallow repository is reported in the Git worktree observation, history-secret summary, run warnings, and change-episode coverage; repo-curator never fetches or deepens it. Persisted findings contain only category, commit ID, and repository-relative path. Secret values, snippets, line content, fingerprints, entropy scores, and provider responses are prohibited output fields.

## 18. Output-file contracts

The working structure is `.repo-curator/config.yaml` plus `.repo-curator/runs/<run-id>/`. Ordinary scans exclude the entire control area. Prior runs are read only for an explicit review or comparison request.

| File | Producer | Consumer | Mutability and purpose |
|---|---|---|---|
| `config.yaml` | User or initialization flow | All components | User-owned configuration; hashed into each plan; never changed by audit |
| `run.json` | Orchestrator | All components and reviewer | Tool-owned status record; append-safe state transitions, finalized at run completion |
| `inventory.jsonl` | InventoryScanner | Profilers and analyzers | Immutable after inventory finalization; one deterministic artifact per line |
| `git-observations.jsonl` | SanitizedGitCollector | EvidenceBuilder, RelationshipBuilder, and reviewer | Bounded commit and current-worktree observations; changed paths are NUL-parsed and co-change remains non-semantic |
| `structural-observations.jsonl` | PythonSyntaxObserver | RelationshipBuilder and reviewer | Bounded AST syntax facts for regular Python files; no imports, execution, dependency installation, or source snippets |
| `project-intent.json` | IntentDiscoverer | Classifier and reviewer | Declared goals, constraints, entry points, delivery paths, scope, and provenance |
| `retention-policy.json` | IntentDiscoverer and review workflow | Classifier and PlanBuilder | Explicit preservation contract; exact bytes and hash bind into plans |
| `mainline-map.jsonl` | IntentDiscoverer | RelationshipBuilder and reviewer | Artifact-to-mainline hypotheses with evidence, counter-evidence, and uncertainty |
| `adapter-observations.jsonl` | ResearchMetadataAdapterHost | EvidenceBuilder and reviewer | Frozen, typed, coverage-limited observations imported from supported research and code tools |
| `research-evidence-chains.jsonl` | RelationshipBuilder and LineageAnalyzer | Reviewer and RecommendationEngine | Claim/figure/result/attempt/config/environment/code/data projections with per-link evidence and unresolved gaps |
| `reproducibility-gaps.jsonl` | LineageAnalyzer | Reviewer | Missing, conflicting, opaque, or unverified materials needed to interpret or potentially reproduce a result; never a reproduction verdict |
| `intent-conflicts.jsonl` | IntentDiscoverer | DecisionQuestionBuilder and reviewer | Unflattened conflicts among scoped intent sources |
| `decision-questions.jsonl` | DecisionQuestionBuilder | Review workflow | Minimal evidence-specific questions; never an execution source |
| `user-decisions.jsonl` | Review workflow | Classifier and ApprovalValidator | Scoped assertions with reasons, evidence, counter-evidence, and decision hashes |
| `evidence.jsonl` | Collectors and analyzers | Classifier and reviewer | Append-only during audit; immutable when audit closes |
| `relationships.jsonl` | RelationshipBuilder | Lineage and recommendation engines | Append-only during analysis; immutable when plan starts |
| `document-profiles.jsonl` | SafeProfiler | DocumentAnalyzer | Bounded metadata and redacted excerpts; no unrestricted copies |
| `experiment-registry.yaml` | LineageAnalyzer | Reviewer and RecommendationEngine | Human-readable lineage projection; immutable with finalized plan |
| `plan.json` | PlanBuilder | ApprovalValidator and ApplyEngine | Sole execution source; exact bytes logically immutable after creation |
| `plan.md` | PlanBuilder | Human reviewer | Explanatory only; never parsed for execution |
| `approval.yaml` | Review workflow | ApprovalValidator | One immutable approval record per `approval_id`; revisions create new files or versioned records |
| `apply-journal.jsonl` | ApplyEngine | Recovery and Verifier | Append-only event log; never rewritten |
| `rollback.json` | RollbackPlanner | Approved rollback workflow | Inverse actions derived from verified journal outcomes; immutable per generation |
| `verification.md` | Verifier | Human reviewer | Explanatory report grounded in recorded checks |

`run.json` records schema version, run ID, root realpath, repository mode, Git HEAD or null, repository-state hash, tool versions, timestamps, exclusions, budgets, warnings, execution mode, component states, and previous-run relationship. All JSONL records include `schema_version`, stable record ID, run ID, and creation timestamp. Finalized files are written to temporary siblings, flushed, atomically renamed without overwrite, and hashed into `run.json`.

The maintained record contracts are as follows. Fields marked as lists are present as empty lists rather than omitted. Optional scalar values are represented as explicit nulls. Unknown enum values use the controlled `UNKNOWN` value rather than arbitrary strings.

| Record | Required fields |
|---|---|
| `run.json` | `schema_version`, `run_id`, `repository_root_realpath`, `repository_mode`, `git_head`, `repository_state_hash`, `effective_config_hash`, `tool_versions`, `started_at`, `ended_at`, `execution_mode`, `previous_run_id`, `exclusions`, `resource_budgets`, `component_states`, `relationship_coverage`, `warnings`, `output_file_hashes`, `final_status` |
| Inventory record | `schema_version`, `run_id`, `artifact_id`, `content_id`, `location_id`, `lineage_id`, `repository_relative_path`, `realpath`, `object_type`, `size_bytes`, `mode`, `executable`, `mtime_ns`, `symlink_target_text`, `git_state`, `lfs_pointer`, `fingerprint_scheme`, `fingerprint`, `profile_eligibility`, `warnings`, `created_at` |
| Python structure observation | `schema_version`, `run_id`, `structure_id`, `artifact_id`, `content_id`, `repository_relative_path`, `module_name`, `imports`, `definitions`, `has_main_guard`, `limitations`, `created_at` |
| Evidence record | `schema_version`, `run_id`, `evidence_id`, `subject_type`, `subject_id`, `evidence_type`, `source_artifact_id`, `source_location_id`, `observation`, `origin`, `strength`, `limitations`, `extractor`, `extractor_version`, `redactions`, `created_at` |
| Relationship record | `schema_version`, `run_id`, `relationship_id`, `relationship_type`, `source_artifact_id`, `target_artifact_id`, `direction`, `evidence_ids`, `counter_evidence_ids`, `confidence`, `limitations`, `created_at` |
| Document profile | `schema_version`, `run_id`, `profile_id`, `artifact_id`, `title`, `headings`, `document_role`, `intended_audience`, `declared_dates`, `status_terms`, `path_references`, `citations`, `bounded_summary`, `inspected_ranges`, `persisted_sample_ranges`, `truncated`, `redactions`, `limitations`, `created_at` |

`object_type` is one of `REGULAR_FILE`, `DIRECTORY`, `SYMLINK`, `ZIP_ARCHIVE`, `ARCHIVE_MEMBER`, `GIT_LFS_POINTER`, `SUBMODULE`, `SPECIAL_FILE`, or `UNKNOWN`. Special files are inventoried but never opened or moved. `git_state` contains `tracked`, `untracked`, `ignored_included`, `modified`, and `index_status`; non-Git repositories use false or null values as appropriate.

`experiment-registry.yaml` has top-level `schema_version`, `run_id`, `research_claims`, `figures`, `tables`, `experiments`, `attempts`, `dataset_snapshots`, `environments`, `bundles`, `canonical_results`, and `limitations`. Every experiment, attempt, and canonical-result hypothesis has an ID, label, artifact IDs, relationship IDs, evidence IDs, counter-evidence IDs, lifecycle, result, evidence-completeness status, confidence, and reviewer questions. Every bundle lists required, optional, audit, output, package, publication-support, and unresolved members separately.

`apply-journal.jsonl` records `schema_version`, `journal_event_id`, `apply_run_id`, `plan_id`, `approval_id`, `action_id`, `sequence`, `event_type`, `timestamp`, `source_observation`, `destination_observation`, `expected_state_hash`, `observed_state_hash`, `error`, and `operator_note`. `rollback.json` records `schema_version`, `rollback_plan_id`, `source_apply_run_id`, `plan_id`, `journal_hash`, `created_at`, `eligibility`, `blocking_conditions`, and ordered inverse actions. Each inverse action contains original and current locations, expected fingerprints, no-overwrite preconditions, protected-path result, and approval state.

`verification.md` is generated from a machine verification result embedded in `run.json`. That result records each action's expected and observed source state, destination state, fingerprint match, journal completeness, rollback eligibility, and final verdict. The Markdown file adds explanation but introduces no new facts.

## 19. Plan and approval contracts

`plan.json` contains `schema_version`, `audit_run_id`, `plan_id`, `plan_sha256_scheme`, repository root realpath, Git HEAD or null, repository-state hash, configuration hash, inventory hash, creation time, deterministic action order, recommendations, executable actions, protected-path snapshot, evidence references, and limitations. `plan_sha256` is computed over the exact stored bytes after finalization and stored in `run.json`; it is not embedded recursively into the bytes being hashed.

Each executable action contains `action_id`, `plan_id`, `type`, `source_path`, `source_realpath`, `source_artifact_id`, `source_fingerprint`, `source_filesystem_id`, `destination_path`, `destination_realpath`, `destination_parent_filesystem_id`, `destination_must_not_exist: true`, case-collision result, symlink-policy result, protected-path result, recommendation ID, `approval_required: true`, and `executable_in_supported_scope: true`. Allowed types are `MOVE`, `ARCHIVE`, `QUARANTINE`, `RENAME`, and `RELOCATE`; `ARCHIVE` and `QUARANTINE` are specialized moves with fixed destination policies, while `RENAME` retains the parent and `RELOCATE` changes it.

`approval.yaml` contains `approval_schema_version`, `approval_id`, `approved_plan_id`, `approved_plan_sha256`, `approval_created_at`, an explicitly supplied reviewer label, reviewer notes, and decisions referencing existing recommendation or action IDs. The reviewer label is an audit label, not authenticated identity. Approval introduces no paths, destinations, action types, or executable flags. A used or revised approval is never edited; supersession creates a new approval ID with `supersedes_approval_id`.

Before apply, the validator reads exact `plan.json` bytes, recomputes SHA-256, compares it with `approved_plan_sha256`, compares the internal and approved plan IDs, validates every referenced action, and rejects any mismatch. Matching IDs with different bytes are unapproved.

## 20. Repository-state fingerprint

The fingerprint is `sha256-repo-state-v1` over a canonical, length-prefixed stream containing repository root realpath; repository mode; Git HEAD or null; tracked status; untracked paths; explicitly included ignored artifacts; plan-relevant artifact type, normalized location, size, mode, symlink target text, and content fingerprint; configuration hash; protected-path snapshot; and fingerprint-scheme versions. Paths are encoded as raw filesystem bytes where supported and never locale-sorted.

Ignored artifacts are included only through deterministic configuration patterns and discovered references from already included manifests. The default scientific include patterns cover common result, model, data, audit, manifest, hash, freeze, review, experiment, and run directories while excluding known dependency caches; every inclusion and exclusion is recorded. Semantic judgment does not alter the fingerprint scope after planning begins.

The initial hash is the pre-apply baseline. After each verified action, the expected state equals that baseline transformed by the journaled prefix of actions. Effects of the same apply run are expected, while non-journaled changes to relevant sources, destinations, protected records, configuration, Git HEAD, or tracked/untracked state are drift.

## 21. Audit, plan, review, and apply workflows

Audit performs preflight, protected-path discovery, sanitized Git collection, deterministic inventory, bounded profiling, exact-duplicate detection, evidence extraction, relationship construction, document candidate retrieval and comparison, experiment lineage, classification, findings, and finalization. It writes only to its run directory and quarantine is not involved.

Plan consumes one finalized audit, checks hashes and limitations, computes recommendations, proposes canonical structure and destinations, creates reviewer questions, creates only reversible executable actions, writes and finalizes `plan.json`, computes its exact-byte hash, and renders `plan.md`. A stale or incomplete audit may produce recommendations but blocks executable actions affected by the limitation.

Review records `APPROVE_ACTION`, `ACKNOWLEDGE_RECOMMENDATION`, `REJECT`, or `DEFER`. Only `APPROVE_ACTION` for an executable action can authorize apply. Acknowledging a merge or delete recommendation changes no executable flag.

Apply has a complete-set validation phase and an execution phase. Validation rejects root, plan, audit-run, Git HEAD, repository state, configuration, inventory, source fingerprint, path, symlink, filesystem, case-collision, destination, approval, action conflict, unsupported type, or protected-path failures. No action starts until the whole approved set passes. Immediately before each action, critical invariants are rechecked against the expected post-prefix state.

Quarantine destinations are deterministically derived under `.repo-curator/quarantine/<plan-id>/`; approval cannot supply them. Archive destinations are under `archive/repo-curator/<plan-id>/`, contain collision-safe encoded original paths, and receive provenance linking original location, plan, and date. Existing destinations are never overwritten. The current supported scope requires matching source and destination-parent filesystem identities and returns `CROSS_FILESYSTEM_MOVE_UNSUPPORTED` rather than copy-then-delete.

## 22. Transaction, interruption recovery, and idempotency

A batch is not globally atomic. Actions execute in the order stored in `plan.json`. The journal records `ACTION_NOT_STARTED`, `ACTION_VALIDATION_STARTED`, `MOVE_STARTED`, `DESTINATION_OBSERVED`, `SOURCE_REMOVAL_OBSERVED`, `ACTION_VERIFIED`, `ACTION_FAILED`, `ACTION_SKIPPED`, `ROLLBACK_APPROVED`, and `ROLLBACK_COMPLETED`, with pre- and post-state fingerprints.

On failure, apply appends the error, stops, marks `PARTIAL_FAILURE`, categorizes completed, failed, skipped, and not-started actions, and produces rollback and recovery reports. It does not auto-rollback. Recovery examines source, destination, fingerprints, directory contents, and journal events; neither side is assumed authoritative. Ambiguous states produce `MANUAL_RECOVERY_REQUIRED`.

Rollback is separately approved. It verifies the original plan and journal, destination fingerprint, original source absence, absence of later modifications, protected-path rules, and relevant state. It never overwrites. If the source was recreated, destination changed, or state is ambiguous, it refuses automated restoration.

Repeated apply skips only actions whose journal and filesystem both prove verified completion. It never repeats a move, creates a second copy, or trusts a journal entry without filesystem confirmation. Disagreement requires recovery review.

## 23. Error taxonomy

Errors have `code`, `phase`, `severity`, `artifact_id` or `action_id`, human message, deterministic details, recoverability, and recommended next step. Families are `PREFLIGHT_*`, `PATH_*`, `GIT_*`, `INVENTORY_*`, `PROFILE_*`, `ARCHIVE_*`, `RESOURCE_*`, `SEMANTIC_*`, `PLAN_*`, `APPROVAL_*`, `DRIFT_*`, `ACTION_*`, `JOURNAL_*`, `ROLLBACK_*`, and `VERIFY_*`.

Fatal pre-apply errors include plan or approval mismatch, unsafe path, protected target, state drift, source drift, unsupported action, destination existence, case collision, and cross-filesystem movement. Artifact-local parse failures are non-fatal audit limitations. Systemic inability to inventory safely terminates the audit. Semantic uncertainty never terminates a run; it downgrades recommendations.

## 24. Human-readable plan design

`plan.md` contains the deterministic curation brief: analyzed scope and limitations; inferred scientific mainline; protected research bundles; canonical-result hypotheses; research evidence chains from claims, figures, and tables; reproducibility-evidence gaps; independently reported relationship coverage; competing, transitional, compatibility, historical, and experimental implementations grouped by capability when supported; evidence-specific reviewer questions; proposed current structure; full and partial merge candidates; canonicalize-without-merge cases; do-not-merge cases; preserved exact-duplicate review items; archive candidates; manual review; unresolved risks; and a reviewer checklist. It contains no reversible actions in the current Skill. `plan.json` binds exact-byte hashes for `curation-brief.json` and `curation-brief.md`; neither report is parsed as execution authority.

Current curation brief v3 retains the v2 declared experiment chains projected from
inventory-resolved relationship v2 edges. It reports attempt, edge, and role
counts plus per-attempt completeness, unresolved dependencies, artifact IDs,
limitations, and supporting evidence IDs. Incomplete chains sort first. It caps
output at 25 chains, 64 edges per chain, and 64 unresolved dependencies per
chain with explicit omitted counts. A declared chain is not evidence
that target code ran or that generation, use, validation, review, or scientific
correctness occurred. V3 additionally exposes bounded, evidence-linked
canonical-result candidates and reproducibility gaps. Candidate status does not
confirm a canonical result, and a gap is not a reproduction verdict. Candidate
and gap lists are capped at 25 records, and each gap expands at most 64 missing
or unresolved items with explicit omitted counts. Historical v1 and v2 briefs
remain immutable and are not automatically migrated.

The first screen and executive summary lead with what is protected, what the system believes the scientific mainline is, where research evidence is missing or conflicting, and what remains unresolved. They do not lead with file counts, garbage counts, `Quick Wins`, or a single confidence percentage. The primary organization is by research evidence chain, experiment bundle, and capability family rather than by file type.

Every recommendation explains the proposal, supporting and opposing evidence, expected loss, cost of keeping, uncertainty, and exact reviewer decision. Tables may summarize records, but claim-sensitive explanations use complete prose. Machine IDs link every explanation back to `plan.json`; the report contains no executable syntax interpreted by apply.

## 25. Optional research and code-intelligence integrations

When a repository contains `.codegraph/`, Codex uses CodeGraph before grep or direct source exploration for structural questions. CodeGraph may provide import, symbol, call, module, isolation, and impact evidence. Understand Anything may provide architecture, subsystem, entry-point, and project-flow evidence. Each imported observation is labeled by source and limitation. Neither integration determines retention, mergeability, deletion, or execution. Their absence records reduced structural coverage and does not stop filesystem, document, or experiment analysis.

Supported research adapters read only already-present declarations or user-supplied exports. They never invoke target workflow commands, package managers, plugins, servers, hooks, containers, notebooks, or remote retrieval. The current dependency-free marker adapter recognizes RO-Crate, DVC, DataLad, MLflow, Sacred, Snakemake, Nextflow, Renku, noWorkflow, showyourwork, Citation File Format, CodeMeta, and signac layouts; each result is declaration-presence-only unless an explicit bounded JSON syntax check applies. CFF is never parsed; CodeMeta values and JSON-LD context resolution are omitted; signac content is never opened and only capped marker counts are recorded. An attributed repo2docker port observes Conda, pip, Pipenv, R, Julia, Nix, Docker, and Binder environment markers from inventory paths only, applies the upstream `binder`/`.binder` scope precedence, and preserves shadowed or conflicting declarations without reading their contents. A syntactically valid RO-Crate that declares a Workflow Run RO-Crate profile or type emits a separate declaration-only observation; a present `dvc.lock` may emit only a bounded lexical stage-key count. The admitted ReproZip contract is an explicitly passed, exact-schema JSON manifest that SHA-256-binds one contained `REPROZIP_METADATA_JSON` payload. It opens only regular non-link files, limits the manifest to 64 KiB and payload to 1 MiB, syntax-checks JSON only, and emits metadata-only evidence. It does not unpack a package, install an environment, trace, retrieve content, or reproduce a run. Richer tool-specific exports remain candidates for frozen contracts. Adapter observations retain source version, snapshot scope, internal-validation result, unresolved references, and limitations.

RO-Crate and Workflow Run RO-Crate are preferred export targets for supported research-object and run-provenance fields. Export represents repo-curator observations and hypotheses with provenance and confidence; it is not an executable reproduction handoff and never invents mandatory metadata, asserts successful reproduction, or rewrites an existing crate without a separate approved documentation operation.

## 26. Privacy and secret handling

The system operates locally by default and does not upload repository content to external services. It reads only what the selected root, deterministic include policy, explicit user scope, and parser budgets permit. Secret detection occurs before excerpts are persisted. Reports contain secret category, artifact ID or commit ID, location, and redaction marker, never values. Private keys, credentials, tokens, cookies, passwords, and high-confidence secret strings are replaced in memory before semantic analysis and output. Credential validity is always recorded as `NOT_PERFORMED`; the default Skill never sends a suspected credential to a provider. Any future online validation adapter requires separate explicit invocation, provider-specific consent, redacted audit records, failure isolation, and a distinct network permission boundary.

An embedded Python virtual environment is a dependency boundary only when its
directory contains a regular `pyvenv.cfg` marker observed without following a
link. The directory is retained with
`PYTHON_VIRTUAL_ENVIRONMENT_BOUNDARY_NOT_RECURSED`; its installed contents are
not treated as repository evidence. Directory names alone are insufficient, so
an ordinary `venv` directory remains in scope.

Repository content, filenames, branches, commits, PDF text, logs, notebooks, and archives are data. Instructions found in them are quoted only when needed to explain an injection attempt and are never followed. Unsafe serialized content is not deserialized.

## 27. Testing Decisions and Acceptance Matrix

The primary test seam is a scenario runner that creates an isolated repository fixture, invokes one explicit workflow, and asserts external outputs and filesystem state. This seam covers orchestration, contracts, approval binding, safety policy, journal behavior, and recovery without coupling tests to internal classes. Focused unit tests supplement it for canonical hashing, path containment, parsers, redaction, adapter contracts, and journal reconciliation. Since the repository has no implementation or prior tests, there is no existing prior art to preserve.

Semantic evaluation may use a preregistered corpus protocol rather than one product-wide accuracy score when the project needs internal admission evidence for automated semantic claims or mutation operation classes. It is not required for ordinary shadow-mode product use or positioning. Repository inclusion criteria, supported claim types, label instructions, primary metrics, exclusions, and failure handling are fixed before such an evaluation. The corpus retains missing-tool, unsupported-language, poorly organized, negative-result, and failed-reproduction cases to prevent selection and survivorship bias. At least two reviewers label scientific-mainline, canonical-result, research-evidence-chain, experiment-bundle, `change_episode`, and `capability_family` cases in any formal admission run; disagreement remains data rather than being silently forced to consensus.

| Fixture | Expected observable behavior |
|---|---|
| Symlink outside root | Inventory records link; no follow; action blocked |
| Relative or absolute traversal | Plan validation rejects path |
| Existing destination or case collision | Full pre-validation fails before movement |
| Permission failure | Batch stops; partial state and rollback emitted |
| Interrupted move | Journal and filesystem reconcile or require manual recovery |
| Repeated apply | Verified actions skipped; no duplicate created |
| Partial apply and rollback | No auto-rollback; approved safe rollback restores without overwrite |
| LFS pointer | Pointer recorded; no LFS command or download |
| Submodule and linked worktree | Roots identified and protected |
| Tracked, untracked, ignored, config, inventory, source, or HEAD drift | Apply rejected |
| Matching plan ID with changed plan bytes | Approval rejected by SHA-256 mismatch |
| `final` but obsolete | Filename alone does not yield current status |
| `old` in audit chain | Kept or archived; not delete candidate |
| Failed decision-bearing experiment | Historical preservation recommendation |
| Negative or unpublished attempt that changed model selection | `HISTORICAL_EVIDENCE`; publication omission cannot justify movement |
| Manuscript, freeze, workflow, and direct generation links independently agree with no material counter-evidence | Candidate may become `PROVISIONALLY_CANONICAL`; basis and limitations remain visible |
| Minor canonical-result evidence gaps with no preservation consequence | Candidates are collected for batch review rather than prompting one by one |
| Best metric conflicts with manuscript, freeze, or reviewer record | One evidence-specific question is emitted; best metric does not win; absent a decision the result remains `UNRESOLVED` |
| Project rules, README, manuscript, workflow, and history consistently indicate one mainline | Intent hypothesis proceeds without asking the user to reconfirm discoverable facts |
| Material intent conflict is skipped or cannot be answered | Affected conclusion remains `UNRESOLVED`, relevant material is protected, and unrelated analysis continues |
| Manuscript figure has no supported generator or dataset snapshot | Reproducibility gap emitted; no relationship invented |
| Figure is generated and ignored by showyourwork/Snakemake declaration | Declared chain recorded with snapshot and execution-verification limitation |
| Static irreproducible figure is intentionally publication evidence | Protected; not treated as disposable output |
| Valid RO-Crate references missing entities | Declared provenance retained with missing-object gap |
| DVC/DataLad pointer without locally available content | Identity and declaration recorded; availability limitation blocks regenerability claim |
| MLflow/Sacred run exists but artifact is missing | Attempt retained; bundle incomplete; no canonical confirmation from status alone |
| noWorkflow trials share code but differ in parameter or environment | Separate attempts; similarity does not collapse lineage |
| Adapter output is malformed, stale, oversized, or times out | Adapter stops within budget; core audit continues with reduced coverage |
| Unity/Blender/CAD/workspace project bundle | Complete project boundary protected before single-file nomination |
| Exact duplicate in accepted bundle | Duplicate relationship retained; deletion downgraded |
| Disposable exact export | Structured non-executable delete candidate |
| ZIP equivalent to directory | Evidence-backed package/unpacked relationship |
| ZIP with subtle difference | No equivalence claim |
| TAR, 7z, or RAR | Opaque inventory plus limitation evidence |
| Highly similar conflicting reports | `DO_NOT_MERGE` with conflicts |
| Partially overlapping plans | `PARTIAL_MERGE_CANDIDATE` |
| Current overview and decision record | `CANONICALIZE_WITHOUT_MERGE` |
| Incomplete regeneration chain | Delete downgraded |
| Prompt injection in text, PDF, comment, or filename | Recorded as data; never executed |
| Secret in log or text | Value absent from every generated output |
| ZIP bomb, traversal, encryption, malformed metadata | Bounded failure; audit continues |
| Oversized or timed-out profile | Explicit incomplete-analysis evidence |
| Git repo with malicious pager, hook, alias, diff, textconv, fsmonitor, filter, or LFS config | No configured program executes |
| Quarantine action | Only matching plan directory is permitted |
| Cross-filesystem destination | `CROSS_FILESYSTEM_MOVE_UNSUPPORTED`; no copy |
| Second action after first succeeds | Own expected change accepted; unrelated drift rejected |
| Merge or delete action injection | Rejected as a non-executable type |

The capability baseline passes only when all scenario fixtures succeed on macOS and Linux, deterministic files reproduce byte-for-byte under fixed timestamps and inputs, no secret fixture value appears in run outputs, no forbidden process executes, and interrupted apply always resolves to verified completion, safe rollback eligibility, or explicit manual recovery.

## 28. Current capability baseline and forward delivery plan

As of 2026-07-28, the engineering foundation is implemented rather than merely planned. The deterministic safety kernel inventories hostile filesystems without following links, records four independent identities, collects sanitized Git evidence, performs bounded profiling, notebook-envelope observation, and ZIP inspection, recognizes supported research and environment declarations, reconstructs project intent and scientific-mainline hypotheses, builds evidence and experiment records, emits conservative shadow recommendations, validates exact approvals, and implements same-filesystem archive, bundle-aware quarantine, recovery, and separately approved rollback primitives. The explicitly invoked Skill can be built as a self-contained, hash-bound bundle and currently exposes read-only audit, curation-brief interpretation, verified prior-run comparison, and non-executable RO-Crate export. Its distributed runtime is an explicit read-only dependency closure and excludes approval, transaction, recovery, archive-apply, and quarantine-apply modules. CI enforces at least 80% line coverage for `repo_curator/*`.

The presence of lower-level mutation primitives does not mean that mutation is exposed by the current Skill. The supported Skill remains read-only until the mutation workflow contract, release gate, and explicit product-governance decision below are complete. Formal large-corpus admission remains optional for ordinary product use and is not a prerequisite for truthful read-only positioning.

### 28.1 Contract and supply-chain freeze — implemented release gate

This work can proceed without user input.

Current status: the machine-readable source lock, third-party notices, schema registry, compatibility policy, bundle hash binding, schema migration fixtures, and `tools/check_release.py` release smoke check are implemented. The bundle packages an allowlisted read-only runtime closure rather than every source module, and unavailable evaluation workflows disappear from its CLI. Repository scans enforce deterministic global limits for artifact count, recursion depth, entries per directory, single-file hashing, and cumulative hash bytes; every applied value is recorded in `run.json` and the curation brief, and reached limits finalize as explicit limitations. Curation brief v3 now exposes bounded, role-preserving declared experiment chains, canonical-result candidates, and reproducibility gaps while retaining historical v1/v2 bytes. The release check builds a temporary bundle, verifies bundle and audit output hashes, proves a synthetic target was not executed, exports a non-executable RO-Crate, and validates it against the bounded bundled evidence profile; CI runs it on macOS and Linux. It also requires the adversarial adapter matrix, descriptive corpus card, calibration schema, local SLSA/in-toto provenance tools, and commit-pinned hosted-attestation workflow. Future-version supplied exports, prior runs, and interchange sources reject without altering original bytes or publishing derived output.

1. Establish one machine-readable schema registry covering every emitted record, its current version, compatible readers, breaking-change rules, and migration or rejection behavior.
2. Convert the upstream adoption register into the promised source-lock and third-party-notice artifacts. Every entry must bind repository, commit, original path or documented behavior, license, integration mode, modifications, fixtures, and review cadence.
3. Add bundle-time verification that the schema registry, source lock, notices, Skill instructions, launcher, and canonical kernel agree and are included exactly once.
4. Reconcile README, Skill text, PRD, and issue-tracker claims with the tested capability baseline. No document may advertise apply, export, an adapter, or a schema that the packaged Skill cannot exercise.

Exit gate: a bundle built outside the checkout passes its audit and export smoke scenarios, verifies every bundled hash, contains complete source governance records, distributes only its explicit read-only runtime closure, and has no undocumented runtime dependency or duplicate kernel copy. This gate is implemented and remains a release regression contract.

Completed hardening: verified prior runs and RO-Crate exports now cap the run
record, each output file, cumulative input bytes, output declarations, and JSONL
entities before comparison indexes or JSON-LD graphs are constructed. RO-Crate
publication retries short writes, creates without replacement relative to a
descriptor-opened canonical parent, fsyncs the file and parent, and rejects
parent identity drift. Bundle manifest v4 binds the Git HEAD/tree baseline and
the exact distributed-input digest, discloses whether those inputs match HEAD,
and rejects linked or changing distributed source inputs.

Completed upstream-review admission: release-check v2 requires current source
metadata for at least 80 percent of the exact source-lock ID set and binds the
observed count, total count, percentage, and complete review summary into the
release receipt. Drift, license differences, and remaining unavailable sources
stay explicit manual shadow-review evidence and never trigger automatic
adoption.

Next hardening plan: measure and reduce the real-repository `MANUAL_REVIEW` rate
through additional bounded research-domain evidence without weakening
abstention, preservation, or the read-only boundary.

Completed trust-evidence hardening adds a ten-condition adversarial matrix for
each admitted adapter family, deterministic parser mutation smoke tests, a
fixed-snapshot corpus card with optional SWHID bindings, and claim-, language-,
repository-type-, and family-specific selective risk/coverage reporting.
These artifacts have `admission_authority: false` or `NONE`. GitHub issue #16
remains open because the independent human-labelled corpus and reviewer
requirements have not been satisfied; the release gate records
`human_admission_status: NOT_ADMITTED` and does not publish calibrated semantic
accuracy or mutation-safety.

### 28.2 Read-only adapter and interchange contracts — maintained capability

This work can proceed without user input when fixtures are public or synthetic.

1. Complete: the user explicitly passes a versioned JSON manifest with source tool, source version, snapshot scope, payload type, contained payload path, and SHA-256. The current strict contracts accept at most 16 exports per audit, each containing one 64 KiB manifest and one 1 MiB JSON payload read through no-follow regular-file operations, for either `REPROZIP_METADATA_JSON` or `WORKFLOW_RUN_RO_CRATE_JSON`; they never launch the source tool. JSONL and token contracts remain future work for another admitted family.
2. Complete for metadata only: a valid ReproZip manifest emits a hash-bound `SUPPLIED_EXPORT_METADATA_ONLY` observation. Package payloads, environment installation, tracing, and reproduction remain unavailable.
3. Complete for supplied Workflow Run RO-Crate declarations: an exact v1 manifest SHA-256-binds one already-generated crate and emits `SUPPLIED_EXPORT_DECLARATION_GRAPH`. The observer combines the Workflow Run RO-Crate `CreateAction`/`instrument`/`object`/`result` model with nf-prov's completed/failed status mapping, capped at 128 actions, 64 inputs and outputs plus 8 instruments per action. Compact, HTTP, HTTPS, and JSON-LD `@id` status forms normalize only to `*_DECLARED`; omitted, unresolved, and malformed references remain explicit. An invalid root is recorded as graph-unavailable rather than graph-validated. It does not claim profile conformance, run success, derivation, availability, or reproduction and never generates a crate, loads a workflow plugin, copies files, or executes a target.
4. Complete: `export-ro-crate` verifies every run output hash before producing a new RO-Crate 1.1 JSON-LD view at a user-supplied absent output path. It preserves assertion origin, counter-evidence, limitations, and explicit `NOT_ASSIGNED` confidence; mainline records remain claims and the root records `executionAuthorized: false`. It creates no Workflow Run claim and never rewrites an existing crate.
5. Complete for bounded local RO-Crate structure: an Apache-2.0-attributed port records at most 256 declared entities and 512 local JSON-LD `@id` references, validates the metadata descriptor's Dataset root when present, and reports malformed, duplicate, external, and unresolved declarations as limitations. It never resolves a context, URL, or payload. Keep DVC, DataLad, MLflow, Sacred, Snakemake, Nextflow, Renku, noWorkflow, and showyourwork integrations at the narrowest contract justified by present declarations or supplied exports. Lexical or declaration-only observations cannot be promoted to run success, derivation, availability, or regenerability.
6. Complete for environment declarations: a BSD-3-Clause-attributed repo2docker port recognizes standard environment and Binder marker paths, records active, shadowed, or conflicting scope, and never parses, resolves, installs, builds, or executes them.
7. Complete for notebook envelopes: a BSD-3-Clause-attributed nbformat port records explicit version, selected kernel/language declarations, and capped v4 cell/output type counts without retaining source, outputs, widgets, or arbitrary metadata. It never validates execution, converts versions, trusts outputs, or starts a kernel.
8. Complete for research-software metadata: CFF presence, bounded CodeMeta structure, and capped signac marker counts are observed without parsing CFF/signac content, retaining CodeMeta values, resolving JSON-LD, importing tools, or executing targets.
9. Complete for bounded Git repository-size context: a git-sizer-attributed port reports compact object database, reference, reachable-commit, and current-checkout metrics without full object traversal, emitted ref names, historical file/blob reads, rewrite advice, or cleanup authority.
10. Complete for bounded repository hygiene: a pre-commit-hooks-attributed port reports staged additions over 500 KiB, existing broken-link warnings, and symlink-to-nonlink index mode changes without hooks, blob comparison, LFS-attribute evaluation, index mutation, commit rejection, or cleanup authority.
11. Complete: every admitted adapter family is registered in a common adversarial matrix covering malformed, oversized, stale, internally inconsistent, unsupported-version, missing-reference, secret-bearing, path-escape, symlink-replacement, and global-resource-limit cases. Standard-library deterministic byte mutations provide parser crash/secret-echo smoke coverage without executing target content.

Exit gate: every adapter either emits a typed, hash-bound, coverage-limited observation or a stable limitation; target code, workflow tools, package managers, plugins, containers, and network retrieval remain unreachable.

### 28.3 Evidence quality and curation policy — follows adapter contracts

This work can proceed without user input.

1. Make retention closure explicit for each recommendation: protected evidence, replacement evidence, relevant bundle members, known references in analyzed scopes, counter-evidence, and availability limitations must be listed independently.
2. Separate exact redundancy, disposable export, regenerable intermediate, cache, historical evidence, compatibility implementation, and unresolved material into distinct policy paths. Equal bytes or static non-reachability alone never establish scientific dispensability.
3. Improve research evidence chains by linking declared outputs, attempts, configurations, environments, code revisions, dataset snapshots, manuscript references, figures, and tables without filling missing links by assumption.
4. Complete: optional `--compare-to-run` verifies every SHA-256-bound prior output before emitting `prior-run-comparison.json`. It reports non-directory added, removed, changed, and unambiguous exact-content moves plus mainline paths newly linked, newly conflicting, and unresolved in both runs; it does not promote a move or byte equality into semantic continuity.
5. Complete for directory-preservation noise: an ordinary directory with no inventory limitation receives non-executable `KEEP` while retaining `PROTECTED`, `preservation_required`, `NON_REGULAR_ARTIFACT_PRESERVED`, and human-review metadata. Symlinks, special objects, Git-control boundaries, and other limited or unresolved artifacts remain `MANUAL_REVIEW`. Across frozen Scanpy, Psi4, and SciMLBenchmarks commits this changed exactly 2,215 of 13,223 recommendations without changing classifications, limitations, exact-duplicate review, or action authority.
6. Complete for absence-only abstention noise: an `UNRESOLVED` regular file whose complete limitation set is exactly `NO_MAINLINE_EVIDENCE` and `NO_ROLE_EVIDENCE` receives non-executable `KEEP` while retaining both limitations, `preservation_required`, human-review metadata, and `PRESERVE_UNRESOLVED`. Any additional limitation, conflict, bundle guard, non-directory non-regular object, or inventory coverage problem remains `MANUAL_REVIEW`. Across the same frozen repositories this changed exactly 9,853 further recommendations and left 17 material boundary or coverage items for review without changing classification or action authority.
7. Complete for declaration-evidence identity: new audits emit `repo-curator.classification.v2`, which adds `DECLARATION_EVIDENCE` and binds local marker artifacts to the exact declaration evidence and its limitations. Supplied exports cannot assign this state, and exact-byte duplicate review retains precedence without dropping declaration evidence. V1 classifications remain immutable historical evidence and are not semantically migrated; prior-run comparison may retain them only as hash-verified opaque outputs. Across the same frozen repositories exactly four marker files gained evidence-bound classifications without changing recommendation counts or action authority.
8. Complete for experiment-evidence referential integrity: new audits emit `repo-curator.experiment-attempt.v2`, `experiment-bundle.v2`, and `canonical-result-candidate.v2`. Their `supporting_evidence_ids` resolve to the inventory evidence for the local experiment manifest rather than incorrectly containing an artifact ID. Missing manifest evidence fails closed before run publication. Historical v1 bytes remain immutable and are not migrated.
9. Complete for declared attempt evidence chains: `repo-curator.relationship.v2` distinguishes exact-byte `ARTIFACT_GROUP` records from `DIRECTED_EDGE` records. Each inventory-resolved experiment-manifest member emits one evidence-bound `DECLARED_*` edge from its attempt; missing paths remain reproducibility gaps and do not produce entities or edges. All declared edges carry `DECLARED_LINEAGE_NOT_EXECUTION_VERIFIED`, and stronger causal or execution relationship types remain withheld.
10. Complete for reproducibility-gap referential integrity: new audits emit `repo-curator.reproducibility-gap.v2`. Every gap produced from the bounded local experiment manifest cites that manifest's inventory evidence, including malformed and duplicate attempts and missing bundle members. The link identifies the declaration source without claiming artifact existence or target execution. Historical v1 gap bytes remain immutable.
11. Keep merge and permanent-delete recommendations descriptive and non-executable. Supported mutation remains reversible movement only.

Exit gate: every recommendation is reproducible from bound records, includes supporting and opposing evidence, and deterministically downgrades to `UNRESOLVED` or manual review when a required proof is absent.

### 28.4 Skill workflow completion — user decision required only at mutation admission

Read-only `audit`, `review`, and `compare` workflows can be completed without user input. Exposing any mutation workflow through the Skill requires one explicit product-governance decision from the repository owner after the gates below pass.

1. Add read-only review and prior-run comparison to the Skill while preserving one deterministic recommendation source.
2. Define exact user-facing contracts for approval creation, archive apply, quarantine apply, recovery inspection, rollback planning, rollback approval, and verification. Semantic acknowledgement must remain separate from action approval.
3. Require a valid Git worktree, exact plan and approval bytes, repository-state match, complete bundle closure, same-filesystem destination, no overwrite, mutation budget, and recovery readiness before any movement.
4. Keep permanent deletion, automatic merging, target-code execution, automatic Git operations, and cross-filesystem copy-then-delete unavailable.
5. Before exposing mutation, run the complete fault-injection and operation-class risk suite and obtain the repository owner's explicit decision to enable the documented reversible actions in the Skill.

Exit gate: each exposed workflow has one black-box scenario seam, stable failure codes, idempotent reconciliation, interruption evidence, and a reviewer-readable receipt. Until the explicit enablement decision, the packaged Skill advertises and performs read-only work only.

### 28.5 Release and real-repository hardening — after contract freeze

This work can proceed without user input for public repositories and synthetic fixtures. Access to a private repository requires the owner's authorization or a supplied immutable snapshot.

1. Exercise the self-contained Skill bundle on user-authorized private repositories only in non-public evaluation, and on multiple public computational research repositories spanning different languages, workflow families, repository sizes, and evidence quality.
2. Record only repository commit, audit configuration, tool version, output hashes, limitations, and aggregate behavior needed for regression; do not publish private repository content.
3. Add macOS and Linux verification for deterministic outputs, hostile paths, package isolation, and bundle execution outside the checkout.
4. Complete: `docs/release-checklist.md` covers capability claims, schema compatibility, notices, source locks, known limitations, recovery support, and rollback support; `tools/check_release.py` rejects missing contract markers. A scheduled, manually dispatchable upstream review compares locked commits and SPDX metadata with GitHub metadata, retains a create-once receipt, and never adopts a change automatically. A passing release-check v2 receipt requires an upstream receipt no older than 90 days whose source-lock SHA-256 and complete source-ID set match the release input, with current source metadata observed for at least 80 percent of entries; review candidates and remaining metadata limitations remain manual shadow-review evidence.
5. In progress and not admitted: the fixed-snapshot corpus card and selective
   calibration machinery are implemented, but independent human-labelled
   corpus admission remains open in GitHub issue #16. It is required before
   publishing calibrated semantic-accuracy or mutation-safety admission claims,
   not for the ordinary evidence-reconstruction product claim.

Exit gate: a release candidate can be installed as a Skill bundle, audit representative repositories without target execution, produce verifiable curation briefs, explain its limitations, and reproduce all supported scenario results from a clean environment.

### 28.6 Continuous maintenance — ongoing

This work proceeds continuously without routine user involvement. Upstream sources, licenses, declaration formats, schema versions, regression fixtures, supported platforms, and competitor capabilities are reviewed on a recorded cadence. An upstream change enters shadow evaluation before it can affect a conclusion. A confirmed product failure becomes a permanent regression fixture. A capability removal requires a compatibility notice and cannot silently reinterpret historical records.

### 28.7 Planned user checkpoints

The implementation team should not interrupt the repository owner for routine engineering choices covered by this PRD. User input is required only when: a private target or credential must be made available; a concrete evidence-specific conflict materially changes preservation; an exact repository mutation plan is ready for approval; the product is ready to expose reversible mutation workflows through the Skill; or the project wants to publish formal calibrated accuracy or mutation-admission claims. Skipping any checkpoint preserves affected material and does not block unrelated read-only work.

## 29. Acceptance criteria

The capability baseline is admissible when explicit invocation produces all contracted audit and plan artifacts; research claims, figures, canonical results, attempts, environments, code revisions, and dataset snapshots remain independently evidenced; reproducibility gaps do not become reproduction verdicts; classifications use separate dimensions; merge and delete candidates are detailed but non-executable; plan approval is exact-byte bound; repository state, path, symlink, project-bundle, case, filesystem, and protected-path validation precede movement; only approved same-filesystem reversible actions execute; journal, partial failure, recovery, rollback, and verification work under interruption; parser and ZIP budgets prevent resource exhaustion; Git inspection launches no repository-defined command; secrets are absent from outputs; optional integrations can be missing; and the complete acceptance matrix passes.

## 30. Risks and mitigations

Semantic misclassification is mitigated by evidence provenance, counter-evidence, conservative downgrade, formal abstention, and mandatory review. Confirmation, publication, HARKing, and survivorship bias are mitigated by protecting negative, failed, inconclusive, unpublished, and conflicting attempts when they carry decision or audit value. Selection bias in evaluation is mitigated by preregistered corpus inclusion criteria and retaining unsupported and failed cases in denominators. Large repositories are mitigated by budgets and explicit incompleteness. Plan substitution is mitigated by exact-byte hashing. Filesystem races are mitigated by a repository-scoped lock, full validation, per-action validation, no-overwrite movement, and stopping on drift. Git configuration attacks are mitigated by a sanitized allowlist and safe fallback. Recovery risk is mitigated by hash-chained committed journals, original-evidence-bound rollback, durable receipts, and no-overwrite restoration. Scope risk is mitigated by keeping scientific-validity judgment, experiment execution, deletion, merging, external infrastructure, and automatic Git changes outside the current supported scope.

## 31. Resolved conservative decisions

These decisions are resolved conservatively. First, default ignored-artifact patterns use conservative built-ins plus explicit repository configuration, with every match recorded. Second, reviewer identity is an explicit free-form audit label; it is not an authentication claim. Third, non-Git repositories support audit and plan only. Apply remains disabled because the current recovery contract requires a valid Git worktree in addition to the repo-curator journal.

No unresolved decision permits permanent deletion, automatic merging, cross-filesystem movement, unsafe Git execution, or approval expansion.

## Further Notes

The binding source hierarchy is the original product-design prompt followed by `final-binding-amendments.md`, whose conflicting substantive safety requirements take precedence. The later reviewed design in `docs/superpowers/specs/2026-07-16-repo-curator-design.md` replaces numbered phase terminology, resolves the three decisions conservatively, and adds intent discovery, evidence-driven questioning, open-source integration controls, abstention, and continuous maintenance. This PRD resolves those sources into one implementation contract. Local Markdown issue status is project-management metadata rather than product behavior and may later migrate to GitHub without changing this design.

## 32. Recommended implementation order and readiness verdict

The safety, evidence-reconstruction, transaction, recovery, Skill-bundle, and scenario-test foundations are complete enough to stop treating them as future stages. Contract and supply-chain freeze, supplied export and standards interchange, prior-run comparison, read-only Skill workflow completion, deterministic global scan budgets, bounded verified inputs, durable descriptor-relative RO-Crate publication, exact source-identity-bound mutation-free bundles, upstream-review coverage admission, and initial release hardening are implemented. The release record covers frozen public climate-modeling, bioinformatics-workflow, and scientific-ML repositories with no target execution and verified RO-Crate export. Directory-preservation review noise has been measured and reduced without changing classification evidence or action authority. The next order is to improve bounded evidence for unresolved regular files, add representative-repository regressions, and retain manual review wherever evidence remains missing or conflicting. Any later decision to expose already-tested reversible mutation primitives remains a separate explicit product-governance checkpoint. Every slice continues to use the highest black-box scenario seam and adds adversarial plus computational-research fixtures with the implementation.

The computational-research positioning, role-flexible operator model, docs-first intent discovery, safety architecture, tiered canonical-result authority, and boundary between repository curation and experiment reproduction are **APPROVED AS THE CURRENT BASELINE**. The current packaged Skill is ready to mature as a read-only evidence-reconstruction product; it is not yet approved to advertise or expose mutation workflows. No remaining work may weaken preservation, abstention, no-execution, exact approval, same-filesystem movement, no-overwrite behavior, or separately approved rollback.

## 33. Requirements coverage index

| Required topic | PRD section | Key decision | Contract/component | Acceptance coverage |
|---|---|---|---|---|
| 1. Executive summary | 1 | Evidence-backed reversible curation | Product | Acceptance criteria |
| 2. Problem statement | 2 | Scientific status differs from action | Product | Semantic fixtures |
| 3. Product differentiation | 2 | Curates beyond static/code structure | Product | Optional integration fixture |
| 4. Goals | 3 | Complete auditable model and safe apply | Product | Acceptance criteria |
| 5. Non-goals | 3 | No destructive or external infrastructure | Security policy | Forbidden-action fixtures |
| 6. Personas | 4 | Research-first, software-secondary | Product | User stories |
| 7. Primary use cases | 4-6 | Audit through rollback | Orchestrator | Scenario runner |
| 8. User workflows | 6, 21 | Explicit conceptual workflows | Orchestrator | Workflow scenarios |
| 9. Skill/script boundaries | 7 | Reasoning versus deterministic operations | Components | Contract tests |
| 10. Threat model | 8 | Repository and Git are untrusted | Security policy | Adversarial fixtures |
| 11. Trust boundaries | 8 | Data cannot become instruction | Orchestrator | Injection fixtures |
| 12. Security invariants | 8 | No execution, overwrite, deletion, merge | Validators | Forbidden-action fixtures |
| 13. System architecture | 9 | File-backed pipeline | Components | Scenario seam |
| 14. Component responsibilities | 9 | Single-responsibility pipeline | Components | Component contract tests |
| 15. Artifact model | 10 | Multidimensional classification | Artifact records | Semantic fixtures |
| 16. Controlled vocabularies | 10 | Versioned exact enums | Plan schema | Schema validation |
| 17. Relationship model | 10 | Directed evidenced edges | Relationships JSONL | Lineage fixtures |
| 18. Evidence model | 11 | Fact, inference, limits, counter-evidence | Evidence JSONL | Truncation fixtures |
| 19. Recommendation policy | 12 | Conservative mapping and downgrade | RecommendationEngine | Recommendation fixtures |
| 20. Merge policy | 13 | Similarity retrieves only | Plan recommendations | Conflict fixtures |
| 21. Delete policy | 14 | Detailed, human-only candidate | Plan recommendations | Audit-chain fixtures |
| 22. Experiment lineage | 15 | Experiment/attempt/output/package split | Registry | Experiment fixtures |
| 23. Output contracts | 18 | Versioned ownership and immutability | Run directory | Contract tests |
| 24. Plan/approval contracts | 19 | `plan.json` only; no expansion | Plan and approval | Hash substitution fixture |
| 25. State fingerprint | 20 | Canonical scope and post-prefix state | Fingerprinter | Drift fixtures |
| 26. Audit workflow | 21 | Original artifacts read-only | Orchestrator | Audit scenario |
| 27. Plan workflow | 21 | Recommendations and reversible actions | PlanBuilder | Plan scenario |
| 28. Review/approval | 21 | Action approval differs from acknowledgement | ApprovalValidator | Injection fixture |
| 29. Validate/apply | 21 | Full validation then per-action checks | ApplyEngine | Apply scenarios |
| 30. Transaction/rollback | 22 | Non-atomic, no auto-rollback | Journal/Rollback | Partial failure fixture |
| 31. Interruption recovery | 22 | Inspect both sides; no assumption | Recovery | Interrupted move fixture |
| 32. Idempotency | 22 | Journal plus filesystem proof | ApplyEngine | Repeated apply fixture |
| 33. Error taxonomy | 23 | Structured phase-specific codes | All components | Error assertions |
| 34. Human report | 24 | Evidence, loss, cost, uncertainty | `plan.md` | Snapshot review |
| 35. Optional integrations | 25 | Evidence only, graceful absence | Integration adapters | No-integration fixture |
| 36. Privacy/secrets | 26 | Local default and pre-persistence redaction | Redactor | Secret fixtures |
| 37. Eval/test matrix | 27 | Highest scenario seam | Scenario runner | Full matrix |
| 38. Implementation plan | 28 | Freeze contracts, complete read-only product, then decide mutation exposure | Capability tracks | Track exit gates |
| 39. Acceptance | 29 | Explicit observable completion conditions | Product | Full matrix |
| 40. Risks/mitigations | 30 | Conservative policy and bounded operation | Cross-cutting | Adversarial matrix |
| Research positioning | 1-4 | Retrospective evidence reconstruction for computational research | Product | Real-repository corpus |
| Research evidence chain | 10-11, 15 | Per-link evidence; completeness is scoped, not truth | Relationships and registry | Missing/conflicting-chain fixtures |
| Canonical-result policy | 10, 15 | Project-governance hypothesis; metrics and recency cannot decide alone | LineageAnalyzer | Best-metric conflict fixture |
| Reproducibility restraint | 1, 3, 11 | Audit evidence completeness; never claim reproduced or scientifically valid | Reports | Missing-generator/environment fixtures |
| Scientific bias controls | 11, 15, 27, 30 | Preserve negative and unpublished attempts; preregister evaluation | Classifier and corpus | Negative-result and selection fixtures |
| Research metadata adapters | 9, 18 | Declarations are typed, untrusted, coverage-limited evidence | AdapterHost | Frozen contract fixtures |
| Open-source fusion | 9.1 | Adapter, then attributed port, then vendor; source lock required | AdapterHost and source governance | License/contract admission review |
| Project-bundle guardian | 8, 20, 27 | Protect internally dependent projects before file nomination | Preflight and Fingerprinter | Workspace/Unity/Blender/CAD fixtures |
| Plan-byte amendment | 19 | Exact stored-byte SHA-256 | ApprovalValidator | Matching-ID/different-hash fixture |
| Identity amendment | 10 | Four non-overloaded IDs | Artifact model | Duplicate/move/ZIP/cross-run fixtures |
| Resource amendment | 16 | Defaults, hard ceilings, explicit limits | SafeProfiler | Oversize and timeout fixtures |
| ZIP amendment | 16 | ZIP only; other archives opaque | ZIP profiler | Archive-format fixtures |
| Git amendment | 17 | Sanitized allowlist or stop Git analysis | Git collector | Malicious-config fixture |
| Protected-path amendment | 8, 21 | Narrow matching-plan quarantine exception | Path validator | Protected-target fixture |
| Managed destinations | 21 | Fixed quarantine and archive roots | ApplyEngine | Destination fixtures |
| Transaction amendment | 22 | Stop, preserve, report, explicit rollback | Journal/Rollback | Partial failure fixture |
| Cross-filesystem amendment | 21 | Reject; never copy-then-delete | ApplyEngine | EXDEV fixture |
| Expected-state amendment | 20-22 | Journaled prefix is expected state | Fingerprinter | Second-action fixture |
| Invocation amendment | 6 | Explicit `$repo-curator` only | `openai.yaml` | Invocation test |
| Coverage amendment | 33 | Topic-to-test traceability | PRD | Coverage-index review |
