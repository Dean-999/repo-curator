# Release Validation

This record captures black-box release validation on frozen public repository
commits. Each target was fetched into a temporary directory, audited through
the normal read-only command, and passed through `export-ro-crate`. No target
installation, test, workflow, notebook, hook, package-manager, container, or
project command was run. Temporary paths are intentionally not release
artifacts; the source URL and immutable commit are the reproducible identity.
The expanded validation set used fresh depth-one Git repositories with system
and global configuration disabled, interactive credentials disabled, tags
excluded, and hooks directed to an empty path. Both the checked-out commit and
tree were matched to the committed snapshot descriptor before audit. The
resulting `GIT_SHALLOW_REPOSITORY_HISTORY_INCOMPLETE` limitation is intentional:
the Skill records incomplete history coverage and never fetches or deepens the
target.

The portable-bundle smoke check additionally creates a Git repository with a
pattern-matched token present only in an earlier commit, a synthetic Binder
environment with `environment.yml` and a hostile `postBuild`, plus a notebook
containing side-effecting source and a secret-bearing output. A release passes
only when the bundled Skill reports the historical token category, commit, and
path without persisting its value or validating it online; emits the expected
`COMPUTATIONAL_ENVIRONMENT` observation; records `BINDER` scope; emits a
content-free `NOTEBOOK` envelope; keeps the notebook secret absent; observes a
Data Package containing local, credential-bearing remote, and inline resources;
links only the local inventory path while keeping the remote URI and inline
value absent from every run output; verifies
every audit-output hash; and does not execute the build instruction, notebook,
or any target Python file. The same portable-bundle check stages a file larger
than 500 KiB, replaces a committed symlink with an equal-content regular file,
and inventories a broken symlink; release passes only when bounded hygiene
evidence reports all three without granting cleanup authority. CI separately
verifies that over-budget Git output
terminates the subprocess, truncated output is not parsed, and blocked stdin
cannot bypass the command timeout.

The release check also requires a create-once upstream-review receipt produced
against the current source-lock SHA-256 no more than 90 days before the release
timestamp. Review candidates and metadata limitations never update the lock;
they remain manual shadow-review inputs.

The synthetic release audit also verifies curation brief v3 publication. The
brief's declared experiment-chain section is a bounded projection of
inventory-resolved relationship v2 edges, retains manifest evidence IDs and
`DECLARED_LINEAGE_NOT_EXECUTION_VERIFIED`, and keeps
`execution_authorized: false`. Missing declared paths remain reproducibility
gaps rather than invented edges.

The same brief exposes bounded canonical-result candidate and reproducibility-
gap review projections with original evidence IDs and limitations. Candidate
status is not canonical confirmation, gaps are not reproduction verdicts, and
the report retains explicit omitted counts.

Reproducibility gap v2 records in the synthetic audit resolve their supporting
evidence IDs to the local experiment manifest's inventory evidence. This is a
declaration-source integrity check, not execution or reproducibility evidence.

