# Automatic Interaction Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Analyze one Geode source project in the existing sidebar, automatically surface relevant entries from a bounded real-mod catalog, and explain the evidence and next verification action without a developer guessing a peer.

**Architecture:** Extend real compiler reports with source facts, compare validated reports locally, and reuse that engine across a versioned catalog. Keep project analysis independent of catalog failures. Catalog source navigation uses immutable repository links; optional manual comparison uses contained local roots. No server or new application.

**Tech Stack:** Existing C++23/Clang 21.1.8 LibTooling, CMake/Ninja, Python unittest, plain JavaScript/Node test runner, VS Code/Cursor WebviewView. No new runtime dependencies.

**Spec:** [Approved automatic discovery design and interaction foundation](../../product-scope.md#next-increment-automatic-interaction-discovery).

**Status:** The user directed immediate implementation; executed inline on
`codex/interaction-discovery`, with one independent code review. Native facts,
comparison/catalog modules, real inputs and sidebar discovery are implemented.
Fresh final verification is recorded in docs/progress.md. Remaining manual/platform
checks stay explicitly unverified; this plan does not authorize commit, push,
publishing or game changes.

## Global Constraints

- Shared hook targets do not imply a conflict; matching source signatures do not prove matching runtime addresses.
- Combined order/risk explanations require the same analyzed SDK and target and the same concrete declared game version; gaps remain visible.
- Use real selected Geode 5.8.2/5.10.1/5.11.1 macOS ARM64 configurations; the real catalog demonstration targets SDK 5.10.1. Preserve SDK adaptation and selected-unit labels. Native Windows and portable distribution are not validated by this increment.
- Schema 2 stays backwards-readable. Missing behavior, helper-mediated calls and unsupported constructs remain unknown. Source requests do not establish effective runtime order.
- The default interaction experience needs only the developer's project/build. Manual peer selection is an advanced view, never a prerequisite for catalog discovery.
- At least three distinct real mod catalog entries; controlled fixtures test boundaries and cannot replace the real demonstration. No whole mod is labeled harmless.
- Read-only interactions. Existing primary repairs retain preview, human approval, digest/version checks, undo and reanalysis. No automatic hook-order repairs.
- Preserve workspace trust, argument-array execution, bounded processes, canonical source containment, existing GD assets, readable light/dark text, reduced motion, CSP and code/Agents layout.
- Catalog data cannot execute code or authorize local file reads. No automatic downloads, third-party builds on the user's computer, ecosystem crawler, backend, account, game installation/launch or marketplace publication.
- Preserve existing local work. Generated reports and third-party caches stay ignored. Commit/push only upon user authorization. Record evidence in docs/progress.md.

## Review Focus

1. A catalog version is not the developer's intended dependency version: show exact constraints and mismatch/unknown, withhold combined conclusions and never silently choose the newest version. Tasks 2–3.
2. A report can contain absolute paths, traversal, forged repositories or malformed nested evidence: sanitize at preparation, validate on ingestion and resolve navigation from host-owned records. Tasks 3, 5.
3. Shared-header observations differ across translation units, or forwarding is helper-mediated/out-of-line/nested: preserve source facts and disagreement/unknown, never infer a missing original call. Task 1.
4. A catalog load fails or a source/snapshot/peer selection changes during an async run: retain valid primary diagnostics, reject stale discovery/navigation and display unavailable coverage. Tasks 3, 5.
5. A dependency makes a standalone test invalid, a priority request is conditional/overflows, or a successful retrieval is mistaken for a reproduced defect: constrain suggestions and distinguish source evidence from runtime outcomes. Tasks 1–2, 6.

## File responsibilities

| Files | Responsibility |
| --- | --- |
| `src/hook_behavior.hpp/.cpp` (new), `src/model.hpp`, `src/extraction.cpp`, `src/analysis.cpp`, `src/report.cpp`, `CMakeLists.txt` | Extract, merge and expose registered-hook behavior facts. |
| `tests/test_hook_behavior.py` (new), `editor/core.js`, `editor/test/core.test.cjs`, `.github/workflows/checks.yml` | Real-SDK contracts, strict optional-field validation and CI selection. |
| `editor/interactions.js`, `editor/test/interactions.test.cjs` (new) | Pure pair comparison and source-specific review suggestions. |
| `editor/catalog.js`, `editor/test/catalog.test.cjs` (new) | Snapshot validation, candidate retrieval and immutable source URLs. |
| `scripts/prepare-interactions.py` (new), `docs/toolchain-lock.json` | Real pinned source preparation, sanitized catalog generation and provenance. |
| `editor/analysis-session.js`, `editor/source-state.js`, corresponding `.test.cjs` files (new) | Run generations, independent state and source/configuration fingerprints. |
| `editor/extension.js`, `editor/package.json`, `editor/webview.js`, `editor/media/panel.js`, `editor/media/panel.css`, editor host tests | Default discovery, optional manual peer investigation, trusted navigation and existing repair regression. |
| `docs/showcase.md`, `docs/progress.md`, `docs/product-scope.md`, README files | User-repeated evaluation, actual coverage and limits. |

Create files only when their task needs them. The generated catalog stays under `build/interaction-catalog`; do not commit third-party reports or sources.

## Task 1: Extract hook behavior evidence

**Consumes:** Registered derived method and target class from `Visitor::finish`, validated SDK provenance in `Inventory`, and existing `Location`/`Unknown` types.

**Produces:** In `src/model.hpp`, `ForwardingCall { Location location; std::string context; }`, `PriorityRequest { Location location; std::string hookName, api, status, relativeMod; std::optional<int64_t> requestedValue, preOrderValue; }`, and `HookBehavior { std::vector<ForwardingCall> forwardingCalls; std::vector<PriorityRequest> priorityRequests; std::vector<Unknown> unknown; }`. Append `std::optional<HookBehavior> behavior` to `Method`.

Native interface in `src/hook_behavior.hpp`:

```cpp
HookBehavior inspectHookBehavior(
    const clang::CXXMethodDecl& method,
    const clang::CXXRecordDecl& modification,
    const clang::CXXRecordDecl& target,
    clang::ASTContext& context, const Inventory& inventory,
    const fs::path& root);
```

JSON `hook.behavior` contains `scope: "source_facts_only"`, `forwarding_calls`, `priority_requests`, and `unknown`. Calls contain a location and context: `body`, `condition`, `conditional_branch`, `loop`, or `nested_callable`. Priority requests contain `hook`, `api`, `status`, `relative_mod`, nullable `requested_value`/`pre_order_value`, and location. Status is `observed_constant`, `observed_relative`, or `unknown`; neither observed status means the request succeeded at runtime.

- [ ] **1. Write actual-SDK tests in `tests/test_hook_behavior.py`.** Reuse `AnalyzerTests.fixture`/`run_warden`; do not replace headers. Assert exact target/signature/source line for `MenuLayer::init()`, including an out-of-line definition. Assert that overloads, another receiver, helpers, and comments do not count as direct forwarding. A call in an `if` condition is `condition`; one inside its branch is `conditional_branch`. Nested lambdas, loops, and short-circuit branches retain explicit context rather than an all-paths claim.
- [ ] **2. Run the new file and observe missing behavior evidence fail.** Command: `python3 -m unittest discover -s tests -p test_hook_behavior.py -v`.
- [ ] **3. Implement forwarding extraction.** Match the actual SDK target declaration/class/type and current receiver; resolve method definitions. Static/indirect/helper-mediated/unresolved forms stay unknown. Record only observed call sites; zero direct calls must never create a missing-original diagnostic. Do not add behavior-only gaps to legacy inventory-completeness claims: keep them in the hook's explicit evidence/unknown fields.
- [ ] **4. Add priority red tests, then implement priority extraction.** Scan instantiated `onModify` context only. Resolve SDK callees for `setHookPriority`, `setHookPriorityPre`, `setHookPriorityPost`, and supported before/after requests. For numeric requests use compiler constant evaluation; raw/Pre preserves the pre-order value, Post negates it only within int32 range. Assert raw `GEODE_ID_PRIORITY` is 2000 in the selected real SDK and `setHookPriorityPost(..., Priority::Early)` requests -1000 with pre-order value 1000. Cover NodeIDs' actual shape: the priority call is the eagerly evaluated condition in `if (!self.setHookPriority(...)) { log failure; }`, not a conditionally executed branch call. A call inside a branch/short-circuit RHS stays unknown for ordering. Post with INT32_MIN, dynamic/conditional requests, absent instantiation, unrelated receiver/API, and ambiguous overload names cannot yield a known numeric order. Preserve a resolvable relative mod ID/API as a request fact; do not solve effective relative order in this increment.
- [ ] **5. Wire model, extraction, reporting, and CMake.** `methods()` serializes optional behavior; text output describes the same facts. `parseReport` accepts old schema-2 reports and validates every new enum, numeric range, bounded array, and source location when behavior exists. Malformed behavior fails the report boundary rather than being rendered as clean evidence.
- [ ] **6. Merge evidence across units.** Extend hook deduplication in `analysis.cpp`; if the same declaration has different observations, retain the source facts plus a configuration-dependent unknown and withhold ordering. Add a real-header/two-TU test with different active branches; also test that syntax errors discard the affected unit's behavior and that PCH-backed source does not lose SDK identity.
- [ ] **7. Verify and checkpoint.** Run the new SDK tests and `node --test editor/test/core.test.cjs`, then the full strict suite after the task settles. Extend the existing native CI selection to include the new class. Record the inspected SDK cases and unavailable forms; leave changes uncommitted unless authorized.

## Task 2: Compare validated reports and generate useful observations

**Files:** `editor/interactions.js`, `editor/test/interactions.test.cjs`.

**Consumes:** Parsed schema-2 inspection reports with optional Task 1 behavior.

**Produces:** `compareReports(primary, peer)` returning `{status, reasons, relationships}`. Status is `ready`, `partial`, or `blocked` and refers to source review availability, never compatibility. Each relationship has `target_class`, `method`, `signature`, `primary_hooks`/`peer_hooks` (indexes into those reports), and observations `{evidence, message, sources, suggestion}`. Sources are `{side, hook, kind, index}`; side is `primary`/`peer`, kind is `declaration`/`forwarding`/`priority`/`unknown`.

- [ ] **1. Write failing pure-adapter tests.** Two registered hooks with the same canonical class/method/signature produce one informational relationship and no conflict verdict. Same names with different signatures and helpers do not join. Multiple modify classes remain attached as separate hook indexes. Missing behavior remains unknown. Missing/failed reports and duplicate roots/IDs produce blocked reasons; partial reports cannot become a clean compatibility result.
- [ ] **2. Observe red.** Run `node --test editor/test/interactions.test.cjs` before implementation.
- [ ] **3. Implement grouping/configuration rules.** Require equal nonempty analyzed SDK/target strings and the same concrete numeric game-version string from `mod.gd.mac` or a string `mod.gd`. Missing values, wildcards/ranges, or mismatches retain informational source relationships but block combined ordering/risk conclusions. Never treat missing metadata as a match.
- [ ] **4. Add scenario tests, then implement observation generation.** Direct versus nested/conditional call sites generate different, source-specific explanations. Show numeric priority requests with correct pre/post meaning; discuss requested order only conditionally when both sides have unambiguous constant requests and no configuration-dependent/conditional gaps. Equal priorities, multiple requests, relative requests, missing requests, and missing behavior keep order unknown. Never invent a default priority or call absence a bug.
- [ ] **5. Respect dependencies and intentional replacements.** A peer ID in legacy required dependency metadata, or an object dependency not explicitly optional/recommended, makes the dependent-alone scenario unavailable. Unknown dependency shapes require manual confirmation. Do not implement a new version-range solver; flag required version verification. A helper-based intentional replacement yields an unknown forwarding fact and no automatic fix. Suggestions must quote the relevant observation; unavailable evidence gets a next action, not a generic fabricated scenario.
- [ ] **6. Verify and checkpoint.** Run the adapter tests and all editor tests. Check results are deterministic and source references point to the original validated reports. No source/path data comes from executable webview text.

## Task 3: Validate a versioned catalog and retrieve candidates

**Files:** Create `editor/catalog.js` and `editor/test/catalog.test.cjs`; consume `parseReport` from core and `compareReports` from Task 2.

**Interfaces:**

- `loadCatalog(directory): Promise<CatalogSnapshot>` reads a bounded manifest and report files locally; no network. Snapshot is `{id, createdAt, entries, rejected}` where `id` is the manifest-bytes SHA256, entries are validated and rejected records carry entry ID/reason. Bad manifest prevents discovery; a bad entry is unavailable coverage, not a missing relationship.
- `discoverInteractions(primary, snapshot): DiscoveryResult` returns `{snapshotId, status, candidates, checked, unavailable, excluded}`. Status is `ready`, `partial`, or `unavailable`, concerning discovery coverage only. Each candidate has `entryId`, `group`, `metadataRelationships`, and the Task 2 comparison. Groups are `declared_relationship`, `hook_evidence`, `shared_target` in that order, then stable mod ID/version/revision order. Never show a crash probability.
- `catalogSourceUrl(entry, location): string` resolves only validated GitHub repository/revision plus project-relative location into `https://github.com/OWNER/REPO/blob/REV/PATH#Lline`. Host passes a selected entry and stored record location, never a URL supplied by a webview.

Manifest format: `{schema_version:1, created_at:ISO8601, entries:[{id, report_file, report_sha256, repository, revision, analyzer_revision, analyzer_dirty, build_id, sdk_revision, bindings_revision, source_files:[{file,sha256}], scope, adaptations, runtime_status, license_status}]}`. Reports use a sanitized schema-2 projection accepted by `parseReport`; keep mod identity/version/SDK/game/dependency/incompatibility metadata, toolchain, selected file statuses/diagnostics, hooks and unknowns. Clear local project root and omit build paths, compiler arguments, repairs and unrelated findings. `scope` explicitly lists selected units; runtime status is `not_run`. `analyzer_dirty` and a source/build identity record prevent attributing locally modified behavior to the clean analyzer commit.

Validate manifest <=1 MiB, <=100 entries, each report <=8 MiB and total reports <=32 MiB. Read with bounded file handles, enforce canonical containment for reports, reject symlink escapes and duplicate entry IDs or duplicate mod/version/revision identities. Only relative forward-slash source paths without `..`, empty components, NUL, backslashes or absolute forms may generate links. Repositories must be exact HTTPS github.com owner/repo URLs without credentials, query or fragment; revisions and hashes are lowercase 40/64-character hex as appropriate; `build_id` is a SHA256 of the local build identity record. Integrity hashes are not authentication or permission to redistribute; show catalog origin and `license_status` (`unreviewed`, `redistributable_with_notice`, `restricted`) as provenance. Local alpha supports unreviewed local inputs; public catalog publishing remains deferred.

- [ ] **1. Add failing tests** `test_default_discovery_finds_peer_without_selection`, `test_corrupt_entry_is_unavailable_not_clean`, `test_no_candidates_is_not_compatibility`, and `test_version_constraints_are_not_resolved_by_sort_order`. Assert primary identity is excluded with an explicit self reason, duplicate candidates are stable, and metadata-only optional dependencies stay labeled optional. No implicit version-range solver: only a normalized exact literal (`v` prefix allowed) can establish a version match; ranges/other forms are unknown. Group entries with unresolved constraints but withhold combined order/risk conclusions, even when `compareReports` alone has matching SDK/game metadata. Assert this suppression in the test.
- [ ] **2. Run red** with `node --test editor/test/catalog.test.cjs`.
- [ ] **3. Implement loading and provenance validation** through the exact interfaces above. Add failure tests for file/aggregate limits, invalid exit/status combinations, malformed behavior, forged source URLs, symlinks, bad hashes and missing provenance. Derive exit code from the valid report status before calling `parseReport`; setup-error reports never supply hook conclusions. Conflicting duplicate identity records become rejected coverage instead of first-one-wins.
- [ ] **4. Implement retrieval** using hooks and metadata, not raw text searches. Preserve all candidate versions, exclude primary identity, show exact entry versions, and call Task 2 for source relationships. Treat partial selected-unit coverage as partial even when the native report completed all selected units. `checked` means inspected supported report data, not every file/mod combination. A metadata edge does not establish a provider/consumer API contract.
- [ ] **5. Implement source URLs and test** `test_catalog_paths_cannot_open_local_files`, percent-encoded traversal/URL delimiters, invalid source positions, pinned revisions and missing source mappings. Enforce positive positions and selected source-file membership. Report a missing mapping as unavailable navigation.
- [ ] **6. Verify** with all Node tests. Assert separate counts for accepted checked entries, rejected/configuration gaps and self exclusions; no ecosystem coverage percentage or conflict verdict is produced.

## Task 4: Prepare real catalog inputs and source evidence

**Files:** Create `scripts/prepare-interactions.py`; modify `docs/toolchain-lock.json`; add `tests/test_interaction_catalog.py` for provenance/integration contracts.

**Interfaces:** `python3 scripts/prepare-interactions.py` prepares isolated `.deps/interaction-catalog` inputs and writes `build/interaction-catalog/manifest.json`, sanitized reports and `build/interaction-catalog/evaluation.json`. It does not publish, install, launch the game or overwrite existing unrelated cache edits. Missing inputs exit nonzero with exact dependency/revision/configuration steps.

Pinned initial sources: NodeIDs `fc9b3aa12a4eee67f0d26e3f115190cba2deddf1`, BetterInfo `04365ad20d13bd9618413f134fba6ff9ada074b7`, Server API `924dfc7511cf754fc41530ac9432bce7a67d4223` from `kingminer7/server-api`. Use actual SDK 5.10.1 (`7e41336f68660b990644f5c3450b6da6ae944560`) and the existing bindings lock. NodeIDs/BetterInfo LevelInfoLayer units supply a candidate shared-layer relationship. Server API's `src/hooks/CCHttpClient.cpp` supplies a different hook-family control; BetterInfo also declares it as an optional dependency, so do not call it wholly unrelated. All SDK adaptations and selected-unit limits remain visible.

- [ ] **1. Add failing provenance tests** for original Git HEAD and selected C++ bytes, analyzed versus declared SDK, real bindings, exact compile/PCH settings, all source paths referenced by records, projected report hashes and absence of local paths/repair payloads. Test dirty/unexpected inputs are preserved and rejected. Record the analyzer binary SHA256 and source-diff digest in `evaluation.json`; manifest references this local build identity through a non-private digest field.
- [ ] **2. Run red** with `python3 -m unittest discover -s tests -p test_interaction_catalog.py -v`; missing prepared real inputs fail this explicit integration milestone. Keep its full preparation out of hosted SDK-only CI until its bootstrap is reproducible there; do not hide missing local evidence as a passed check.
- [ ] **3. Prepare genuine configurations**, preserving original C++ and PCH context, with documented CMake-only ARM64/DONT_INSTALL adaptations. Reuse verified dependency caches; do not change the user's mod/game installations. Record the compiler database hash and full local provenance separately from the sanitized catalog. If any chosen source cannot parse usefully with this configuration, report the blocker; do not fabricate hooks, swap in headers or quietly drop the third real entry.
- [ ] **4. Generate and inspect evidence.** Assert direct forwarding and NodeIDs priority facts at real source locations; compare source declarations with report content. Keep intentional helper-based replacements unknown. Load the generated catalog with Task 3 and analyze BetterInfo as the primary project: exclude its own entry; retrieve NodeIDs without selecting it; expose Server API's optional metadata relationship and only actual shared hooks. No claim that either relationship is a discovered defect.
- [ ] **5. Record independent expected relationships before retrieval checks** in `evaluation.json`, citing metadata/source locations and source-review rationale. Measure retrieval of those expectations separately from diagnostic false positives. Selected fixtures may establish unknown/error behavior, never historical crash effectiveness. Add one explicit no-shared-layer check for the selected Server API hook, not a global harmless label.
- [ ] **6. Verify** the preparation script, integration test and generated manifest loader sequentially; record `runtime_status: not_run`, unreviewed licensing and unavailable full-project/platform cases. Keep generated data ignored and report failures explicitly.

## Task 5: Show default discovery and advanced local comparison in the sidebar

**Files:** Create `editor/analysis-session.js`, `editor/source-state.js` and focused tests; modify extension/package/webview/panel files and existing host tests.

**Interfaces:**

- Add `warden.catalogPath` (default empty), `warden.peerProjectPath` and `warden.peerBuildPath` string settings. For this local alpha, resolve catalog to configured path or the development checkout's `build/interaction-catalog`; if absent, show **Interaction catalog unavailable** with a setup action, while primary reviews remain usable. Do not claim catalog bundling/easy public installation is solved.
- Keep `warden.analyze` returning the primary native report for backwards compatibility; it also loads the catalog and computes default discovery. `warden.compare` remains an optional sequential primary/peer run. `warden.interactions` focuses the Interactions tab and returns the current validated discovery result for host verification.
- `createAnalysisSession()` exposes `select(side,{root,build})`, `begin(side)`, `complete(token,report)`, `fail(token,error)`, `invalidate(side)`, `setCatalog(snapshot)`, `failCatalog(error)`, `snapshot()`. A token binds side, generation, root and build; obsolete completion returns false. Snapshot retains independent primary/peer reports/errors/running/stale state plus catalog generation and discovery currentness. Catalog replacement invalidates discovery, not a valid primary diagnostic/repair preview; source edits invalidate affected source and related discovery.
- `captureSourceState(root,build): Promise<string>` fingerprints mod.json, compile_commands.json and current project C++/header paths/bytes with analyzer exclusions and canonical containment. Before/after scans and generations reject observed source changes; this is not an immutable filesystem or transitive-SDK snapshot guarantee.

- [ ] **1. Add failing state/source tests** for outdated completion, primary preservation on catalog/peer failure, catalog snapshot replacement during loading, closed-file edits/additions/deletions, compiler DB edits and external peer edits. Outside-root symlinks cannot cause outside-root reads. Run `node --test editor/test/analysis-session.test.cjs editor/test/source-state.test.cjs` red, then implement the modules.
- [ ] **2. Wire default analysis and invalidation.** Load catalog with independent error handling; display working primary diagnostics even if discovery is unavailable. Capture source/configuration state around each native scan. Bound native execution using existing time/output limits, run optional pair scans sequentially and dispose watchers on selection changes. Watch selected roots, exact compile DB files and manifest/report changes; before navigation revalidate snapshot identity/content, report digest and current generation. A changed snapshot requires reload/reanalysis, not use of cached entry positions.
- [ ] **3. Add host-boundary failures then navigation.** Webview messages carry host-owned result generation, entry/relationship/hook/index and source kind; they cannot supply paths/URLs. Local source uses its contained root and dirty/stale/UTF-8 guards. Catalog source uses Task 3's URL builder and VS Code external-link action. Reject stale cards, forged indexes, malformed sides, traversal and untrusted execution. Catalog has no repair action; primary repairs retain existing approval, undo and reanalysis behavior.
- [ ] **4. Render the Guided Interactions tab.** Show **Interactions to investigate**, snapshot identity/date, checked entries, unavailable/configuration gaps and exact mod versions. Display declared relationships separately from shared-hook evidence; collapse overlap-only details. Each useful card shows evidence, explanation and a specific review/test action. Never label retrieved candidates as crashes/conflicts. Empty/old/corrupt/mismatched catalogs have distinct explanations. Preserve readable GD styling, keyboard access, reduced motion, textContent/CSP and code/Agents layout. Put manual **Compare with another mod** and **Remove comparison** in advanced controls; default Analyze never requests a peer.
- [ ] **5. Verify state and editor boundaries** with `node --test editor/test/*.test.cjs`; extend `editor/test/host.js` so `warden.analyze` plus `warden.interactions` retrieves a real catalog entry with no peer setting. Test missing/corrupt catalog still leaves the original reviews. Actual rendering/click claims require the real editor host/manual observation, not mocks.

## Task 6: Verify the installed workflow and give the user a repeatable evaluation

**Files:** `docs/showcase.md`, `docs/progress.md`, README files, `docs/product-scope.md`; update editor host harness as needed.

**Produces:** A tested local VSIX, actual one-project discovery evidence, explicit limitations and steps the user can perform. Completion concerns this increment, not the full Warden release.

- [ ] **1. Run the actual installed extension** using the established local VSIX process and isolated editor profile. Configure the real BetterInfo project, its selected compiler settings and prepared catalog once. Click Analyze without selecting a peer; inspect NodeIDs evidence, optional Server API metadata, source links, configuration/coverage gaps and snapshot identity. Verify local and pinned remote sources open correctly. Changing/undoing primary source and replacing a catalog snapshot must invalidate/recompute the appropriate results. Test manual pair selection separately; it is not the main showcase.
- [ ] **2. Recheck supported repair regression** with the existing SDK-backed bounds fixture: preview/cancel/apply/undo/save/reanalyze; confirm catalog availability does not bypass human approval or stale-source checks. Keep controlled-fixture observations labeled as engineering checks. Exercise keyboard, narrow light/dark sidebar and preserved code/Agents groups. If UI automation is unavailable, record exactly which actions require the user's check instead of claiming them passed.
- [ ] **3. Write hands-on steps** in `docs/showcase.md`: install the local VSIX, configure primary/build/catalog, Analyze, read the observed interaction, open both sources, inspect checked/version gaps, edit/undo/rescan and record what was useful or confusing. Explain actual source evidence versus unexecuted tests. Required dependencies make some standalone scenarios invalid. No game test runs until its concrete paths/packages/recovery procedure is approved.
- [ ] **4. Run final verification after changes settle.** Sequentially run `cmake --build build`, `python3 tests/run.py --strict --report build/quality/native-tests.json`, `node --test editor/test/*.test.cjs`, the actual-host check and `git diff --check`. Confirm fresh preparation/integration results as well as pure tests; any skip/unavailable input prevents an evidence-complete claim. Extend the existing native CI selection with new SDK contracts but do not claim hosted historical/catalog coverage until it runs.
- [ ] **5. Request one independent whole-change review**, fix actionable findings and rerun affected checks. Record exact verified results, omitted checks, open distribution/platform work and user next action. Commit/push only if newly authorized.

## Completion gate

One real project must surface a relevant real catalog entry in the actual sidebar
without peer selection, with useful source facts, coverage/version limits, working
local/remote navigation and a repeatable user procedure. Three distinct real
catalog entries are required; fixture-only catalogs or a two-project screenshot
are insufficient. No universal conflict detection, reproduced historical crash,
validated developer demand, runtime safety, easy public distribution or native
Windows support is established by this increment.

## Execution notes

The implementation uses existing epoch/repair state rather than a duplicate
analysis-session module. Catalog state is independently invalidated; source-state
fingerprints and peer-specific disposed watchers protect report freshness. The
real selected-unit preparation expands genuine SDK PCH umbrella headers textually
and preserves source bytes; full historical/CMake builds are not reproduced.
These rulings and the independent review fixes are recorded in docs/progress.md.

Observed real Cursor behavior includes rendered discovery cards and both local
and pinned remote source navigation. The packaged extension host also exercised
source edit/Undo/reanalysis. A new full manual repair-button walkthrough, light-theme
rendering and manual-peer clicks remain unverified in this increment. Passing
engineering tests is not runtime compatibility or product-demand evidence.
