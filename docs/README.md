# Repository documentation

The repository keeps a small active documentation surface. Historical design
notes and implementation plans are intentionally not part of the active Skill
contract; the Git history remains the record of superseded drafts.

## Canonical documents

- [Project contract](PROJECT.md): product boundary, evidence model, safety
  rules, architecture, and current capability.
- [Evaluation](EVALUATION.md): corpus, labels, metrics, calibration, and
  admission limits.
- [Release](RELEASE.md): release workflow, supply-chain rules, and validation.
- [Research](RESEARCH.md): external standards, prior art, and adoption policy.
- [Binding safety amendments](final-binding-amendments.md): normative safety,
  identity, parser, and transaction requirements.
- [Evidence standards mapping](evidence-standards-mapping.md): stable PROV and
  RO-Crate vocabulary used by the exporter.
- [Release checklist](release-checklist.md): machine-checked release markers.

## Governance documents

- `adr/` contains reviewed architectural decisions.
- `agents/` contains repository operating rules for agents.
- `profiles/` contains versioned evidence and evaluation profile descriptions.
- `AGENTS.md` remains a repository root contract; [`CONTEXT.md`](CONTEXT.md)
  and [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) are maintained in
  this documentation directory.

The public Skill bundle contains only its launcher, concise Skill instructions,
the read-only runtime closure, schemas, source locks, notices, and license
texts. It does not ship this documentation tree.
