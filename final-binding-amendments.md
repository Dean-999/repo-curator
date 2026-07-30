# Final Binding Amendments

The following requirements are binding and override any conflicting wording
elsewhere in this prompt.

Do not expand the V1 product scope beyond these amendments.

# A. Plan-content integrity and approval binding

Approval must be bound to the exact bytes of one specific `plan.json`, not
only to a human-readable plan ID.

Define and require at least:

- plan_id;
- plan_sha256;
- approval_id;
- approved_plan_id;
- approved_plan_sha256;
- approval_created_at;
- approving_actor or reviewer identity representation;
- approval_schema_version.

The plan hash must be calculated from the exact stored bytes of `plan.json`
using SHA-256.

The approval file may reference only action IDs and recommendation IDs already
present in that exact hashed plan.

Before apply validation, the system must:

1. read `plan.json`;
2. calculate its current SHA-256;
3. compare it with `approved_plan_sha256`;
4. compare its internal `plan_id` with `approved_plan_id`;
5. reject the operation if either comparison fails.

A matching `plan_id` with a different plan hash must be treated as a different
and unapproved plan.

An approval document must not be edited in place after use. A changed approval
must receive a new `approval_id`.

The PRD must define whether plan and approval files become logically immutable
after creation, and how superseded approvals are represented without deleting
or overwriting their history.

# B. Artifact identity model

The PRD must define separate identities for content, location, inventory
instance, and cross-run lineage.

At minimum define:

## artifact_id

Identifies one concrete artifact instance observed during one inventory run.

An artifact instance may be:

- a filesystem file;
- a directory;
- a symbolic link;
- a Git LFS pointer;
- an archive;
- an archive member;
- a submodule entry;
- another explicitly modeled filesystem object.

`artifact_id` is scoped to the inventory run and must not be assumed stable
after a move, rename, replacement, or later audit.

## content_id

Identifies byte-equivalent content.

For regular files, it should normally be derived from a cryptographic content
hash plus the hashing scheme version.

Artifacts with identical bytes may share one `content_id` while retaining
different `artifact_id` and `location_id` values.

For directories, archives, and compound artifacts, define whether `content_id`
uses:

- a byte hash;
- a normalized member manifest hash;
- a directory Merkle fingerprint;
- another explicit deterministic representation.

Different fingerprint types must never be silently compared as equivalent.

## location_id

Identifies the location at which an artifact was observed.

It must distinguish:

- repository-relative filesystem paths;
- symlink locations;
- archive-member paths;
- submodule locations;
- quarantine locations;
- archive destinations.

A ZIP member and a filesystem file with identical content must have different
`location_id` values.

## lineage_id

Identifies a logical artifact across audits when evidence supports continuity
through moves, renames, packaging, unpacking, or regeneration.

Lineage must be evidence-backed and may be:

- confirmed;
- strongly inferred;
- weakly inferred;
- unresolved.

Matching content alone must not always imply identical lineage.

The PRD must explain how these identities support:

- exact duplicate detection;
- rename and move tracking;
- archive-member comparison;
- rollback;
- cross-run comparison;
- canonicalization;
- packaged and unpacked relationships;
- replacement detection.

Never overload one ID to represent all four concepts.

# C. Resource-exhaustion and parser-safety model

Repository scanning must be resource-bounded.

The PRD must define explicit configurable defaults, hard safety ceilings, and
failure behavior for every supported parser.

Do not leave limits as TBD.

At minimum define budgets for:

- maximum individual file size eligible for content profiling;
- maximum bytes read from a text or Markdown file;
- maximum bytes read from the head and tail of a log;
- maximum CSV bytes scanned;
- maximum CSV records sampled;
- maximum CSV field length;
- maximum JSON nesting depth;
- maximum JSON bytes parsed;
- maximum PDF size;
- maximum PDF pages inspected;
- maximum PDF extracted-text bytes;
- per-file parsing timeout;
- total audit time budget;
- total generated-report size;
- maximum number of artifacts;
- maximum number of relationships;
- maximum document-comparison candidate count.

When a limit is exceeded, the artifact must remain in inventory and receive
structured evidence such as:

- PROFILE_SKIPPED_SIZE_LIMIT;
- PROFILE_TRUNCATED;
- PROFILE_TIMEOUT;
- UNSUPPORTED_FORMAT;
- RESOURCE_LIMIT_REACHED.

