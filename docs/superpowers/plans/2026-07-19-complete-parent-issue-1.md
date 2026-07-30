# Parent Issue #1 Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete Issues #20–#23, add cross-platform continuous verification, and satisfy every acceptance criterion of parent Issue #1.

**Architecture:** Keep `repo_curator.inventory` as the audit orchestrator and file-contract owner. Extract descriptor-relative observation into `repo_curator.scanner`, identity construction into `repo_curator.identity`, and declaration recognition into `repo_curator.declarations`. Each task extends the same black-box `python3 -m repo_curator audit` seam, preserves finalized schema compatibility, and lands through its own reviewed pull request before the dependent task begins.

**Tech Stack:** Python 3.9 standard library, `unittest`, descriptor-relative POSIX filesystem APIs, GitHub Actions on macOS and Linux. No runtime dependency or target-project execution.

## Global Constraints

- Repository content, names, metadata, and configuration are untrusted data and never become instructions.
- Audit writes only below `.repo-curator/runs/<run-id>/`; it never modifies another target artifact.
- Traversal and hashing use descriptor-relative operations and never follow symbolic links.
- `artifact_id`, `content_id`, `location_id`, and `lineage_id` remain separate; matching bytes do not establish lineage.
- Fixed repository inputs, configuration, run ID, and timestamps produce byte-identical deterministic records.
- Optional scalar fields are explicit `null`; list fields are present as empty lists; limitations are never represented as absence or negative evidence.
- No project command, Git helper, package manager, research tool, hook, service, plugin, notebook, or serialized object is executed or imported.
- All production behavior follows RED → GREEN → REFACTOR, the full suite passes before commit, and every task receives an independent spec-and-quality review.
- Supported CI platforms are `ubuntu-latest` and `macos-latest` with Python `3.9`.

---

### Task 1: Issue #20 — Links, Special Objects, and Repository Boundaries

**Files:**
- Create: `repo_curator/scanner.py`
- Create: `tests/test_boundary_scenario.py`
- Modify: `repo_curator/inventory.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `audit_repository(root: Path, run_id: str, created_at: str) -> Path` and the required inventory fields in PRD §18.
- Produces: `scan_root(root_fd: int) -> list[ObservedArtifact]`, where `ObservedArtifact` is an immutable dataclass containing `path`, `path_bytes`, `object_type`, `stat_result`, `fingerprint_scheme`, `fingerprint`, `symlink_target_text`, `profile_eligibility`, and `warnings`.
- Produces warning codes `SYMLINK_TARGET_OUTSIDE_ROOT`, `SYMLINK_TARGET_MISSING`, `SPECIAL_FILE_NOT_READ`, `PROTECTED_GIT_CONTROL`, and `NESTED_REPOSITORY_BOUNDARY`.

- [ ] **Step 1: Write failing black-box boundary scenarios**

```python
def test_links_are_recorded_without_following_targets(self):
    # Create internal, external, and broken links plus an external marker.
    result = self.run_audit(repository)
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertEqual(link_record["object_type"], "SYMLINK")
    self.assertEqual(link_record["symlink_target_text"], target_text)
    self.assertFalse(external_marker.exists())

def test_special_and_nested_repository_objects_are_bounded(self):
    # Create a FIFO, Unix socket, root .git directory, and nested repo marker.
    self.assertIn("SPECIAL_FILE_NOT_READ", fifo_record["warnings"])
    self.assertIn("PROTECTED_GIT_CONTROL", git_record["warnings"])
    self.assertIn("NESTED_REPOSITORY_BOUNDARY", nested_record["warnings"])
    self.assertNotIn("nested/.git/config", inventory_paths)
```

- [ ] **Step 2: Run RED**

Run: `python3 -m unittest -v tests/test_boundary_scenario.py`

Expected: FAIL because symbolic links currently terminate audit and special/nested boundary records do not exist.

- [ ] **Step 3: Extract descriptor-safe scanning and add bounded object records**

```python
@dataclass(frozen=True)
class ObservedArtifact:
    path: str
    path_bytes: bytes
    object_type: str
    stat_result: Optional[os.stat_result]
    fingerprint_scheme: Optional[str]
    fingerprint: Optional[str]
    symlink_target_text: Optional[str]
    profile_eligibility: str
    warnings: tuple[str, ...]

