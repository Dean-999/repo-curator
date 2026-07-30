# Evaluation Corpus Governance

This policy governs the real v2 corpus used for semantic and mutation
admission. It is a process control. Hashes and artifact verification preserve
evidence, but do not authenticate people or prove reviewer independence.

## Roles

The corpus steward freezes repository snapshots, records inclusions and
exclusions before labels are reviewed, maintains the artifact ledger, and
publishes the immutable corpus bundle. A prediction operator runs the approved
evaluator and retains each prediction artifact. Reviewers label cases from the
frozen evidence. A reviewer must not author the prediction artifact for the
same case and must use an individually attributable reviewer ID. The admission
operator runs the manifest, artifact-verification, and evaluation commands and
retains their outputs unchanged.

At least two distinct reviewers label every case that is counted as consensus.
Matching labels yield `SUPPORTED` or `UNSUPPORTED`; disagreement remains
`DISAGREED`, and one or zero labels remains unreviewed. A steward does not
replace disagreement with a consensus label or remove it from denominators.

## Freeze And Retention

For every corpus release, retain the ordered case and risk arrays,
reviewer-provenance registry, artifact ledger, repository snapshot descriptors,
prediction artifacts, expected-label artifacts, individual label artifacts,
fault-injection reports, and mutation-evidence artifacts. Store a corpus
manifest, artifact-verification receipt, admission report, evaluator version,
and CI run identity beside them.

Corrections create a new corpus ID and new output paths. They do not overwrite
prior labels, reports, or receipts. A release that lacks a required artifact,
has an unresolved reviewer conflict, or fails any gate remains `SHADOW_ONLY`.

## Independence Review

Before requesting admission, the steward records reviewer affiliations and any
relationship to the evaluator implementation or target repository. This review
is retained as reviewer provenance, but no local command upgrades it into
cryptographic proof. Material conflicts of interest require a replacement
reviewer or conservative exclusion from the consensus population, with the
excluded case retained in the corpus record.

Each released snapshot registry also has a create-once
`repo-curator.corpus-card.v1`. The card documents the sampling scope,
repository-family composition, public/private source counts, fixed Git
identities, and optional Software Heritage identifiers. Missing archival
identifiers remain missing and are never fetched during evaluation. The card
is descriptive only and carries no admission or mutation authority.
