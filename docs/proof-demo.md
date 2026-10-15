# Warden: first compatibility proof

Status: superseded as the primary milestone by the user's October 14, 2026
product correction. Retain the controlled fixtures as engineering tests. See
docs/research/real-mod-product-review.md; no runtime/account setup is required
for this synthetic demonstration now.

Earlier status: direction approved by the user on October 14, 2026, with a requirement
for continued human participation. No compatibility diagnostic or runtime
reproduction has been implemented yet. Execute in separate milestones, beginning
with the controlled runtime probe; editor integration follows a working diagnostic.

## Purpose

Produce a demonstration a Geode developer can reproduce and inspect: Warden
identifies a specific interaction between two mods, explains the source evidence,
and helps eliminate an observed failure. The eventual presentation is a short
video accompanied by source, pinned versions, and reproduction instructions.

## What is verified today

- The native analyzer parses the official Geode example against SDK 5.11.1.
  A fresh run identifies MenuLayer::init as a hook and onMyButton as a helper,
  exits 0, and reports no unknown cases in that example.
- The prior engine verification passed 23 SDK-backed extraction tests. These
  tests establish extraction behavior, not compatibility detection.
- The local game and Geode libraries contain ARM64 binaries. The October 11
  game log records Geode 5.11.1 and Geometry Dash 2.2081 on MacArm. This is
  evidence of a suitable existing installation, not a successful demo run.

## Recommended first demonstration

Use two small, openly published test mods to exercise one narrow UI contract.
Each should work by itself. Together, one changes a node that the other expects;
an unchecked access then fails under a recorded hook order and scenario.

Node removal/access is a candidate mechanism, not a proven historical defect
pattern. Establish the runtime failure before committing to this diagnostic.
If the combination does not reproduce reliably, revise or reject the probe.
Do not make a crash happen through an explicit crash instruction.

The analysis must resolve actual hook registrations and node operations from
source. It must not recognize the demonstration through mod names, filenames,
or a hardcoded list of conflict pairs. Shared hook targets alone are insufficient.

For an interaction finding, show both source locations, the node identity,
the relevant operation and use, and the ordering assumptions. A static risk
remains inferred; a recorded run establishes reproduction only for the tested
versions, configuration, and scenario. Dynamic IDs, unresolved aliases,
unavailable source, or uncertain ordering must remain visibly unknown.

## Required evidence matrix

| Scenario | Runtime evidence | Analyzer requirement |
|---|---|---|
| Mod A alone | Target scenario works | No cross-mod finding |
| Mod B alone | Target scenario works | No cross-mod finding; a local unchecked-access warning may be appropriate |
| A and B together | Target scenario fails reproducibly | Identify the candidate interaction and both source locations |
| A and repaired B | Target scenario works | Clear the resolved finding after reanalysis |
| Same hooks, unrelated node operations | Target scenario works | Do not label hook overlap a conflict |
| Similar operations with a verified guard | Target scenario works | Do not repeat the unguarded-access finding |
| Missing source or unsupported construct | No safety conclusion | Explicit unknown coverage |

Keep separate examples for evaluation that were not used to develop the rule.
Report the actual counts of correct findings, false positives, missed supported
cases, and unresolved cases. A small controlled matrix does not establish
ecosystem-wide precision or coverage.

## Repair and developer experience

First prove the finding and a manually reviewed repair. A null guard can prevent
an access failure while still disabling a feature; define the intended fallback
and check both optional UI behavior and initialization before calling it fixed.

Then expose the working diagnostic through an editor workflow: automatic
reanalysis on save, a source-linked explanation, and visible analysis coverage.
Default to a previewed patch that a developer approves before application.
Any future automatic application requires explicit opt-in to a supported repair
policy with an explicit fallback contract, an undoable change, and appropriate
rerun checks. A passing build alone does not prove runtime compatibility.
Ambiguous repairs stay as suggestions.

## Presentation

Record the real sequence: individual mods work, combined scenario fails,
Warden explains the risk, the repair is inspected, and the combined scenario
works. Include a harmless overlap example so viewers can see this goes beyond
listing hooks. Editor footage must use live analyzer results rather than staged
diagnostics.

An honest first claim would be: “A prototype that explains one supported
cross-mod UI interaction in a reproducible Geode demonstration.” Clearly label
the test mods as a controlled reproduction. Do not claim an organically
discovered bug, universal conflict detection, proven demand, or measured time
savings.

## After the controlled proof

Use the historical-defect research set and community debugging stories to test
whether this rule transfers to real incidents. Select another diagnostic if the
node rule does not recur or adds little value over a local check. Keep SDK and
platform feasibility explicit for older incidents.

Runtime testing must use an isolated configuration and test accounts/data where
available. Prepare reviewable test packages and a restoration procedure before
changing the user's current mod installation. No publication is part of this
milestone.

## Human checkpoints

The builder implements and verifies authorized local changes without asking for
each routine action. The user reviews the concrete runtime-test procedure before
it affects their installation, assesses the diagnostic's usefulness, and approves
the intended repair behavior. Public claims and publication require a separate
user review. Project guidance is recorded in AGENTS.md.
