# Release Acceptance — 32.5.8

32.5.8 is een gerichte ClearUp_001 live-fix bovenop 32.5.6.

## Verplichte acceptatie
- Normale releaseketen Incoming -> Processing -> GitHub -> handmatige HA-update -> COMPLETE -> Processed blijft ongewijzigd.
- `akkoord` voor ClearUp_001 wordt via bestaand Projectmanager `admin_update` transport met `classification_hint=clearup_apply` uitgevoerd; geen nieuwe Native-MCP intent/reload nodig.
- Voor delete: actieve App exact 32.5.8, releasecontroller COMPLETE, processing leeg, recovery staging exact gelijk aan live tree en actieve dependency guard GREEN.
- Privileged watcher-executor accepteert alleen schema `energie_clearup_type1_delete_request_v1`, exact ClearUp_001 en exact vier allowlisted roots.
- De watcher hard-movet eerst alle vier roots transactioneel naar een tijdelijke CLEARUP-run; pas daarna volgt permanente delete. Bij een move-fout wordt teruggerold.
- Na delete moeten alle vier oude Inbox-paden afwezig zijn en moeten incoming/processing ongewijzigd zijn.
- Geen terminal, docker exec, directe release-state mutatie of handmatige Inbox stage-bypass.
- Bestaande watcher move/restore regressies blijven GREEN.
- Fysieke eind-ZIP: veilige unieke entries, canonieke MANIFEST.sha256 en SHA256SUMS.json, volledige payloaddekking, geen caches/bytecode/temp.

Audit <100% GREEN binnen deze release-scope betekent niet uitleveren.
## TYPE2 acceptance
- 32.5.8 bevat de Type2 commando's `clearup_type2_prepare`, `clearup_type2_export_info`, `clearup_type2_export_chunk`, `clearup_type2_migrate`, `clearup_type2_validate`, `clearup_type2_finalize` en `clearup_type2_restore`, allemaal via bestaand `admin_update` transport.
- De concrete, vooraf geïnventariseerde plannen `ClearUp_002` t/m `ClearUp_012` moeten in de fysieke release aanwezig zijn; een voorbeeld-/placeholderplan is niet toegestaan.
- Iedere planregel bevat een exacte `Inbox/...` bron, definitieve `Data/03_Systeem/Projectmanager/...` bestemming, `path_key` en actieve contractchecks.
- Alle betrokken actieve readers/writers gebruiken het centrale `system_path_contract` of zijn expliciet als tijdelijke functionele bridge beschermd; omschakeling gebeurt pas na een geverifieerde activatiemarkering.
- Prepare is non-destructief en mag vóór de code/pad-omschakeling plaatsvinden.
- Migrate vereist expliciet `akkoord`, exact recovery/live bewijs én actieve contractchecks voor de nieuwe locatie; source blijft bestaan.
- Finalize vereist expliciet `akkoord` plus afzonderlijk GREEN live-validation bewijs met exact dezelfde plan-SHA; pas dan worden oude sources transactioneel verwijderd.
- Sources mogen nooit onder incoming/processing/processed/failed liggen; destinations moeten onder Data/03_Systeem liggen.
- Type2 restore herstelt de oude source non-destructief vanuit recovery staging en laat de nieuwe destination intact.
- Type1 ClearUp_001 en de normale Incoming releaseketen blijven regressie-GREEN.

