# Warden: useful release outcome

Status: evolving product scope. The hook inventory, two limited diagnostic
families, one reviewed bounds-guard repair, and a local installable editor
extension are implemented. The VSIX contains the editor, with a separately built
native analyzer/LLVM requirement. Initial bounded-catalog interaction discovery
and hook behavior evidence are implemented locally; broader interaction semantics,
runtime/developer evaluation, and portable distribution remain unfinished.

## User outcome

A Geode developer changes a mod and can understand supported crash risks,
relevant interactions discovered across a supported mod catalog, and concrete checks needed
before releasing. Findings provide evidence and an action rather than a bare
list of shared hooks. Warden remains useful across successive edits and releases.

## Capabilities that belong together

1. **Preflight diagnostics:** several supported Geode-specific defect families,
   initially evaluated from ownership/deferred callbacks, callback validity, and
   hook/API assumptions. Resolve actual types and configured SDK contracts;
   no blanket warning for every raw pointer or hook.
2. **Interaction explanations:** selected mod versions, relevant source/hook/API
   relationships, known continuation/priority facts, and explicit assumptions.
   Identify established risks where supported; otherwise explain what needs a
   reproduction. Shared hook targets do not imply a conflict.
3. **Guided verification and repair:** focused gameplay/editor/network scenarios,
   repeatable configuration and outcome records, and a reviewable repair where
   the intended behavior is clear. Keep fixes undoable and human approved.
4. **Developer workflow:** automatic reanalysis on edits/builds, source-linked
   findings, visible unknown coverage, and a clear way to review or dismiss a
   finding. Interface polish supports working analysis; it does not replace it.

These are product requirements to design and validate, not claims of universal
static-analysis feasibility. Source availability, platform/SDK coverage, changing
runtime state, and mod settings constrain each capability.

## Product readiness evidence

- Evaluate multiple real mod projects and several independently sourced defect
  examples across supported families; do not stop at one training example.
- Separate development cases from evaluation cases, and include verified harmless
  scenarios and unsupported inputs. Count false positives, missed supported cases,
  and unknown cases rather than treating unknown as safe.
- Show an interaction report that contributes useful information beyond a local
  warning or existing metadata checks. Use real compatibility repairs as benchmarks.
- Verify the proposed repair's intended behavior, not merely a passing build.
- Have active mod developers assess whether findings help their actual task.
  Demand, debugging effort saved, and effectiveness remain unmeasured until then.

A first successful detector is a building block. A useful release combines
reliable checks, interaction context, and a practical developer review workflow.
The real-mod evidence and first diagnostic candidate are recorded in
docs/research/real-mod-product-review.md.

## First editor interface specification

User choice: a panel inside VS Code/Cursor. The first local extension now
consumes the native schema 2 report. This section records the agreed interface
and its boundaries. Keep a single editor/ directory for
the extension and use the host editor's existing settings and file dialogs.

### Visual direction and delivery priority

Use the selected Guided layout: code beside Warden, with source-linked details
and clear next actions. Give the panel a Geometry Dash-inspired identity with
geometric outlines, electric cyan/lime accents, and an original small cube
mascot. Use color for hierarchy and explicit status labels, not as the only
indication of severity. Preserve readable contrast in light/dark themes, a
narrow layout, keyboard access, and reduced motion. Keep decorative animation
subtle and separate from analysis results.

Functional readiness comes before final styling. The first inventory panel is
an integration milestone, not the finished product. Establish real diagnostic
behavior using historical repairs, separate evaluation cases, harmless controls,
and visible unknown coverage; then exercise analysis, explanations, source
navigation, and supported repair review in the actual editor. Release readiness
still requires the broader evidence above, including useful interaction context.

Warden runs as a local extension. The Warden: Open command opens
a native sidebar webview beside source code and invokes the native analyzer through
the extension host. During development, test this in an Extension Development
Host window; the local VSIX can also be installed in the normal editor. A browser
preview is only design evidence. The local extension and commands are implemented; marketplace distribution is
not provided.

### User flow

1. Open Warden from the editor and choose the mod project. Use mod.json to identify
   the project; show its name and the analysis configuration in the panel.
2. Find compiler settings automatically in the project's build folder where
   unambiguous. Otherwise let the user choose compile_commands.json through a
   file picker. Missing settings produce a setup message with a next action.
