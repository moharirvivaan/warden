# Warden product correction: real Geode developer workflows

Research date: October 14, 2026. The research below is source review only; no
historical crash was independently reproduced and no developer adoption or time
saving was measured. Subsequent implementation added a limited ownership review
and an SDK-adapted source benchmark; see the implementation note at the end.

## Decision

The synthetic remove/access demonstration was too weak as the primary product
proof. Preserve its SDK/build/package tests, but defer its runtime test. The
existing Clang hook inventory remains useful infrastructure. It is not yet a
compatibility product.

Warden's target is a Geode-specific preflight and debugging companion: identify
supported lifetime/API hazards, explain relevant mod interactions, and help a
developer decide what to reproduce before releasing a change. Analysis may run
automatically; repairs and runtime experiments retain human review.

## What real mods do

- **Click Between Frames:** input queues, substeps, timewarp, physics bypass,
  scene transitions, and platform-specific hook choices. Current source modifies
  PlayLayer, CCScheduler, GJBaseGameLayer, PlayerObject, and other classes. The Mac
  path explicitly substitutes a direct update hook for an inlined delta method.
  [Source](https://github.com/theyareonit/Click-Between-Frames/blob/master/src/main.cpp)
- **BetterEdit / Tinker / Editor Tab API:** editor modes, tabs, toolbar scaling,
  object manipulation, playtesting, and extension callbacks. The BetterEdit repair
  adopts API-managed tab state/callbacks and changes hook priorities; it is not
  explained by a removed-node rule.
  [BetterEdit repair](https://github.com/HJfod/BetterEdit/commit/f0bd86f502f6e48a352fae138acf0d8dd17bfc41),
  [Tinker features/API](https://github.com/Alphalaneous/Tinker/blob/main/README.md)
- **BetterInfo / Stat Changes / GDDP:** online responses, profile/leaderboard
  lifetimes, cached data, level-completion bookkeeping, persistence, and resources.
  GDDP's PlayLayer source also checks practice, test mode, and ignore-damage state
  before recording completion.
  [GDDP gameplay source](https://github.com/Minemaker0430/GDDPIntegration/blob/main/src/hooks/PlayLayer.cpp)
- **Globed:** multiplayer events and third-party event API contracts. A listener
  can close its owner while multiple events are queued, requiring explicit batch
  termination; runtime/platform ABI issues also appear.
  [Event lifetime repair](https://github.com/GlobedGD/globed2/commit/94fc4d3e69354d6aae5ab1705e75b4d99b84ccbe)

Read-only installed metadata supplied source URLs for CBF, BetterInfo, Integrated
Demonlist, and Eclipse. Eclipse's listed public repository returned 404 during
this review, so its implementation is not analyzed here. Installed metadata is
not proof of source availability or a defect. Current source/history was inspected
for CBF, BetterInfo, BetterEdit, Tinker, Globed, Stat Changes, and GDDP. No whole
mod is categorized as safe or unsafe.

## Historical candidate set

Fourteen candidates are recorded below. “Source repair” means the author's
repair and relevant code change are visible, not that Warden reproduced or detects
the failure. Changelog-only cases and source changes without defect confirmation
carry weaker evidence. Separate related candidates must not be counted as
independent validation of one rule without examining their mechanisms.

| Candidate | Source finding and strength | Product implication / feasibility |
|---|---|---|
| CBF / More Level Tags | [Repair](https://github.com/theyareonit/Click-Between-Frames/commit/bebf844c86c63bb1429ae9520934b58263be3104) adds missing-parent and zero-step handling. Source repair names the other mod. | Real gameplay/scene-context compatibility case. AST can expose the changed checks; full runtime reproduction and historical Windows setup are pending. |
| CBF input-hook priority | [Change](https://github.com/theyareonit/Click-Between-Frames/commit/749cd5bf075f5d4bb67322ed26b21205e0bf6811) moves push/release priorities from 50000 to INT_MIN. Source change; exact defect linkage unestablished. | Hook order is a useful fact, not a sufficient conflict detector. Don't recommend this priority universally. |
| CBF physics bypass | [Repair](https://github.com/theyareonit/Click-Between-Frames/commit/9dcf401d1052745521e812c053f8aa429a485e24) clamps step count and changes delta gating. Source compatibility repair. | Numeric/timing assumptions require scenario testing; unlikely to be proved by a simple AST overlap rule. |
| CBF spawn-trigger timing | [Repair](https://github.com/theyareonit/Click-Between-Frames/commit/c26b39d22dbb07d21330eb8c8c6d295fce9d01e1) moves input processing into processCommands and handles first-frame physics timing. Source gameplay repair. | Operation placement within the update cycle matters. Static facts can prioritize tests; behavioral proof needs a runtime scenario. |
| CBF editor playtest | [Repair](https://github.com/theyareonit/Click-Between-Frames/commit/a26cd0ee23fc1161f2a852079473216f37c9dd52) adds explicit editor-context early return and narrows a declared incompatibility version. Source repair/changelog. | Test editor playtest separately from ordinary levels. Version-specific metadata is context, not novel detection by itself. |
| BetterEdit / Editor Tab API | [Repair](https://github.com/HJfod/BetterEdit/commit/f0bd86f502f6e48a352fae138acf0d8dd17bfc41) adopts API-managed state/callbacks, adjusts priority, and changes dependency metadata. Source compatibility repair. | Cross-mod API coordination is a strong benchmark. Several coordinated changes prevent attributing the repair to one static warning. |
| BetterInfo deferred level lifetime | [Repair](https://github.com/Cvolton/betterinfo-geode/commit/04365ad20d13bd9618413f134fba6ff9ada074b7) changes a queued raw capture to a Ref capture after closing a popup. Author calls it a possible crash. | Best initial ownership diagnostic seed. Historical metadata targets SDK 5.10.1 and supports Mac; whole-project build/settings/dependencies still need verification. |
| BetterInfo failed-request delegate | [Repair](https://github.com/Cvolton/betterinfo-geode/commit/2fdcf7f9362645f5cf406f05911d9dd96b9ce79b) checks registration and erases the delegate on the error branch, matching success handling. Source crash repair. | Callback validity must survive failed requests and closed views. A null check alone doesn't establish delegate validity. |
| BetterInfo pagination bounds | [Repair](https://github.com/Cvolton/betterinfo-geode/commit/7afad587dede7309eddfc7e582c31a0dd8c5572a) moves the bounds check before objectAtIndex. Author labels a potential crash. | SDK-aware array checks are plausible diagnostics; generic analyzers may also help. Do not claim cross-mod specificity. |
| BetterInfo saved enum | [Repair](https://github.com/Cvolton/betterinfo-geode/commit/03193815f0c8141516581a364487ca83dbbceb33) handles a failed saved-value lookup before label refresh. Author labels a possible crash. | Persistence input validation is useful but lower differentiation than ownership/interaction analysis. |
| Globed event batch lifetime | [Repair](https://github.com/GlobedGD/globed2/commit/94fc4d3e69354d6aae5ab1705e75b4d99b84ccbe) introduces SkipRemainingEvents and returns it after a callback closes its owner. Source use-after-free repair and API documentation. | Distinct SDK/API contract diagnostic candidate. Requires explicit batch semantics; a Ref-capture rule alone does not solve it. |
| Globed Windows player list | [Repair](https://github.com/GlobedGD/globed2/commit/c07b3efec1fbfbb04ce77fcae13c6c45d252f19c) uses a local comparator with an author comment about Clang/MSVC ABI. Source Windows crash repair. | Demonstrates platform/compiler constraints. This is outside a first Mac AST diagnostic; never label a Mac pass as Windows coverage. |
| Stat Changes / GDDL profile close | [Report](https://github.com/RedLime/Stat-Changes-Geode/issues/1), [repair](https://github.com/RedLime/Stat-Changes-Geode/commit/0a31cc8f9d7a88a066f4f50726fbae3f47422b63) replace a stored profile pointer with a current-scene lookup. Source repair; preexisting null check remained insufficient. | Related lifetime evidence, not the exact queued-capture rule. Old SDK/platform configuration limits straightforward reuse. |
| GDDP / Grandpa Demon | [Changelog](https://github.com/Minemaker0430/GDDPIntegration/blob/main/changelog.md) attributes crashes to changed vanilla nodes and records incompatibility handling/removal over versions. Maintainer account, not inspected repair diff. | Node assumptions do occur in real mods. That does not justify making synthetic node removal the product's entire scope or claiming the exact removal/lookup mechanism is proven. |

Additional leads, not extra confirmed defects: GDDP's changelog documents resource
crashes involving square.png; [BetterInfo's Ref adoption](https://github.com/Cvolton/betterinfo-geode/commit/6aa5cb0d65b49eda5e24f8ad87bfa58a9b2bbbe9)
provides manual retain/release and RAII ownership controls. A refactor is not proof
that every changed raw pointer was buggy.

## Existing tools and differentiation

The official VS Code extension already checks settings/resources, offers hook
method suggestions, and recommends numFromString. Its inspected linter uses
regex-based scans. DevTools already inspects live node trees and properties.
These capabilities must not be marketed as new Warden inventions.
[VS Code changelog](https://github.com/geode-sdk/vscode/blob/main/CHANGELOG.md),
[linter source](https://github.com/geode-sdk/vscode/blob/main/src/providers/lint.ts),
[DevTools](https://github.com/geode-sdk/DevTools/blob/main/README.md).

Potential differentiated value: compiler-resolved object types and ownership
flow, deferred-callback contracts, source-linked hook/API interaction explanations,
and version/configuration-specific reproduction guidance. This is a recommendation
from code review, not a measured advantage over all existing analyzers or tools.

## First concrete developer capability

Recommend **deferred Cocos object ownership diagnostics**, initially limited to
Geode queueInMainThread and explicit supported Cocos factories/capture forms.
The first real benchmark is BetterInfo's original and repaired LevelIDLayer
callback, not a renamed toy mod. Resolve types and ownership through the AST:
identify a created/autoreleased object, its raw capture into queued work, uses
inside the callback, and recognized Ref ownership. Explicit/manual retention,
unknown factory ownership, aliases, and externally owned objects need either
supported reasoning or visible unknown results. Do not warn on every lambda.

Proposed finding: the object crosses a deferred execution boundary without
established ownership; display origin, capture, use, platform/SDK context, and
an inferred risk label. Offer a human-reviewed Ref-capture patch only when the
supported contract is established. Retaining an object changes its lifetime and
can affect behavior, so neither automatic application nor universal safety is
assumed.

First milestone acceptance:

1. Configure the selected real mod revision and dependencies with actual build
   settings. Its SDK 5.10.1 metadata is an explicit feasibility decision against
   the engine's initial 5.11.1 coverage; no success claim through mocked headers.
2. Flag the original supported capture and recognize the repaired capture, using
   the author's before/after revisions. Keep report/source labels exact.
3. Verify harmless Ref captures and explicit supported ownership, and unknown
   aliases/unsupported forms. Hold out separate examples for evaluation.
4. Verify whether a reproduction is possible; otherwise label the result as a
   source-level benchmark, not a game crash reproduced by Warden.
5. Ask active developers whether the evidence/action fits their workflow. Record
   actual correct findings, false positives, misses, and unknown cases; no invented
   percentages or time-saving claims.

## Preserve the cross-mod product objective

Local diagnostics are the first useful capability, not a replacement for mod
interaction analysis. Build the next layer around selected mod versions and a
specific changed method/API: show relevant source, hook continuation/priority
facts, known metadata relationships, and which gameplay/editor scenarios deserve
testing. Use CBF and BetterEdit historical repairs as evaluation cases.

Observed source facts, inferred risks, and runtime findings must be separate.
Hook order cannot generally prove physics or replay behavior. If static analysis
cannot establish a conflict, the tool should explain uncertainty and help narrow
reproduction instead of generating a confident conflict label. A useful report
should tell a developer why a selected scenario matters, not list every mod that
shares a function.

No editor integration or runtime instrumentation is implemented by this research.
The diagnostic design must cover real-project setup, the
specific ownership contract, evaluation controls, and the developer's review
action. Keep the synthetic tests as lower-level engineering coverage.

## Implementation note — October 14, 2026

The native analyzer now provides `geode.deferred-cocos-ownership` as a review
finding with observed source locations and an inferred-risk label. It recognizes
explicit supported raw captures and retaining Ref constructors; unsupported
ownership transformations remain unknown. It does not infer a confirmed crash
from a pointer capture, certify a mod, or apply fixes.

The complete, unchanged historical `LevelIDLayer.cpp` was parsed using actual
SDK 5.11.1 headers and CMake compiler settings. Its metadata declares 5.10.1;
the original SDK build and other translation units/external API dependencies
remain unverified. The reviewed callback at line 28 produces an ownership review
in parent b68e2fda4be2e671b0907c2e803c4094124e2fa4, and the author's Ref capture
in 04365ad20d13bd9618413f134fba6ff9ada074b7 is recognized as retaining. Other raw
leaderboard captures at lines 50 and 65 are review leads, not confirmed new bugs.
The macOS GJGameLevel factory body is opaque in the bindings, so these findings
explicitly mark that contract unverified. CCNode::create has a documented
autorelease contract in the real SDK header. No runtime crash was reproduced.

Preparation: scripts/prepare-ownership.py. Rule and benchmark contracts:
tests/test_ownership.py. A missing real-source cache explicitly skips the benchmark,
never substitutes a mock mod. These results establish one engineering capability,
not the multiple-family, multi-project product readiness outcome.