| Repository | Frozen commit | Family | Audit outcome | Observed adapter boundary |
| --- | --- | --- | --- | --- |
| [climlab](https://github.com/climlab/climlab) | `fcbde377d131d98b05e2e9d0729d9a22ec60bd18` | Climate process modeling | 248 artifacts; `COMPLETED_WITH_LIMITATIONS`; RO-Crate export verified | No supported marker present. Git and bounded Python observations remained coverage-limited. |
| [nf-core/rnaseq](https://github.com/nf-core/rnaseq) | `1f03b53ef799e298f60c813440e961e867017043` | Bioinformatics workflow | 1,107 artifacts; `COMPLETED_WITH_LIMITATIONS`; RO-Crate export verified | `NEXTFLOW` and `RO_CRATE` emitted only `DECLARATION_PRESENCE_ONLY` observations. |
| [DeepXDE](https://github.com/lululxvi/deepxde) | `0ffcbed84c38146a61650b92a094dd855a14d1f4` | Physics-informed scientific ML | 347 artifacts; `COMPLETED_WITH_LIMITATIONS`; RO-Crate export verified | No supported marker present. Git and bounded Python observations remained coverage-limited. |
| [Scanpy](https://github.com/scverse/scanpy) | `27bba90ce019b0d85d71211f2c8f9098da4b2806` | Single-cell bioinformatics | 1,432 artifacts; `COMPLETED_WITH_LIMITATIONS`; 25 output hashes and RO-Crate export verified | Root `pyproject.toml` emitted one `COMPUTATIONAL_ENVIRONMENT` presence-only observation; environment content and availability were not evaluated. |
| [Psi4](https://github.com/psi4/psi4) | `a260858888381d2764bcf54ac41ad24620eb1b10` | Quantum chemistry | 11,447 artifacts; `COMPLETED_WITH_LIMITATIONS`; 25 output hashes and RO-Crate export verified | Root `environment.yml` remained presence-only. `codemeta.json` was syntax checked with allowlisted structure only; its context, schema, values, and semantics were not resolved. |
| [SciMLBenchmarks.jl](https://github.com/SciML/SciMLBenchmarks.jl) | `8cb51bd2810fcf0561c04c60f6a5af99cb52d112` | Scientific ML benchmarks | 344 artifacts; `COMPLETED_WITH_LIMITATIONS`; 25 output hashes and RO-Crate export verified | Root `Project.toml` emitted one `COMPUTATIONAL_ENVIRONMENT` presence-only observation; environment content and availability were not evaluated. |

The supplied-export gate also covers a synthetic Workflow Run RO-Crate payload
bound to the fixed `repo-curator.workflow-run-ro-crate-export-manifest.v1`
contract. It exercises completed and failed `CreateAction` declarations,
JSON-LD `@id` status forms, unresolved inputs, malformed roots, schema/family
mismatch rejection, path containment, payload hashing, and the no-target-code
execution boundary. The observer is bounded to 256 entities, 512 graph
references, 128 actions, 64 inputs/outputs, and 8 instruments per action.
The audit-level supplied-export count is capped at 16, and malformed action
references remain counted limitations. Invalid roots are reported as declaration
graph unavailable rather than validated.
These records remain declaration-only and do not establish profile conformance,
execution, reproduction, or scientific validity.

The original three validation records retained only non-executable review
recommendations. The expanded three runs observed 13,223 artifacts and produced
12,085 `MANUAL_REVIEW` plus 1,138 preserved
`REVIEW_EXACT_DUPLICATE` recommendations. Their shadow plans contained no action
candidates and every curation brief recorded `execution_authorized: false`.

A second audit of the same expanded repositories at the same frozen commits
separated deterministic directory preservation from unresolved evidence. It
changed exactly 2,215 limitation-retaining `PROTECTED` directories from
`MANUAL_REVIEW` to non-executable `KEEP`, reducing `MANUAL_REVIEW` from 12,085
to 9,870 (18.33 percent) while retaining 1,138
`REVIEW_EXACT_DUPLICATE` recommendations. Artifact counts, classification
states, classification limitations, and exact-duplicate recommendations were
unchanged. The six Git-control boundary directories, eleven symlinks, and all
unresolved regular files remained `MANUAL_REVIEW`; all action-candidate and
executable-recommendation counts remained zero. This is review-queue noise
reduction, not evidence of semantic accuracy or scientific dispensability.

A third audit separated absence-only abstention from material review attention.
It changed exactly 9,853 regular files whose complete classification-limitation
set was `NO_MAINLINE_EVIDENCE` plus `NO_ROLE_EVIDENCE` from `MANUAL_REVIEW` to
non-executable `KEEP`. These files remain `UNRESOLVED`, preservation-required,
and explicitly limited, and their recommendations add `PRESERVE_UNRESOLVED`.
The expanded set now contains 12,068 `KEEP`, 17 `MANUAL_REVIEW`, and 1,138
`REVIEW_EXACT_DUPLICATE` recommendations. The 17 retained review items are six
Git-control boundary directories and eleven symlinks with inventory coverage
limitations. Artifact counts, classification states, classification
limitations, duplicate recommendations, action candidates, and executable
recommendations again remained unchanged. `KEEP` here means conservative
in-place preservation without a supported treatment decision; it does not
establish research value, semantic role, availability, or dispensability.

A fourth audit emitted `repo-curator.classification.v2` and bound local
declaration markers to their exact declaration evidence. Exactly four paths
changed state: Scanpy `pyproject.toml`; Psi4 `codemeta.json` and
`environment.yml`; and SciMLBenchmarks `Project.toml`. Every new
`DECLARATION_EVIDENCE` classification referenced one `DECLARED`/
`DECLARATION` evidence record and retained its declaration and role-coverage
limitations. Recommendation counts and the 17 material review items were
unchanged; no classification lacked supporting evidence, and action-candidate
and executable-recommendation counts remained zero. A hostile supplied export
fixture could not assign the new state. A separate N-1 fixture retained v1
classification bytes unchanged during prior-run comparison while the new run
emitted v2; no historical classification was migrated or rewritten. A
duplicate-marker regression additionally preserved `EXACT_DUPLICATE_REVIEW`
while retaining the marker's declaration evidence.

A synthetic experiment-manifest regression exposed and corrected a historical
referential-integrity defect: v1 attempt, bundle, and canonical-candidate
records placed the manifest artifact ID in `supporting_evidence_ids`. New v2
records instead reference the manifest's inventory evidence ID, and every link
is resolved against `evidence.jsonl` in the black-box scenario. A defensive
fixture withholds that internal evidence mapping and confirms the audit fails
closed rather than publishing an empty link or relabelling an artifact ID.
Historical v1 bytes are not migrated. This correction adds no experiment run,
scientific-validity, or reproducibility claim.

The same synthetic scenario now emits ten `repo-curator.relationship.v2`
declared attempt-member edges for inventory-resolved output, input,
configuration, generator, validation, and reviewer-record paths. The declared
missing input emits no entity or edge and remains a reproducibility gap. Every
edge resolves its manifest supporting evidence and carries
`DECLARED_LINEAGE_NOT_EXECUTION_VERIFIED`. Exact-byte relationships use the v2
`ARTIFACT_GROUP` shape and retain their prior review behavior. These edges are
review projections of local manifest text, not PROV activities or proof that an
experiment ran.

All six runs withheld scientific validity, successful reproduction, semantic
equivalence, canonical-result, complete-history, and file-movement claims.
`INTENT_UNRESOLVED`, shallow or bounded Git history, parser limits, and broad
Git co-change limits remained explicit rather than becoming positive findings.

This is release hardening evidence, not an accuracy study or mutation-admission
claim. Formal semantic and mutation claims remain governed by the separate
evaluation protocol and corpus gates.