3. Analyze with a visible running state and Cancel. Keep the editor responsive.
   An optional Analyze on save setting reruns after supported source saves;
   debounce edits and cancel/discard obsolete runs so results match the selection.
4. Show Reviews, Hooks, and Coverage. Reviews contains actual compiler
   diagnostics and unresolved analysis, not invented semantic bug warnings.
   Hooks separates registered declarations from helpers. Coverage shows files,
   SDK/target, and incomplete/unknown cases; completion never means compatibility.
5. Select an item to see its source location, what was observed, why it matters,
   and what to do next. Open the real file at the relevant line in the editor.
   Preserve raw compiler messages in expandable details rather than inventing a
   certain fix for an ambiguous compiler error.

### First version and later diagnostics

The first version renders the current report: hook/helper declarations, compiler
errors, setup failures, limited ownership reviews, and unknown coverage. Ownership
reviews show their inferred-risk label, creation/capture/use locations, suggestion,
and limits. It must clearly state that comprehensive lifetime and cross-mod
behavior checks are unavailable. The official SDK example provides an inventory
demonstration; the SDK-adapted BetterInfo benchmark demonstrates a source-level
ownership review, not an independently reproduced crash.

Future supported diagnostic records add explanation, supporting locations,
confidence/coverage, and a human-reviewed fix preview. Do not show Apply Fix or a
green compatible verdict before that data exists and the behavior is implemented.

### Implementation boundaries and simplicity

- One extension package with host integration, a small report adapter, and one
  themed view. Prefer plain JavaScript and host/native APIs; no React framework,
  local HTTP server, account system, database, telemetry, or publishing workflow.
- Call the configured native executable with an argument array, no shell. The
  extension does not automatically build/configure arbitrary mod projects.
- Use the existing JSON schema; validate received data before rendering. Keep
  stdout/stderr and exit codes 0/1/2 distinct from transport/process failures.
- Respect workspace trust before spawning native analysis. Webview content uses
  a restrictive CSP, no remote resources, escaped text, and validated messages.
- Source navigation must stay within the selected project's canonical path;
  reject traversal, symlink escape, and invalid line/column data. Other SDK file
  diagnostics remain readable but aren't silently opened as project files.
- Record settings for analyzer path and selected build configuration in the
  editor, not a second project configuration format. Native analyzer remains
  independently testable; analyzer/compiler processes have bounded lifetime.
- Save UI previews outside the repository. Retain existing source/tests/history;
  avoid unrelated cleanup or speculative feature folders. Fold this design into
  the current product document rather than creating another proposal tree.

### Acceptance evidence

- Actual SDK example runs from the editor and displays the correct init hook,
  helper, and source locations. Native file navigation is demonstrated.
- A real SDK-backed parsing failure and missing compiler settings display an
  honest message and next action. Partial analysis preserves unknown coverage.
- Cancellation, stale results, invalid JSON, process errors, untrusted workspace,
  and invalid source navigation have meaningful boundary tests.
- Check rendering/selection in light and dark themes and a narrow panel, then
  test the actual extension host in the installed editor. A browser preview is
  design evidence, not proof of a functioning Cursor/VS Code extension.

