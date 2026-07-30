# Forensic Safety Inventory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver Issue #1's explicit `audit` workflow, deterministic inventory records, research-metadata evidence, hostile filesystem fixtures, and reusable end-to-end scenario runner.

**Architecture:** A dependency-free Node.js ESM CLI calls a read-only audit orchestrator. A no-follow repository walker emits raw filesystem observations; focused modules enforce repository boundaries, build separate artifact/location/content/lineage identities, detect declaration-only research metadata, and atomically write deterministic JSON/JSONL outputs. Tests create disposable repositories and exercise the CLI as a black box, while unit tests pin boundary and identity behavior.

**Tech Stack:** Node.js 22 or newer, JavaScript ESM, Node standard library, `node:test`, `assert/strict`, Conventional Commits.

## Global Constraints

- Do not execute target-repository code, package scripts, hooks, commands, or instructions discovered in content.
- Do not install runtime or development dependencies for this slice.
- Follow symbolic links only far enough to classify the link target; never traverse through them.
- Ordinary scans exclude `.git/` and `.repo-curator/` contents but record protected-path exclusions.
- Preserve artifacts when inspection fails; emit a typed limitation instead of omitting the artifact.
- Sort repository-relative paths with bytewise UTF-8 comparison before assigning sequence-based artifact IDs.
- Hash regular-file identity with SHA-256 over exact bytes only; do not normalize content.
- Keep `artifactId`, `locationId`, `contentId`, and `lineageId` as separate fields. `lineageId` is `null` until later evidence supports continuity.
- Test-generated timestamps and run IDs are explicit inputs so repeated runs can reproduce bytes exactly.
- Use camelCase file and function names, PascalCase classes if introduced, relative imports, and `*.test.js` test filenames.
- Use `feat`, `fix`, `test`, or `docs` Conventional Commit prefixes.

---

## File Structure

- `package.json` — ESM package metadata and explicit audit/test entrypoints.
- `src/cli.js` — validates CLI arguments and invokes the audit orchestrator.
- `src/audit/runAudit.js` — coordinates boundary validation, scanning, evidence detection, and output writing.
- `src/security/repositoryBoundary.js` — resolves the selected root, identifies protected paths, and checks containment.
- `src/inventory/walkRepository.js` — deterministic, no-follow traversal with entry and byte budgets.
- `src/inventory/buildArtifactRecord.js` — converts one observation into the inventory contract.
- `src/inventory/identities.js` — canonical SHA-256 identity helpers.
- `src/inventory/metadataDetectors.js` — declaration-only DVC, DataLad, MLflow, Sacred, RO-Crate, and BagIt detection.
- `src/output/writeRunOutputs.js` — stable JSON/JSONL serialization and no-overwrite atomic publication.
- `tests/helpers/repositoryFixture.js` — creates disposable ordinary and hostile repository fixtures without invoking their contents.
- `tests/scenarios/auditScenario.test.js` — black-box audit contract and determinism tests.
- `tests/unit/repositoryBoundary.test.js` — containment and protected-path tests.
- `tests/unit/identities.test.js` — exact-byte and location identity tests.
- `tests/unit/metadataDetectors.test.js` — research-metadata declaration tests.

---

### Task 1: Establish the explicit audit seam

**Files:**
- Create: `package.json`
- Create: `tests/helpers/repositoryFixture.js`
- Create: `tests/scenarios/auditScenario.test.js`
- Create: `src/cli.js`
- Create: `src/audit/runAudit.js`
- Create: `src/output/writeRunOutputs.js`

**Interfaces:**
- Produces: `runAudit({ rootPath, runId, createdAt, budgets }): Promise<{ runPath, inventory, metadataEvidence, run }>`.
- Produces: CLI `node src/cli.js audit --root <path> --run-id <id> --created-at <ISO-8601>`.
- Produces: `.repo-curator/runs/<run-id>/run.json`, `inventory.jsonl`, and `metadata-evidence.jsonl`.