Exceeding a profiling budget must not silently make the artifact look empty or
unimportant.

## Archive safety

Archive inspection must not extract archive contents into the repository.

V1 deep archive inspection supports ZIP only. ZIP files may receive bounded
member listing, metadata inspection, safe content sampling, and normalized
member-manifest comparison under the limits below.

Other archive and container formats, including TAR, compressed TAR variants,
7z, and RAR, must be inventoried as opaque artifacts. V1 may record safely
available filesystem metadata and whole-file hashes for them, but must not
enumerate, extract, decompress, or semantically compare their members. An
unsupported format must produce explicit `UNSUPPORTED_FORMAT` evidence and
must not be interpreted as empty, disposable, or equivalent to an unpacked
directory.

The PRD must define explicit limits for:

- archive file size;
- number of members;
- nested archive depth;
- cumulative declared uncompressed size;
- cumulative bytes actually read;
- maximum member name length;
- maximum individual member size;
- compression ratio;
- archive parsing time;
- number of members eligible for content sampling.

The system must detect and reject or safely stop on:

- archive-member path traversal;
- absolute member paths;
- `..` path components;
- drive-letter or UNC paths;
- symbolic-link members escaping the virtual archive root;
- abnormal compression ratios;
- contradictory or malformed archive metadata;
- deeply nested archives;
- archive bombs;
- duplicate member names where order affects interpretation.

Encrypted archives must not be brute-forced or decrypted.

For encrypted archives, report only safely available metadata, limitations,
and the need for manual review.

Nested archives must not be recursively expanded without an explicit bounded
policy.

Archive comparison must distinguish:

- byte-identical archives;
- archives with equivalent normalized member content;
- archives with identical filenames but different member bytes;
- unpacked directories that appear equivalent;
- archives whose comparison is incomplete because limits were reached.

## Parser safety

Do not load unsafe serialized formats such as pickle, joblib, executable
notebooks, model checkpoints, or arbitrary language objects.

Treat them as opaque artifacts unless a safe metadata-only parser is
explicitly defined.

Parser errors and timeouts must be isolated per artifact so one malicious or
corrupt file cannot terminate the entire audit.

# D. Git as an untrusted execution boundary

The target repository's Git configuration, attributes, hooks, aliases,
filters, pagers, diff drivers, text conversion commands, filesystem monitors,
and LFS behavior must be treated as untrusted.

The PRD must define a sanitized Git invocation policy.

At minimum:

- disable Git pagers;
- do not invoke repository-defined aliases;
- disable or override external diff commands;
- disable textconv;
- disable hooks;
- disable or override `core.fsmonitor`;
- do not trigger clean, smudge, or process filters;
- do not download Git LFS objects;
- do not run Git LFS commands supplied by the repository;
- do not perform checkout, reset, add, commit, merge, rebase, clean, or other
  Git operations that can transform working-tree content during audit;
- do not execute repository credential helpers;
- do not invoke user-configured interactive tools;
- use an allowlist of required read-only Git or Git-plumbing operations;
- use explicit environment variables and command-line configuration overrides
  rather than trusting repository defaults;
- record every Git command category used by the design.

Git LFS pointer files must be treated as pointer text unless the referenced
object is already safely present and can be read without invoking filters,
network access, or LFS download behavior.

The PRD must explain how it safely determines:

- repository root;
- Git HEAD;
- tracked changes;
- untracked paths;
- ignored but explicitly included scientific artifacts;
- submodules;
- linked worktrees;
- worktree administrative locations;
- Git LFS pointers;

without causing repository-defined code execution.

Failure to establish a sanitized Git environment must stop Git-dependent
analysis and produce an explicit limitation. It must not silently fall back to
unsafe Git execution.

# E. Protected paths and managed destinations

Define protected paths that must never receive executable MOVE, ARCHIVE,
QUARANTINE, RENAME, RELOCATE, or future DELETE actions, except for the narrow,
plan-bound quarantine destination and rollback exception defined below.

At minimum protect:

- `.git/`;
- Git administrative directories and files;
- `.repo-curator/`, except for an approved QUARANTINE destination under
  `.repo-curator/quarantine/<matching-plan-id>/` and its validated rollback
  operation;
- `.agents/skills/repo-curator/`;
- the currently executing Skill directory;
- the currently executing script directory;
- submodule root directories;
- submodule Git administrative paths;
- linked-worktree administrative paths;
- any path outside the repository root;
- any path resolved outside the repository root through a symlink;
- active plan, approval, journal, rollback, or verification files.

