# repo-curator project contract

## Purpose

`repo-curator` is a local-first, read-only Skill for retrospective evidence
reconstruction in computational research repositories. It helps a reviewer
understand what a repository contains, which artifacts may support a research
claim, which experiment materials are incomplete, and which conservative
curation decisions deserve human review.

It is not an experiment runner, truth verifier, generic file cleaner,
deduplicator, provenance collector, or replacement for DVC, DataLad, MLflow,
RO-Crate, or workflow engines.

## Supported boundary

The public Skill may:

- inventory files, directories, links, special objects, and Git state;
- compute separate artifact, content, location, and repository identities;
- observe bounded research metadata and explicitly supplied exports;
- reconstruct project intent, scientific-mainline hypotheses, experiment
  bundles, declaration-only relationships, document conflicts, and evidence
  gaps;
- emit evidence-linked classifications, recommendations, decision questions,
  curation briefs, and non-executable RO-Crate exports;
- compare a finalized run with a verified prior run.

The public Skill must never execute target code, notebooks, workflows,
containers, hooks, package managers, aliases, filters, services, or experiments.
It must not install dependencies, fetch data, follow untrusted links, rewrite
history, merge documents, delete files, or expose mutation and recovery
internals.

## Evidence model

Every conclusion separates:

1. deterministic inventory facts;
2. declared evidence supplied by repository metadata;
3. bounded observations made by an adapter;
4. semantic hypotheses and candidate relationships;
5. user assertions and recommendations.

Records retain source, extractor, scope, limitations, supporting evidence, and
counter-evidence. Missing evidence is an explicit gap. `UNRESOLVED` means the
repository does not support a safe conclusion within the analyzed scope.
Equal bytes do not prove common purpose, lineage, or replacement. A declared
workflow relation does not prove execution or scientific validity. A canonical
result is always a candidate until governance evidence supports promotion.

## Current audit modes

The default audit is the stable compatibility path. The opt-in
`--advanced-review` mode adds bounded local observations for DVC, MLflow,
DataLad, and BagIt, near-duplicate candidates, information-value ordering for
one open decision question, and an evidence-coverage matrix. Advanced outputs
are review-only and hash-bound in `run.json`; they cannot authorize merge,
archive, deletion, or execution.

All adapters use descriptor-relative, no-follow reads and finite byte, record,
depth, and output budgets. Malformed, unavailable, changed, opaque, or
oversized input becomes a limitation and does not erase unrelated evidence.

## Architecture

The Skill launcher is a thin invocation layer. The deterministic kernel owns
filesystem boundaries, budgets, identity, evidence construction, output
hashing, and atomic publication. Read-only adapters recognize declarations or
bounded metadata. The shadow layer produces classifications and
recommendations without action candidates. Interchange code projects verified
records to non-executable RO-Crate JSON-LD.

JSONL audit outputs are canonical. The curation brief and plan are derived,
hash-bound views. Unknown schema versions are rejected; incompatible changes
receive a new schema ID or version; historical bytes are never rewritten.

## Safe review policy

The system reports one evidence-specific question at a time. Questions include
scope, support, counter-evidence, consequences, and a conservative preserve
recommendation. Advanced ordering exposes its factors; it is not a confidence
score and never grants mutation authority.

Exact duplicates and near duplicates are review candidates. Near-duplicate
similarity is a discovery signal only and cannot establish semantic
equivalence. Experiment bundles guard all member artifacts when completeness
is uncertain. Recommendations remain shadow guidance until a future, separately
governed mutation product is admitted.

## Third-party reuse

Mature standards and projects may inform a bounded adapter or vocabulary. Any
copied, adapted, or behaviorally derived component must have a fixed upstream
commit, license, source path, integration mode, modification summary, and
regression fixture in `third_party/sources.lock.yaml` and
`docs/THIRD_PARTY_NOTICES.md`. Upstream changes enter shadow review before affecting
user-facing conclusions or safety behavior.

## Deferred work

The repository deliberately defers automatic merge/delete, broad workflow
parsing, cloud services, unrestricted RDF/SHACL execution, and calibrated
semantic claims until independent gold labels, coverage measurements, and
mutation admission gates exist.
