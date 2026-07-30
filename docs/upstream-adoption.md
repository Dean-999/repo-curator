# Upstream Adoption Register

This human-readable register explains what repo-curator borrows from mature public projects.
It does not make any upstream package a runtime dependency, authorize target
repository execution, or transfer scientific or mutation authority to an
external tool. Stars are a discovery signal, not a security, correctness, or
fitness guarantee.

The release-bound machine record is `third_party/sources.lock.yaml`; bundled
attribution and exclusion notices are in `THIRD_PARTY_NOTICES.md`.

| Source | Checked 2026-07-28 | License | Adopted boundary | Explicitly not adopted |
| --- | ---: | --- | --- | --- |
| [DVC](https://github.com/treeverse/dvc) | 15,776 stars, `f74c1c0e709de61f571905802bc0c75035dc6ef2` | Apache-2.0 | Declaration-marker recognition for `dvc.yaml`, `dvc.lock`, `.dvc/config`, and `*.dvc`; its explicit reference-scope discipline informs retention review. | YAML execution, remote access, cache garbage collection, dependency installation, and any DVC command. |
| [DataLad](https://github.com/datalad/datalad) | 652 stars, `755752d27582d0ac1f541007fd0adeced1978ba3` | MIT, verified from `COPYING` | Read-only `.datalad/config` recognition and the distinction between declared content and locally available content. | git-annex operation, dataset installation, content retrieval, drop, run, and rerun. |
| [MLflow](https://github.com/mlflow/mlflow) | 27,239 stars, `6f96bf7a53c192479e3b0bae89ca716c0200dbe9` | Apache-2.0, verified from `LICENSE.txt` | Read-only root `MLproject` marker recognition. | YAML parsing, entry-point or environment resolution, tracking-server access, and project execution. |
| [Sacred](https://github.com/IDSIA/sacred) | 4,370 stars, `86865b03d05e83da35ca582392ca31777db88d11` | MIT, verified from `LICENSE.txt` | Co-located `config.json` and `run.json` recognition with bounded JSON syntax checking. | Observer startup, run interpretation, source copying, artifact retrieval, and experiment execution. |
| [bagit-python](https://github.com/LibraryOfCongress/bagit-python) | 263 stars, `4bd2713cedbe1f8e634567c20ef0dded9622011d` | `NOASSERTION`; upstream package classifier says Public Domain but no license text is present | Required `bagit.txt` marker recognition as package-declaration evidence. | Tag parsing, manifest hashing, payload fetching, bag creation, and validation. |
| [Renku Python](https://github.com/SwissDataScienceCenter/renku-python) | 37 stars, `b2418a15c89e16e4442a1ecf11f703f4e15922e8` | Apache-2.0, verified from `LICENSE` | Read-only `.renku` project-directory recognition. This replaces the unsupported `renku.yaml` marker. | Metadata database access, migration, Git-hook installation, remote access, and workflow execution. |
| [noWorkflow](https://github.com/gems-uff/noworkflow) | 126 stars, `4a2c4c8bdea2be73570a1aa598042940f4f4270f` | MIT, verified from `LICENSE` | Read-only `.noworkflow` provenance-directory recognition. | Database/content-store access, collection, restoration, and target script execution. |
| [showyourwork](https://github.com/showyourwork/showyourwork) | 659 stars, `212422b622ffa05a7aaeda20f7ef3fbcd865a015` | MIT, verified from `LICENSE` | Read-only root `showyourwork.yml` marker recognition. | Jinja rendering, YAML parsing, Zenodo access, LaTeX compilation, and Snakemake execution. |
| [Snakemake](https://github.com/snakemake/snakemake) | 2,837 stars, `1a2774645a599d6c7d0589a048b64023b360c7d3` | MIT | Read-only `Snakefile` marker recognition; workflow declarations are evidence, not proof of a completed run. | Rule parsing with execution semantics, DAG construction, conda/container handling, and workflow execution. |
| [Nextflow](https://github.com/nextflow-io/nextflow) | 3,451 stars, `cb222312c0724884dde075b567d252a1529b429c` | Apache-2.0 | Read-only `nextflow.config` or `main.nf` marker recognition. | Config evaluation, plugin resolution, container handling, cloud execution, and report generation. |
| [repo2docker](https://github.com/jupyterhub/repo2docker) | 1,730 stars, `f90d7e9b2f9bc8fb9fbccf916afa512a460eac3d` | BSD-3-Clause, verified from `LICENSE` | Attributed inventory-only port of Conda, pip, Pipenv, R, Julia, Nix, Docker, and Binder marker selection plus `binder`/`.binder` scope precedence. Root declarations shadowed by a Binder scope and conflicting Binder directories remain explicit. | File-content parsing, environment resolution, package installation, image building, container startup, and every build or start script. |
| [nbformat](https://github.com/jupyter/nbformat) | 312 stars, `4421827289087d37e57ee770e115a13db9a45dd5` | BSD-3-Clause, verified from `LICENSE` | Attributed bounded port of JSON notebook-envelope reading and explicit version observation; v4 cell types, output types, kernel, and language declarations are counted under hard caps. | Schema validation, version conversion, NotebookNode construction, cell/output persistence, output trust, widgets, kernels, and notebook execution. |
| [RO-Crate Python](https://github.com/ResearchObject/ro-crate-py) | 86 stars, `05effe591443934e48e3fe59c53d7bc01a3334e0` | Apache-2.0 | Attributed bounded port of local `@context`/`@graph` entity indexing and metadata-descriptor-to-root validation; it emits capped entity and reference observations. | Network/context retrieval, mutable entity objects, profile conformance claims, payload fetches, and workflow execution. |
| [Frictionless Framework](https://github.com/frictionlessdata/frictionless-py) | 834 stars, `52ec5477f07612639b1505edc669128ce5e49a30` | MIT, verified from `LICENSE.md` | Attributed bounded port of Data Package package/resource field selection and repository-relative local-path presence; 128 resources and 16 paths per resource are hard limits. | Resource reads, remote retrieval, inline-value persistence, schema/dialect parsing, inference, dereferencing, plugins, publication, and target execution. |
| [Citation File Format](https://github.com/citation-file-format/citation-file-format) | 544 stars, `0c5b4aa07071490eaf261775ce96ccdd13a6e2d5` | CC-BY-4.0 | Root `CITATION.cff` presence recognition only. | YAML parsing, schema validation, metadata-value persistence, conversion, and target execution. |
| [CodeMeta](https://github.com/codemeta/codemeta) | 350 stars, `0bc1f26d9575c9bfc288571b358a24a464595443` | Apache-2.0 | Public vocabulary terms constrain allowlisted field-name and cardinality observation from bounded syntax-valid JSON. | Value persistence, JSON-LD resolution, schema validation, remote retrieval, and target execution. |
| [signac](https://github.com/glotzerlab/signac) | 147 stars, `9419e3c71900bbbd6a4a177ac91ae895d1290b2d` | BSD-3-Clause, verified from `LICENSE.txt` | Attributed port of five stable filename constants into a 256-marker-capped inventory observer. | Config/statepoint/document reads, project migration, import/export, package import, and target execution. |
| [git-sizer](https://github.com/github/git-sizer) | 4,062 stars, `88eaa80df48db1b47291f3a43b084b8c79082339` | MIT, verified from `LICENSE.md` | Attributed bounded port of size metric categories, selected reference scales, and value/scale ratios over compact Git counts and current inventory. | Full reachable-object graph traversal, emitted ref names, historical file/blob reads, remote access, history rewriting, and cleanup authority. |
| [pre-commit-hooks](https://github.com/pre-commit/pre-commit-hooks) | 6,647 stars, `4189d189e039fd49eb235357c9d9977b026c6c8e` | MIT, verified from `LICENSE` | Attributed 500 KiB staged-add threshold, broken-link condition, and destroyed-symlink mode transition with 256 retained findings. | Hook execution/installation, blob comparison, `.gitattributes` or LFS evaluation, index/filesystem mutation, commit rejection, and cleanup authority. |
| [ReproZip](https://github.com/VIDA-NYU/reprozip) | 362 stars, `ac9bb2439123212ed707f2ec7c82f07334bae0bc` | BSD-3-Clause, verified from `LICENSE` | An explicit, SHA-256-bound metadata JSON export becomes a `SUPPLIED_EXPORT_METADATA_ONLY` observation. | Package unpacking, environment installation, tracing, reproduction, remote retrieval, and any ReproZip command. |
| [Workflow Run RO-Crate](https://github.com/ResearchObject/workflow-run-crate) | `4add9f64a49d8c6a79cb34f146b35b887a60852d` | Apache-2.0 | Attributed bounded port of `CreateAction`, `instrument`, `object`, `result`, and `actionStatus` over an explicitly supplied hash-bound JSON document. | Profile conformance claims, context or payload resolution, crate generation, remote access, execution, and execution verification. |
| [nf-prov](https://github.com/nextflow-io/nf-prov) | 30 stars, `97d350065f89d7a98aad8506586b54bce32f1acb` | Apache-2.0 | Attributed mapping of inputs/outputs and completed/failed action status from already-generated Workflow Run RO-Crate JSON. | Nextflow plugin loading, workflow/task execution, file copying, parameter values, configuration serialization, and report generation. |
| [Gitleaks](https://github.com/gitleaks/gitleaks) | 28,334 stars, `b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b` | MIT, verified from `LICENSE` | Attributed fixed-format GitHub token, AWS access-key, JWT, and private-key classifier plus an independently bounded recent-changed-blob Git history scan. | Full-history diff scanning, entropy scoring, allowlist engine, secret values/snippets/fingerprints, credential validation, remote access, and target execution. |
| [restic](https://github.com/restic/restic) | 35,178 stars, `8baffc40273bb3aa4f6c7826d582ebe576f4c90c` | BSD-2-Clause | Immutable-record thinking, verify-before-destructive-maintenance, and retention scope as explicit policy. | Backup repository format, credentials, remote storage, prune, forget, and data deletion. |
| [Borg](https://github.com/borgbackup/borg) | 13,547 stars, `4bd18591f4fe86158d7a9f4823183a4fdb64fb20` | BSD-3-Clause, verified from `LICENSE` | Lock, transaction, and commit-record design references already reflected by the apply journal. | Repository format, crypto, compression, pruning, and backup execution. |
| [rmlint](https://github.com/sahib/rmlint) | 2,386 stars, `b311f38dab01585a138ed0f3ac14d2b426d12523` | GPL-3.0 | Candidate-discovery pattern only: group before proposing action, and keep a dry review step. | Source code, linking, vendoring, or runtime dependency. GPL code is intentionally excluded. |

## Adapter Contract

The marker adapter is deterministic and dependency-free. For one family it
emits one observation with a stable primary source plus every matching marker
path and artifact identifier. The result is `DECLARATION_PRESENCE_ONLY`:
marker presence does not establish syntax, semantic validity, referenced
payload availability, run success, reproducibility, canonical status, or
permission to move a file. RO-Crate and Sacred retain their existing bounded
JSON syntax validation. A declared Workflow Run RO-Crate is represented as a
separate, declaration-only observation. A present `dvc.lock` receives only a
bounded lexical stage-key count, not YAML evaluation or DVC semantics.
The repo2docker-derived observer reads inventory paths only. It records active,
shadowed, or unresolved environment markers under the upstream Binder scope
rules and never opens or interprets their content.
The nbformat-derived observer recognizes `.ipynb` by path, parses at most the
profiler's bounded local bytes, requires explicit notebook version fields, and
summarizes only a controlled v4 envelope. Older versions remain version-only;
source, output data, arbitrary metadata, and widget state are never persisted.
The Frictionless-derived observer recognizes every regular root or nested
`datapackage.json`, syntax-checks at most 1 MiB, and records only safe structural
tokens, source kinds, and normalized local-path inventory status. It observes at
most 128 resources and 16 paths per resource. Remote URLs and inline values are
classified but omitted, resource files are never opened, and the generic
profile is content-free to prevent descriptor data from reaching another
output.
The research-software metadata observer treats CFF as presence-only, parses at
most 1 MiB of CodeMeta JSON while retaining no values, and counts signac
filesystem declarations without opening their content. CFF, CodeMeta, and
signac generic profiles are content-free. None of these observations establish
schema conformance, citation quality, project validity, or a completed run.
The git-sizer-derived observer reports compact object-database, ref,
reachable-commit, and current-checkout metrics through the existing bounded Git
runner. Its ratios preserve upstream reference scales but are context only.
Object database counts can include unreachable objects or alternates, and no
metric establishes that a file is disposable or that history should be rewritten.
The pre-commit-hooks-derived observer composes existing broken-link inventory
warnings with staged-large-file and symlink-mode-change evidence. It preserves
differing-content cases as candidates and does not evaluate LFS attributes,
compare blobs, run hooks, mutate the index, or reject a commit.

New adapters must first add an entry here with a frozen source, license check,
input contract, resource budget, adversarial fixture, and a statement of the
authority it cannot receive. A candidate may then enter the deterministic
kernel only if it remains read-only and any absence, malformed input, or
coverage gap degrades to an explicit limitation.

The current ReproZip contract accepts only an explicitly named absolute
manifest path passed to the audit CLI. The manifest has the exact schema
`repo-curator.supplied-adapter-export-manifest.v1`, declares `REPROZIP`, the
literal source tool `reprozip`, source version, snapshot scope, and one
`REPROZIP_METADATA_JSON` payload with a lowercase SHA-256. Both files are
regular files opened without following links; the payload path is relative to
the manifest directory and cannot escape it. Manifest input is limited to 64
KiB and payload input to 1 MiB. Payload JSON is syntax-checked only. It does
not establish a traced run, package completeness, environment availability,
or reproducibility.

## Prioritized reuse queue

These are evaluated upstream sources, not current dependencies or capabilities.
They enter `third_party/sources.lock.yaml` only with a frozen commit, an
adopted boundary, an attribution notice when code is distributed, and an
adversarial fixture.

| Source | Frozen observation | Candidate bounded use | Explicitly excluded |
| --- | --- | --- | --- |
| [fclones](https://github.com/pkolaczk/fclones) | MIT, 2,850 stars, `a74f90d293e05856d19a4c0ac2b29b46ef16cf23` | If profiling shows need, borrow staged size/prefix/full-hash candidate ordering for large local duplicate sets. | Deletion, linking, copying, cross-device actions, and any semantic retention judgment. |
