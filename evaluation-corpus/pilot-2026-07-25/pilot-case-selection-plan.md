# Pilot Case Selection Plan

This plan is preregistered before reviewer labels exist. It validates the
corpus workflow; it is deliberately too small to satisfy any admission gate.
The pilot's only permissible verdict is `SHADOW_ONLY`.

## Gold Cases

Create 40 proposed gold cases: two per claim type for each of the five
registered repositories.

| Claim type | Per repository | Total |
| --- | ---: | ---: |
| `inventory_artifact` | 2 | 10 |
| `exact_byte_duplicate` | 2 | 10 |
| `capability_family` | 2 | 10 |
| `change_episode` | 2 | 10 |

For every repository and claim type, select one candidate predicted as an
assertion and one candidate predicted as an abstention or unresolved result,
when the evaluator produces such a candidate. If the prescribed category is
absent, retain a documented `NO_ELIGIBLE_CANDIDATE` limitation rather than
substituting a post-label choice. Predictions do not determine reviewer
labels.

Each selected candidate must have a retained snapshot descriptor, evaluator
run ID, prediction artifact, and expected-label artifact before it is offered
to review. Reviewers receive only frozen evidence. Their labels may agree,
disagree, or remain missing; none is changed to meet a quota.

## Mutation Risk Cases

Create 20 proposed mutation-risk cases: two candidates for each operation
class in each repository.

| Operation class | Per repository | Total |
| --- | ---: | ---: |
| `ARCHIVE` | 2 | 10 |
| `QUARANTINE` | 2 | 10 |

For every candidate, use a controlled copy or a non-destructive fault harness;
never mutate the registered source snapshot. Retain the named invariant
results, fault-injection report, and all evidence artifacts. `SAFE` and
`UNSAFE_FALSE_POSITIVE` are observed outcomes, not quotas. An unsafe outcome
or failed invariant is retained and immediately confirms that the operation
class stays `SHADOW_ONLY`.

## Stop Conditions

- Do not add a v2 record when its snapshot, prediction, expected label,
  reviewer label, or mutation evidence is absent.
- Do not replace a selected case after labels are visible. Record limitations
  and start a new pilot revision if correction is necessary.
- Do not run target-repository code, dependency installers, project test
  commands, or data downloads.
- Do not invoke `ARCHIVE` or `QUARANTINE` against a registered source
  snapshot. Pilot mutation evidence must come from an isolated controlled
  copy or fault harness.