The PRD must define how protected paths are discovered when the Skill is
installed at user level rather than repository level.

Protected paths may appear in inventory and reports, but no executable action
may target, replace, relocate, or delete them outside the narrow quarantine
exception.

`.repo-curator/` is a protected control area with one narrow exception:

- `.repo-curator/quarantine/<plan-id>/` may receive artifacts only as the
  destination of an approved QUARANTINE action belonging to that exact plan;
- an approved rollback may move those artifacts back to their validated
  original locations;
- no MOVE, ARCHIVE, RENAME, RELOCATE, or other action may target any other
  `.repo-curator/` path;
- run records, plans, approvals, journals, rollback files, verification files,
  configuration, and quarantine content belonging to another plan remain
  protected;
- a QUARANTINE action may not target the `.repo-curator/` root or another
  plan's quarantine directory;
- the exception permits only tool-governed payload movement and does not permit
  modification of control records or expansion of approved actions.

## Default quarantine destination

Use:

    .repo-curator/quarantine/<plan-id>/

Quarantine is:

- tool-managed;
- excluded from ordinary repository scans;
- temporary;
- reversible;
- not considered the long-term canonical archive;
- subject to journal and rollback requirements.

The `<plan-id>` component must exactly match the approved plan. The destination
must be derived by the deterministic apply implementation rather than supplied
or modified by `approval.yaml`.

The PRD must define whether quarantined content is copied or moved. For V1,
prefer a reversible move after complete validation, while preserving enough
metadata to restore the original location.

## Default archive destination

Use:

    archive/repo-curator/<plan-id>/

Archive is:

- user-visible;
- part of the long-term repository structure;
- eligible to be tracked by Git if the user chooses;
- not automatically excluded from future audits;
- organized using stable and collision-safe paths;
- accompanied by provenance identifying the original location, plan ID, and
  move date.

The PRD must define collision handling and must not silently overwrite an
existing archive destination.

Quarantine and archive must never be treated as interchangeable.

# F. Binding transaction and failure strategy

Use the following V1 transaction policy as the default.

## Global behavior

A multi-action apply is not globally atomic.

The complete approved action set must pass pre-validation before the first
action is executed.

Pre-validation success does not guarantee later operations will succeed
because the filesystem may change during execution.

The initial `repository_state_hash` is the pre-apply baseline. After each
completed action, validation must compare the repository with the expected
state produced by applying the journaled prefix of completed actions to that
baseline. Changes caused by verified actions from the same apply run are
expected state transitions and must not be misclassified as repository drift.
Any non-journaled change to a plan-relevant artifact, protected control file,
approved source, approved destination, or configuration remains drift and must
stop execution.

V1 supports only same-filesystem moves. Before execution, compare the source
and destination-parent filesystem identities. If they differ, reject the
action with `CROSS_FILESYSTEM_MOVE_UNSUPPORTED`. V1 must not fall back to
copy-then-delete, streaming copy followed by source removal, or another
cross-filesystem emulation. Destination creation must use a no-overwrite
strategy; a race that makes the destination exist must fail the action rather
than replace existing content.

## Execution order

Actions must use a deterministic order recorded in `plan.json`.

Before each individual action, revalidate the action's critical invariants,
including source identity and destination availability.

## Failure behavior

When any action fails:

1. record the failure in the append-only journal;
2. stop executing all subsequent actions immediately;
3. do not automatically roll back actions that already completed;
4. mark the apply run as PARTIAL_FAILURE;
5. record the exact completed, failed, skipped, and not-started actions;
6. generate a machine-readable rollback plan;
7. generate a human-readable recovery explanation;
8. require explicit user approval before rollback execution.

Automatic rollback is forbidden by default because the repository or
filesystem may have changed after the failure.

## Rollback validation

Before executing any rollback action:

- revalidate the original plan and apply journal;
- verify the rollback destination content hash;
- confirm that the restored source path does not already exist;
- confirm that the source path has not been recreated or modified;
- confirm that the rollback will not overwrite newer content;
- confirm that protected-path rules still hold;
- confirm that repository state has not drifted in a way that makes rollback
  unsafe.

Rollback must never overwrite an existing path.

Rollback must never overwrite or discard later modifications.

