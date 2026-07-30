# Evidence Standards Mapping

`repo-curator` records a conservative internal evidence graph and can export a
hash-verified audit as a non-executable RO-Crate 1.1 JSON-LD view. This document
freezes the minimum conceptual mapping to PROV and RO-Crate. The export is not
a complete PROV document, a Workflow Run RO-Crate, or a reproduction claim.

The versioned evidence profile is identified by
`https://github.com/Dean-999/repo-curator/tree/main/docs/profiles/evidence-v1`.
Evidence records carry this URI in `conforms_to`. As in RO-Crate, declaring a
profile identifies the intended contract; it does not prove that a record is
valid, complete, or scientifically correct.

| Internal record | PROV concept | RO-Crate concept | Constraint |
| --- | --- | --- | --- |
| Inventory evidence for an artifact | `prov:Entity` | `File` or `Dataset` | The artifact remains distinct from its location and content identities. |
| Declared metadata evidence | `prov:Entity` describing an assertion | `CreativeWork` metadata | A declaration is not treated as proof that its referenced payload exists or reproduced. |
| Data Package descriptor observation | `prov:Entity` describing a dataset declaration | `Dataset` metadata | Local path presence is inventory evidence only; remote and inline values are omitted, resources are not read, and schema conformance is not claimed. |
| Sanitized Git commit observation | `prov:Entity` | `SoftwareSourceCode` when applicable | A commit alone does not establish a run `prov:Activity`. |
| Profile or archive observation | `prov:Entity` describing an observation | `PropertyValue` on the observed object | Truncation, redaction, malformed input, and unsupported formats remain limitations. |
| Exact-byte duplicate relationship | no `prov:wasDerivedFrom` mapping | local `repo-curator:exactByteDuplicate` relationship | Equal bytes do not establish derivation, common lineage, or common purpose. |
| Declared experiment-member edge | declared association only; no `prov:Activity` | local `repo-curator:declaredExperimentMember` relationship | The manifest named an output, input, configuration, generator, validation, or reviewer record that exists in inventory. The edge does not prove execution, generation, use, validation, review, or scientific correctness. |

`export-ro-crate` verifies every output hash named by a finalized `run.json`
before exporting. It carries assertion origin, limitations, counter-evidence,
and `NOT_ASSIGNED` confidence under the `repo-curator:` namespace. Mainline
entries are claims with their supporting and counter-evidence links. The root
records `executionAuthorized: false`; no `prov:Activity` or Workflow Run is
created merely because the audit observed provenance-like material.

Each `evidence.jsonl` record carries `assertion_origin`, `source_type`,
`extractor`, `scope`, `limitations`, and `counter_evidence_ids`. The controlled
origins are `DECLARED`, `OBSERVED`, `INFERRED`, `DETERMINISTIC`, and `SEMANTIC`.
Only origins supported by the collected inputs are emitted; absence of an origin
or relationship is not negative evidence. `relationships.jsonl` explicitly
lists both supporting and counter-evidence identifiers. Exact-byte groups make
no semantic or lineage assertion. Declared experiment-member edges retain
`DECLARED_LINEAGE_NOT_EXECUTION_VERIFIED`, and a missing manifest path remains a
reproducibility gap rather than becoming an edge to an invented entity.