- [ ] **Step 1: Add package metadata and the first failing scenario test**

```json
{
  "name": "repo-curator",
  "private": true,
  "type": "module",
  "engines": { "node": ">=22" },
  "scripts": {
    "audit": "node src/cli.js audit",
    "test": "node --test",
    "test:scenario": "node --test tests/scenarios/*.test.js"
  }
}
```

```js
// tests/scenarios/auditScenario.test.js
import assert from 'node:assert/strict'
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { afterEach, test } from 'node:test'
import { spawnSync } from 'node:child_process'

const roots = []

afterEach(async () => {
  await Promise.all(roots.splice(0).map((root) => rm(root, { recursive: true, force: true })))
})

test('explicit audit writes deterministic run contracts', async () => {
  const root = await mkdtemp(join(tmpdir(), 'repo-curator-'))
  roots.push(root)
  await mkdir(join(root, 'src'))
  await writeFile(join(root, 'src', 'index.js'), 'export const value = 1\n')

  const result = spawnSync(process.execPath, [
    'src/cli.js', 'audit', '--root', root,
    '--run-id', 'fixture-run', '--created-at', '2026-07-16T00:00:00.000Z'
  ], { cwd: process.cwd(), encoding: 'utf8' })

  assert.equal(result.status, 0, result.stderr)
  const runPath = join(root, '.repo-curator', 'runs', 'fixture-run')
  const run = JSON.parse(await readFile(join(runPath, 'run.json'), 'utf8'))
  assert.equal(run.finalStatus, 'COMPLETE')
  assert.match(await readFile(join(runPath, 'inventory.jsonl'), 'utf8'), /src\/index\.js/)
})
```

- [ ] **Step 2: Run the scenario and verify RED**

Run: `npm run test:scenario`

Expected: FAIL because `src/cli.js` does not exist or the audit output is absent.

- [ ] **Step 3: Implement the minimal CLI, orchestrator, and deterministic writer**

```js
// src/cli.js
#!/usr/bin/env node
import { resolve } from 'node:path'
import { runAudit } from './audit/runAudit.js'

const [command, ...tokens] = process.argv.slice(2)
const values = new Map()
for (let index = 0; index < tokens.length; index += 2) {
  values.set(tokens[index], tokens[index + 1])
}

const runId = values.get('--run-id') ?? `run-${Date.now()}`
const createdAt = values.get('--created-at') ?? new Date().toISOString()
const validRunId = /^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$/.test(runId)
const validCreatedAt = Number.isFinite(Date.parse(createdAt))

if (command !== 'audit' || !values.get('--root') || !validRunId || !validCreatedAt) {
  process.stderr.write('Usage: repo-curator audit --root <path> [--run-id <id>] [--created-at <ISO>]\n')
  process.exitCode = 2
} else {
  try {
    const result = await runAudit({
      rootPath: resolve(values.get('--root')),
      runId,
      createdAt
    })
    process.stdout.write(`${result.runPath}\n`)
  } catch (error) {
    process.stderr.write(`${error.code ?? 'AUDIT_FAILED'}: ${error.message}\n`)
    process.exitCode = 1
  }
}
```

