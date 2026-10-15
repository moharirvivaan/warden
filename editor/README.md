# Warden for Geode — local alpha

Warden is a source-based preflight companion inside VS Code and Cursor. Its
Geometry Dash-inspired panel displays real compiler evidence, supported hook
signatures, diagnostic explanations, and unsupported coverage.

## Install and open

1. Run **Extensions: Install from VSIX...** and choose the local Warden package.
2. Open a Geode mod project. Run **Warden: Open** from the Command Palette, or
   click the Warden cube in the Activity Bar. No development window or
   F5 is needed after installation.
3. Under **Project setup**, select your compiled native `warden` executable and
   the mod's `compile_commands.json` if they aren't already configured.
4. Save source and click **Analyze mod**. Analysis on save is optional.

This package contains the editor extension, not the native compiler toolchain.
Build the native analyzer from the repository first; LLVM 21 is required. Current
validated coverage is selected Geode 5.8.2, 5.10.1, and 5.11.1 configurations on
macOS ARM64. Other platforms/configurations are not release-tested.

## What works

- Compiler-resolved hook declarations and helpers with source navigation.
- Limited deferred Cocos ownership and late array-bounds review findings.
- Automatic relationship discovery against a prepared local real-mod catalog,
  with pinned source links, source-call/priority facts and visible version gaps.
- Compiler diagnostics, incomplete files, and explicit unknown coverage.
- Cancellation and invalidation after source edits.
- A bounds-guard patch for supported cases: preview, human approval, undo, and
  reanalysis. Ownership findings currently provide guidance without a patch.

For interactions, select a prepared catalog under **Project setup → Interaction
catalog**, then Analyze. No second source checkout is required. Catalog maintenance
and public distribution are unfinished; missing data shows unavailable coverage.

Findings are source-based risk reviews. Neither a finding nor a clean scan
establishes runtime compatibility. Shared hook targets are normal. Cross-mod
conflict detection is not implemented, and Warden cannot approve an Index mod.

## For Index moderators

Pilot Warden on a supported source checkout to inspect selected lifetime and
array-access risks, jump to evidence, and identify what still needs manual
review. This may help focus review; review-time savings and precision across
unseen submissions have not been measured. Original compiler settings and SDK
headers are required. Warden complements Geode's existing tools and human review.

See the repository's `docs/showcase.md` for the historical source comparison and
controlled repair demonstration. No runtime crash has been independently replayed.

Visual references: [RobTop's official UI screenshot](https://www.robtopgames.com/Images/screenshot01.png).
The panel uses original CSS and an original SVG mascot, with no game artwork,
fonts, or network resources bundled into the interface.
