# Reference design sources

repo-curator borrows safety and evidence-contract concepts, not execution
authority, from the following official project documentation:

The implementation-facing source locks, licenses, adopted boundaries, and
explicit exclusions are maintained in [the upstream adoption register](upstream-adoption.md).

- [git-annex required content](https://git-annex.branchable.com/git-annex-required/)
  and [drop safety](https://git-annex.branchable.com/git-annex-drop/) motivate
  hard retention requirements and availability proof before local removal.
- [DVC garbage collection](https://docs.dvc.org/command-reference/gc) motivates
  explicit scope and the union of references across retained repository views.
- [DataLad run records](https://handbook.datalad.org/en/latest/basics/101-108-run.html)
  motivate machine-readable declared generation records. Repo-curator imports
  such records as declarations and never invokes `run` or `rerun`.
- [MLflow project discovery](https://github.com/mlflow/mlflow/blob/6f96bf7a53c192479e3b0bae89ca716c0200dbe9/mlflow/projects/_project_spec.py)
  defines the case-insensitive `MLproject` marker; repo-curator records only its
  root presence and never parses its YAML or executes an entry point.
- [Sacred file storage](https://github.com/IDSIA/sacred/blob/86865b03d05e83da35ca582392ca31777db88d11/sacred/observers/file_storage.py)
  establishes paired `config.json` and `run.json` records. repo-curator performs
  bounded syntax checks without treating them as proof of a valid or completed run.
- [BagIt RFC 8493](https://www.rfc-editor.org/rfc/rfc8493) and
  [bagit-python](https://github.com/LibraryOfCongress/bagit-python/blob/4bd2713cedbe1f8e634567c20ef0dded9622011d/src/bagit/__init__.py)
  establish required `bagit.txt` presence. repo-curator does not validate tags,
  manifests, payloads, or fetch references.
- [Renku project constants](https://github.com/SwissDataScienceCenter/renku-python/blob/b2418a15c89e16e4442a1ecf11f703f4e15922e8/renku/core/constant.py)
  define `.renku` as the project directory. repo-curator observes only that
  directory and intentionally rejects unrelated root `renku.yaml` files.
- [noWorkflow persistence configuration](https://github.com/gems-uff/noworkflow/blob/4a2c4c8bdea2be73570a1aa598042940f4f4270f/src/noworkflow/now/persistence/config.py)
  defines `.noworkflow` as the provenance path. Its database and content store
  remain opaque to repo-curator.
- [showyourwork configuration](https://github.com/showyourwork/showyourwork/blob/212422b622ffa05a7aaeda20f7ef3fbcd865a015/src/showyourwork/config.py)
  defines `showyourwork.yml`; repo-curator records marker presence without
  rendering templates, parsing YAML, or invoking the workflow.
- [RO-Crate profiles](https://www.researchobject.org/ro-crate/specification/1.2/profiles.html)
  motivate versioned profile URIs and the distinction between an intended
  conformance assertion and successful validation.
- [RO-Crate Python metadata handling](https://github.com/ResearchObject/ro-crate-py/blob/05effe591443934e48e3fe59c53d7bc01a3334e0/rocrate/metadata.py)
  supplies the attributed local-only model for indexing declared `@graph`
  entities and checking a metadata descriptor's Dataset root. The bounded port
  does not use upstream network reads, mutable entities, or profile validation.
- [Frictionless Framework Package and Resource descriptors](https://github.com/frictionlessdata/frictionless-py/tree/52ec5477f07612639b1505edc669128ce5e49a30/frictionless)
  supply the MIT-attributed package/resource field selection used by the
  bounded `datapackage.json` observer. The port caps descriptors at 128
  resources and 16 paths per resource, retains no remote or inline values, and
  never opens a resource, parses a schema or dialect, loads a plugin, infers a
  format, dereferences an identifier, or accesses the network.
- [Citation File Format](https://github.com/citation-file-format/citation-file-format/tree/0c5b4aa07071490eaf261775ce96ccdd13a6e2d5),
  [CodeMeta](https://github.com/codemeta/codemeta/tree/0bc1f26d9575c9bfc288571b358a24a464595443),
  and [signac](https://github.com/glotzerlab/signac/tree/9419e3c71900bbbd6a4a177ac91ae895d1290b2d)
  supply stable research-software metadata names and vocabulary. repo-curator
  recognizes CFF presence, retains only allowlisted CodeMeta structure, and
  adapts signac filename constants into bounded inventory counts. It does not
  parse CFF/signac content, retain metadata values, resolve JSON-LD, or import
  and execute any upstream package.
- [repo2docker buildpack marker selection](https://github.com/jupyterhub/repo2docker/blob/f90d7e9b2f9bc8fb9fbccf916afa512a460eac3d/repo2docker/buildpacks/base.py)
  supplies the attributed inventory-only model for environment marker names and
  `binder`/`.binder` scope precedence. The bounded port never parses a
  dependency declaration, builds an image, starts a container, or executes a
  target build instruction.
- [nbformat notebook reading](https://github.com/jupyter/nbformat/blob/4421827289087d37e57ee770e115a13db9a45dd5/nbformat/reader.py)
  supplies the attributed pattern for JSON parsing and explicit notebook
  version observation. The bounded port does not validate or convert versions,
  construct NotebookNode objects, retain cell/output content, or start a kernel.
- [Gitleaks fixed-format rules](https://github.com/gitleaks/gitleaks/tree/b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b/cmd/generate/config/rules)
  supply the attributed high-confidence patterns used to replace selected
  provider tokens, JWTs, and private-key envelopes before persistence.
  [Its Git source design](https://github.com/gitleaks/gitleaks/blob/b58d3f102cf3a2c84cb7f923d05c25c9b1aed84b/sources/git.go)
  also informs a separately implemented recent-changed-blob scan. repo-curator
  replaces the upstream diff traversal with validated object IDs, literal path
  arguments, and hard budgets. It excludes entropy scoring, full-history diff
  scanning, secret-value reporting, and credential validation.
- [git-sizer repository metrics](https://github.com/github/git-sizer/tree/88eaa80df48db1b47291f3a43b084b8c79082339/sizes)
  supply the attributed metric categories, selected reference scales, and
  value-to-scale context ratios used by the bounded Git size summary. The port
  does not construct the upstream reachable-object graph, emit ref names,
  read historical file/blob content, access remotes, or recommend history rewriting.
- [pre-commit-hooks repository hygiene checks](https://github.com/pre-commit/pre-commit-hooks/tree/4189d189e039fd49eb235357c9d9977b026c6c8e/pre_commit_hooks)
  supply the attributed 500 KiB staged-add threshold, broken-link condition,
  and destroyed-symlink mode transition. repo-curator retains bounded evidence
  only and excludes hook execution, blob comparison, LFS-attribute evaluation,
  repair commands, index mutation, commit rejection, and cleanup authority.
- [Borg repository transactions and locks](https://borgbackup.readthedocs.io/en/stable/internals/data-structures.html)
  motivate exclusive mutation locks, integrity metadata, and explicit commit
  records.
- [restic append-only security](https://restic.readthedocs.io/en/latest/060_forget.html#security-considerations-in-append-only-mode)
  motivates separating ordinary writers from destructive maintenance
  authority and avoiding false append-only claims for local `O_APPEND` files.

No target repository command from these systems is executed automatically.
Their declarations remain untrusted, coverage-limited evidence.
