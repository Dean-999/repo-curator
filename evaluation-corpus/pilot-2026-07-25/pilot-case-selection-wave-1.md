# Pilot Case Selection: Wave 1

This is a dated scope revision to the preregistered
`pilot-case-selection-plan.md`; it does not alter that plan or fill its
unavailable quota with substitute cases. It is created before any case-level
reviewer labels exist.

## Frozen Scope

Wave 1 contains ten review cases: one `inventory_artifact` assertion and one
`exact_byte_duplicate` assertion for each registered repository. Each case
has a retained snapshot descriptor, audit run, and prediction artifact. Both
reviewers are assigned the same packet before either label is visible.

| Claim type | Eligible asserted cases | Missing second candidate | Status |
| --- | ---: | ---: | --- |
| `inventory_artifact` | 5 | 5 | REVIEWABLE_FIRST_WAVE |
| `exact_byte_duplicate` | 5 | 5 | REVIEWABLE_FIRST_WAVE |
| `capability_family` | 0 | 10 | NO_ELIGIBLE_CANDIDATE |
| `change_episode` | 0 | 10 | NO_ELIGIBLE_CANDIDATE |

The five audit runs each contain zero `capability-families.jsonl` and zero
`change-episodes.jsonl` records. Their `run.json` files record
`STRUCTURAL_ADAPTER_UNAVAILABLE`; no claim from either category is eligible
for reviewer labeling in this revision.

The audit output does not provide an independent abstained or unresolved
candidate for the first two claim types. The absent second candidate is
retained as `NO_ELIGIBLE_CANDIDATE`; no post-label substitution is allowed.

## Boundaries

- This revision is `SHADOW_ONLY` and remains below every admission threshold.
- Reviewer labels, consensus, expected-label artifacts, v2 records, an
  artifact ledger, and an admission report do not yet exist.
- Every exact-byte-duplicate claim repeats the source limitation: equal bytes
  do not establish common lineage or purpose.
- Mutation-risk cases are outside this wave. No `ARCHIVE` or `QUARANTINE`
  action is authorized against a registered source snapshot.

## Next Gate

The two assigned reviewers each create one immutable label artifact per case.
Only a case with both retained labels may be considered for a later v2 corpus
revision, where disagreement and any missing label remain explicit.
