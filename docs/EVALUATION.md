# Evaluation contract

Evaluation measures whether repo-curator is conservative and useful; it does
not establish scientific truth or grant mutation authority.

## Corpus

Cases are bound to immutable repository snapshots, exact source identities,
licenses, repository family, language, evidence-tool ecosystem, intended use,
limitations, and reviewer provenance. The corpus card is descriptive and has
no admission authority. Real repositories may include DVC, DataLad, MLflow,
Sacred, RO-Crate, BagIt, notebooks, ordinary Git, and legacy unstructured
layouts.

## Labels

Independent reviewers label artifact role, preservation requirement, experiment
bundle membership, canonical-result candidacy, relationship type, evidence
coverage, and mutation risk. Disagreement is retained. If reviewers cannot
agree on a case, the system is expected to abstain rather than manufacture a
deterministic answer.

## Metrics

Report claim-specific precision, recall, coverage, abstention, unresolved rate,
and reviewer correction burden. Also report unsafe-move false positives,
accepted-bundle break rate, unsupported-certainty rate, secret leakage,
rollback success, parser-boundary failures, and runtime/resource cost.

Confidence and evidence coverage are separate dimensions. A high-confidence
conclusion with low coverage remains review-only. Metrics are stratified by
language, repository family, evidence availability, adapter, and repository
size. New repository families are treated as distribution shift until tested.

## Safety tests

The adversarial matrix must cover prompt injection, shell text in metadata,
malformed and oversized files, symlink/path escape, secret values, changed
files, unavailable content, parser crashes, output-hash drift, and target
execution attempts. Metamorphic tests ensure that JSON key order, enumeration
order, unrelated files, timestamps, and removed evidence cannot create a
stronger unsupported conclusion.

## Gates

Evaluation receipts are exact-version and manifest-bound. A passing receipt
does not imply representativeness, scientific correctness, or public mutation
admission. The current public release remains `READ_ONLY`, with calibrated
accuracy unpublished and human corpus admission not claimed.