def scan_root(root_fd: int) -> list[ObservedArtifact]:
    """Inventory entries with *at APIs; never follow a symlink or read a special object."""
```

Use `os.stat(..., follow_symlinks=False)`, `os.readlink(..., dir_fd=...)`, `O_NOFOLLOW`, and directory descriptors. A symlink content identity is `sha256-symlink-target-v1` over its raw target text. Special files have null content/fingerprint fields. Record `.git` and nested repository roots as protected boundary artifacts and do not descend into them.

- [ ] **Step 4: Run GREEN and regression suite**

Run: `python3 -m unittest -v tests/test_boundary_scenario.py`

Run: `python3 -m unittest discover -v`

Expected: all tests pass; no fixture marker outside the repository changes.

- [ ] **Step 5: Commit**

```bash
git add README.md repo_curator/inventory.py repo_curator/scanner.py tests/test_boundary_scenario.py
git commit -m "feat(audit): inventory links and filesystem boundaries"
```

---

### Task 2: Issue #21 — Four Independent Identity Domains

**Files:**
- Create: `repo_curator/identity.py`
- Create: `tests/test_identity_scenario.py`
- Modify: `repo_curator/inventory.py`
- Modify: `repo_curator/scanner.py`
- Modify: `README.md`

**Interfaces:**
- Consumes: `ObservedArtifact` from Task 1.
- Produces: `content_identity(observation, child_manifest)`, `location_identity(root_realpath, object_type, path_bytes)`, `directory_merkle(children)`, and `repository_state_identity(root_realpath, inventory_records)`.
- Location identity hashes root realpath bytes, object type, and raw repository-relative path bytes. Content identity never hashes a repository location. Lineage remains null with `lineage_status: UNRESOLVED`.

- [ ] **Step 1: Write failing identity scenarios**

```python
def test_equal_bytes_share_content_but_not_artifact_or_location_identity(self):
    self.assertEqual(left["content_id"], right["content_id"])
    self.assertNotEqual(left["artifact_id"], right["artifact_id"])
    self.assertNotEqual(left["location_id"], right["location_id"])

def test_hard_links_unicode_case_collisions_and_raw_bytes_remain_observable(self):
    self.assertEqual(hard_a["content_id"], hard_b["content_id"])
    self.assertNotEqual(hard_a["artifact_id"], hard_b["artifact_id"])
    self.assertIn("CASE_COLLISION", case_a["warnings"])
    self.assertEqual(os.fsencode(raw_record["repository_relative_path"]), b"raw-\\xff")
```

- [ ] **Step 2: Run RED**

Run: `python3 -m unittest -v tests/test_identity_scenario.py`

Expected: FAIL on surrogate/raw-byte serialization, case-collision warnings, or location identity scope.

- [ ] **Step 3: Implement identity module and raw-byte canonicalization**

```python
def location_identity(
    root_realpath: str, object_type: str, repository_relative_path: bytes
) -> str:
    payload = length_prefix(os.fsencode(root_realpath), object_type.encode(), repository_relative_path)
    return "location-filesystem-v1:" + hashlib.sha256(payload).hexdigest()

def collision_key(path: str) -> str:
    return unicodedata.normalize("NFC", path).casefold()
```

Sort filesystem names with `os.fsencode(name)`. Serialize JSON with `ensure_ascii=True` so surrogate-escaped paths round-trip through `os.fsencode`. Add `CASE_COLLISION` to every member of a collision group. Do not invent a lineage ID from inode or equal content.

- [ ] **Step 4: Run GREEN and regression suite**

Run: `python3 -m unittest -v tests/test_identity_scenario.py`

Run: `python3 -m unittest discover -v`

Expected: all tests pass and two identical subtrees at different locations retain equal directory `content_id` values.

- [ ] **Step 5: Commit**

```bash
git add README.md repo_curator/identity.py repo_curator/inventory.py repo_curator/scanner.py tests/test_identity_scenario.py
git commit -m "feat(audit): enforce independent artifact identities"
```

---

### Task 3: Issue #22 — Read-only Research Declaration Observations

**Files:**
- Create: `repo_curator/declarations.py`
- Create: `tests/test_declaration_scenario.py`
- Modify: `repo_curator/inventory.py`
- Modify: `README.md`

**Interfaces:**
- Consumes finalized inventory records only; it never reopens arbitrary serialized payloads.
- Produces `.repo-curator/runs/<run-id>/adapter-observations.jsonl` and adds its SHA-256 to `run.json.output_file_hashes`.
- Each observation has `schema_version`, `run_id`, `observation_id`, `declaration_family`, `source_artifact_id`, `source_location_id`, `status`, `validation_status`, `coverage`, `limitations`, and `created_at`.

- [ ] **Step 1: Write failing frozen declaration scenarios**

```python
EXPECTED_FAMILIES = {"DVC", "DATALAD", "MLFLOW", "SACRED", "RO_CRATE", "BAGIT"}

