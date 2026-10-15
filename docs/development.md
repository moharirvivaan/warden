# Analyzer development and coverage

Commands below run from the repository root. For installation status and the editor
workflow, start with the [project README](../README.md).

## Build

Initial supported environment: macOS ARM64, LLVM **21.1.8**, C++23, and Geode
**5.8.2, 5.10.1, or 5.11.1**. Xcode or Command Line Tools must provide a macOS SDK. Build dependencies:

```bash
brew install llvm@21 cmake ninja
WARDEN_LLVM_PREFIX="$(brew --prefix llvm@21)"
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_CXX_COMPILER="$WARDEN_LLVM_PREFIX/bin/clang++" \
  -DCMAKE_C_COMPILER="$WARDEN_LLVM_PREFIX/bin/clang" \
  -DLLVM_DIR="$WARDEN_LLVM_PREFIX/lib/cmake/llvm" \
  -DClang_DIR="$WARDEN_LLVM_PREFIX/lib/cmake/clang"
cmake --build build
```

Python 3 is used for setup and integration tests; the analyzer is a native C++ executable.

## Test gates

Fast checks, without SDK setup:

```bash
python3 -m unittest discover -s tests -p test_runner.py -v
node --test editor/test/*.test.cjs
```

With all SDK and historical source inputs prepared:

```bash
python3 -m pip install -r tests/requirements.txt
python3 tests/run.py --strict --report build/quality/native-tests.json
```

The JSON report separates failures, setup errors, skips with reasons, and expected
failures. Strict mode rejects any skipped or expected-failure test; an empty or
all-skipped run always fails. A successful Python gate does not establish editor
host behavior, game behavior, cross-mod compatibility, or release readiness.

CTest uses the same runner. Configure `-DWARDEN_STRICT_TESTS=ON` to require strict
evidence; its JSON report is written under the build's `Testing/` directory.
Development mode still permits optional historical inputs to be absent, but labels
the result `passed_with_skips` rather than treating those tests as executed proof.

The GitHub workflow prepares the official SDK 5.11.1 example and exercises the
core extraction/ownership/bounds contracts. It also runs editor boundary tests on
Linux and macOS. It does not bootstrap the historical SDK/PCH configurations, run
the installed editor UI, or establish native Linux/Windows support. A fresh clone
still needs the separately documented historical inputs for the full strict gate;
one-command historical setup remains unfinished.

## Run the real Geode example

```bash
python3 scripts/prepare-example.py
./build/warden inspect .deps/example-mod -p .deps/example-mod/build
./build/warden inspect .deps/example-mod -p .deps/example-mod/build --format json
ctest --test-dir build --output-on-failure
```

Preparation downloads pinned source and checksum-verified binaries under `.deps/`.
It configures the official example for ARM64 with concrete metadata, explicit macOS
SDK paths, and precompiled headers disabled for that example. The upstream `src/main.cpp` is unchanged
and its checksum is verified. Geode's `GEODE_DISABLE_CLI_CALLS` configuration avoids
game-profile requirements; no mod is installed into Geometry Dash. The example's
NodeIDs dependency is a runtime dependency and is not installed by this syntax-only
demo. First preparation needs network access; dependency/configuration failures stop
the script rather than fall back to substitute headers.

Exact SDK, bindings, example, and compiler versions are recorded in
[docs/toolchain-lock.json](toolchain-lock.json). Preparation also writes
`.deps/example-mod/warden-provenance.json`, recording the macOS SDK, code-generator
checksum, and dependency revisions used in that checkout. The upstream code-generator
download is published under a moving release label; if its content changes, the
recorded checksum deliberately rejects it. Updating that pin requires review.

Expected inventory: `MenuLayer::init()` is a hook and `onMyButton()` is a helper.
This validates extraction against the SDK, not crash detection or game execution.

## Analyze another mod

Configure the mod with its real SDK and dependencies, `CMAKE_EXPORT_COMPILE_COMMANDS=ON`,
one ARM64 architecture, and an explicit `CMAKE_OSX_SYSROOT` from
`xcrun --sdk macosx --show-sdk-path`. Preserve the mod's real includes. Compatible
Clang 21 PCH files are supported; disabling a PCH may remove required umbrella
headers and change the compilation context. Then run:

```bash
./build/warden inspect /path/to/mod -p /path/to/mod/build --format json
```

The tool parses source using `compile_commands.json`; it does not run compiler command
strings through a shell. SDK headers and generated bindings must already exist.
Warden does not configure or build arbitrary input projects automatically.

The report includes mod metadata, Clang/SDK/target information, original compiler
arguments and working directories, per-file diagnostics, modifications, hooks,
helpers, ownership/bounds findings, proposed patches when supported, and unknown cases. JSON schema version 2 adds
`findings` and `ownership` to the inventory. Locations in the project are relative to its root.
Implementation files outside the mod root, and files under `.deps/`, `.git/`,
`.cache/`, `build/`, or the selected build directory, are excluded. Other vendored
or submodule directories inside the root are treated as project content; automatic
dependency ownership inference is outside this version's scope. Included project headers are listed, declarations are
deduplicated across translation units, and unseen source/header files are unknown.
Only the active conditional-compilation configuration is analyzed.

Exit codes:

| Code | Meaning |
|---|---|
| `0` | Analysis completed in the selected scope; review findings may still be present. This is not a compatibility verdict. |
| `1` | Partial analysis, unsupported constructs/target, conflicting commands, or unresolved coverage. |
| `2` | Invalid setup: metadata/database problems or required Geode headers missing. |

