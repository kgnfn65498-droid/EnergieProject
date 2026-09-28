# AGENT_TASK — EnergieProject 32.5.28 recovery-first final Inbox cleanup + always-current handover

- mode: DEVELOPMENT
- reasoning: HIGH
- stap: 1/7
- buildbasis: exact verified EnergieProject_v32.5.27.zip SHA256 ea3674ebc32067a7c71b5798f33cb3e9de03f1d1c178dcb96e0f73e7dc4e89f2
- live productie: 32.5.27 COMPLETE / IDLE
- target: 32.5.28
- productieautoriteit: NEE

## Doel
1. Maak de finale Type-3/Inbox cleanup recovery-first: vóór enige live mutatie bestaat een volledig geverifieerde, extern leverbare recovery-ZIP die exact aan het current cleanup-plan en de live source-bytes is gebonden.
2. Maak development-handover vanaf 32.5.28 automatisch en fail-closed actueel: current handover/pointer/checkpoint moeten één machine-verifieerbare generatie vormen; stale/mismatch blokkeert release-ready en nieuwe-chat `verder` gebruikt altijd de nieuwste geldige waarheid.
3. Borg de ontwikkelstandaard van de releaseketen opnieuw end-to-end: een nieuwe geldige ZIP verlaat `Inbox/incoming`, wordt duurzaam eigenaar in `Inbox/processing`, blijft daar tijdens de handmatige HA-update, en gaat pas na exact bewezen HA-target naar `Inbox/processed`; daarna moet een volgende ZIP dezelfde permanente processing-mailbox opnieuw kunnen gebruiken.

## Scope — wijzigen toegestaan
- slimmemeterportal_import/rootfs/app/projectmanager_v2/inbox_cleanup_32526.py
- slimmemeterportal_import/rootfs/app/projectmanager_v2/command_processor.py
- slimmemeterportal_import/rootfs/app/projectmanager_v2/development_context_enforcement.py
- slimmemeterportal_import/rootfs/app/projectmanager_v2/manager_service.py indien nodig voor bestaande PM-sync
- één nieuwe compacte handover-sync module binnen dezelfde projectmanager_v2 package indien dat aantoonbaar de kleinste structurele oplossing is
- tools/project_clearup_move_executor.py
- tools/release_controller_service.py en tools/ha_delivery_adapter.py uitsluitend wanneer een 32.5.28-regressietest een werkelijk ketendefect aantoont
- tests voor 32.5.28 + bestaande relevante tests
- release-identiteit/docs/ledger/checkpoint uitsluitend nadat functionele gates GREEN zijn

## Expliciet niet wijzigen
- geen derde filesystem-executor, watcher, daemon of lifecycle-owner;
- Type-2 ClearUp_002–012 blijft CLOSED;
- Inbox/processing blijft permanent aanwezig en leeg; nooit cleanup-item;
- canonical GitHub publication state blijft Data/03_Systeem/Projectmanager/ReleaseController/Publication;
- geen GitHub/productieboom als buildbasis;
- geen live cleanup, productie-installatie, restart/recreate, handmatige ZIP move of Terminal als normale route.

## Bewezen feiten
- exacte predecessor-ZIP is lokaal hersteld uit het bestaande retentie-artifact en SHA256 is exact geverifieerd.
- eerdere 32.5.28 recovery-first implementatie had gerichte 23/23 GREEN; die lokale worktree was niet persistent beschikbaar in deze chat, dus alleen de bewezen requirements/architectuur worden hergebruikt en de herstelde bytes moeten opnieuw volledig worden getest.
- live = 32.5.27 COMPLETE / IDLE; 32.5.28 is nog geen release.
- Type-2 002–012 CLOSED; Processing permanent.

