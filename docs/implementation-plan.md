# Warden first analyzer implementation plan

Approved scope: C++23/Clang LibTooling CLI for one macOS ARM64 Geode SDK
configuration. Extract supported hook declarations, helpers, locations, and
unknown coverage from real SDK-backed source. No runtime compatibility claims.

## Tasks

1. Prepare LLVM 21.1.8, CMake/Ninja, Geode v5.11.1, and the official example.
   Record exact upstream revisions and configure a real compilation database.
2. Write CLI integration assertions first, observe failure, then implement
   compile database loading, AST/preprocessor extraction, and text/JSON reports.
3. Add SDK-backed cases for anonymous/named modifications, helpers/overloads,
   shared headers, inactive code, diagnostics, manual hooks, and setup failures.
   Observe failures before extending behavior and run the complete suite.
4. Review the whole feature, resolve correctness findings, and verify the
   official example and full suite. Leave changes on the feature branch.

## Interface

`warden inspect MOD_ROOT -p BUILD_DIRECTORY [--format text|json]`

JSON reports contain metadata, toolchain/configuration, files, modifications,
hook declarations, helpers, and unresolved cases. Records carry project-relative
source locations. Analysis errors invalidate that translation unit's inventory.
Exit codes: 0 completed extraction, 1 partial/unsupported analysis, 2 setup error.

## Acceptance

The real official example reports MenuLayer::init as a hook and onMyButton as a
helper. Controlled tests verify declaration deduplication, macro origins,
registration evidence rather than method names, diagnostics, and equivalent
text/JSON results. Mock headers cannot satisfy the real-example acceptance gate.