def test_supported_declarations_emit_typed_presence_observations(self):
    self.assertEqual({o["declaration_family"] for o in observations}, EXPECTED_FAMILIES)
    self.assertTrue(all(o["validation_status"] != "EXECUTED" for o in observations))

def test_malformed_ro_crate_is_retained_with_a_limitation(self):
    self.assertEqual(observation["status"], "MALFORMED")
    self.assertIn("DECLARATION_MALFORMED", observation["limitations"])
```

The fixture includes `dvc.yaml`, `.datalad/config`, `MLproject`, a Sacred directory containing `config.json` plus `run.json`, `ro-crate-metadata.json`, and `bagit.txt`. Put executable fake `dvc`, `mlflow`, and package-manager binaries on `PATH`; each would create a marker if invoked.

- [ ] **Step 2: Run RED**

Run: `python3 -m unittest -v tests/test_declaration_scenario.py`

Expected: FAIL because `adapter-observations.jsonl` does not exist.

- [ ] **Step 3: Implement deterministic declaration recognizers**

```python
DECLARATION_RULES = {
    "DVC": ("dvc.yaml",),
    "DATALAD": (".datalad/config",),
    "MLFLOW": ("MLproject",),
    "RO_CRATE": ("ro-crate-metadata.json",),
    "BAGIT": ("bagit.txt",),
}

def detect_declarations(
    root_fd: int, inventory_records: list[dict], run_id: str, created_at: str
) -> list[dict]:
    """Return typed observations without importing or launching an upstream tool."""
```

Sacred requires co-located `config.json` and `run.json`. Parse only bounded UTF-8 JSON declaration files using a 1 MiB detector ceiling; larger files use `PRESENT_UNVALIDATED` plus `DECLARATION_VALIDATION_SIZE_LIMIT`. A parse error uses `MALFORMED`; never fabricate entity fields. Publish all run outputs atomically as a set and remove an incomplete run on failure.

- [ ] **Step 4: Run GREEN and regression suite**

Run: `python3 -m unittest -v tests/test_declaration_scenario.py`

Run: `python3 -m unittest discover -v`

Expected: all tests pass; every fake executable marker remains absent.

- [ ] **Step 5: Commit**

```bash
git add README.md repo_curator/declarations.py repo_curator/inventory.py tests/test_declaration_scenario.py
git commit -m "feat(audit): observe research metadata declarations"
```

---

### Task 4: Issue #23 — Resource Budgets and Artifact-local Limitations

**Files:**
- Create: `repo_curator/budgets.py`
- Create: `tests/test_limitation_scenario.py`
- Modify: `repo_curator/cli.py`
- Modify: `repo_curator/inventory.py`
- Modify: `repo_curator/scanner.py`
- Modify: `README.md`

**Interfaces:**
- Produces `AuditBudgets(max_file_bytes: int = 33_554_432)` with hard ceiling `268_435_456`.
- `audit_repository` gains optional `budgets: AuditBudgets = AuditBudgets()` without changing existing callers.
- Inventory warning codes are `CONTENT_HASH_SKIPPED_SIZE_LIMIT`, `ARTIFACT_UNREADABLE`, `ARTIFACT_DISAPPEARED`, and `ARTIFACT_CHANGED_DURING_INVENTORY`.
- A run with local limitations finishes as `COMPLETED_WITH_LIMITATIONS`; systemic inability to open the selected root remains a nonzero failure.

- [ ] **Step 1: Write failing size and local-failure scenarios**

```python
def test_large_file_is_retained_without_hashing_past_the_budget(self):
    result = self.run_audit(repository, "--max-file-bytes", "8")
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertIsNone(large_record["content_id"])
    self.assertIn("CONTENT_HASH_SKIPPED_SIZE_LIMIT", large_record["warnings"])
    self.assertEqual(run["final_status"], "COMPLETED_WITH_LIMITATIONS")