```js
// src/output/writeRunOutputs.js
import { mkdir, rename, writeFile } from 'node:fs/promises'
import { join } from 'node:path'

const sortValue = (value) => {
  if (Array.isArray(value)) return value.map(sortValue)
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.keys(value).sort().map((key) => [key, sortValue(value[key])]))
  }
  return value
}
const stableJson = (value) => `${JSON.stringify(sortValue(value), null, 2)}\n`
const jsonLines = (records) => records.map((record) => JSON.stringify(sortValue(record))).join('\n') + (records.length ? '\n' : '')

export async function writeRunOutputs({ rootPath, runId, run, inventory, metadataEvidence }) {
  const runsPath = join(rootPath, '.repo-curator', 'runs')
  const finalPath = join(runsPath, runId)
  const temporaryPath = join(runsPath, `.${runId}.tmp`)
  await mkdir(runsPath, { recursive: true })
  await mkdir(temporaryPath, { recursive: false })
  await writeFile(join(temporaryPath, 'run.json'), stableJson(run), { flag: 'wx' })
  await writeFile(join(temporaryPath, 'inventory.jsonl'), jsonLines(inventory), { flag: 'wx' })
  await writeFile(join(temporaryPath, 'metadata-evidence.jsonl'), jsonLines(metadataEvidence), { flag: 'wx' })
  await rename(temporaryPath, finalPath)
  return finalPath
}
```

```js
// src/audit/runAudit.js
import { relative } from 'node:path'
import { writeRunOutputs } from '../output/writeRunOutputs.js'

export async function runAudit({ rootPath, runId, createdAt }) {
  const inventory = [{
    schemaVersion: 1,
    runId,
    artifactId: `art_${runId}_000001`,
    locationId: 'pending',
    contentId: 'pending',
    lineageId: null,
    repositoryRelativePath: relative(rootPath, `${rootPath}/src/index.js`).replaceAll('\\', '/'),
    objectType: 'REGULAR_FILE',
    limitations: [],
    createdAt
  }]
  const metadataEvidence = []
  const run = { schemaVersion: 1, runId, createdAt, finalStatus: 'COMPLETE', warnings: [] }
  const runPath = await writeRunOutputs({ rootPath, runId, run, inventory, metadataEvidence })
  return { runPath, inventory, metadataEvidence, run }
}
```

- [ ] **Step 4: Run the scenario and verify GREEN**

Run: `npm run test:scenario`

Expected: 1 test passes, 0 failures.

- [ ] **Step 5: Commit the tracer seam**

```bash
git add package.json src tests
git commit -m "test(inventory): add explicit audit scenario seam"
```

---

### Task 2: Enforce repository boundaries and no-follow traversal

**Files:**
- Create: `tests/unit/repositoryBoundary.test.js`
- Create: `src/security/repositoryBoundary.js`
- Create: `src/inventory/walkRepository.js`
- Modify: `src/audit/runAudit.js`

**Interfaces:**
- Produces: `createRepositoryBoundary(rootPath): Promise<{ rootPath, rootRealpath, protectedNames, contains(path) }>`.
- Produces: `walkRepository({ boundary, budgets }): AsyncGenerator<RawObservation>`.
- `RawObservation` contains `relativePath`, `absolutePath`, `objectType`, `stat`, `symlinkTargetText`, and `limitations`.

- [ ] **Step 1: Write failing boundary and no-follow tests**

```js
// tests/unit/repositoryBoundary.test.js
import assert from 'node:assert/strict'
import { mkdtemp, symlink } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import { createRepositoryBoundary } from '../../src/security/repositoryBoundary.js'
import { walkRepository } from '../../src/inventory/walkRepository.js'

test('boundary rejects paths outside the selected root', async (t) => {
  const root = await mkdtemp(join(tmpdir(), 'repo-root-'))
  const outside = await mkdtemp(join(tmpdir(), 'repo-outside-'))
  t.after(async () => Promise.all([
    import('node:fs/promises').then(({ rm }) => rm(root, { recursive: true, force: true })),
    import('node:fs/promises').then(({ rm }) => rm(outside, { recursive: true, force: true }))
  ]))
  const boundary = await createRepositoryBoundary(root)
  assert.equal(boundary.contains(join(root, 'inside.txt')), true)
  assert.equal(boundary.contains(join(root, '..', 'escape.txt')), false)
  await symlink(outside, join(root, 'outside-link'))
  const entries = []
  for await (const entry of walkRepository({ boundary, budgets: { maxEntries: 100 } })) entries.push(entry)
  assert.equal(entries.find((entry) => entry.relativePath === 'outside-link').objectType, 'SYMLINK')
  assert.equal(entries.some((entry) => entry.relativePath.startsWith('outside-link/')), false)
})
```

