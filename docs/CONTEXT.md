# repo-curator

repo-curator is a curation domain for reconstructing evidence and safely converging computational research repositories after repeated human and AI-assisted changes.

## Language

**Computational Research Repository**:
A repository whose relevant research evidence is primarily expressed through code, data, configurations, computational environments, experiment runs, results, figures, tables, and publication materials. Wet-lab sample tracking, instrument control, participant consent, LIMS, ELN, and laboratory administration are outside this boundary.
_Avoid_: Scientific project, general research project, laboratory repository

**Product Positioning**:
Retrospective evidence reconstruction and safe curation for computational research repositories. The positioning is defined by the repository problem and outcome, not by one persona or lifecycle event; publication, handoff, revival, and archival are use contexts.
_Avoid_: AI file sorter, reproduction platform, publication-preparation tool

**repo-curator Skill**:
The explicitly invoked reusable Skill that owns user interaction, semantic reasoning, and workflow orchestration. It is the product boundary, not a general-purpose research platform, autonomous cleanup agent, or standalone CLI product.
_Avoid_: Cleanup bot, research management platform, repository janitor

**Deterministic Safety Kernel**:
The dependency-minimized scripts bundled with the repo-curator Skill that own filesystem observation, identity, hashing, boundaries, plan validation, reversible movement, journaling, and verification. They do not make semantic retention or scientific judgments.
_Avoid_: Tool backend, cleanup script, autonomous executor

**Read-only Evidence Adapter**:
An optional, versioned integration that imports existing declarations or supplied exports from an external research or code-intelligence tool as typed, coverage-limited observations. It never installs the tool, executes the target project, or grants semantic or mutation authority.
_Avoid_: Plugin executor, automatic integration, trusted detector

**Retrospective Evidence Reconstruction**:
Recovery of relationships that remain supportable after provenance is incomplete, conflicting, or spread across historical tools and artifacts. It preserves missing links and counter-evidence instead of completing the record by assumption.
_Avoid_: Provenance capture, automatic provenance recovery

**Research Evidence Chain**:
A scoped review projection linking a declared claim, figure, or table through a result and experiment attempt to relevant configuration, environment, code revision, and dataset snapshot. Each link has independent evidence and may remain unresolved.
_Avoid_: Provenance truth, verified reproduction chain

**Scientific Mainline**:
The hypothesized current research path containing the code, data, configuration, environment, validation, results, and explanation needed to interpret the project's current accepted work. It is not the Git default branch.
_Avoid_: Main branch, latest files

**Project Intent Hypothesis**:
A scoped, evidence-linked interpretation of what the repository is for, what is currently maintained, and what must be retained. It is reconstructed from project documents and records before asking the user; unresolved material conflicts remain explicit.
_Avoid_: Repository truth, README summary, user questionnaire

**Evidence-specific Decision Question**:
One minimal question raised only when conflicting or missing evidence would materially change preservation, recommendation, or safe action. A skipped or unanswered question produces conservative abstention without blocking unrelated analysis.
_Avoid_: Onboarding survey, confirmation prompt, general interview

**Canonical Result Candidate**:
A result proposed for project-governance review as the result currently representing a research outcome. Recency, filename, metric rank, or statistical significance cannot establish it alone.
_Avoid_: Best result, winning run, final result

**Canonical Result Governance State**:
The scoped status of a canonical-result candidate: `CANDIDATE`, `PROVISIONALLY_CANONICAL`, `USER_CONFIRMED`, or `UNRESOLVED`. The Skill may assign `PROVISIONALLY_CANONICAL` when independent evidence classes strongly agree and no material counter-evidence exists; only an explicit scoped user or reviewer decision yields `USER_CONFIRMED`. Material conflict yields one evidence-specific question or `UNRESOLVED`, not repeated approval work.
_Avoid_: Scientific truth, automatic winner, mandatory per-result approval

**Reproducibility Evidence Completeness**:
The scoped status of whether materials needed to interpret or potentially reproduce a result were found, linked, missing, conflicting, opaque, or unverified. It is not a claim that an experiment has reproduced successfully.
_Avoid_: Reproducibility score, reproduction verification

**Curation Boundary**:
The point at which repo-curator's responsibility ends: it reconstructs existing computational-research evidence, identifies gaps, recommends treatment, and supports approved reversible organization. Executing code, reproducing experiments, and preparing an executable reproduction handoff remain responsibilities of other workflows.
_Avoid_: Reproduction platform, workflow runner, experiment validator
