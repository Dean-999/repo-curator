# Third-Party Notices

repo-curator distributes ten bounded source adaptations identified below, and
no upstream binaries or runtime dependencies. The remaining projects are
recorded because their public formats, documentation, and safety patterns
informed repo-curator contracts.
The exact reviewed commits, integration modes, exclusions, and regression
fixtures are bound in `third_party/sources.lock.yaml`.
The complete license texts required for these distributed adaptations are
bundled under `third_party/licenses/`.

## dvc

DVC is available under Apache-2.0. repo-curator recognizes selected declaration
markers and borrows explicit retention-scope discipline. It does not execute or
distribute DVC.

## datalad

DataLad is available under the MIT License, with additional upstream notices
for code distributed by DataLad itself. repo-curator recognizes `.datalad/config`
and borrows declared-record and content-availability distinctions. It does not
execute or distribute DataLad or git-annex.

## mlflow

MLflow is available under Apache-2.0. repo-curator independently recognizes a
root `MLproject` marker as declaration-only evidence. It does not parse the
project, resolve an entry point or environment, contact a tracking server, or
execute or distribute MLflow.

## sacred

Sacred is available under the MIT License. repo-curator independently recognizes
co-located `config.json` and `run.json` files and performs bounded JSON syntax
checks. It does not start an observer, copy sources, retrieve artifacts,
interpret run semantics, or execute or distribute Sacred.

## bagit-python

bagit-python identifies itself as public domain in its package classifier but
does not provide a standalone license text, so the source lock records
`NOASSERTION` rather than inferring an SPDX license. repo-curator independently
recognizes `bagit.txt` presence only. It copies no upstream code and does not
parse tags, hash manifests, fetch payloads, create bags, or validate bags.

## renku-python

Renku Python is available under Apache-2.0. repo-curator independently
recognizes the upstream `.renku` project directory marker. It does not read the
metadata database, migrate metadata, install Git hooks, contact Renku services,
or execute or distribute Renku.

## noworkflow

noWorkflow is available under the MIT License. repo-curator independently
recognizes the upstream `.noworkflow` provenance directory marker. It does not
open its database or content store, collect provenance, restore trials, execute
target scripts, or distribute noWorkflow.

## showyourwork

showyourwork is available under the MIT License. repo-curator independently
recognizes the root `showyourwork.yml` user configuration marker. It does not
render Jinja, parse YAML, access Zenodo, compile LaTeX, invoke Snakemake, or
execute or distribute showyourwork.

## snakemake

Snakemake is available under the MIT License. repo-curator recognizes standard
Snakefile locations as declaration-only evidence. It does not execute or
distribute Snakemake.

## nextflow

Nextflow is available under Apache-2.0. repo-curator recognizes standard
Nextflow declaration markers. It does not evaluate configuration or execute or
distribute Nextflow.

## repo2docker

repo2docker is available under the BSD 3-Clause License. Copyright 2017-2026
Project Jupyter Contributors. repo-curator adapts environment marker selection
and `binder`/`.binder` scope precedence from the buildpack modules at commit
`f90d7e9b2f9bc8fb9fbccf916afa512a460eac3d` into
`repo_curator/environment_declarations.py`. The port reads inventory paths
only. It does not parse dependency files, resolve or install packages, build
images, start containers, or execute `postBuild`, `start`, `install.R`,
Dockerfiles, Nix expressions, or any other target instruction.

BSD 3-Clause License

Copyright (c) 2017, Project Jupyter Contributors
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.
* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.
* Neither the name of the copyright holder nor the names of its contributors
  may be used to endorse or promote products derived from this software without
  specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR
ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

## nbformat

nbformat is available under the BSD 3-Clause License. Copyright 2001-2015 the
IPython Development Team and 2015-2026 the Jupyter Development Team.
repo-curator adapts JSON notebook-envelope parsing and explicit version
observation from `nbformat/reader.py` and `nbformat/v4/nbjson.py` at commit
`4421827289087d37e57ee770e115a13db9a45dd5` into
`repo_curator/notebook_envelope.py`. The port does not construct NotebookNode
objects, validate schemas, convert versions, retain cell source or output data,
load widgets, trust outputs, start kernels, or execute notebooks. The complete
upstream license is bundled at
`third_party/licenses/BSD-3-Clause-nbformat.txt`.

## ro-crate-py

