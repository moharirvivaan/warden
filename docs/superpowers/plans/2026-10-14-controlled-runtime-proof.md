# Controlled Runtime Proof Implementation Plan

**Status:** Task 1/2 preparation implemented and tested. Task 3 is deferred by
the user's product correction: real mod evidence must drive the next capability.
This synthetic demonstration is no longer the primary product milestone. See
docs/research/real-mod-product-review.md.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Execute natively in the current session; no agent delegation is needed for this tightly coupled probe.

**Goal:** Build reviewable SDK-backed test mods and establish whether a specific
node removal/access interaction reproduces a runtime failure and has a valid repair.

**Architecture:** Keep test mods and their build/packaging tooling separate from
the analyzer. Produce candidate and repaired binaries, record their provenance,
and run a user-approved scenario matrix. Implement the compatibility diagnostic
only in the next milestone if this probe succeeds.

**Tech Stack:** C++23, Geode SDK 5.11.1, pinned bindings from
docs/toolchain-lock.json, LLVM 21.1.8, CMake, Ninja, Python standard library.

**Spec:** docs/proof-demo.md; human participation requirements in AGENTS.md.

## Global Constraints

- macOS ARM64 first; use docs/toolchain-lock.json and record source/binary hashes.
- Real SDK headers, bindings, and linked libraries; no mock Geode implementation.
- Neither dependency setup nor packaging installs mods automatically.
- Controlled test mods are not historical defect evidence or index submissions.
- No explicit crash instruction: the candidate failure arises from an unchecked
  node use after another mod changes the relevant node.
- A person reviews the packages, run procedure, intended fallback, and results.
- Preserve uncommitted work; do not retry the declined commit, merge, or publish.

## Review Focus

1. Hook post-call order differs from assumed order: log actual operation order
   and reject the demonstration if it does not exercise the intended interaction.
2. NodeIDs or base initialization is absent: record dependencies and base init
   success; distinguish setup failures from the candidate interaction.
3. A repair prevents a crash by breaking initialization or feature behavior:
   verify the optional feature both present and intentionally absent.
4. A copied game shares saved data: do not claim isolation from a separate bundle
   alone; approve an explicit protection/recovery procedure before launching.
5. Stale packages produce misleading results: associate each run with package
   hashes, loaded versions, platform, and run identity.

---

### Task 1: Build the controlled source variants

**Files:** Create `examples/compatibility-proof/CMakeLists.txt`,
`examples/compatibility-proof/remover/mod.json`,
`examples/compatibility-proof/remover/src/main.cpp`,
`examples/compatibility-proof/consumer/mod.json`,
`examples/compatibility-proof/consumer/src/main.cpp`,
`examples/compatibility-proof/consumer-guarded/mod.json`,
`examples/compatibility-proof/README.md`, `scripts/configure-proof.py`, and
`tests/test_proof_packages.py`.

**Interfaces:** Consumes pinned SDK/bindings and official example conventions.
Produces build targets `proof_remover`, `proof_consumer`, and
`proof_consumer_guarded`, with unique IDs `warden.proof-remover`,
`warden.proof-consumer`, and `warden.proof-consumer-guarded`.

- [ ] Write SDK-backed build assertions: all three targets compile and link for
  ARM64; compiler database entries resolve the actual SDK; each has a distinct
  GEODE_MOD_ID matching its metadata. Confirm failure before adding the targets.
- [ ] Add a single top-level SDK subdirectory and three shared-library targets.
  Use Release, ARM64, no PCH, and no automatic installation. Reuse pinned cached
  codegen and dependency sources rather than downloading moving inputs.
- [ ] Implement `configure-proof.py` as a local-only configuration command.
  Verify the lockfile's SDK/bindings revisions and LLVM version, copy the verified
  cached codegen binary into build/proof/bindings/codegen/Codegen, and configure
  examples/compatibility-proof into build/proof with Ninja, the explicit macOS
  sysroot, compile_commands enabled, GEODE_BINDINGS_REPO_PATH=.deps/bindings,
  GEODE_DISABLE_CLI_CALLS=ON, GEODE_DISABLE_PRECOMPILED_HEADERS=ON, and
  SKIP_BUILDING_CODEGEN=ON. Resolve all paths absolutely. Missing cached inputs
  produce a setup error pointing to prepare-example.py rather than downloading
  or changing global settings. Run `python3 scripts/configure-proof.py` before
  building the targets.
- [ ] Implement named MenuLayer::init hooks that check the base initializer.
  The remover looks up `bottom-menu`, checks it, and removes it. The consumer
  looks up the same node and performs a visible optional UI operation without a
  guard. The guarded variant performs that operation only when the node exists
  and still returns successful initialization when the optional UI is absent.
  Use a separate guarded translation unit and its own metadata so inventory
  databases never conflate two configurations of one source. The guarded source
  preserves the same UI action and changes only the guard and explicit fallback.
- [ ] Configure explicit differing hook priorities through the SDK's
  setHookPriorityPost API. Log base-init success and operation markers before
  node removal/access, plus whether the node exists. Check priority-setting
  results; an error is a setup failure. Actual order must be confirmed at runtime.
