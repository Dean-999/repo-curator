# Require manifest-bound, diverse corpora for admission

Legacy evaluation records remain readable for metrics but cannot produce
`ADMISSION_READY`. Positive admission requires v2 gold and mutation-risk
records bound byte-for-byte by a versioned corpus manifest. Records identify
the evaluator, repository family, repository snapshot, run, prediction or
test artifacts, reviewer-label artifacts, and fault-injection evidence.

Semantic gates require minimum sample sizes and repository diversity.
Capability-family and change-episode precision use the 95% Wilson lower bound,
not only point estimates. Mutation gates require at least 3,000 v2 candidates
per operation across multiple repositories and families, all named invariants
passing, fault-injection evidence present, and zero unsafe false positives.

These checks prevent fixture-sized and duplicated synthetic corpora from
accidentally enabling mutation. They do not cryptographically establish human
reviewer independence; reviewer governance remains a procedural control and
must not be represented as stronger proof.