- [ ] **Step 2: Run the unit test and verify RED**

Run: `node --test tests/unit/repositoryBoundary.test.js`

Expected: FAIL because the boundary and walker modules do not exist.

- [ ] **Step 3: Implement boundary containment and `lstat` traversal**

```js
// src/security/repositoryBoundary.js
import { lstat, realpath } from 'node:fs/promises'
import { isAbsolute, relative, resolve, sep } from 'node:path'

export async function createRepositoryBoundary(rootPath) {
  const resolvedRoot = resolve(rootPath)
  const rootStat = await lstat(resolvedRoot)
  if (!rootStat.isDirectory()) throw Object.assign(new Error('Audit root must be a directory'), { code: 'INVALID_ROOT' })
  const rootRealpath = await realpath(resolvedRoot)
  return {
    rootPath: resolvedRoot,
    rootRealpath,
    protectedNames: new Set(['.git', '.repo-curator']),
    contains(candidate) {
      const child = relative(rootRealpath, resolve(candidate))
      return child === '' || (!child.startsWith(`..${sep}`) && child !== '..' && !isAbsolute(child))
    }
  }
}
```

```js
// src/inventory/walkRepository.js
import { lstat, readlink, readdir } from 'node:fs/promises'
import { join } from 'node:path'

const classify = (stat) => stat.isFile() ? 'REGULAR_FILE'
  : stat.isDirectory() ? 'DIRECTORY'
    : stat.isSymbolicLink() ? 'SYMLINK' : 'SPECIAL_FILE'

export async function* walkRepository({ boundary, budgets }) {
  const pending = ['']
  let count = 0
  while (pending.length) {
    const parent = pending.pop()
    const names = await readdir(join(boundary.rootPath, parent), { encoding: 'buffer' })
    names.sort(Buffer.compare)
    for (const nameBytes of names) {
      if (++count > budgets.maxEntries) return
      const name = nameBytes.toString('utf8')
      const relativePath = parent ? `${parent}/${name}` : name
      if (boundary.protectedNames.has(name)) continue
      const absolutePath = join(boundary.rootPath, ...relativePath.split('/'))
      const stat = await lstat(absolutePath)
      const objectType = classify(stat)
      const symlinkTargetText = objectType === 'SYMLINK' ? await readlink(absolutePath) : null
      yield { relativePath, absolutePath, objectType, stat, symlinkTargetText, limitations: [] }
      if (objectType === 'DIRECTORY') pending.push(relativePath)
    }
  }
}
```

- [ ] **Step 4: Connect the walker to `runAudit` and verify GREEN**

Replace the hard-coded record in `runAudit` with observations from `walkRepository`; preserve `.git` and `.repo-curator` as exclusions in `run.json`.

Run: `node --test tests/unit/repositoryBoundary.test.js tests/scenarios/auditScenario.test.js`

Expected: all tests pass and the external symlink has no descendants.

- [ ] **Step 5: Commit boundary enforcement**

```bash
git add src/security src/inventory src/audit tests/unit
git commit -m "feat(inventory): add no-follow repository traversal"
```

---

### Task 3: Build deterministic, separate identities

**Files:**
- Create: `tests/unit/identities.test.js`
- Create: `src/inventory/identities.js`
- Create: `src/inventory/buildArtifactRecord.js`
- Modify: `src/audit/runAudit.js`

**Interfaces:**
- Produces: `hashExactFile(path): Promise<string>` returning `sha256-file:<hex>`.
- Produces: `buildLocationId({ relativePath, objectType, symlinkTargetText }): string`.
- Produces: `buildArtifactRecord({ observation, runId, sequence, createdAt, budgets }): Promise<InventoryRecord>`.

