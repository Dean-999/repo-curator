# Research and adoption notes

`repo-curator` combines established ideas rather than claiming that inventory,
provenance, duplicate detection, experiment tracking, or reversible review are
new inventions. Its useful distinction is the combination of retrospective
research-repository reconstruction, scientific evidence chains, preservation
guards, counter-evidence, and a strict no-target-execution boundary.

## Standards and adjacent systems

- W3C PROV supplies Entity, Activity, Agent, and derivation vocabulary.
- RO-Crate supplies a portable research-object graph and JSON-LD packaging.
- OpenLineage supplies Run, Job, Dataset, and Facet concepts.
- BagIt and PREMIS inform fixity and preservation-event language.
- DVC, DataLad, MLflow, Sacred, Snakemake, Nextflow, and showyourwork provide
  prospective declarations that repo-curator may observe without executing.
- noWorkflow and ReproZip are accepted only as explicitly supplied exports or
  manifests; their collection or execution paths are excluded.
- datasketch and DataTrove inform bounded similarity and deduplication design;
  similarity remains a review signal.

## Adoption rule

Prefer a mature documented pattern over a new general-purpose implementation.
Use the smallest local, read-only, bounded slice. Record the upstream commit,
license, path, modification, excluded authority, and regression fixture in the
source lock. Shadow-evaluate upstream changes before changing a conclusion.

## Product claims

Do not claim global novelty, formal scientific validity, universal semantic
accuracy, or safe automatic cleanup. The defensible claim is that repo-curator
provides a conservative evidence-governance layer for heterogeneous legacy
research repositories and interoperates with existing research tooling.

## Next research priorities

1. Calibrate DVC, MLflow, DataLad, BagIt, and near-duplicate observations on
   independently reviewed fixtures.
2. Keep the static HTML audit view as a derived presentation layer; JSONL
   evidence remains canonical. Defer SQLite until multi-run query needs are
   demonstrated.
3. Add OpenLineage/PROV projections as exports, not internal authorities.
4. Add process-conformance and incremental caching only after event coverage
   and invalidation behavior have fixtures.