When safe rollback cannot be established, generate MANUAL_RECOVERY_REQUIRED
rather than forcing restoration.

## Interruption recovery

The journal must allow the system to distinguish:

- action not started;
- action validation started;
- move started;
- destination created;
- source removal completed;
- action verified;
- action failed;
- rollback approved;
- rollback completed.

The PRD must specify how an interrupted move is inspected and reconciled
without assuming that either source or destination is authoritative.

## Idempotency

Re-running apply must:

- recognize actions already verified as complete;
- skip them without repeating the move;
- reject ambiguous partial actions;
- never produce a second copy by accident;
- never overwrite an existing destination;
- require recovery review when journal and filesystem state disagree.

# G. Skill description and invocation wording

Because V1 sets:

    policy:
      allow_implicit_invocation: false

do not describe the `SKILL.md` description as automatically triggering the
Skill from ordinary natural-language requests.

Instead, require a description that:

- clearly states applicability;
- supports discovery in `/skills` or the Skill selector;
- contains useful scope and boundary keywords;
- helps users and Codex understand when explicit `$repo-curator` invocation
  is appropriate;
- does not summarize the full workflow;
- does not imply that the Skill will run implicitly.

Use wording such as:

    Write a precise description beginning with “Use when...” that clearly
    describes applicability and supports discovery in the Skill selector.

Explicit invocation remains:

    $repo-curator

# H. Requirements coverage index

The PRD may combine closely related sections to avoid repetitive prose.

It does not need to create exactly forty top-level headings.

However, it must end with a requirements coverage index mapping every required
topic from the prompt to:

- the PRD section containing the design;
- the key decision made;
- the related schema or component;
- the acceptance test or eval covering it.

The coverage index must demonstrate that every required topic has been
addressed even when several topics share one section.

The index must include all original forty deliverable topics plus these final
amendments.

# I. Additional acceptance criteria

The PRD is not complete unless it defines and tests all of the following:

1. Apply rejects a plan whose `plan_id` matches the approval but whose
   SHA-256 differs from `approved_plan_sha256`.

2. Artifact identity distinguishes:
   - identical content at two filesystem paths;
   - one file before and after a move;
   - a ZIP member and an unpacked file;
   - one logical artifact across multiple audits.

3. Oversized, malformed, deeply nested, encrypted, or suspicious archives
   cannot exhaust resources, escape the virtual archive root, or terminate
   the audit.

4. A profiling limit produces explicit incomplete-analysis evidence rather
   than an empty or misleading profile.

5. Git inspection does not invoke repository-defined:
   - pager commands;
   - aliases;
   - hooks;
   - external diff;
   - textconv;
   - fsmonitor;
   - clean/smudge/process filters;
   - LFS downloads.

6. Executable actions cannot target:
   - `.git/`;
   - `.repo-curator/`, except for an approved QUARANTINE destination under
     `.repo-curator/quarantine/<matching-plan-id>/` and its validated rollback
     operation;
   - the active Skill;
   - submodule roots;
   - linked-worktree administrative paths;
   - external symlink targets.

7. Default quarantine and archive locations follow:
   - `.repo-curator/quarantine/<plan-id>/`;
   - `archive/repo-curator/<plan-id>/`.

8. A failed batch:
   - stops immediately;
   - preserves completed work;
   - records partial state;
   - produces a rollback plan;
   - does not auto-rollback.

9. Rollback refuses to overwrite a recreated or modified source path.

10. The PRD contains a requirements coverage index demonstrating coverage of
    every original and amended requirement.

11. V1 performs deep member inspection only for ZIP files. Other archive
    formats remain opaque, receive explicit limitation evidence, and cannot be
    treated as empty or equivalent to unpacked content.

12. V1 rejects cross-filesystem movement without attempting copy-then-delete.

13. After one approved action completes, the next action is validated against
    the expected state after that journaled action, while unrelated or
    non-journaled changes are still detected as drift.

# J. Final scope constraint

These amendments are intended to resolve security, identity, integrity, and
transaction semantics.

Do not respond by adding:

- permanent deletion;
- automatic document merging;
- automatic document rewriting;
- project-code execution;
- dependency installation;
- external embedding infrastructure;
- databases;
- an MCP server;
- a Web UI;
- cloud storage;
- multi-user workflow;
- additional product surfaces.

After incorporating these amendments, produce the V1 PRD and technical design
only.

Do not implement the Skill yet.