- [ ] **Step 1: Write failing identity tests**

```js
// tests/unit/identities.test.js
import assert from 'node:assert/strict'
import { mkdtemp, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import { buildLocationId, hashExactFile } from '../../src/inventory/identities.js'

test('content identity hashes exact bytes and ignores location', async () => {
  const root = await mkdtemp(join(tmpdir(), 'identities-'))
  const first = join(root, 'first.txt')
  const second = join(root, 'second.txt')
  await writeFile(first, Buffer.from([0, 10, 255]))
  await writeFile(second, Buffer.from([0, 10, 255]))
  assert.equal(await hashExactFile(first), await hashExactFile(second))
  assert.notEqual(
    buildLocationId({ relativePath: 'first.txt', objectType: 'REGULAR_FILE', symlinkTargetText: null }),
    buildLocationId({ relativePath: 'second.txt', objectType: 'REGULAR_FILE', symlinkTargetText: null })
  )
})
```

- [ ] **Step 2: Run the identity test and verify RED**

Run: `node --test tests/unit/identities.test.js`

Expected: FAIL because `identities.js` does not exist.

- [ ] **Step 3: Implement exact-byte and location identity helpers**

```js
// src/inventory/identities.js
import { createHash } from 'node:crypto'
import { createReadStream } from 'node:fs'

const sha256 = (value) => createHash('sha256').update(value).digest('hex')

export async function hashExactFile(path) {
  const hash = createHash('sha256')
  for await (const chunk of createReadStream(path)) hash.update(chunk)
  return `sha256-file:${hash.digest('hex')}`
}

export function buildLocationId({ relativePath, objectType, symlinkTargetText }) {
  return `loc:${sha256(JSON.stringify([objectType, relativePath, symlinkTargetText]))}`
}
```

```js
// src/inventory/buildArtifactRecord.js
import { buildLocationId, hashExactFile } from './identities.js'

export async function buildArtifactRecord({ observation, runId, sequence, createdAt, budgets }) {
  const limitations = [...observation.limitations]
  let contentId = null
  if (observation.objectType === 'REGULAR_FILE' && observation.stat.size <= budgets.maxFileBytes) {
    try { contentId = await hashExactFile(observation.absolutePath) }
    catch (error) { limitations.push({ code: 'CONTENT_READ_FAILED', message: error.code ?? 'UNKNOWN' }) }
  } else if (observation.objectType === 'REGULAR_FILE') {
    limitations.push({ code: 'HASH_SKIPPED_SIZE_LIMIT', limit: budgets.maxFileBytes })
  }
  return {
    schemaVersion: 1,
    runId,
    artifactId: `art_${runId}_${String(sequence).padStart(6, '0')}`,
    locationId: buildLocationId(observation),
    contentId,
    lineageId: null,
    repositoryRelativePath: observation.relativePath,
    objectType: observation.objectType,
    sizeBytes: observation.stat.size,
    mode: observation.stat.mode,
    executable: (observation.stat.mode & 0o111) !== 0,
    symlinkTargetText: observation.symlinkTargetText,
    hardLinkKey: observation.stat.nlink > 1 ? `${observation.stat.dev}:${observation.stat.ino}` : null,
    gitState: null,
    limitations,
    createdAt
  }
}
```

- [ ] **Step 4: Build records only after bytewise path sorting and verify GREEN**

In `runAudit`, collect observations, sort with `Buffer.compare(Buffer.from(a.relativePath), Buffer.from(b.relativePath))`, then call `buildArtifactRecord` with one-based sequence numbers.

Run: `node --test tests/unit/identities.test.js tests/scenarios/auditScenario.test.js`

Expected: all tests pass; equal bytes share `contentId` while their `artifactId` and `locationId` differ.

- [ ] **Step 5: Commit deterministic identities**

```bash
git add src/inventory src/audit tests/unit/identities.test.js
git commit -m "feat(inventory): separate artifact and content identities"
```

