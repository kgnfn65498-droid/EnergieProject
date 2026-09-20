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
