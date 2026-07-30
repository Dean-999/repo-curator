# Mutation Risk Case Intake Template

This is an intake worksheet, not a corpus record. Do not add it to
`mutation-risk-cases.json`.

## Candidate identity

- Candidate ID:
- Operation class: `ARCHIVE` or `QUARANTINE`
- Repository ID from `snapshot-registry.json`:
- Exact repository snapshot artifact hash:
- Test run ID:
- Evaluator version:

## Evidence and fault injection

- Evidence artifact paths and SHA-256 values:
- Fault-injection report path and SHA-256:
- Named invariant results, including `no-overwrite`, `source-identity`, and
  `recovery`:
- Outcome: `SAFE` or `UNSAFE_FALSE_POSITIVE`

Any failed invariant, absent evidence, or unsafe false positive remains in the
record and blocks the operation-class gate.
