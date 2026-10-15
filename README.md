<div align="center">

<img src="editor/media/cube.svg" width="88" alt="Warden’s original cube mascot">

# Warden for Geode

**Geode source reviews, right beside your code.**

A local preflight companion for Geometry Dash mod developers, inside VS Code and Cursor.

**Local alpha · macOS ARM64 validated · Human-reviewed repairs**

[Try it](#try-the-local-alpha) · [Features](#what-works-today) · [Roadmap](#where-warden-is-going) · [Development](docs/development.md)

</div>

---

Building a mod means reasoning about C++, Geode hooks, object lifetimes, and the
game’s behavior. Warden brings selected source risks into an editor sidebar, links
them to the relevant code, explains its evidence, and shows where analysis stops.

The broader goal is to help developers understand and test interactions between
mods before release. **Cross-mod compatibility analysis is not implemented yet.**
The current alpha establishes the source-analysis and reviewed-repair workflow.

## What works today

| Capability | Current behavior |
| --- | --- |
| **Hook inventory** | Resolve supported hook declarations, modified classes, signatures, and source locations; keep helpers separate. |
| **Deferred ownership reviews** | Flag selected raw Cocos object captures used in queued callbacks and explain the lifetime concern. |
| **Bounds reviews** | Identify supported `CCArray::objectAtIndex` accesses where an upper-bound exit happens too late. |
| **Reviewed bounds repair** | Preview an early guard, approve the edit, and reanalyze. Undo stays available in the source editor. |
| **Visible uncertainty** | Show compiler errors, incomplete files, unsupported constructs, and the configuration analyzed. |
| **Native editor sidebar** | Geometry Dash-inspired styling, an original cube mascot, source navigation, cancellation, and optional analysis on save. |

Analysis uses Clang’s AST and the selected SDK’s instantiated registration
machinery. A matching method name alone does not establish a supported hook.

**Shared hook targets are normal—not proof of a conflict.** A clean scan is not a
runtime safety verdict. Ownership reviews provide guidance, not generated repairs;
neither rule proves general memory or bounds safety.

## Try the local alpha

Warden is **not published on an extension marketplace yet**. The current package
requires the native analyzer and LLVM separately. Easier installation is
unfinished release work.

1. [Build the native analyzer](docs/development.md#build) with LLVM **21.1.8**.
2. Package the editor extension from this checkout:

   ```bash
   cd editor
   npx @vscode/vsce package --no-dependencies --skip-license --out ../build/warden-geode-0.1.0.vsix
   cd ..
   ```

3. In VS Code or Cursor, run **Extensions: Install from VSIX…** and select that
   package. Open your mod and run **Warden: Open**, or click its cube in the
   Activity Bar. **F5 is only for extension development.**
4. Under **Project setup**, choose `build/warden` and your mod’s real
   `compile_commands.json`. SDK headers, generated bindings, and required
   dependencies must already be available.
5. Save your source and click **Analyze mod**. Open **Reviews** for findings,
   **Hooks** for inventory, and **Coverage** for gaps.

For supported bounds findings, select **Preview fix**, inspect the diff, then
**Apply reviewed fix**. Applying requires approval; source changes never happen
silently. Build and test the intended gameplay behavior after any repair.

No server, account, telemetry, or AI service is required. Warden does not launch
Geometry Dash or install mods into your game.

## Platforms and coverage

| Environment | Status |
| --- | --- |
| macOS ARM64 | Validated selected configurations with Geode **5.8.2**, **5.10.1**, and **5.11.1**. |
| Windows | Not yet validated or packaged. Windows x64 is a planned release target. |
| Other platforms / SDK versions | No release claim; unsupported analysis remains unknown. |

The current macOS executable links Homebrew LLVM. Copying it alone is not a
portable installation. Only the active compilation configuration is analyzed;
manual hooks and many ownership/control-flow patterns remain outside coverage.
See [detailed coverage and exit codes](docs/development.md#analyze-another-mod).

## Evidence, not a safety badge

Warden has SDK-backed extraction and diagnostic tests, editor boundary tests, and
a real Cursor extension-host test harness. A historical BetterInfo source comparison
checks that a supported late-bounds review appears before an author’s repair and
is absent afterward, using selected real SDK/dependency settings.

**Historical crashes have not been independently reproduced.** Fixture tests and
source comparisons do not establish gameplay compatibility, general precision,
developer demand, or time savings. Warden does not approve Index submissions.

- [Hands-on test and historical source demonstration](docs/showcase.md)
- [Real-mod research and candidate capabilities](docs/research/real-mod-product-review.md)
- [Recorded SDK, compiler, and source revisions](docs/toolchain-lock.json)

## Where Warden is going

The intended value is specific: **help a developer understand which mod
interactions need testing, why, and what the tests actually observed.**

- Explain evidence-supported interactions between specific mod versions, beyond
  merely listing shared hooks.
- Guide repeatable compatibility scenarios and distinguish suspected risks from
  observed failures.
- Compare changes against previous findings and tests so regressions are visible.
- Ship an extension with managed analyzer setup and validated Windows support.
- Validate usefulness with independent modders and real tasks, across multiple
  diagnostic families and interactions.

These are product goals, not capabilities of the current alpha. A general coding
assistant can already investigate local bugs; Warden needs to earn its place through
Geode-specific evidence and a repeatable compatibility workflow.

## Develop and verify

After building and preparing the pinned example:

```bash
python3 scripts/prepare-example.py
./build/warden inspect .deps/example-mod -p .deps/example-mod/build
./build/warden inspect .deps/example-mod -p .deps/example-mod/build --format json
ctest --test-dir build --output-on-failure
node --test editor/test/*.test.cjs
```

Before claiming the full prepared Python/SDK suite passed, run the strict gate:

```bash
python3 tests/run.py --strict --report build/quality/native-tests.json
```

Strict mode fails on skipped tests, expected failures, or no executed tests. It
records missing-evidence reasons in JSON. Historical inputs must be prepared;
their absence cannot count as passing release evidence. CTest can use the same
policy with `cmake -S . -B build -DWARDEN_STRICT_TESTS=ON`.

[GitHub checks](.github/workflows/checks.yml) define editor boundary checks and
a scoped native SDK 5.11.1 job. They do not run the full historical benchmark set,
the interactive editor workflow, or gameplay tests; their configuration alone is
not evidence that they have executed successfully.

Expected inventory: `MenuLayer::init()` is a hook; `onMyButton()` is a helper.
Preparation needs network access and leaves dependencies under ignored `.deps/`.
Some historical benchmarks need additional cached source/configurations; see the
[development guide](docs/development.md) for requirements and explicit skips.

For editor development, prepare the example, open this checkout, and launch
**Warden: Editor Panel** from Run and Debug. Source lives in `src/`, the extension
in `editor/`, setup helpers in `scripts/`, and regression tests in `tests/`.

The older synthetic node-removal experiment remains an engineering fixture; it is
deferred as the main product demonstration. See [product scope](docs/product-scope.md)
and [implementation notes](docs/progress.md) for context.

---

Warden is an independent project, not an official Geode, Geometry Dash, VS Code,
or Cursor product. Its interface uses original CSS/SVG assets inspired by Geometry
Dash’s visual style.
