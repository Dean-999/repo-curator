# repo-curator evaluation profile v1

This profile identifies evaluation reports produced from
`repo-curator.gold-case.v2`, `repo-curator.mutation-risk-case.v2`, and a
`repo-curator.evaluation-corpus-manifest.v1` manifest. Its profile URI is the
URL of this directory.

Positive admission requires exact manifest hashes, evaluator-version
agreement, consistent repository snapshot identities, reviewer provenance,
minimum sample sizes, repository-family diversity, and all claim-specific and
mutation gates. Legacy v1 records may be reported but cannot contribute to a
positive gate.

Conformance describes the evaluation contract. It does not authenticate a
reviewer, prove that a repository family is representative, or replace
independent governance of the corpus. Incompatible gate or provenance changes
require a new profile URI and explicit migration rules.