Compiler errors discard that translation unit's hook/helper and ownership evidence and remain
visible in its diagnostics. Matching a base name is not enough: the supported
registration branch must select the actual derived method. Helpers with different
signatures remain helpers. Constructors, destructors, lifecycle modifications,
member templates (including generic `onModify`), manual/raw hooks, and unresolved registration forms
are outside supported coverage and reported as unknown when encountered.
Recognized manual entry points are `Mod::hook`, `Hook::create`, and Tulip's
`createHook`; this is not universal manual-hook discovery. Unsupported constructs
present in the AST can remain unknown even inside discarded `if constexpr` branches.

## Deferred Cocos ownership review

The first rule, `geode.deferred-cocos-ownership`, recognizes actual SDK
`Loader::queueInMainThread` and free `geode::queueInMainThread` calls. For supported
local flows it reports a raw Cocos object used inside an explicit by-value lambda
capture, with its creation, capture, and use locations. Each finding explains the
inferred risk, suggests reviewing ownership/using a retaining `Ref` capture, and
states the limits. Nothing is edited automatically.

Initial factory coverage is `cocos2d::CCNode::create()` (documented autorelease)
and `GJGameLevel::create()` (macOS implementation unavailable in the bindings).
The latter produces an explicitly unverified ownership review; Warden does not
claim it proved that factory's macOS autorelease behavior or reproduced a crash.
`Ref(pointer)` captures are recognized as retaining, without a safety verdict.
Aliases, manual lifetime operations, reference/default captures, recognizable
Cocos template wrappers, branching flow, captured `this`, stored callable objects,
and unmodeled factories remain unknown. Arbitrary ownership hidden inside custom
classes, other asynchronous APIs, and full lifetime proof are outside coverage.

An optional real-source benchmark uses BetterInfo's historical before/after
`LevelIDLayer.cpp`, unchanged, with SDK 5.11.1 compiler settings. The mod originally
declares 5.10.1: this is a **selected-unit, SDK-adapted source benchmark**, not an
original-SDK full-project build or runtime reproduction. Prepare the existing
cached SDK/example first, then:

```bash
git clone --no-checkout https://github.com/Cvolton/betterinfo-geode.git .deps/betterinfo-benchmark
git -C .deps/betterinfo-benchmark checkout --detach 04365ad20d13bd9618413f134fba6ff9ada074b7
python3 scripts/prepare-ownership.py
./build/warden inspect .deps/betterinfo-benchmark -p .deps/betterinfo-benchmark/build/level-id-only
```

Preparation records its CMake adaptation, revisions, hashes, and scope in the
cached build's `warden-provenance.json`. It does not fetch missing external API
headers, stub them, install a mod, or launch the game. Unanalyzed files remain
visible. The integration test compares parent `b68e2fda4be2e671b0907c2e803c4094124e2fa4`
with repair `04365ad20d13bd9618413f134fba6ff9ada074b7`; without that cache the
benchmark test explicitly skips, while SDK-backed rule contracts still run.

## Scope and next step

The second rule, `geode.late-array-bounds-check`, resolves actual CCArray API
declarations and reviews an adjacent upper-bound exit that appears **after**
`objectAtIndex`. It handles raw arrays and Geode `Ref<CCArray>` member access.
Supported preceding guards suppress the review; guard mutations, intervening
effects, and unmodeled control flow remain unknown. General missing-bounds,
alias, negative-index, and lifetime proof are not provided by this rule.

The regression benchmark compares unchanged BetterInfo `BIViewLayer.cpp` from
revision `04365ad20d13bd9618413f134fba6ff9ada074b7` with the author's repair
`7afad587dede7309eddfc7e582c31a0dd8c5572a`, using SDK 5.10.1 compiler settings.
The earlier snapshot is not the repair's immediate parent. Warden reviews the
late access at line 206 before the repair; that review is absent afterward.
This validates source-level behavior, not an independently reproduced crash.

The supported registration form is `GEODE_APPLY_MODIFY_FOR_FUNCTION` in the pinned
SDK, for named/anonymous `$modify` classes and resolved direct `Modify<Derived, Base>` inheritance. Results describe observed declarations;
runtime addresses, hook priority, enable/disable state, and actual installation are
not established. Windows, Android, iOS, other SDK versions, and other build
configurations are not validated by this release.

Cross-mod diagnostics, revision comparisons, ecosystem graphs, CI integration, and
runtime compatibility testing are future work. Further diagnostic families need
independent real-mod examples and developer feedback. The integration fixtures
verify analyzer behavior; they are not reproduced historical crash cases.

## Controlled runtime proof preparation

This experiment is deferred as the primary product milestone. Three SDK-backed test mods provide a candidate node-removal/access experiment
and a guarded repair variant. Their ARM64 builds, hook inventories, package
contents, provenance, and overwrite protections have automated checks. Live-game
reproduction remains a human-reviewed milestone; no crash detection is claimed.

See [the probe sources and build instructions](../examples/compatibility-proof/README.md)
and [the runtime review procedure](runtime-test-procedure.md). Analysis may
run automatically; repairs default to human-approved patches, and changes to the
game installation or publication require user authorization.

The evidence-schema tests use the development dependency in
`tests/requirements.txt`; the native analyzer and packaging commands do not.
