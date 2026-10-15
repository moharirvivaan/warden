# Warden controlled runtime test: review before execution

Status: packages can be prepared locally; no runtime test has been performed.
This procedure is for the controlled probe, not a compatibility certification.

## Concrete artifacts

- Package directory: `build/proof/packages/` within this repository.
- Candidates: `warden.proof-remover.geode`, `warden.proof-consumer.geode`.
- Repair candidate: `warden.proof-consumer-guarded.geode`.
- Input and artifact identities: `build/proof/packages/manifest.json`.
- Existing installation, read-only during preparation:
  `/Users/vivaanmoharir/Library/Application Support/Steam/steamapps/common/Geometry Dash/Geometry Dash.app`.
- Existing NodeIDs package, inspected read-only: `Contents/geode/mods/geode.node-ids.geode`,
  whose metadata currently says v1.23.3.
- Recent October 11 log: Geode 5.11.1, Geometry Dash 2.2081, MacArm.
  Recheck versions at the actual run; bundle Info.plist alone is less precise.

## User approval checkpoint

Approve the test environment and protection/recovery procedure before copying
test mods or launching the controlled combination. The unguarded combination is
expected to fail, but neither a crash nor the proposed repair has been reproduced.
Do not alter the existing installation's mod files during this experiment.

Preferred isolation is a separate macOS test user running the privately copied
game bundle. This needs a human to create/log into that user and confirm any Steam
access requirements. The assistant will guide this preparation. Neither the test
user nor the private bundle has been created. If this is unavailable, stop and
review a specific backup/recovery alternative before launching under the normal
user; do not silently substitute it.

For a separate test user, agree on a writable test bundle location in that user's
home before preparation. A local workspace copy under `build/proof/runtime/`
can be used only when the test user has verified access. These are proposed
locations, not established isolation. Keep the game private; never commit/upload it.

## Why a copied bundle alone is insufficient

Pinned SDK code resolves mod configuration under the executable's bundle
`Contents/geode`, but persistent data uses the user's
`~/Library/Application Support/GeometryDash` and its `geode` and `geode-persistent`
subdirectories. The game also maintains its own saved data. A changed working
directory, copied `.app`, or different test mod directory does not establish
saved-data isolation. Do not repurpose HOME as a workaround.

## Approved preparation sequence

1. Close Geometry Dash. Record the source bundle and package-manifest hashes.
   Confirm the separate test user's game/save paths cannot resolve to the normal
   user's data through symlinks or shared folders.
2. Copy the existing game bundle privately to the agreed test location. Preserve
   the original. In the copied bundle only, replace the copied Geode state with a
   minimal test state: current loader resources and the exact NodeIDs package,
   with no other third-party mods, old config, logs, update queue, or unzipped
   mod binaries. Verify bootstrapper/framework paths and package signatures.
3. Confirm the test user is active and Steam/game access works without copying
   the normal user's account data. A failure to launch is a setup issue. Verify
   the fresh log's game directory, loader version, architecture, loaded mod set,
   and saved-data directory before treating the environment as isolated.
4. Preserve a baseline snapshot of the test user's data and test mod set for
   repeatable runs. Record its location; keep account/save data out of evidence
   committed to the repository.

## Scenario matrix

Quit the test game before every package switch. Copy only the selected packages
whose hashes match the manifest. Start the agreed private executable, record
stderr and Geode logs under a new run identity, and reach the main menu without
opening/saving levels or synchronizing accounts. The action under test is
`MenuLayer::init`.

| Run | Loaded test packages | Observe |
|---|---|---|
| Baseline | None; NodeIDs only | Main menu loads and navigation works |
| A | Remover | Main menu loads; bottom menu absent |
| B | Unguarded consumer | Main menu loads; WARDEN PROOF label visible |
| A+B | Remover + unguarded consumer | Record actual order, missing-node access, and resulting behavior |
| A+B repeat | Same hashes as prior run | Determine whether the same failure repeats |
| B repaired alone | Guarded consumer | Label still appears when its node is present |
| A+B repaired | Remover + guarded consumer | Log shows optional label skipped; main menu and navigation work |

Use only one consumer variant per run. A failed priority-configuration message,
missing NodeIDs, unsuccessful base initialization, or rejected package invalidates
that run as interaction evidence. Flushed stderr markers distinguish remover
before removal from consumer before access even if buffered logs are lost.
Inspect the crash trace if the combination fails: an unrelated crash is not proof.

If the combination works, report that result and investigate order/context; do
not add an explicit crash instruction to force the expected outcome. If either
mod fails alone, investigate or revise the candidate before proceeding.

## Human interpretation and recovery

The guarded repair intentionally omits an optional label if the bottom menu is
absent. A person must accept that fallback and verify it does not prevent normal
initialization. Restoring the removed bottom menu itself is not the repair's goal.

After testing, close the private game, remove the test packages from its copied
state, and archive only sanitized run evidence. The normal user's original
installation and saved data should be unchanged; verify this against the initial
snapshot/checks. Keep the private bundle/test-user state until results are reviewed
and a person authorizes cleanup. Do not delete game/user data automatically.

Record each observation using `examples/compatibility-proof/run-record.schema.json`.
Required context includes package hashes, game/loader/NodeIDs versions, actual
operation order, artifact locations, outcome, and human review. Leave unobserved
results unknown. The demonstration is controlled and cannot establish ecosystem
precision, adoption, or time savings.
