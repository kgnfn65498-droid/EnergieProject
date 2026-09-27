
## 2026-09-27 tunnel racefix
Live retry van de vorige tunnel bewees een source-writer TOCTOU: carrier-write vóór watcher-stop kon door de actieve ReleaseController-source-sync worden teruggezet naar de oude 32.5.23 qnap bootstrap. Correctie: watcher eerst stoppen, daarna carrier schrijven, SHA controleren, 2 seconden race-window, opnieuw SHA controleren en pas daarna control-plane recreëren. Regressietest simuleert exact de oude resync en is GREEN.
# 32.5.24 integrated final checkpoint

Scope bevat nu ook DS9/Spock FULL_KB/runtime enforcement, dynamische Requirements-discovery, runtime logs/current-truth, release-ZIP retentie 3, command-proof en de bounded Incoming tunnel voor de huidige predecessor-runtimeblokkade. Geen afsplitsing naar 32.5.25 voor deze scope.

# Development checkpoint — 32.5.24 replacement

- Basis: exact physical 32.5.23, SHA256 `a1238939297dec600a0e5b6c9519ac7c7ed9651b80c515418c7a526af60c8e09`, 6,820,911 bytes.
- Earlier 32.5.24 SHA `3d2ce89c45afdd9a67879ea7ce46f81a7d2202292067e6bb92b0bf923b43e2aa` is SUPERSEDED.
- PM version: rc58.
- Required N+1 control-plane activation carrier retained.
- Recovery receipt truth and current recovery-set integrity are now separate fail-closed states.
- Full Type-2 002–012 fixture E2E includes prepare/export/migrate/path activation/validate/recovery gate/finalize/delete readback/restore and preserves non-empty release mailboxes.
- ClearUp_007 fixture proves actual system_path_contract writer handoff to canonical ControlPlane/Runtime and quiescent legacy source.
- LIVE_REQUIRED task completion cannot bypass LIVE_PROVEN.
- Development output contract enforces Step X/Y + elapsed/ETA; exceptional terminal fallback enforces exact terminal/wait/success/stop/return fields.
- PM reports VERSION_STACKING_ATTENTION for unresolved carry-forward across multiple releases.
- Source tests: 165/165 32.5 GREEN; 72/72 broader PM/handoff/build-contract GREEN; static 600/600 +2 skipped; compileall/shell GREEN.
- No production Type-2 finalize/delete performed.

## Live-boundary defect found from real Incoming
- `control_plane_prepare_failed:RuntimeError` on running 32.5.23 was traced to a mount/write contract mismatch, not to Type-2 business logic.
- Fix: explicit `--security-root /control-plane-runtime`; `ReleaseController` stays read-only.
- Regression: `test_v32524_control_plane_readonly_release_controller.py` proves exact mount and marker behavior.

- Startup parser boundary: `--security-root` is consumed by `qnap_control_plane_bootstrap.py` before `control_plane.main()`; regression added so the private bootstrap-only argument cannot leak into the existing parser.

## QNAP canonical control-plane closure — 2026-09-26
Live recreate bewees dat broncode/fingerprint alleen niet volstaat: de nieuwe canonical runtime bind vereist dezelfde begrensde filesystem-capabilities die al elders in het project voor QNAP-hostmutaties zijn bewezen. 32.5.24 houdt `CapDrop: ALL` + `no-new-privileges`, voegt exact `DAC_OVERRIDE`, `DAC_READ_SEARCH`, `FOWNER` toe en verifieert die in de binding-readback. Compose en recreate-payload zijn gelijkgetrokken. Type-2 002–012 en recovery-truth bleven GREEN.