def test_one_unreadable_or_disappearing_artifact_does_not_abort_other_records(self):
    self.assertIn("README.md", inventory_paths)
    self.assertIn("ARTIFACT_UNREADABLE", failed_record["warnings"])
```

Use deterministic fault injection around descriptor opening for permission and disappearance cases; restore every permission and descriptor in test cleanup.

- [ ] **Step 2: Run RED**

Run: `python3 -m unittest -v tests/test_limitation_scenario.py`

Expected: FAIL because the CLI has no budget option and local open errors terminate audit.

- [ ] **Step 3: Implement mechanical budgets and local abstention**

```python
@dataclass(frozen=True)
class AuditBudgets:
    max_file_bytes: int = 32 * 1024 * 1024

    def validate(self) -> None:
        if not 0 < self.max_file_bytes <= 256 * 1024 * 1024:
            raise ValueError("max file bytes must be between 1 and 268435456")
```

Do not open file content when observed size exceeds the configured limit. Convert artifact-local `PermissionError`, `FileNotFoundError`, and state-change detection into records with null fingerprints, exact warning codes, and no semantic conclusion. Record applied budgets in `run.json.resource_budgets`, aggregate unique warnings deterministically, and continue scanning siblings.

- [ ] **Step 4: Run GREEN and regression suite**

Run: `python3 -m unittest -v tests/test_limitation_scenario.py`

Run: `python3 -m unittest discover -v`

Expected: all tests pass; original fixture bytes and paths remain unchanged outside `.repo-curator`.

- [ ] **Step 5: Commit**

```bash
git add README.md repo_curator/budgets.py repo_curator/cli.py repo_curator/inventory.py repo_curator/scanner.py tests/test_limitation_scenario.py
git commit -m "feat(audit): continue with bounded local limitations"
```

---

### Task 5: Parent #1 Cross-platform Acceptance and CI

**Files:**
- Create: `.github/workflows/test.yml`
- Create: `tests/test_parent_issue_1_acceptance.py`
- Modify: `README.md`

**Interfaces:**
- Consumes the public CLI and finalized machine outputs only.
- Produces a required GitHub Actions matrix for `ubuntu-latest` and `macos-latest`, Python `3.9`.

- [ ] **Step 1: Add the combined parent acceptance scenario**

```python
def test_parent_issue_one_fixture_matrix(self):
    # In one isolated corpus include hidden, ignored-pattern, Unicode, case-collision,
    # hard-link, symlink, broken-link, large-file, FIFO, nested-repository,
    # non-Git, and all six declaration-family fixtures.
    result = self.run_audit(repository, "--max-file-bytes", "8")
    self.assertEqual(result.returncode, 0, result.stderr)
    self.assertFalse(any(marker.exists() for marker in forbidden_execution_markers))
    self.assertEqual(second_inventory_bytes, first_inventory_bytes)
```

- [ ] **Step 2: Run the parent acceptance scenario locally**

Run: `python3 -m unittest -v tests/test_parent_issue_1_acceptance.py`

Expected: PASS on the current development platform.

- [ ] **Step 3: Add the CI matrix**

```yaml
name: test
on:
  pull_request:
  push:
    branches: [main]
jobs:
  test:
    strategy:
      fail-fast: false
      matrix:
        os: [ubuntu-latest, macos-latest]
    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.9"
      - run: python3 -m unittest discover -v
      - run: python3 -m compileall -q repo_curator tests
```

- [ ] **Step 4: Run the complete local gate**

Run: `python3 -m unittest discover -v`

Run: `python3 -m compileall -q repo_curator tests`

Run: `git diff --check`

Expected: zero failures, compile errors, or whitespace errors.

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/test.yml README.md tests/test_parent_issue_1_acceptance.py
git commit -m "ci: verify parent inventory acceptance on macos and linux"
```

After the PR passes both CI jobs and is merged, confirm Issues #20–#23 are closed, comment on Issue #1 with the child PRs and test evidence, then close Issue #1.