## Verplichte implementatie — recovery-first
- prepare exact current cleanup plan;
- snapshot alle te verplaatsen source-bytes naar staging vóór mutatie;
- manifest met paths/types/sizes/SHA256 + plan_sha256;
- ZIP CRC + manifest + payload deep verify;
- live source na snapshot opnieuw exact verifiëren;
- prepare/export is non-destructive;
- projectmanager_submit_command routes: inbox_cleanup_prepare_recovery, inbox_cleanup_export_info, inbox_cleanup_export_chunk;
- bounded base64 chunks met chunk SHA256/offset/next_offset/eof en immutable artifact identity;
- apply vereist exact current plan, recovery ZIP opnieuw GREEN, current source==manifest en exacte expliciete bevestiging;
- privileged executor herverifieert dezelfde gates vlak vóór mutatie;
- restore request-scoped/hash-bound;
- projectmanager_v2 absoluut laatste cleanupactie;
- 20s resurrection soak behouden.

## Verplichte implementatie — always-current handover
- bestaande DS9/Projectmanager-laag gebruiken; geen parallelle waarheid;
- een canonieke machine-readable development handover generation/fingerprint;
- current handover + chat-switch pointer + hoogste checkpoint worden atomisch/projectiematig naar dezelfde generation gesynchroniseerd en teruggelezen;
- stale/missing/mismatched target/live/predecessor/checkpoint/generation => HANDOVER_STALE/RED;
- nieuwe-chat `verder` kiest nieuwste geldige checkpoint; oudere statische claims kunnen niet winnen;
- live release en target-in-development blijven expliciet gescheiden;
- final_zip_exists/release_ready mogen niet impliciet uit VERSIE.txt volgen;
- freshness is pre-release/fresh-extract gate en wordt na meaningful checkpoint/statusovergang ververst.

## Verplichte releaseketen — Incoming → Processing → HA → Processed
- `Inbox/processing` is een permanente mailbox; idle = bestaat als echte directory en is leeg.
- stabiele geldige nieuwe ZIP mag niet in `Inbox/incoming` blijven hangen: controller claimt hem atomisch naar `Inbox/processing`.
- tijdens `WAITING_MANUAL_HA_UPDATE` blijft exact dezelfde ZIP in `processing`; geen vroegtijdige archive/move.
- pas wanneer GitHub/publication exact én HA-runtime exact target bewijzen, archiveert controller exact dezelfde SHA256 naar `Inbox/processed`.
- COMPLETE mag nooit gelden wanneer de eigen release-ZIP nog in `processing` staat of ontbreekt uit `processed`.
- regressie omvat minimaal twee opeenvolgende releases zodat processing-hergebruik en volgende ingress aantoonbaar werken.
- geen handmatige publication-state reconciliatie, processing-map rename, handmatige ZIP move, watcher/restart of Peter-Terminal als normale keten.
- release acceptance en host-capability Platform Qualification blijven afzonderlijke contracten; een groene platformkwalificatie vervangt geen release acceptance en omgekeerd.

## Acceptance
- TDD RED → GREEN voor beide scopes.
- gerichte 32.5.28 tests + bestaande 32.5.26/27 cleanup regressies GREEN.
- full applicable regressie GREEN; compileall en shell syntax GREEN.
- predecessor-boundary bewijs: 32.5.27 kan de definitieve 32.5.28 via normale Incoming-keten verwerken zonder manual publication reconciliation, processing rename, ZIP move of Peter-Terminal.
- twee-op-een releaseketenregressie GREEN: ZIP A incoming→processing→HA exact→processed, processing blijft leeg/bestaan, daarna ZIP B opnieuw incoming→processing→HA exact→processed.
- definitive ZIP exact: unique names, CRC, MANIFEST.sha256, SHA256SUMS.json, identity/version correct.
- fresh-extract voert dezelfde tests/gates uit en bewijst handover freshness.
- Work self-audit, onafhankelijke Spock-audit en exact één Codex Terra/Medium bounded audit vóór vrijgave.
- recovery-ZIP voor live cleanup moet in chat zijn geleverd/gedownload en extern exact bevestigd vóór enige live cleanup.

## Stopcriteria
Stop alleen bij protected productieapproval, echte onoplosbare artifact/safety/model blocker, of volledig geverifieerde 32.5.28 artifact-ready toestand. Checkpointing is geen stopmoment.
