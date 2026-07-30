# repo-curator evidence profile v1

This profile identifies repo-curator evidence records that preserve assertion
origin, source identity, analyzed scope, extractor, limitations, and
counter-evidence. Its profile URI is the URL of this directory.

Conformance requires a versioned record with stable `evidence_id`, `run_id`,
`subject`, `source`, `assertion_origin`, `extractor`, `scope`, `limitations`,
and `counter_evidence_ids` fields. Evidence produced from declarations remains
declared evidence. Observations with truncation, redaction, opaque content, or
unsupported formats must retain those limitations.

`conforms_to` is an intended-format assertion. It is not proof that referenced
objects exist, that an experiment ran, that the record is complete, or that a
scientific claim is valid. Later incompatible profiles must use a new URI and
document migration rules rather than silently changing this contract.
