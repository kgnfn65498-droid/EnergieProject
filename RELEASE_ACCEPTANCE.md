# Release Acceptance — 32.5.24 integrated final

Pre-installatie vereist: changed-surface tests GREEN; volledige toepasselijke 32.5-regressie; exact ZIP CRC/manifest/SHA256SUMS/compile/shell; FULL_KB/Requirements dynamic-discovery tests; retentie-3 tests; tunnel check-only/state-machine/rollback tests.

Live-required: één expliciet goedgekeurde bounded tunnel-run indien de 32.5.23 control-plane/ReleaseController blokkade nog aanwezig is; daarna control-plane GREEN, watcher GREEN, ReleaseController IDLE, Incoming/Processing leeg. Vervolgens exact één officiële 32.5.24-ZIP via Incoming -> Processing -> live -> Processed. PM/runtime moet daarna 32.5.24, FULL_KB COMPLETE, dynamische Requirements-discovery en Master Index/current-truth readback tonen.

Geen GREEN op documentatie alleen, enqueue alleen, of pre-installatie zonder live readback.
De bestaande split-state-gate blijft onverkort onderdeel van release acceptance; NAS/HA/PM/runtime mogen niet uiteenlopen.

# Release Acceptance — 32.5.24 replacement

Status: PRE-INSTALL GREEN — LIVE FUNCTIONAL ACCEPTANCE REMAINS REQUIRED AFTER INSTALL

## Binding requirements implemented
- N+1 predecessor-controller activation for the 32.5.23 control-plane repair.
- Project Manager live truth: functional LIVE_REQUIRED cannot close before LIVE_PROVEN; technical release acceptance remains separate.
- New-chat/handoff/status/task/intake/acceptance are runtime-first and cannot retain proven-stale blockers.
- Type-2 historical recovery receipt and current recovery bytes are separate truths; stale “not received” blockers are reconciled without weakening current-set integrity.
- Development updates require Step X/Y + elapsed/ETA; exceptional terminal fallback requires terminal, step, duration, max wait, success/stop markers and return requirement.
- PM detects multi-release carry-forward/version stacking and requires a concrete blocker/next action.
- Requirements discovery dynamically inventories the canonical Requirements/*.md register instead of relying on a hard-coded subset.
- No parallel watcher/controller/status chain.

## Type-2 pre-install E2E gate
Exact ClearUp_002..012 fixture route executes:
`prepare -> export verify -> migrate -> path activation -> validate -> external-recovery truth/gate -> finalize -> delete-readback -> restore`.

Additionally:
- incoming/processing/processed/failed are non-empty and byte/hash unchanged;
- an active runtime source mutates before cutover;
- post-activation writer uses the canonical path only;
- ClearUp_007 proves legacy control-plane quiescence + canonical writer proof;
- each item remains fail-closed on plan/recovery/validation mismatch;
- restore is practically executed.

## Pre-install audit evidence
- 32.5 family: 166/166 GREEN.
- broader PM/handoff/build-contract regression set: 72/72 GREEN.
- static: 600/600 GREEN + 2 skipped.
- compileall: GREEN.
- MANIFEST.sha256 and SHA256SUMS.json generated from exact payload.
- canonical builder excludes runtime/test caches and pyc/pyo files and applies the atomic ZIP safety gate.

## Live-only functional acceptance after install
Technical install may become ACCEPTED while these remain LIVE_REQUIRED. Functional Type-2/PM closure requires LIVE_PROVEN for the actual runtime, including fresh canonical control-plane heartbeat, quiescent legacy writer, ClearUp_007 GREEN and required new-chat/handoff smoke evidence. No destructive live ClearUp is authorized by pre-install acceptance alone.

## Control-plane read-only release-controller acceptance
- Recreated control-plane MUST keep `Data/03_Systeem/Projectmanager/ReleaseController:/release-controller:ro`.
- Bootstrap security-marker writes MUST target the existing writable `/control-plane-runtime` mount, never `/release-controller`.
- Acceptance regression: `tests/test_v32524_control_plane_readonly_release_controller.py`.

- Bootstrap-only `--security-root` MUST be removed from `sys.argv` before delegation to `control_plane.main()`; exact regression is part of `test_v32524_control_plane_readonly_release_controller.py`.


## QNAP root/tunnel acceptance addendum
- Candidate is RED if QNAP bootstrap only accepts one assumed host root.
- Candidate is RED if tunnel desired fingerprint equals the stale failed-attempt fingerprint.
- Required tests: proven host-root aliases accepted, unknown root rejected; tunnel `sh -n`; `--check-only` read-only; successful recreate reaches corrected runtime fingerprint; create-failure restores previous source/container/attempt and watcher.
- Required ordering regression: watcher/ReleaseController must be quiescent before carrier install; a simulated source-resync on watcher-stop must not be able to replace the carrier after quiescence. Double SHA readback with bounded race-window is mandatory.
- Any command text shown to Peter must resolve/verify the live project root before invoking the exact tunnel SHA.
