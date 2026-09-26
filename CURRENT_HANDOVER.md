# CURRENT HANDOVER — EnergieProject 32.5.22

## Actuele waarheid
- Live vóór installatie: 32.5.21, PM 2.0.0-rc54, release COMPLETE 9/9.
- Doelrelease: 32.5.22, PM 2.0.0-rc55.
- Type-2 is nog NIET gefinaliseerd/verwijderd.
- Peter heeft cleanup toegestaan, maar actuele post-migrate recoverylevering + expliciete ontvangstbevestiging blijft verplicht vóór finalize/delete.

## Live Type-2 stand
- 002,003,004,005,006,008,009,010,011,012: MIGRATED_PENDING_VALIDATION + validation GREEN.
- 007: MIGRATED_PENDING_VALIDATION maar validation RED: `old_source_still_mutating:Inbox/control_plane` + `runtime_writer_proof_missing:Inbox/control_plane`.
- Root cause: live `energie-control-plane` gebruikt nog legacy runtime-root/bind; de canonieke runtime stopte met heartbeat terwijl legacy Inbox runtime bleef schrijven.
- 5.21 bootstrap controleerde alleen health/fingerprint en accepteerde `stale_but_exact`, waardoor een oude bindconfig onzichtbaar bleef.

## 32.5.22 reparatie
- Bootstrap bewijst na actieve Type-2 mapping de daadwerkelijke control-plane command/binds.
- Legacy binding triggert exact één bounded container recreate met canonieke runtime-, release-controller- en native-MCP mounts.
- Mislukte recreate rolt terug naar de vorige container en blijft fail-closed.
- Control-plane security migration schrijft na recreate naar de canonieke ReleaseController en niet opnieuw naar retired Inbox.

## Na installatie autonoom uitvoeren
1. Bevestig 32.5.22 COMPLETE 9/9, PM rc55, canonieke HA/NAS alignment en control-plane binding current.
2. ClearUp_007 validate; eis GREEN.
3. Readback 002–012: allemaal MIGRATED_PENDING_VALIDATION + validation GREEN.
4. Refresh recovery waar door live verandering vereist; controleer externe gate/hashes.
5. Bouw/download de ACTUELE 002–012 recoveryset en lever rechtstreeks als chatbestand.
6. Na Peters expliciete ontvangstbevestiging: external recovery confirm en finalize/delete 002–012 sequentieel, met GREEN readback na ieder item.
7. Iedere afwijking: fail-closed stoppen met delete en autonoom repareren.

## Finale buildacceptatie 32.5.22
- Source exact: `EnergieProject_v32.5.21.zip`, SHA256 `fbe0b729006bdefd2b774363ee46be3f89610d2da737bd727d89f55301716cde`.
- 32.5-suite: 134/134 GREEN; static 600/600 GREEN (+2 skipped); fresh targeted 45/45 GREEN; fresh static 600/600 GREEN (+2 skipped); compileall GREEN.
- Exact atomic 32.5.21→32.5.22: LIVE_ACCEPTANCE→ACCEPTED.
- Geen Type-2 finalize/delete uitgevoerd tijdens build/audit.
