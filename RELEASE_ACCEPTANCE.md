# Release Acceptance — 32.5.23

Status: READY FOR INCOMING — LIVE TYPE-2 GATE REQUIRED

## Scope
1. Fix only the 32.5.22 live gap where `ensure_control_plane_current()` exists but is skipped when Native MCP is already current.
2. For 32.5.23+, prove/prepare the control-plane binding once per exact release fence before the ready Native-MCP shortcut.
3. Reuse the 32.5.22 bounded binding recreate + rollback path; no new actuator or lifecycle owner.
4. Fail closed when binding preparation fails or cannot prove `binding_current=true`.
5. Preserve all Type-2 recovery, validation, external-copy and finalize/delete gates.

## Live evidence before build
- 32.5.22 is COMPLETE 9/9; NAS/HA 32.5.22; PM rc55.
- ClearUp_005 and ClearUp_006 validate GREEN.
- ClearUp_007 remains RED because the live control-plane still updates legacy `Inbox/control_plane` while canonical `Data/03_Systeem/Projectmanager/ControlPlane/Runtime` is stale.
- 32.5.22 bootstrap correctly detects/recreates the binding when called.
- Proven call-path defect: `NativeRuntimeCoordinator.align()` returns `native_mcp_current` before `control_plane_prepare()` when Native MCP guard is already ready.

## TDD / regression acceptance
- Exact 32.5.22 baseline: new v32523 regression = 3 RED / 1 GREEN.
- After code repair: v32523 targeted = 4/4 GREEN.
- Impact regression chunk = 43/43 GREEN.
- Complete 32.5 regression set = 138/138 GREEN, with one known duplicate-name warning.
- Static suite = 600/600 GREEN + 2 skipped.
- Source compileall = GREEN.

## Final pre-install acceptance
- Canonical builder regenerates MANIFEST.sha256 and SHA256SUMS.json from exact payload bytes.
- Exact physical ZIP artifact-integrity/readback: GREEN.
- Exact fresh-extract complete 32.5 set: 138/138 GREEN, one known duplicate-name warning.
- Exact fresh-extract static: 600/600 GREEN + 2 skipped.
- Exact fresh-extract compileall: GREEN.
- Exact isolated atomic 32.5.22→32.5.23: LIVE_ACCEPTANCE → ACCEPTED.

## Live-only gate after install
1. 32.5.23 COMPLETE 9/9; PM rc56; NAS/HA aligned.
2. Canonical ControlPlane runtime heartbeat fresh; legacy `Inbox/control_plane` quiescent.
3. ClearUp_007 revalidation GREEN through the real PM→privileged watcher route.
4. Readback all ClearUp_002–012 GREEN.
5. Current post-migrate recovery bundle delivered directly in ChatGPT and receipt explicitly confirmed by Peter.
6. Only then may finalize/delete 002–012 proceed sequentially with readback.