---

### Task 4: Preserve limitations, collisions, and resource exhaustion

**Files:**
- Modify: `tests/scenarios/auditScenario.test.js`
- Modify: `tests/helpers/repositoryFixture.js`
- Modify: `src/inventory/walkRepository.js`
- Modify: `src/inventory/buildArtifactRecord.js`
- Modify: `src/audit/runAudit.js`

**Interfaces:**
- Extends budgets with `maxEntries` and `maxFileBytes` integer ceilings.
- Adds run warnings `RESOURCE_LIMIT_REACHED` and record limitations `CONTENT_READ_FAILED`, `HASH_SKIPPED_SIZE_LIMIT`, `BROKEN_SYMLINK`, `EXTERNAL_SYMLINK`, and `CASE_COLLISION`.

- [ ] **Step 1: Add failing hostile-fixture assertions**

```js
test('audit preserves hostile and incomplete filesystem observations', async () => {
  const root = await createRepositoryFixture({
    unicode: true,
    caseCollision: true,
    hardLink: true,
    brokenSymlink: true,
    externalSymlink: true,
    largeFile: true,
    specialFile: process.platform !== 'win32'
  })
  const { inventory, run } = await invokeAudit(root, { maxEntries: 10_000, maxFileBytes: 8 })
  assert.ok(inventory.some((record) => record.objectType === 'SYMLINK'))
  assert.ok(inventory.some((record) => record.objectType === 'SPECIAL_FILE'))
  assert.ok(inventory.some((record) => record.limitations.some((item) => item.code === 'CASE_COLLISION')))
  assert.ok(inventory.some((record) => record.limitations.some((item) => item.code === 'HASH_SKIPPED_SIZE_LIMIT')))
  assert.equal(run.finalStatus, 'COMPLETE_WITH_LIMITATIONS')
})
```

- [ ] **Step 2: Run the scenario and verify RED**

Run: `npm run test:scenario`

Expected: FAIL because collision, target-status, special-file, and budget limitations are absent.

- [ ] **Step 3: Implement fail-closed observation enrichment**

After traversal, group case-folded UTF-8 paths; append `CASE_COLLISION` to every member of a group with more than one distinct path. For each symlink, resolve its target lexically and attempt `realpath` only to classify `BROKEN_SYMLINK`, `EXTERNAL_SYMLINK`, or `INTERNAL_SYMLINK`; do not enqueue the target. Catch per-entry `lstat`, `readdir`, and hashing errors and emit an observation or run warning rather than dropping unrelated entries.

Use these exact run transitions:

```js
const finalStatus = warnings.length || inventory.some((record) => record.limitations.length)
  ? 'COMPLETE_WITH_LIMITATIONS'
  : 'COMPLETE'
```

- [ ] **Step 4: Verify GREEN and deterministic repeated output**

Run: `npm test`

Expected: all tests pass; running the same fixed fixture twice with the same `runId` in clean output directories produces byte-identical `run.json`, `inventory.jsonl`, and `metadata-evidence.jsonl`.

- [ ] **Step 5: Commit limitation handling**

```bash
git add src tests
git commit -m "feat(inventory): preserve bounded scan limitations"
```

---

### Task 5: Detect research metadata without executing tools

**Files:**
- Create: `tests/unit/metadataDetectors.test.js`
- Create: `src/inventory/metadataDetectors.js`
- Modify: `src/audit/runAudit.js`
- Modify: `tests/scenarios/auditScenario.test.js`

**Interfaces:**
- Produces: `detectResearchMetadata(inventory, createdAt): MetadataEvidence[]`.
- `MetadataEvidence` contains `schemaVersion`, `evidenceId`, `standard`, `declarationType`, `artifactId`, `repositoryRelativePath`, `origin: 'DECLARED'`, `collectionMethod: 'PATH_PATTERN'`, `limitations`, and `createdAt`.

