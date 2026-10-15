# Warden showcase and moderator pilot

Warden is a local Geode source-review companion inside VS Code/Cursor. The panel
uses a Geometry Dash-inspired visual style; the findings come from the native
compiler analyzer, not the theme or staged demo data.

## Why a moderator might pilot it

Geode's [Index guidelines](https://docs.geode-sdk.org/mods/guidelines/) require
compatibility and identify preventable crashes as a reason for rejection. The
[review tips](https://github.com/geode-sdk/docs/blob/main/mods/guidelines-tips.md)
identify concrete C++/SDK pitfalls. Warden's current contribution is narrower:

- Bring selected deferred-object and array-access risks to the reviewer's attention.
- Link each review to source locations and the SDK/configuration actually analyzed.
- Separate registered hooks from helpers and expose unknown/incomplete coverage.
- Explain possible repairs and require a person to review any generated patch.

This is a case for an opt-in pilot on supported source checkouts. It is not a
recommendation that all Index moderators install Warden yet. Cross-mod interaction
analysis, precision on unseen submissions, and review-time savings remain
unvalidated. Warden cannot decide whether a mod meets all Index rules, identify
AI-written code reliably, or replace source/gameplay review. Shared hooks are normal.

## Install the current local alpha

The local VSIX is generated in `build/warden-geode-0.1.0.vsix`. Use
**Extensions: Install from VSIX...** in VS Code/Cursor. Open a mod project and run
**Warden: Open**, or click the Warden cube in the Activity Bar. Installed use
stays in your normal editor window; F5 is only for extension development.

The extension package does not include the analyzer or LLVM. Build `build/warden`
using the root README, then select it under **Project setup → Configure analyzer**.
Use the actual mod build's `compile_commands.json`. Current validation covers
selected Geode 5.8.2/5.10.1/5.11.1 configurations on macOS ARM64. The present binary
links Homebrew LLVM 21; copying only that executable is not a portable distribution.

Do not instruct reviewers to run arbitrary project setup scripts automatically.
They should inspect the source/build configuration they choose to trust. Warden
requires editor workspace trust before executing its native analyzer.

## Try automatic interaction discovery

This is the new one-project workflow. It demonstrates source investigation using
three pinned real mods, not automatic detection of a confirmed incompatibility.

On this prepared development Mac:

Verified locally: 98 strict Python/SDK contracts and 45 editor tests pass. The
installed Cursor host checks discovery plus saved-source edit/Undo/reanalysis;
actual sidebar cards and both source-link actions were also observed. These are
engineering/source-workflow results, not game compatibility evidence.

1. Install the freshly packaged `build/warden-geode-0.1.0.vsix` using
   **Extensions: Install from VSIX…**, then reload the editor window.
2. Open `build/Try-Warden-Interactions.code-workspace`. It points to the isolated
   BetterInfo source copy, real SDK 5.10.1 compiler settings, native analyzer and
   local catalog. You do not need F5 or another source project selection.
3. Run **Warden: Analyze Mod**, then select **Interactions**.
4. Expect NodeIDs and Server API relationship cards, two catalog entries checked
   and one self entry excluded. NodeIDs has shared `LevelInfoLayer::init` and
   `updateLabelValues` targets. Server API appears because BetterInfo declares it
   as optional; the selected source units do not share layer hooks.
5. Expand a NodeIDs target. **Open your source** opens the local BetterInfo file;
   **Open pinned mod source** opens the exact NodeIDs GitHub revision in a browser.
   Inspect direct-call placement and the observed priority request. Warden does
   not infer that UI IDs are supplied solely from these hook/metadata facts.
6. Read configuration and coverage. Only selected units were analyzed; other
   source, versions, runtime conditions and platforms remain unknown. NodeIDs'
   declared SDK differs from the selected SDK. A bare dependency version is a
   minimum in Geode; differing literals remain unresolved without a range solver.
7. Add a comment to the isolated BetterInfo source, save, and confirm results
   become stale. Undo, save and Analyze again. This changes only the disposable
   source copy. To inspect behavior with real dependencies in the game, prepare
   and approve a separate concrete runtime procedure first.

Record whether the tool located relevant code faster than your usual workflow,
which explanation helped, and which card was irrelevant or confusing. Do not
record a crash prevented or compatibility passed when no game test ran.

Preparation for developers maintaining this checkout:

```bash
python3 scripts/prepare-interactions.py
python3 -m unittest discover -s tests -p test_interaction_catalog.py -v
```

This script requires the pinned source caches and genuine SDK 5.10.1 BetterInfo
compiler configuration already present. It fails with the missing input rather
than downloading/building arbitrary projects. Original C++ is preserved. A
selected-unit compiler adapter expands the real CMake PCH's SDK umbrella headers
textually; it does not reproduce the historical/full-project build. Private local
compiler settings and full reports remain in ignored build outputs. Catalog
reports link pinned public source and retain unreviewed license status; public
catalog redistribution has not been approved or validated.

## Showcase 1: an author's real source repair

Purpose: demonstrate a useful source review from a real Geode mod.

1. Open `.deps/betterinfo-original-sdk` at baseline revision
   `04365ad20d13bd9618413f134fba6ff9ada074b7` in the installed extension.
2. Choose `build/bounds-only/compile_commands.json`, the prepared real SDK 5.10.1
   configuration. Analyze saved source.
3. Open the bounds review at `src/layers/_bases/BIViewLayer.cpp:206`. Explain that
   `objectAtIndex(i)` occurs before the upper-bound check. Show the late guard and
   the suggestion, then open Coverage so the selected-unit limitation is visible.
4. Open `.deps/betterinfo-bounds-fixed` at author repair
   `7afad587dede7309eddfc7e582c31a0dd8c5572a`, choose its build settings, and analyze.
   The supported bounds review is absent after the author checks bounds first.

[Author repair](https://github.com/Cvolton/betterinfo-geode/commit/7afad587dede7309eddfc7e582c31a0dd8c5572a).
The chosen baseline is not the immediate parent of this repair. This is a source
comparison using selected real SDK/dependency settings, not a reproduction of
the original historical runtime/dependency environment. No crash was independently
replayed. Other raw captures are review leads, not confirmed new defects.

The current supported source produces a patch candidate. Preview it without
changing historical source: it inserts an early upper-bound guard and preserves
the original null handling. Apply only to a disposable copy or your own working
branch after reviewing the intended fallback. The author's fixed revision remains
a separate comparison; a generated patch is not proof of gameplay behavior.

## Showcase 2: controlled repair workflow

Purpose: demonstrate editor integration and human participation; this is not an
independent historical crash benchmark.

### Try it yourself on the prepared development Mac

The ignored local workspace `build/Try-Warden.code-workspace` already selects
the prepared mod, analyzer, and compiler settings. It is a convenience for this
machine, not a portable installer or an end-user setup solution.

1. In your normal Cursor/VS Code window, run **Extensions: Install from VSIX...**
   from the Command Palette and select `build/warden-geode-0.1.0.vsix`. Reload
   the editor if it asks. Do not press F5; that starts a development host.
2. Use **File → Open Workspace from File...** and select
   `build/Try-Warden.code-workspace`. Review/trust this local workspace so the
   analyzer can run. Open **Warden: Open** from the Command Palette.
3. Click **Analyze mod**. Expect two reviews and one registered hook. Open each
   review's source link and check that its explanation matches the actual code.
4. In the bounds review, click **Preview fix**. The diff should insert an early
   bounds check; the actual `main.cpp` must still be unchanged. Click
   **Apply reviewed fix**, then cancel the approval dialog: no edit should occur.
5. Preview again and approve the repair. Expect the bounds review to disappear
   after reanalysis, leaving the ownership review. Focus `main.cpp`, undo with
   Cmd+Z, save, and analyze again: both reviews should return.
6. To check failure handling, add `this_name_does_not_exist();` inside the hook's
   `init()` body, save, and analyze. Expect a compiler error/incomplete coverage,
   not a successful clean scan. Undo that edit, save, and analyze to restore it.

Stop and record the exact action/error if any expected result fails. These steps
let you judge the current interface and repair controls; they do not test gameplay
or prove cross-mod usefulness. For independent product validation, the next test
must involve an actual modding task and a supported real defect or interaction.

The actual extension-host test prepares an SDK-backed mod under
`build/editor-host/mod`, with one registered `MenuLayer::init` hook, a raw queued
Cocos capture, and an array access followed by a late guard. Its compiler settings
come from the real official Geode example, not mock headers.

1. Analyze the controlled mod. Show both diagnostic families.
2. Click the bounds source location. **Preview fix** opens the actual proposed diff;
   the file must remain unchanged at this point.
3. Review the inserted early guard. **Apply reviewed fix** requires a modal approval.
   The existing null guard stays intact, and Warden saves and reanalyzes the source.
4. Verify that the bounds finding disappears while the unrelated ownership review
   remains. Undo the edit in the source editor, save, and reanalyze; it reappears.
5. Show a syntax-error scan and Coverage, so the audience sees incomplete analysis
   rather than an empty result being marketed as safety.

Compiler reanalysis and undo do not establish correct gameplay fallback behavior.
Before any mod release, test pagination/empty-array behavior in the intended game
configuration. Warden currently launches no game and changes no game installation.

## Claims suitable for a post

“I'm building Warden, a compiler-backed Geode preflight extension for VS Code and
Cursor. It links selected object-lifetime and array-access risks to source, shows
where analysis is incomplete, and previews supported fixes for human approval.
I've tested a real historical source repair plus controlled SDK-backed editor
workflows. Cross-mod interaction analysis is the next major capability.”

Do not claim automatic ecosystem-wide conflict detection, proven crash prevention,
measured review savings, universal platform coverage, or completed product-market
validation. Ask interested modders/moderators to share cases and try a supported
source checkout; do not imply Geode has endorsed Warden.

## Verification commands

- Native contracts and historical source controls: `ctest --test-dir build --output-on-failure`.
- Editor process/navigation/repair/setup boundaries: `node --test editor/test/*.test.cjs`.
- Actual Cursor host: `editor/test/host.js`, launched with the installed package in
  an isolated profile. A browser design preview is only visual QA.

Assets are original CSS/SVG. Visual direction was researched from
[RobTop's official screenshot](https://www.robtopgames.com/Images/screenshot01.png)
and [the official Steam listing](https://store.steampowered.com/app/322170/Geometry_Dash/).
