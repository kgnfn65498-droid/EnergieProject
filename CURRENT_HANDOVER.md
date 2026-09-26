# CURRENT HANDOVER — EnergieProject 32.5.21

## Actuele waarheid
- Live vóór installatie: 32.5.20, PM 2.0.0-rc53.
- Doelrelease: 32.5.21, PM 2.0.0-rc54.
- Type-2 is gedeeltelijk live gemigreerd maar NIET gefinaliseerd/verwijderd.
- Peter heeft cleanup/finalize toegestaan, maar destructive finalize blijft technisch geblokkeerd tot de actuele post-migrate recoveryset opnieuw extern is geleverd en bevestigd.

## Live Type-2 stand op 32.5.20
- 002: MIGRATED_PENDING_VALIDATION + validation GREEN.
- 003: MIGRATED_PENDING_VALIDATION + revalidation GREEN; eerste poging detecteerde terecht een pre-activation publisher-writer.
- 004: MIGRATED_PENDING_VALIDATION + validation GREEN.
- 005: PREPARED; migratie geblokkeerd omdat gedeelde destination ReleaseController al sibling State/Publication bevat.
- 006: MIGRATED_PENDING_VALIDATION; validatie geblokkeerd door embedded-PM PermissionError op privileged native_mcp_runtime inhoud.
- 007: MIGRATED_PENDING_VALIDATION; validatie geblokkeerd door embedded-PM PermissionError op privileged control_plane inhoud.
- 008–012: MIGRATED_PENDING_VALIDATION + validation GREEN.
- Geen bron verwijderd.

## 32.5.21 reparatie
- ClearUp_005 kan veilig in een reeds bestaande gedeelde destination-directory mergen zonder sibling data te overschrijven of bij rollback te verwijderen.
- Type-2 filesystemvalidatie wordt volledig door de privileged watcher uitgevoerd; PM blijft orchestrator en leest geen privileged payloadbomen meer.
- Alle eerdere fail-closed checks blijven actief.

## Na installatie autonoom uitvoeren
1. Bevestig COMPLETE 9/9, PM rc54, HA/NAS alignment.
2. ClearUp_005 migrate → validate; eis GREEN.
3. ClearUp_006 en 007 validate; eis GREEN. Bij RED: root cause oplossen, niet finalizen.
4. Controleer 002–012 allemaal `MIGRATED_PENDING_VALIDATION` + validation GREEN.
5. Controleer/refresh recovery alleen waar noodzakelijk; daardoor gewijzigde artifacts maken eerdere ontvangstbevestiging ongeldig.
6. Bouw/download de actuele exacte 002–012 recoveryset en lever die rechtstreeks als chatbestand; geen ngrok-link als eindlevering.
7. Pas na Peters bevestiging van de ACTUELE post-migrate recoveryset: external recovery confirm → finalize 002–012 sequentieel; na iedere finalize readback GREEN en bron afwezig/destination behouden.
8. Bij iedere fout fail-closed stoppen met destructieve vervolgacties en autonoom repareren.