- [ ] **Step 1: Write failing detector tests**

```js
// tests/unit/metadataDetectors.test.js
import assert from 'node:assert/strict'
import test from 'node:test'
import { detectResearchMetadata } from '../../src/inventory/metadataDetectors.js'

test('detects declarations without reading or invoking external tools', () => {
  const inventory = [
    ['dvc.yaml', 'DVC'], ['.datalad/config', 'DATALAD'], ['MLproject', 'MLFLOW'],
    ['sacred/runs/1/config.json', 'SACRED'], ['ro-crate-metadata.json', 'RO_CRATE'],
    ['bagit.txt', 'BAGIT']
  ].map(([repositoryRelativePath], index) => ({ artifactId: `a${index}`, repositoryRelativePath }))
  const evidence = detectResearchMetadata(inventory, '2026-07-16T00:00:00.000Z')
  assert.deepEqual(new Set(evidence.map((item) => item.standard)),
    new Set(['DVC', 'DATALAD', 'MLFLOW', 'SACRED', 'RO_CRATE', 'BAGIT']))
  assert.ok(evidence.every((item) => item.origin === 'DECLARED'))
})
```

- [ ] **Step 2: Run the detector test and verify RED**

Run: `node --test tests/unit/metadataDetectors.test.js`

Expected: FAIL because `metadataDetectors.js` does not exist.

- [ ] **Step 3: Implement anchored path-pattern detection**

```js
// src/inventory/metadataDetectors.js
import { createHash } from 'node:crypto'

const declarations = [
  ['DVC', /(^|\/)dvc\.yaml$|\.dvc$/],
  ['DATALAD', /(^|\/)\.datalad(\/|$)/],
  ['MLFLOW', /(^|\/)MLproject$|(^|\/)mlruns(\/|$)/],
  ['SACRED', /(^|\/)sacred(\/|$)/],
  ['RO_CRATE', /(^|\/)ro-crate-metadata\.json$/],
  ['BAGIT', /(^|\/)bagit\.txt$|(^|\/)manifest-[^/]+\.txt$/]
]

export function detectResearchMetadata(inventory, createdAt) {
  return inventory.flatMap((record) => declarations
    .filter(([, pattern]) => pattern.test(record.repositoryRelativePath))
    .map(([standard]) => ({
      schemaVersion: 1,
      evidenceId: `evi:${createHash('sha256').update(`${standard}\0${record.locationId}`).digest('hex')}`,
      standard,
      declarationType: 'REPOSITORY_METADATA',
      artifactId: record.artifactId,
      repositoryRelativePath: record.repositoryRelativePath,
      origin: 'DECLARED',
      collectionMethod: 'PATH_PATTERN',
      limitations: ['DECLARATION_PRESENCE_ONLY'],
      createdAt
    })))
}
```

- [ ] **Step 4: Connect evidence output and verify GREEN**

Call `detectResearchMetadata` only after inventory finalization. Do not import or spawn any DVC, DataLad, MLflow, Sacred, RO-Crate, or BagIt package or executable.

Run: `npm test`

Expected: all tests pass and both standards-aware and legacy fixtures complete; the legacy fixture emits no false declaration.

- [ ] **Step 5: Commit metadata evidence**

```bash
git add src tests
git commit -m "feat(inventory): detect research metadata declarations"
```

---

### Task 6: Prove the complete Issue #1 acceptance seam

**Files:**
- Modify: `tests/helpers/repositoryFixture.js`
- Modify: `tests/scenarios/auditScenario.test.js`
- Modify: `README.md`

**Interfaces:**
- The scenario runner remains `npm run test:scenario`.
- The complete suite remains `npm test`.
- The user entrypoint remains `npm run audit -- --root <path>`.

- [ ] **Step 1: Add the final failing black-box acceptance test**

