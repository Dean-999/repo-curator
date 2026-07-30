# repo-curator improvement research

Date: 2026-07-29

## Lookup method

The requested `research-lookup` workflow was attempted first with
`parallel-cli 0.7.1`. The installed CLI required interactive device
authorization and neither `PARALLEL_API_KEY` nor `OPENROUTER_API_KEY` was
configured, so the waiting processes were stopped. The lookup then used the
available web search backend, restricted to primary papers, standards, and
official project documentation.

No target repository code, workflow, hook, notebook, package manager,
container, or remote project operation was executed.

## Findings

### 1. Treat semantic conclusions as selective predictions

Selective prediction literature separates coverage from risk: a system may
abstain on uncertain cases instead of optimizing one product-wide accuracy
number. Confidence calibration must be evaluated on held-out data, and
calibration can degrade under distribution shift.

Implication for repo-curator:

- publish risk-versus-coverage curves per claim type;
- report precision, recall, coverage, abstention, and unresolved rates
  separately;
- stratify by repository type, language, evidence availability, and adapter;
- calibrate only on independently reviewed cases;
- treat a new repository family as distribution shift until evaluated;
- never translate an uncalibrated score into mutation authority.

Primary sources:

- Guo et al., "On Calibration of Modern Neural Networks", ICML 2017:
  https://proceedings.mlr.press/v70/guo17a
- Ovadia et al., "Can You Trust Your Model's Uncertainty? Evaluating
  Predictive Uncertainty under Dataset Shift", NeurIPS 2019:
  https://proceedings.neurips.cc/paper_files/paper/2019/hash/8558cb408c1d76621371888657d2eb1d-Abstract.html
- Xin et al., "The Art of Abstention: Selective Prediction and Error
  Regularization for Natural Language Processing", ACL 2021:
  https://aclanthology.org/2021.acl-long.84/
- Fisch et al., "Calibrated Selective Classification", 2022:
  https://arxiv.org/abs/2208.12084

### 2. Add metamorphic tests, not only example fixtures

Research-repository interpretation has an oracle problem: for many repositories
there is no cheap universal ground truth. Metamorphic testing checks relations
between inputs and outputs after controlled transformations. Property-based
generation can automate those transformations.

Useful repo-curator metamorphic relations include:

- reordering JSON object keys must not change evidence identity;
- changing file enumeration order must not change deterministic outputs;
- adding an unrelated file must not change existing semantic claims;
- renaming a file without supporting lineage must not invent lineage;
- changing timestamps alone must not establish a canonical result;
- replacing a regular file with a symlink must reduce coverage or fail closed;
- adding prompt-injection text must remain an observation and not alter policy;
- removing evidence may preserve or weaken a claim, never strengthen it;
- adding a limitation may preserve or reduce authority, never authorize action;
- adapter failure must not erase unrelated inventory evidence.

Primary sources:

- Alzahrani, Spichkova, and Harland, "Application of property-based testing
  tools for metamorphic testing", 2022:
  https://arxiv.org/abs/2211.12003
- Saha and Kanewala, "Fault Detection Effectiveness of Source Test Case
  Generation Strategies for Metamorphic Testing", 2018:
  https://arxiv.org/abs/1802.07361

### 3. Continuously fuzz every untrusted parser boundary

OSS-Fuzz and libFuzzer emphasize small deterministic harnesses, mixed valid and
invalid seed corpora, coverage guidance, corpus minimization, and continuous
execution. repo-curator's archive, JSON, JSON-LD, notebook, CSV, manifest, and
supplied-export parsers fit this model.

Implication for repo-curator:

- one local fuzz harness per adapter or parser family;
- fuzz only repo-curator code against synthetic bytes, never target code;
- assert bounded time, memory, entity counts, references, and output size;
- treat crash, secret echo, path escape, network attempt, or authority increase
  as failures;
- minimize every discovered failure into a permanent regression fixture;
- track parser-boundary coverage separately from unit-test line coverage.

Primary sources:

- OSS-Fuzz documentation:
  https://google.github.io/oss-fuzz/
- LLVM libFuzzer documentation:
  https://llvm.org/docs/LibFuzzer.html
- OWASP malicious archive upload guidance:
  https://owasp.org/www-project-web-security-testing-guide/latest/4-Web_Application_Security_Testing/10-Business_Logic_Testing/09-Test_Upload_of_Malicious_Files
- OWASP path traversal guidance:
  https://owasp.org/www-community/attacks/Path_Traversal

