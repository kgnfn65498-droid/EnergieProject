# Crash Recovery watcher-cleanup design

## Doel
Na een volledig geslaagde browserdownload van een Complete Crash Recovery ruimt het systeem alle tijdelijke run-artifacten automatisch op zonder afhankelijk te zijn van de Home Assistant-containerrechten op de QNAP-share. Dezelfde backendketen blijft bruikbaar wanneer de Crash Recovery later via een spraakopdracht wordt gestart.

## Architectuur
Home Assistant blijft eigenaar van generatie, deep verify, RestoreStaging-test, browserexport en downloadstatus. Na een volledige stream verwijdert HA alleen de lokale browserexport onder `/config/output/crash_recovery_exports` en schrijft het een strikt gevalideerd cleanup-verzoek naar `Inbox/crash_recovery_cleanup_request.json`.

De bestaande `energie-release-watcher` verwerkt dat verzoek in zijn QNAP/Docker-context. Een nieuwe kleine helper `tools/crash_recovery_cleanup.py` valideert uitsluitend:
- `Energie_Complete_Backup_*.zip` als bronbackup;
- exact het daarvan afgeleide manifest in `Backups/Manifests`;
- exact één subpad onder `/recovery/RestoreStaging/`.

Maandbackups, `FULL_RECOVERY*.tar.gz`, release-ZIP's en willekeurige paden zijn verboden. De helper is idempotent: reeds verdwenen exacte run-artifacten gelden als veilig afgehandeld.

De watcher schrijft het resultaat naar `Inbox/crash_recovery_cleanup_result.json`. HA reconcileert dit resultaat naar `complete_crash_recovery_state.json`; daadwerkelijke cleanup is dus headless en GUI-onafhankelijk.

## Bestaande v32.0.31 warning
Als v32.0.32 een gedownloade Crash Recovery aantreft met `cleanup_status=warning`, wordt hetzelfde strikt afgeleide cleanup-verzoek opnieuw aangeboden. Er wordt geen nieuwe Crash Recovery gemaakt en niets buiten de geregistreerde run-artifacten verwijderd.

## Spraakcompatibiliteit
De backendactie voor `Maak complete Crash Recovery` blijft onafhankelijk van de GUI. Een toekomstige spraaklaag kan dezelfde backendactie starten. Cleanup wordt pas gestart nadat een daadwerkelijke ZIP-overdracht/download volledig is afgerond; automatische iCloud-upload valt buiten deze release.

## Statusmodel
- `ready_for_download`: export is geverifieerd en wacht op overdracht.
- `downloaded` + `cleanup_pending`: stream is voltooid; watcher moet NAS-artifacten opruimen.
- `downloaded` + `cleanup_status=ok`: export én exacte tijdelijke NAS-run-artifacten zijn verwijderd.
- `downloaded` + `cleanup_status=warning/error`: veilig behouden; exacte oorzaak zichtbaar, opnieuw aanbieden toegestaan.

## Veiligheid
- Geen `finalize_month` of maandworkflow-aanroepen.
- Augustus blijft open.
- Geen brede delete van `Backups`, `Inbox`, `App` of `Data`.
- Geen delete op basis van een door HA aangeleverd absoluut NAS-pad.
- Cleanup-request en resultaat worden atomisch geschreven.
- Retentiebeleid van release/backups wordt niet gewijzigd.

## Teststrategie
TDD met unit- en integratietests voor request-validatie, path traversal, maandbackup/FULL_RECOVERY-blokkade, idempotentie, watcher-aanroep, succesvolle stream + pending cleanup, reconciliation naar `ok`, retry van de bestaande 32.0.31-warning en behoud bij fout. Daarna volledige regressie en release-ZIP-gates.