The test creates one Git-backed fixture containing tracked, untracked, explicitly ignored, hidden, Unicode, case-colliding, hard-linked, symlinked, broken-link, large, executable, special, nested-repository, and unreadable artifacts plus one non-Git fixture. It creates inert `package.json` lifecycle scripts and executable marker scripts whose marker files must remain absent after audit.

```js
test('scenario runner covers Issue 1 without executing repository content', async () => {
  const fixture = await createCompleteScenarioFixture()
  const first = await invokeAudit(fixture.root, fixture.fixedOptions)
  const firstBytes = await readRunBytes(first.runPath)
  await rm(first.runPath, { recursive: true })
  const second = await invokeAudit(fixture.root, fixture.fixedOptions)
  const secondBytes = await readRunBytes(second.runPath)

  assert.deepEqual(secondBytes, firstBytes)
  assert.equal(await pathExists(fixture.executionMarker), false)
  assert.equal(first.run.exclusions.some((item) => item.path === '.git'), true)
  assert.equal(first.inventory.some((item) => item.repositoryRelativePath === '.ignored-evidence'), true)
  assert.equal(first.inventory.some((item) => item.repositoryRelativePath.startsWith('.git/')), false)
  assert.equal(first.inventory.some((item) => item.repositoryRelativePath.startsWith('.repo-curator/')), false)
})
```

- [ ] **Step 2: Run the acceptance scenario and verify RED**

Run: `npm run test:scenario`

Expected: FAIL on at least one not-yet-covered fixture assertion, never because target content executed.

- [ ] **Step 3: Make the minimal fixture or orchestration changes needed for GREEN**

Do not add Git status collection; that belongs to Issue #2. The tracked, untracked, and ignored files must all be present in inventory, with Git state left `null`. Do not add ZIP parsing, semantic classification, mutation, dependency installation, or external metadata tools.

- [ ] **Step 4: Document the supported audit command and limitations**

Add to `README.md`:

```markdown
## Audit inventory

Run `npm run audit -- --root /absolute/path/to/repository` to create a read-only inventory under the target repository's `.repo-curator/runs/` directory.

The current inventory does not follow symlinks, execute repository code, invoke package lifecycle scripts, install dependencies, inspect Git history, or infer cleanup actions. Research metadata detection reports declaration presence only.
```

- [ ] **Step 5: Run all verification commands**

Run:

```bash
npm test
npm run test:scenario
npm pack --dry-run
git diff --check
```

Expected: all tests pass with 0 failures; the package dry run includes only intended source, tests, and documentation; `git diff --check` is silent.

- [ ] **Step 6: Perform the Issue #1 security review**

Verify from tests and source that:

- no `exec`, `spawn`, dynamic import from the target, package manager, Git, or external metadata tool is reachable from production audit code;
- all paths consumed by production code originate from the validated root plus enumerated child names;
- symlinks are classified but never traversed;
- protected output and Git control directories are excluded;
- errors persist only safe codes and do not reproduce file content;
- no secrets or credentials exist in source, fixtures, output snapshots, or Git history.

- [ ] **Step 7: Commit the acceptance slice**

```bash
git add README.md src tests package.json
git commit -m "test(inventory): cover hostile audit scenarios"
```

---

## Plan Self-Review

- Issue #1 coverage: explicit CLI, deterministic outputs, four identities, no-follow traversal, boundaries, budgets, limitations, metadata declarations, hostile fixtures, non-Git fixture, ignored evidence, and scenario seam are assigned to Tasks 1–6.
- Deferred deliberately: sanitized Git evidence and Git-state classification are Issue #2; safe content profiling is Issue #3; ZIP member inspection is Issue #4; semantic evidence and relationships are later issues.
- Dependency policy: zero installed dependencies; Node standard library only.
- Type consistency: `runAudit`, `walkRepository`, `buildArtifactRecord`, identity helpers, detector outputs, and writer inputs use the same camelCase field names throughout.