RO-Crate Python is available under Apache-2.0. repo-curator follows public
RO-Crate profile concepts and adapts descriptor/root validation and entity-index
behavior from `rocrate/metadata.py` at commit
`05effe591443934e48e3fe59c53d7bc01a3334e0` into
`repo_curator/ro_crate_graph.py`. The adaptation is dependency-free, bounded,
and local-only. It excludes upstream network retrieval, mutable entity models,
profile-conformance authority, payload access, and workflow execution.

## reprozip

ReproZip is available under BSD-3-Clause. repo-curator accepts only an
explicitly supplied, SHA-256-bound metadata JSON export under its own strict
contract. It does not execute or distribute ReproZip, unpack a package, trace
processes, install an environment, retrieve remote content, or reproduce a run.

## frictionless-py

Frictionless Framework is available under the MIT License. Copyright 2020 Open
Knowledge Foundation. repo-curator adapts package/resource field selection and
local resource-path structure from `frictionless/package/package.py` and
`frictionless/resource/resource.py` at commit
`52ec5477f07612639b1505edc669128ce5e49a30` into
`repo_curator/data_package.py`. The port observes at most 128 resources and 16
paths per resource from an already bounded, syntax-valid `datapackage.json`.
It does not retain remote URLs or inline data, open resource payloads, validate
schemas, parse dialects, infer formats, dereference descriptors, load plugins,
publish packages, access the network, or execute target code. The complete
upstream license is bundled at
`third_party/licenses/MIT-frictionless-py.txt`.

## gitleaks

Gitleaks is available under the MIT License. Copyright 2019 Zachary Rice.
repo-curator adapts a narrow set of fixed-format GitHub token, AWS access-key,
JWT, and private-key envelope patterns from the rule generators at commit
`b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b` into
`repo_curator/secret_redaction.py`. The same local classifier is used by a
separately implemented, read-only scan of changed blobs in the newest 100 Git
commits. That traversal borrows Gitleaks' history-source idea but replaces its
diff scan with validated object IDs, literal paths, and hard path, blob, byte,
and finding budgets. Reports retain only category, commit ID, and repository-
relative path. The port does not score entropy, retain values, snippets,
fingerprints, or line content, validate credentials, access a remote service,
or execute target code. The complete upstream license is bundled at
`third_party/licenses/MIT-gitleaks.txt`.

## git-sizer

git-sizer is available under the MIT License. Copyright 2018 GitHub.
repo-curator adapts repository-size metric categories, five reference scales,
and the `value / scale` concern model from `sizes/sizes.go` and
`sizes/output.go` at commit
`88eaa80df48db1b47291f3a43b084b8c79082339` into
`repo_curator/git_repository_size.py`. The port consumes only compact,
timeout- and output-capped Git results plus the existing inventory. It does not
traverse every reachable object, emit ref names, read historical file/blob
content, build an unbounded graph, access a remote, rewrite history, or
authorize cleanup. Object-database counts may include unreachable objects or
alternates, and concern ratios are context rather than action thresholds. The
complete upstream license is bundled at
`third_party/licenses/MIT-git-sizer.txt`.

## pre-commit-hooks

pre-commit-hooks is available under the MIT License. Copyright 2014 the
pre-commit dev team, Anthony Sottile, and Ken Struys. repo-curator adapts the
default 500 KiB staged-add threshold and destroyed-symlink Git mode test from
`check_added_large_files.py` and `destroyed_symlinks.py` at commit
`4189d189e039fd49eb235357c9d9977b026c6c8e` into
`repo_curator/repository_hygiene.py`. Its descriptor-relative scanner already
implements the broken-link condition from `check_symlinks.py` without following
the target. The bounded port retains at most 256 findings and never installs or
executes a hook, mutates the index or filesystem, compares blob content,
evaluates `.gitattributes` or LFS filters, rejects a commit, executes target
code, or authorizes cleanup. A differing blob ID remains an explicit mode-change
candidate. The complete upstream license is bundled at
`third_party/licenses/MIT-pre-commit-hooks.txt`.

## citation-file-format

Citation File Format is available under CC-BY-4.0. repo-curator independently
recognizes a root `CITATION.cff` as declaration-presence evidence. It does not
open or parse the YAML, validate the schema, retain citation values, convert
formats, execute target code, or distribute Citation File Format code.

## codemeta

CodeMeta is available under Apache-2.0. Its public vocabulary constrains the
field-name allowlist used for a bounded `codemeta.json` structural observation.
repo-curator records allowed field names and selected declared cardinalities,
but never persists values, resolves JSON-LD contexts, validates a schema,
retrieves remote content, executes target code, or distributes CodeMeta code.