- [ ] Declare the NodeIDs dependency using the selected SDK's supported metadata
  format; record its exact installed version at the runtime checkpoint. Document
  that the consumer variants are alternatives, never loaded together.
- [ ] Run `cmake --build build/proof --target proof_remover proof_consumer proof_consumer_guarded`
  and the focused SDK-backed tests. Run Warden on each project using the generated
  compiler database: init must resolve as a hook; onModify may remain a documented
  unsupported inventory construct. Do not loosen extraction semantics for the demo.

### Task 2: Produce packages and a reviewable run bundle

**Files:** Create `scripts/prepare-proof.py`,
`examples/compatibility-proof/run-record.schema.json`, and
`docs/runtime-test-procedure.md`; modify `tests/test_proof_packages.py`.

**Interfaces:** `prepare-proof.py --output <directory>` consumes Task 1 binaries
and metadata and emits three `.geode` archives plus `manifest.json`.
Manifest records source hashes, archive hashes, IDs/versions, toolchain pins,
and dependencies. It never launches a game or writes outside the output/build
directories. The run-record schema describes human-observed runtime results.

- [ ] Add package tests asserting matching archive-root mod.json and ARM64 dylib,
  distinct identities, stable content hashes, and refusal to overwrite unrelated
  output files. Verify initial failure before implementation.
- [ ] Implement the producer using the official SDK's mod-package requirements
  and Python zipfile. Compare layout with a locally installed package read-only;
  validate linkage/load paths. Treat successful packaging as preparation, not
  loader acceptance. No Geode CLI installation is required by this approach.
- [ ] Add manifest tests: modifying source changes its recorded digest; stale
  binary/source relationships are rejected instead of silently packaged. Require
  packaging to run the configured CMake build successfully before computing
  hashes, and fail rather than package on a build error. Record target build
  identity and compile configuration alongside hashes.
- [ ] Write a run schema with run ID, scenario, package hashes, SDK/loader/game/
  NodeIDs versions, ARM64 architecture, actual operation order, observations,
  logs/crash artifact paths, intended behavior, and human review status. Keep
  game save content and personal account data out of checked-in evidence.
- [ ] Prepare the exact game-test procedure, paths affected, required dependency
  set, package switch operations, saved-data protection, and recovery steps.
  Inspect macOS SDK path behavior: dirs::getSaveDir uses Application Support/
  GeometryDash; changing working directory or copying the app is not sufficient
  saved-data isolation. Prefer a separate test user/profile with verified isolation;
  otherwise obtain approval for an explicit backup/recovery procedure before run.
- [ ] Run `python3 scripts/prepare-proof.py --output build/proof/packages` and
  package tests; inspect archives and hashes. Present the actual packages and run
  procedure to the user. Wait for this runtime action approval without blocking
  independent local checks. Do not install or launch before approval.

### Task 3: Establish runtime outcomes with the user

**Files:** Create `docs/evidence/controlled-proof/results.json` and
`docs/evidence/controlled-proof/README.md` only as observations arrive. Keep
private logs and crash artifacts under ignored `build/proof/evidence/`.

**Interfaces:** Consumes Task 2 manifest and approved procedure. Produces
schema-valid per-scenario records and a proceed/revise verdict. No compatibility
diagnostic, repair automation, or public release is implemented in this task.

- [ ] Guide the user through checking the isolated baseline and dependency-only
  run. Verify no unrelated third-party mods participate. Record loaded versions.
- [ ] Run remover alone and consumer alone, then their combination, then remover
  plus guarded consumer. Repeat the combined scenario to check reproducibility.
  Use the MenuLayer initialization scenario consistently. If any individual case
  fails, investigate setup or revise the probe; do not call it a cross-mod failure.
- [ ] Verify actual logged order and node availability. The combined failure
  must be linked to the unchecked access; failure to load a package is not evidence.
  If a crash prevents buffered logs being available, use appropriate flushed
  instrumentation or inspect the crash trace before reaching a conclusion.
- [ ] Check the guarded consumer alone visibly performs its optional behavior;
  with remover it intentionally skips that behavior while initialization and
  navigation work. Ask the user whether this fallback is acceptable.
- [ ] Confirm the approved recovery procedure restores the original installation
  and data. Record actual outcomes, including unresolved results; do not backfill
  an observation from a build or static analysis result.
- [ ] Validate results against the run schema, audit evidence labels, and present
  the verdict. Proceed to a separate diagnostic plan only if individual cases
  work, the combined failure is explained and repeatable, and the guarded
  combination works with an accepted fallback.

## Following milestones

1. Supported semantic diagnostic, harmful/harmless matrix, and held-out cases.
2. Reviewed repair preview and rerun checks.
3. Editor background analysis with live findings and visible unknown coverage.
4. Historical defect evaluation and developer feedback; change rules if needed.
5. Reproducible demo video and source-backed public claims, reviewed by the user.

These require their own scoped designs after the preceding milestone produces
evidence. They are not claims of currently implemented capability.