Reference: [VS Code webview API](https://code.visualstudio.com/api/extension-guides/webview).
The scoped implementation is recorded below. Native
analysis displayed in the editor is an integration milestone. Prioritize real
diagnostic capability before final UI polish, and verify the complete supported
workflow in the editor before describing Warden as ready to use.

## Current implementation order

The user authorized continued implementation of the product roadmap. Keep the
existing checkout and uncommitted work; implement locally and use one independent
review at the end. Game changes, external publication, and commits remain outside
this authorization. Record execution results in docs/progress.md.

1. Extend validated SDK coverage to 5.10.1 using its official, checksum-verified
   macOS libraries and real compiler settings. Inventory complete real mod projects
   where their actual dependency headers are available; keep missing units unknown.
2. Add geode.late-array-bounds-check: resolve real CCArray objectAtIndex/count
   calls and detect a supported upper-bound guard that appears after the access.
   Suppress cases with an established preceding guard; use source-linked review
   evidence and before/after BIViewLayer source. Unknown control/alias/mutation
   forms do not earn a confident bug claim. This is not general bounds proof.
3. Build one local editor/ extension package consuming native schema 2 results.
   Use the interface specification above: project/build selection, actual native
   execution, cancellation, opt-in analysis on save, safe source navigation, and
   ownership/bounds explanations. Expose proposed repairs only through a real,
   stale-source-checked patch preview and human approval; do not silently rewrite
   code. A first usable panel is not evidence of complete compatibility analysis.
4. Verify real SDK/defect cases, harmless and unknown controls, editor boundary
   tests, and the actual Cursor/VS Code extension host. Finish with a fresh code
   review and project tests. Keep unavailable runtime/developer evaluation visibly
   unfinished rather than manufacturing proof or contacting people automatically.

The real NodeIDs scan exposes a common SDK registration form: direct
`Modify<Derived, Base>` inheritance. Extend inventory to this form only when the
actual selected SDK registration branches select the derived method, using the
same matcher as `$modify`. Keep generic onModify/priority logic unknown. Current
NodeIDs source also uses a layout API missing in SDK 5.8.2; verify it with the
selected 5.11.1 configuration, recording its declared minimum separately. Do not
edit mod source to mask this configuration mismatch.

Further full-project setup exposed that the normal SDK PCH supplies Geode
umbrella headers. Disabling it changes the compilation context of sources that
rely on those headers; preserve the real PCH-backed build when validating those
projects. Resolve SDK provenance from actual SDK declarations as well as macro
definitions so direct inheritance and bindings-only units do not silently skip
analysis. This requires real compiler/PCH verification, not substitute headers.

## Next increment: automatic interaction discovery

Status: the user approved automatic discovery as the main experience after
identifying the burden of choosing a suspect mod. The revised written design
is approved. The native behavior facts, bounded local catalog and sidebar
discovery are implemented; installed command/report integration and saved-source
edit/Undo/reanalysis are verified.
An independent review found five state/coverage issues, fixed with regression
tests. Real sidebar rendering and both source-link actions were observed; remaining
manual/platform checks are explicitly unverified.

### Default experience: analyze one project

A developer opens their own source project and clicks **Analyze mod**. Warden
matches its supported hooks and declared dependencies against a small, versioned
catalog of real analyzer reports. The developer does not need to guess another
mod or prepare its compiler settings. Warden maintainers prepare catalog entries
from pinned source revisions and real SDK/dependency configurations.

Use a local catalog first. An ecosystem crawler, hosted service, account, and
runtime companion are deferred. Compared with requiring a second checkout, the
catalog reduces developer setup but creates a maintenance and coverage obligation.
An installed-mod list could narrow the catalog later; installed binaries alone do
not supply the source evidence required by this design.

Show **Interactions to investigate**, with a reason and evidence for each
candidate. Use transparent relevance groups rather than an invented crash score:

1. Declared dependency/incompatibility relationships, retaining their exact
   version constraints and origin as metadata rather than a new detected defect.
2. Shared compiler-resolved hooks with supported forwarding/priority facts worth
   inspecting. Explain those facts without treating absent direct forwarding as
   a bug or a requested priority as effective runtime order.
3. Shared targets without stronger facts, collapsed as informational overlaps.

These groups prioritize investigation, not probability of a crash. Do not infer
that one mod supplies a UI ID merely from a dependency or a shared hook. API
provider/consumer relationships require a separate supported extractor or clearly
attributed curated evidence; they are not promised by the current hook plan.

Each card links the developer's code and the catalog mod's pinned source, names
the exact versions/configurations, explains a concrete review or test action, and
labels unsupported behavior. Required dependencies constrain valid tests. The
existing Guided layout remains the presentation direction. Repairs stay human
approved; discovery does not generate automatic hook-order fixes.

### Catalog coverage and trust

Every entry records mod identity/version, source repository and immutable
revision, analyzed SDK/bindings/target/game configuration, analyzer version,
selected units, incomplete coverage, and report provenance. Source revision and
metadata must refer to the same prepared input. A report from a different version
must not silently represent the version the developer intends to release with.

The sidebar always exposes **checked entries**, **configuration/version gaps**,
and **unavailable analysis**. Empty results mean no supported relationship found
within that coverage, never ecosystem compatibility. Do not manufacture a
percentage of the ecosystem checked without a defined denominator.

Catalog reports are data: validate size, schema, nested evidence and identity;
reject duplicate/conflicting identities and invalid provenance. No fetched report
can execute code or direct local file access. Resolve local links only inside the
primary root; catalog links use validated repository/revision-relative paths.
Do not treat a catalog path as a second local project path. Configuration
mismatches withhold combined conclusions just as in local pair review.

Pin the catalog snapshot used by each analysis. Source/configuration changes or
switching that snapshot invalidates the corresponding discovery result. Offline
use keeps the selected snapshot and displays its provenance; it does not claim
to contain the newest mod versions. Updates must not execute third-party build
scripts on the developer's computer. Public catalog distribution, licensing and
ongoing maintenance need validation before a release commitment.

### Validation and delivery order

The two-report engine below is an internal foundation and optional advanced
workflow. It is not completion of automatic discovery. Validate its evidence
first, then connect it to a small catalog so a developer can use one project.

Start with at least three distinct real mod entries, including supported relevant
relationships and unrelated coverage controls. Record why each entry was chosen;
do not call entire mods harmless. NodeIDs/BetterInfo is a candidate relationship,
not evidence of a defect. A controlled fixture may test filtering/error handling
but cannot stand in for the real catalog demonstration.

Acceptance requires analyzing one real project in the actual sidebar, finding a
relevant catalog relationship without selecting a peer, explaining its evidence,
opening both sources, showing coverage/version gaps, and giving the user a
repeatable test procedure. Evaluate retrieval of independently recorded relevant
relationships separately from diagnostic precision. Include informational overlap,
unknown behavior, incompatible configurations, corrupt entries, changed versions,
and empty results. No effectiveness or runtime compatibility claim follows from
candidate retrieval alone.

The implementation plan now includes catalog ingestion, candidate retrieval,
remote-source navigation, snapshot freshness and one-project acceptance alongside
the pair-analysis foundation. The user directed inline implementation; verification
and limits are recorded in docs/progress.md.

## Foundation: selected-mod interaction review

The following proposed engine supports discovery and deeper manual investigation.
Its two-project setup is not the normal developer onboarding flow.

### Outcome and chosen approach

A developer selects their mod and a second source project in the existing sidebar.
For a shared, compiler-resolved hook, they can inspect each implementation, see
source evidence about forwarding and priority requests, and understand what to
verify together in the game. The view never turns overlap into a conflict verdict.

Use the existing analyzer to extract additional facts, then join the two reports
locally in the extension. This preserves the current source/build workflow and
avoids a service or ecosystem crawler. The catalog reuses these reports without
requiring developer-side peer builds. A runtime companion could observe effective
hook state but adds installation/platform work; defer it. A catalog of known issues
could provide attributed context but cannot establish a new source interaction;
issue curation is separate from the analyzer-report catalog.

The first increment is read-only interaction review. Existing supported local
repairs retain their approval flow; no generated priority or cross-mod repairs.

### Developer flow

1. Keep the primary mod selection and add **Compare with another mod**. Select
   the second mod folder and its compiler settings. Reject the same canonical
   root or duplicate mod identity so the view cannot pretend to compare two mods.
2. Analyze both saved projects with separate progress/status and cancellation.
   Reuse existing compiler-diagnostic and coverage behavior. A failed second
   analysis must not erase the first mod's usable report or imply no interactions.
3. Open **Interactions**. Show both identities/versions, analyzed SDK/target,
   configuration limitations, and the number of shared source-level targets.
   Group by canonical target class, method name, and resolved signature; exclude
   helpers and deduplicate declarations seen through shared headers.
4. Expand a target to see both hook implementations, source links, direct
   forwarding-call evidence, supported priority requests, and unresolved facts.
   An overlap without stronger evidence is an informational relationship.
5. Show a focused verification suggestion: for example, inspect behavior before
   and after the original call and compare that screen/action with A alone,
   B alone, and A+B. Label this a suggested scenario, never an executed test.
   Respect required dependencies: if a selected mod requires the other, its
   standalone scenario is unavailable; suggest a valid configuration instead.

The UI must explain the concrete observation behind each suggestion. A generic
checklist attached to every shared hook is not sufficient acceptance evidence.

### Compiler facts and their limits

- Add optional hook behavior evidence to the existing inspection JSON. Keep
  schema 2 backwards-readable: older reports show behavior as unavailable rather
  than manufacturing defaults. Validate new records before rendering/navigating.
- Resolve forwarding calls against the actual registered target's SDK declaration
  and signature, on the current receiver. A similarly named helper, another
  overload, another object, or text in comments must not count as forwarding.
- Record matching direct call locations and whether they occur in conditional or
  nested/deferred code. A direct call's presence does not prove every path calls
  it or that it ran at runtime. Helper-mediated forwarding and unmodeled control
  flow remain unknown. Missing direct evidence does not mean a broken hook.
- Resolve supported priority APIs to the actual SDK declarations in instantiated
  modification context. Record the requested hook name, API, constant value or
  relative-mod target, source location, and uncertainty. Start with direct
  constant-valued requests; unresolved/dynamic/conditional requests remain unknown.
- Distinguish pre/post priority semantics using the selected SDK, not a generic
  ascending list. Do not invent a priority when none was observed or assume that
  an SDK priority call succeeded, a hook was enabled, or the analyzed code loaded.
- A requested order can be explained conditionally under explicit assumptions.
  Effective runtime order, equal-priority ties, missing mods, priority overrides,
  and enabled/disabled state remain unverified. Do not draw an unconditional
  runtime execution chain from source facts alone.
- Initial comparisons require the same analyzed SDK and target and compatible
  declared game-version metadata for that target. Otherwise expose both reports
  and explain the mismatch, withholding combined order/risk conclusions. Matching
  source signatures alone do not prove matching runtime addresses.

Intentional replacement hooks are valid. In particular, BetterInfo's inspected
`onLevelInfo` implementation replaces behavior through a helper. It must not
become a "forgot original call" finding or receive an automatic forwarding fix.

### Integration and source freshness

Keep one native analyzer and the existing editor package. Extend the inspection
model/reporting and add a small pure comparison adapter in `editor/`; use no new
framework, server, account, database, or separate application.

Store the selected second project/build in normal editor settings. Both roots
participate in dirty/saved-source invalidation. Changing either selection,
compiler settings, or source makes the comparison stale; an obsolete async run
cannot overwrite the newer selection. Keep independent per-side errors visible.

Webview navigation identifies a validated report side and record index, never an
arbitrary path. Resolve the source against that side's canonical root, including
the existing symlink/UTF-8 position checks. Preserve workspace trust and bounded
process execution. Do not execute project build scripts or modify game installs.

### Evidence and tests

First real source pair: evaluate NodeIDs and BetterInfo around shared layer hooks,
using documented real SDK configurations. Existing cached reports establish this
as a source-analysis candidate, not confirmed compatibility or a newly discovered
defect. Prepare a common supported SDK configuration before making combined
conclusions; preserve original C++ and label SDK adaptations and unknown units.

The historical BetterEdit / Editor Tab API repair remains a separate research
case. Its SDK 5.0.1 configuration is outside current validated coverage; do not
substitute SDK 5.11.1 or stub headers and present it as a historical reproduction.

Required tests include real SDK-backed direct/conditional/deferred calls, helper
and overload lookalikes, other receivers, inactive code, shared-header duplicates,
and real priority API identity versus user-defined lookalikes. Pair tests cover
benign overlaps, missing/partial reports, configuration mismatches, source edits
in either project, stale async completion, cancellation, and navigation into both
selected roots. Unsupported facts must stay unknown.

Acceptance requires a source-linked two-mod report in the actual editor plus a
hands-on procedure the user can repeat. Identify what the report contributes
beyond the existing inventory. Synthetic chain examples are engineering controls;
they do not establish historical crash detection or useful ecosystem precision.
No gameplay test, compatibility certification, or developer-demand claim follows
from this increment. Record unavailable behavior tests explicitly.

### Delivery boundaries

Implement the foundation in order: compiler evidence, pure report comparison,
sidebar selection and navigation, then boundary/SDK/editor verification. Follow
with validated catalog ingestion and automatic candidate discovery; the foundation
alone does not satisfy the default developer workflow. Stop and revisit this
design if useful evidence cannot be extracted from the chosen real source pair.
Do not fill that gap with a shared-hook warning or staged demo findings.

Portable analyzer distribution and native Windows validation remain separate
release requirements. This increment must not imply they are complete.