## signac

signac is available under the BSD 3-Clause License. Copyright 2016-2026 The
Regents of the University of Michigan. repo-curator adapts the project config,
project document, statepoint cache, statepoint, and job document filename
constants from `signac/_config.py`, `signac/project.py`, and `signac/job.py` at
commit `9419e3c71900bbbd6a4a177ac91ae895d1290b2d` into
`repo_curator/research_metadata.py`. The port only counts regular-file markers
already present in the bounded inventory and retains at most 256 marker IDs and
paths. It does not read signac metadata, discover outside the selected root,
migrate a project, import or export data, import signac, or execute target code.
The complete upstream license is bundled at
`third_party/licenses/BSD-3-Clause-signac.txt`.

## workflow-run-ro-crate

Workflow Run RO-Crate is available under Apache-2.0. repo-curator adapts the
`CreateAction`, `instrument`, `object`, `result`, and `actionStatus` field model
from the 0.5 profile at commit
`4add9f64a49d8c6a79cb34f146b35b887a60852d` into
`repo_curator/workflow_run_crate.py`. The port observes one explicitly supplied,
SHA-256-bound JSON document under hard entity, action, input, and output limits.
It does not claim profile conformance, resolve contexts or payloads, generate or
rewrite crates, verify execution, access a remote, or execute a workflow. The
complete Apache-2.0 license text is bundled at
`third_party/licenses/Apache-2.0.txt`.

## nf-prov

nf-prov is available under Apache-2.0. repo-curator adapts its mapping of task
inputs to `object`, outputs to `result`, and exit status to completed or failed
`actionStatus` from `WrrocRenderer.groovy` at commit
`97d350065f89d7a98aad8506586b54bce32f1acb`. The Python port reads only an
already-generated, hash-bound JSON export. It removes Nextflow APIs, plugin
loading, task access, file copying, parameter-value persistence, configuration
serialization, and report generation. Imported status remains declaration-only
and is never execution verification. The complete Apache-2.0 license text is
bundled at `third_party/licenses/Apache-2.0.txt`. The locked upstream license
artifact is nf-prov's `COPYING`; the bundled file is the shared unmodified
Apache License 2.0 text used by the Apache-2.0 attributed ports.

## slsa

The SLSA specification is available under the Community Specification License
1.0. repo-curator independently implements the in-toto Statement v1 envelope
and SLSA provenance v1 predicate contract documented at commit
`24905939fd7dab34e670592a12b8c303e8328d0b`. The local record binds one release
artifact to its source commit and tree, bundle manifest, passing release-check
receipt, builder, and invocation. It does not claim that a hosted attestation
or signature exists, establish artifact trust, authorize deployment, or
execute target code. No upstream source code is copied.

## actions-attest-build-provenance

`actions/attest-build-provenance` is available under the MIT License. The
release-attestation workflow invokes the official action at immutable commit
`977bb373ede98d70efdf65b84cb5f73e068dcc2a` only for a GitHub-eligible
repository after downloading an existing tagged release and checking its
published `SHA256SUMS`. User-owned private repositories record an explicit
unavailable state instead of calling the action. No action source is
copied or bundled. The action does not create the release, tag, checksums, or
repo-curator's local provenance record, and it never receives a target
research repository.

## w3c-shacl

The W3C Shapes Constraint Language materials are available under the W3C
Software and Document License. repo-curator uses the public node/property shape
model documented at commit `eedda09f93c39be1d2e978f3f942631494ae25a0` to
publish an independently authored evidence-export shape. The dependency-free
runtime checks only a bounded local structural subset. It does not copy an
upstream implementation or shape, run a general RDF/SHACL engine, resolve
JSON-LD contexts, retrieve remote graphs, claim complete SHACL conformance,
establish scientific validity, or grant execution authority.

## restic

restic is available under BSD-2-Clause. Its documented retention and
maintenance security distinctions inform repo-curator policy. repo-curator
does not copy or distribute restic.

## borg

BorgBackup is available under BSD-3-Clause. Its documented transaction, lock,
integrity, and commit concepts inform repo-curator safety design. repo-curator
does not copy or distribute BorgBackup.

## rmlint

rmlint is available under GPL-3.0-only. repo-curator borrows only the general
candidate-grouping and review pattern. No rmlint source code is copied, linked,
vendored, or distributed, and rmlint is not a runtime dependency.
