# Gold Case Intake Template

This is an intake worksheet, not a corpus record. Do not add it to
`gold-cases.json`.

## Case identity

- Case ID:
- Repository ID from `snapshot-registry.json`:
- Exact repository snapshot artifact hash:
- Run ID:
- Evaluator version:

## Claim and prediction

- Claim type: `inventory_artifact`, `exact_byte_duplicate`,
  `capability_family`, or `change_episode`
- Confidence: `DETERMINISTIC`, `HIGH`, or `STRONG` as applicable
- Prediction: `ASSERTED`, `ABSTAINED`, or `UNRESOLVED`
- Prediction artifact path and SHA-256:
- Expected-label artifact path and SHA-256:

## Independent review

- Reviewer 1 ID, label, label-artifact path, and SHA-256:
- Reviewer 2 ID, label, label-artifact path, and SHA-256:
- Conflict-of-interest check:
- Consensus: `SUPPORTED`, `UNSUPPORTED`, `DISAGREED`, or unreviewed:

Do not convert disagreement into consensus. A reviewer who authored the
prediction artifact cannot label the same case.
