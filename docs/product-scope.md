# Warden: useful release outcome

Status: evolving product scope. The hook inventory, two limited diagnostic
families, one reviewed bounds-guard repair, and a local installable editor
extension are implemented. The VSIX contains the editor, with a separately built
native analyzer/LLVM requirement. Broader diagnostics, cross-mod interaction
explanations, runtime/developer evaluation, and portable distribution remain unfinished.

## User outcome

A Geode developer changes a mod and can understand supported crash risks,
relevant interactions with selected other mods, and the concrete checks needed
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
