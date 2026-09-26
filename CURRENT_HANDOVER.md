# CURRENT HANDOVER — EnergieProject 32.5.23

## Actuele waarheid
- Live: 32.5.22, PM 2.0.0-rc55, release COMPLETE 9/9.
- Doelrelease: 32.5.23, PM 2.0.0-rc56.
- Type-2 is nog NIET gefinaliseerd/verwijderd.
- Peter heeft cleanup toegestaan; actuele post-migrate recoverylevering + expliciete ontvangstbevestiging blijft verplicht vóór finalize/delete.

## Live Type-2 stand
- 002,003,004,005,006,008,009,010,011,012: MIGRATED_PENDING_VALIDATION + validation GREEN.
- 007: MIGRATED_PENDING_VALIDATION maar validation RED: `old_source_still_mutating:Inbox/control_plane` + `runtime_writer_proof_missing:Inbox/control_plane`.
- Root cause 32.5.22: binding-recreate code is correct but was not invoked because Native MCP was already current and `NativeRuntimeCoordinator.align()` returned before `control_plane_prepare()`.

## 32.5.23 reparatie
- For 32.5.23+ each exact release fence performs one control-plane prepare/binding proof before Native-MCP ready shortcut.
- Existing bounded 32.5.22 recreate/rollback is reused.
- Failure/unproven binding remains fail-closed.
- Older release semantics remain unchanged.

## Na installatie autonoom uitvoeren
1. Confirm 32.5.23 COMPLETE 9/9, PM rc56, NAS/HA alignment.
2. Prove canonical ControlPlane runtime heartbeat is fresh and legacy Inbox/control_plane is quiescent.
3. Revalidate ClearUp_007 and require GREEN.
4. Readback 002–012 all GREEN.
5. Refresh/rebuild current recovery artifacts where required and deliver current 002–012 bundle directly in ChatGPT.
6. After Peter confirms receipt, confirm external recovery gate and finalize/delete 002–012 sequentially with readback.
7. Any deviation: fail closed and repair before deletion.

## Build basis
- Exact predecessor ZIP: EnergieProject_v32.5.22.zip
- SHA256: b64bd2adc6e04ac1ce123a94de0fcac5f3b7717c54339b36d8a690dbafd0867d
- Size: 6,817,354 bytes.

## 32.5.23 pre-install acceptance
- Source complete 32.5: 138/138 GREEN; static 600/600 GREEN + 2 skipped; compile GREEN.
- Fresh-extract complete 32.5: 138/138 GREEN; static 600/600 GREEN + 2 skipped; compile GREEN.
- Exact isolated 32.5.22→32.5.23 atomic transition: LIVE_ACCEPTANCE → ACCEPTED.
- Final physical ZIP hash/size are persisted in the external Projectmanager final checkpoint after immutable build.
