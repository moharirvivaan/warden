# Warden project agreement

The user wants a useful, tested Geode developer tool and a credible public demo.
Build incrementally and explain the decisions, verified results, limitations,
and the next user action. Guide the user through runtime and product evaluation.

## Human participation

- Proceed autonomously with authorized local implementation, builds, tests,
  and reversible documentation changes. Do not ask for every routine step.
- Analysis may run automatically. Findings must show evidence, coverage, and
  uncertainty; a person makes the compatibility and intended-behavior decision.
- Default repairs to a reviewable patch with a human approval action, an undo
  path, and rerun checks. Do not silently rewrite a developer's mod. Any future
  automatic application requires explicit opt-in to a defined repair policy.
- Before changing the user's game/mod installation or running a controlled
  failure, prepare the concrete packages, exact affected paths, saved-data
  precautions, and recovery procedure for the user's approval. An approval
  covers the agreed procedure; do not repeatedly request the same permission.
- Publishing, uploading, or sending messages requires the user's authorization.
- Preserve local work and respect declined actions. Commit, push, or integrate
  changes only when authorized by the user; do not infer publication approval
  from permission to build or test.

## Evidence and delivery

- A hook inventory does not certify compatibility. Shared hooks alone are not
  conflicts. Unsupported analysis remains unknown.
- Separate controlled reproductions, source-confirmed historical repairs,
  inferred risks, and runtime-observed results. Do not invent effectiveness,
  adoption, or time-saving metrics.
- The user rejected the synthetic node-removal experiment as the main product
  milestone on October 14, 2026. Its fixtures are retained as engineering tests;
  do not resume its runtime/account setup as the main path. Select capabilities
  from real mods and historical repairs across gameplay, editor, and API workflows.
- Consult docs/research/real-mod-product-review.md for the updated evidence and
  proposed direction. Limited deferred Cocos ownership and late-bounds reviews are implemented.
  Source comparisons and full-project scans use selected real SDK/dependency
  configurations; they do not reproduce historical dependency/runtime environments. Cross-mod interaction analysis remains
  a product objective and cannot be replaced by generic C++ warnings alone.
- The user requires value beyond one bug. Treat a single detected defect as an
  early engineering milestone, never product completion or adequate release proof.
  Build a coherent workflow with multiple supported diagnostic families, meaningful
  cross-mod interaction information, and guided tests/reviewable repairs. Validate
  on multiple real projects and independently sourced defects with harmless and
  unknown controls. See docs/product-scope.md for the proposed release outcome.
- The user selected a panel inside VS Code/Cursor as the first interface. Keep
  the repo clean, use plain explanations and source navigation, and make actual
  analyzer results visible. Avoid adding a separate web/desktop app or backend.
  UI previews must label the current coverage and must not stage fake findings.
- The user wants Geometry Dash-inspired colors and geometric styling with a
  small original cube/icon mascot inside the editor panel. Keep text readable
  in light/dark themes and respect reduced motion. Establish working diagnostic
  behavior and editor integration before final visual polish; a stylish hook
  inventory is not the finished product.
- Use the pinned real SDK and meaningful tests. Do not substitute mock headers
  for the SDK-backed milestone or staged UI findings for working diagnostics.
- Show behavior after a repair, including intentional fallback behavior; a
  successful build or disappearance of a warning is insufficient runtime proof.
- Deliver one working capability at a time. Consult docs/product-scope.md for
  the current product/editor direction. The synthetic proof plan is deferred.