### 4. Give the evaluation corpus a data card

Datasheets and Data Cards document origin, composition, collection and
annotation methods, intended use, limitations, maintenance, and decisions that
affect performance. This is directly applicable to repo-curator's gold corpus
and representative repository fixtures.

Implication for repo-curator:

- create a compact corpus card for each evaluation release;
- record sampling frame, excluded repositories, licenses, languages, research
  domains, repository ages, evidence-tool ecosystems, reviewer process, and
  disagreement;
- publish supported and unsupported slices;
- bind metrics to an immutable corpus version;
- report every corpus change as a reviewable evaluation change.

Primary sources:

- Gebru et al., "Datasheets for Datasets", CACM 2021:
  https://www.microsoft.com/en-us/research/publication/datasheets-for-datasets/
- Pushkarna, Zaldivar, and Kjartansson, "Data Cards", ACM FAccT 2022:
  https://research.google/pubs/data-cards-purposeful-and-transparent-dataset-documentation-for-responsible-ai/

### 5. Validate exported evidence graphs with standard shapes

RO-Crate provides an integrated view of research objects. Workflow Run RO-Crate
distinguishes prospective workflow descriptions from retrospective actions.
SHACL provides machine-readable constraints and validation reports for RDF
graphs while leaving the validated graph immutable.

Implication for repo-curator:

- keep the internal exact-version schemas as the authority;
- add an optional SHACL validation profile for exported RO-Crate only;
- validate required identifiers, typed links, action/input/output direction,
  and explicit limitation records;
- keep validation failure separate from scientific truth;
- never infer execution merely because a graph satisfies a shape.

Primary sources:

- RO-Crate 1.2:
  https://www.researchobject.org/ro-crate/specification/1.2/
- Workflow Run RO-Crate profiles:
  https://www.researchobject.org/workflow-run-crate/profiles/
- W3C SHACL Recommendation:
  https://www.w3.org/TR/shacl/

### 6. Sign release provenance, not only artifact hashes

Hashes bind content but do not independently establish who produced an
artifact. SLSA provenance records build definition, resolved dependencies,
builder identity, and output subjects. Sigstore can bind signatures to an
identity and transparency-log evidence.

Implication for repo-curator:

- emit an in-toto/SLSA provenance statement for the Skill bundle;
- bind source commit, builder workflow identity, source-lock, manifest, tests,
  release-check, and output digest;
- sign the bundle and provenance using keyless Sigstore where feasible;
- verify signer-builder pairs and expected workflow identity at installation;
- retain offline-verifiable transparency-log material with the release.

Primary sources:

- SLSA provenance specification:
  https://slsa.dev/spec/v1.2/provenance
- Sigstore verification documentation:
  https://docs.sigstore.dev/cosign/verifying/verify/

### 7. Use archival identifiers for real-repository fixtures

Git commits are necessary but a hosting repository can disappear or be
rewritten. Software Heritage persistent identifiers provide an additional
content-addressed archival reference at repository, revision, directory, and
file granularity.

Implication for repo-curator:

- record both upstream Git commit and SWHID when available;
- preserve license and adoption boundary alongside the identifier;
- derive the smallest fixture needed for the behavior under test;
- do not fetch archived content during normal tests.

Primary sources:

- Software Heritage documentation:
  https://docs.softwareheritage.org/
- Di Cosmo, "Archiving and Referencing Source Code with Software Heritage",
  2020:
  https://www.softwareheritage.org/publications/

## Recommended order

1. Extend the adapter adversarial matrix with metamorphic relations and
   parser-boundary fuzz harnesses.
2. Add corpus cards and SWHIDs to representative real-repository fixtures.
3. Complete claim-specific, stratified calibration with risk-coverage curves.
4. Add signed SLSA/in-toto release provenance.
5. Add optional SHACL validation for exported RO-Crate.
6. Keep mutation disabled until the separate human admission gate is met.

## What qualifies as a good idea for repo-curator

A proposed feature is strong when it:

1. reduces unsafe certainty or improves evidence traceability;
2. reinforces retrospective evidence reconstruction rather than generic file
   management;
3. has a deterministic or independently reviewable failure oracle;
4. preserves no-target-execution and bounded-resource behavior;
5. degrades to limitation, gap, or abstention;
6. can be introduced as a small reversible vertical slice;
7. uses a maintained standard or mature implementation behind the local safety
   boundary;
8. does not expand the user-facing schema unless it changes a real decision.
