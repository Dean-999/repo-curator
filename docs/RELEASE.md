# Release contract

The release process builds a self-contained read-only Skill bundle and verifies
its source, schema, and output contracts outside the checkout.

## Required inputs

- exact schema registry and compatibility guidance;
- locked third-party sources, notices, and distributed license texts;
- explicit read-only runtime closure;
- adversarial fixture matrix and evaluation contract;
- current `docs/release-checklist.md`;
- fresh upstream review receipt with at least 80 percent source metadata
  coverage and no silent adoption.

## Release assertions

The public bundle must advertise only audit, prior-run comparison, and
non-executable RO-Crate workflows. Mutation, archive, quarantine, recovery,
rollback, permanent deletion, history rewriting, and reproduction remain
internal or unavailable. All inventory, parser, export, output, and bundle
budgets are recorded and enforced. Unknown schema versions reject. Every
published output is no-overwrite and hash-bound.

## Verification

```bash
python3 -m unittest discover -q
python3 -m compileall -q repo_curator tests tools
git diff --check
python3 tools/check_upstreams.py --output /absolute/new/upstream-review.json
python3 tools/check_release.py \
  --upstream-review /absolute/new/upstream-review.json \
  --output /absolute/new/release-check.json
```

The release receipt must be `PASSED`. Local provenance uses the exact in-toto
Statement and SLSA predicate tooling. Hosted attestation is availability-gated
and must never be represented as successful when the repository is private or
the immutable commit is unavailable.

The machine-checked details remain in `release-checklist.md`; this document is
the human-facing summary. The evidence export mapping remains in
`evidence-standards-mapping.md` because its URI and vocabulary are stable
contract material.
