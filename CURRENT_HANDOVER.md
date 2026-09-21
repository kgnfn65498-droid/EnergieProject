# CURRENT HANDOVER — EnergieProject 32.4.59

Datum: 2026-09-20
Status: DEVELOPMENT / PRE-LIVE — source implementation GREEN; production remains 32.4.58 until explicit live authorization.

## Canonical predecessor
Only `EnergieProject_v32.4.58_repo_hotfix_final.zip` SHA256 `c9d67b5aec5e800a5dbca2ea0a1b8a5199ea0db6e1a656d488cc0e26789755e4` is the 59 content baseline. Original 3c097 remains historical live-release evidence only.

## Live truth before 59
- NAS App 32.4.58; HA runtime 32.4.58; atomic 57->58 ACCEPTED.
- ReleaseController COMPLETE then PID1 IDLE/pulsing.
- Old 58 publication contract remains the mandatory predecessor-settlement gate before 59 Incoming.
- Corrected GitHub HEAD: `ad9878e6ec124f23dfcd16adbf005c46dac9538a`.

## 32.4.59 structural fix
- No version-only HA delivery GREEN.
- Publisher result is fenced by release_id, generation, version, artifact SHA and target manifest SHA.
- Publisher does not remove the contract; ReleaseController settles only exact owned delivery after GitHub exact + HA target.
- Foreign/unproven contracts fail closed.
- Artifact remains Processing until proven delivery; Processed means complete.
- COMPLETE predecessor settlement gates next Incoming.
- Synthetic 59->60 successor contract works without manual cleanup.
- Corrected repository layout keeps exactly one Home Assistant `config.yaml`.

## Next gates
1. Full source regressions in timeout-safe batches.
2. Canonical artifact build + CRC/manifest/path/layout audit.
3. Exact fresh-extract regression.
4. Pre-live readback and exact 58 predecessor settlement.
5. Only after explicit production authorization: final 59 ZIP to Incoming and live E2E.

No production action, restart, manual JSON edit or terminal by Peter occurred during development.


## Agent bridge v1
- Development-branch: `agent-bridge-v1`; geen productie- of releasecode gewijzigd.
- Nieuwe contractfiles: `AGENTS.md`, `AGENT_TASK.md`, `AGENT_RESULT.md`.
- Doel: persistente Chat/Spock → Work → Codex overdracht zonder Peter als transportlaag.
- Read-back/self-audit GREEN; PR #8 mergeable GREEN. Eerste echte Codex-taak blijft de verplichte live acceptance dat `AGENTS.md` daadwerkelijk wordt toegepast.

## 32.4.60 resume authority after agent bridge GREEN
- Chat/Work/Codex bridge smoke is COMPLETE_GREEN; evidence remains in open PR #9.
- For replacement 32.4.60, the exact technical resume authority is on NAS:
  - `Data/03_Systeem/Projectmanager/CURRENT_HANDOVER_32_4_60_WORK_CODEX.md`
  - `Data/03_Systeem/Projectmanager/WORK_LEDGER_32_4_60.md`
  - complete rejected-60 evidence
- Baseline at that saved checkpoint: App 59 / HA 59 / GitHub 59 / Processing empty.
- Do not restart proven investigation and do not build a ZIP before loading that exact checkpoint.

## 2026-09-20 — Incoming-first decision before replacement 32.4.60
- Peter explicitly chose the predecessor/publisher-fix route after Work returned BLOCKED_SCOPE_EXPANSION.
- Priority 1 is a functioning Incoming chain.
- Active unchanged 32.4.59 publisher cannot publish a next-release candidate from Processing before installation; this must be corrected in the active predecessor before replacement 60 proceeds.
- Commit 398b2aa is rejected/do-not-use because its test exercised future modified code as if already active in 59.
- Last reported Work checkpoint: a59780d.
- Develop the smallest 32.4.59 publisher correction under the existing single ReleaseController/identity-fencing architecture. No second publisher, bootstrap actuator or rescue path.
- No live install until explicit production authorization. Replacement 32.4.60 stays paused until the corrected 59 publisher is live and Incoming E2E is proven GREEN.

## 2026-09-21 — platformtest_run authorization
- Peter explicitly approved a narrow test-only `platformtest_run` intent in the existing standard QNAP handoff/control path.
- Purpose: execute the already-approved platform-isolated full suite for candidate `33bea32534c5114aefe822afe252a6555bc55e58` without manual NAS upload, permission changes, live-network access or alternate execution routes.
- Hard boundaries: approved test image/runtime only; no network; exact candidate/test identity; ephemeral isolated workspace; immutable evidence output; no production/runtime/HA/Incoming/Processed write; no restart/recreate/reboot; no generic shell/docker passthrough; no host python; no privilege broadening.
- Latest safe blocker checkpoint before implementation: `96aae268403aadf737b68a76228f5d0e3e6760b4`.
- Once the narrow capability is TDD/regression GREEN, resume the existing full-suite checkpoint directly and do not repeat already-proven offline-guard work.

## 2026-09-21 — platformtest intent must be activated, not merely coded
- Candidate inspection confirmed current live-source contract: control_plane.py allowlists only watcher_recreate/native_mcp_reload and process_once has no platformtest consumer.
- The existing energie-control-plane loads the synced mounted Python source at process start.
- Therefore Work must not retry the QNAP platform full-suite until the capability has been implemented, synced to the canonical ControlPlane source, and loaded by the existing control-plane with exact fingerprint read-back.
- Build/test of the capability is authorized. Live source-sync/restart is still protected and requires a separate explicit Peter approval.
- Canonical activation route, after approval: existing control_plane_source_sync + tools/control_plane_bootstrap.ensure_control_plane_current(), at most one restart of the existing energie-control-plane, then health/fingerprint + platformtest preflight.
- Only after PLATFORMTEST_INTENT_LIVE_GREEN resume Work checkpoint ca7c0b427359bb4563a0f8dffbdcce0c5f17d32e and candidate 33bea32534c5114aefe822afe252a6555bc55e58.

## 2026-09-21 — PR10 merged / activation approval boundary
- Narrow platformtest_run executor merged via PR #10 at ff480024ea74b237f4088b578db98e22ad9ac63d.
- Source phase is complete; live runtime has not been changed.
- Do not retry Work/QNAP execution until protected activation is approved and live fingerprint readback proves the new control-plane code is loaded.
- After approval: canonical source sync -> at most one bounded restart of existing energie-control-plane if fingerprint mismatch -> health/fingerprint/preflight -> PLATFORMTEST_INTENT_LIVE_GREEN -> Work resumes candidate 33bea325 from ca7c0b4.

## 2026-09-21 — activation approved
- Peter granted the previously requested exact platformtest activation.
- Work/local executor may now perform canonical control-plane source-sync + ensure_control_plane_current(), including at most one bounded restart of existing energie-control-plane if fingerprint mismatches.
- Verify health + exact loaded fingerprint + platformtest preflight.
- Then immediately resume Work task 891b10287eb34f55971f7d01016b38bf from ca7c0b4 for candidate 33bea325 NETWORK=NONE full-suite.
- No additional user transport or repeated approval request.
