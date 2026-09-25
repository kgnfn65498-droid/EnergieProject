# CURRENT HANDOVER — EnergieProject 32.5.13

## 32.5.13 Type2 external recovery gate

- Buildbasis is exact physical `EnergieProject_v32.5.12.zip` with SHA256 `ef1db0794bd4e25de3e62699961b8e73fc9ce61181d4fbc14c950c98a717a5e1`.
- The earlier 32.5.13 candidate SHA256 `2a4ae0da504f96e7a56b2ddad52deedf7b8a8f391b8ea6c56b7f71a54dc02132` is rejected/superseded and must not be installed.
- Reuse only existing filesystem paths. Type2 recovery ZIPs stay under `Data/03_Systeem/Projectmanager/ClearUp/Exports`; gate remains `Data/03_Systeem/Projectmanager/ClearUp/State/TYPE2_EXTERNAL_RECOVERY_GATE.json`.
- Reuse the already visible `projectmanager_status` MCP tool. No new MCP tool catalog entry is needed. When the exact external-recovery gate is active, status supplies short-lived SHA-bound download links for 002–012.
- The download handler has no delete/migrate/finalize capability and serves only exact allowlisted Type2 recovery ZIP identities after verification.
- ClearUp_002 remains already migrated/validated state as present live; do not reprepare/remigrate solely because of this release.
- No Type2 finalize/delete until the real ZIPs have been downloaded outside the NAS, SHA-verified and Peter explicitly confirms possession.

## Release delivery rule
- Deliver the exact audited release ZIP in chat.
- Peter manually places that exact ZIP in `Inbox/incoming`.
- After Peter reports 32.5.13 running, call the existing `projectmanager_status` route, download and SHA-verify 002–012, then provide the real recovery ZIPs in chat before any destructive continuation.

## 32.5.10 Type2 recovery continuation
- Live predecessor before this release: 32.5.9.
- ClearUp_001 Type1 is physically complete/GREEN.
- ClearUp_002 is already `MIGRATED_PENDING_VALIDATION`; source is preserved, destination is active, PM runtime rebind to `Data/03_Systeem/Projectmanager/RuntimeV2` was proven. **Do not prepare or migrate ClearUp_002 again.**
- ClearUp_002 validation was blocked in 32.5.9 because embedded PM could not create the Validation atomic temp file. 32.5.10 commits validation proof through the privileged watcher.
- ClearUp_003..012 recovery ZIP/state were already prepared GREEN; no destructive finalize has started for them.
- Continue strictly 002→012: validate/resume 002 → finalize 002 only after GREEN → for each remaining batch migrate → validate → finalize.
- Never finalize a batch without matching GREEN validation evidence, stable old-source proof, active destination proof and unchanged release mailboxes.
- Release delivery remains: exact audited ZIP is provided in chat; Peter manually places that exact ZIP in `Inbox/incoming`. Library/checkpoints are not the normal release transport.
- When Peter reports the new release is running, automatically perform the full post-live audit before continuing Type2.


32.5.9 is a clean rebuild from the exact physical 32.5.8 release artifact. The withdrawn 32.5.9 artifact with SHA256 71dc599a9c1a8961238ecf87b41df8b84aa89d45c2d8b50efb236d6b4dedb95a was used only as an audit reference and is superseded.

Current release objectives:
- prevent historical Native-MCP/control-plane state from blocking a current incoming release;
- migrate/validate the Native-MCP registry annotation contract before activating `tools_clearup_export.py`, so an old registry can never cause the MCP container to enter a restart-loop;
- permit only exact release-scoped COMPLETE-phase Native-MCP reconciliation when release_id, generation, artifact SHA, release version and expected runtime fingerprint all match;
- keep manual/native restart paths protected and require explicit Peter approval;
- keep retired legacy state as evidence only from 32.5.9 onward;
- provide executable ClearUp Type1 and Type2 002..012 routes via CommandIngress -> Projectmanager -> sideband -> privileged executor;
- preserve all four release mailboxes during ClearUp Type2 operations.

Release validation is artifact-specific. No live production state is claimed by this static handover.
## Bindende release-overdracht naar iedere volgende chat

Deze regels moeten door iedere nieuwe chat als vaste projectwerkwijze worden overgenomen:
- ChatGPT bouwt en audit exact één fysieke release-ZIP en biedt die **in de chat als downloadlink** aan.
- ChatGPT plaatst een release-ZIP **nooit zelf** in NAS `Inbox/incoming`. Peter downloadt exact de aangeboden ZIP en plaatst hem zelf in `Inbox/incoming`.
- De ChatGPT Library is geen normale release-afleverroute en vervangt de downloadlink in de chat niet.
- Vóór aanbieden moet exact de downloadbare ZIP fresh-extract zijn getest, inclusief ZIP-integriteit, manifests, actuele release-regressies, Incoming `voorganger -> incoming -> processing`, en waar van toepassing ClearUp Type1 + Type2 002..012.
- Na Peters melding dat de release draait, voert ChatGPT automatisch de post-live audit uit.
- Deze regels moeten expliciet in elke volgende handover blijven staan; een nieuwe chat mag ze niet opnieuw laten afhangen van Peters herinnering.

