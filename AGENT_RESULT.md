# AGENT_RESULT — EnergieProject 32.5.24 replacement

STATUS: PRE-INSTALL ACCEPTANCE GREEN / LIVE FUNCTIONAL ACCEPTANCE REQUIRED AFTER INSTALL

- exact predecessor: `EnergieProject_v32.5.23.zip`
- predecessor SHA256: `a1238939297dec600a0e5b6c9519ac7c7ed9651b80c515418c7a526af60c8e09`
- predecessor size: `6820911` bytes
- earlier 32.5.24 SHA `3d2ce89c45afdd9a67879ea7ce46f81a7d2202292067e6bb92b0bf923b43e2aa`: SUPERSEDED / DO NOT INSTALL
- PM version: `2.0.0-rc58`

## Implemented scope
1. N+1 predecessor-controller activation carrier retained for the live control-plane rebind.
2. PM live-truth closure: LIVE_REQUIRED cannot close through task completion or direct roadmap completion without LIVE_PROVEN.
3. Step X/Y + elapsed/ETA output and complete terminal-fallback metadata are technically enforced.
4. Multi-release carry-forward/version stacking raises explicit attention with blocker/next-action requirements.
5. Historical Type-2 recovery receipt is persistent truth; current recovery bytes remain an independent exact-integrity gate.
6. Type-2 002–012 practical E2E includes finalize/delete-readback and restore, non-empty release mailboxes, mutating runtime source and real writer path activation.
7. ClearUp_007 specifically proves legacy control-plane quiescence and canonical writer proof.
8. Requirements discovery remains dynamic over the canonical Requirements/*.md tree instead of a stale hard-coded subset.
9. No new watcher/controller/status chain.

## Pre-install evidence
- complete 32.5 regression family: 166/166 GREEN
- broader PM/handoff/build-contract regression set used in final audit: 72/72 GREEN
- static suite: 600/600 GREEN + 2 skipped
- compileall: GREEN
- canonical artifact builder filters `.pytest_cache`, `__pycache__`, `.pyc/.pyo`, `.DS_Store` and rejects forbidden ZIP members
- no live Type-2 finalize/delete performed during build

## Live-only functional gates after install
- release 32.5.24 COMPLETE 9/9 and PM rc58 actually loaded
- canonical control-plane heartbeat fresh; legacy Inbox/control_plane quiescent
- ClearUp_007 live validation GREEN through the real PM -> privileged watcher route
- new_chat_verder_e2e and required PM live acceptance recorded LIVE_PROVEN
- current 002–012 recovery/plan/validation truth reconciled before destructive action
- any changed recovery bytes reported as current-set mismatch, never as missing historical receipt

## Final live-boundary repair
- Root cause found after real 32.5.24 incoming: recreated control-plane mounted `/release-controller` read-only while `qnap_control_plane_bootstrap.py` still wrote `platformtest_security_migration_v1.json` there during startup.
- Fix keeps `/release-controller:ro`; the security marker now uses the existing writable `/control-plane-runtime` mount via `--security-root`.
- New regression proves no `/release-controller:rw` privilege widening and proves the marker is written to the canonical runtime root.
- 32.5 family after final root/tunnel repair: 166/166 GREEN; static + 32.4.57 release-boundary regressions: 657/657 GREEN + 2 skipped.

- Final startup-boundary correction: bootstrap now consumes the private `--security-root` argument before delegating to the existing control-plane argparse parser, preventing an unrecognized-argument exit while preserving the tested read-only ReleaseController mount.

- QNAP bind-mount chmod live-boundary regression added and GREEN; 32.5.24 avoids chmod when mode already matches.

## Final live tunnel race correction
- Live rollback evidence exposed a TOCTOU source-writer race: the recovery-carrier was written before `energie-release-watcher` (the ReleaseController writer) was quiescent.
- Corrected tunnel order: watcher stop -> carrier install -> exact SHA readback -> 2-second race-window -> second SHA readback -> control-plane recreate.
- New regression simulates a release source-resync exactly at watcher-stop and proves the corrected carrier remains authoritative.
- Exact corrected tunnel SHA256: `afe5fac4cd62c6ba19283a122bdeb936fd8e382ebf4394debbb8aacfe49b2848`.
