# Domain docs

This repository uses a single domain context.

## Before exploring

Read these sources when they exist and are relevant:

- `docs/CONTEXT.md` for the domain glossary and main concepts;
- ADRs under `docs/adr/` for reviewed architectural decisions;
- the maintained project contract in `docs/PROJECT.md`;
- the canonical evaluation and release contracts in `docs/EVALUATION.md` and
  `docs/RELEASE.md`.

If `docs/CONTEXT.md` or `docs/adr/` does not yet exist, proceed without treating absence as a problem. Domain-modeling and evidence-driven design workflows create them only when terminology or consequential decisions have actually been resolved.

## Vocabulary

Use terms exactly as defined in `docs/CONTEXT.md`. Do not silently replace established terms with synonyms in issue titles, tests, schemas, or implementation plans. If a required concept is missing, reconsider whether it is necessary or record the gap for domain modeling.

## ADR conflicts

If proposed work conflicts with an ADR, identify the ADR and surface the conflict explicitly. Never silently override a recorded decision.
