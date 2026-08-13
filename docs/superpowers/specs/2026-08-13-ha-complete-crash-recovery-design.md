# v32.0.28 — Home Assistant complete Crash Recovery

## Doel
Voeg aan de bestaande Home Assistant Ingress-GUI een veilige bediening toe voor de reeds bewezen volledige EnergieProject Crash Recovery. De bestaande maandworkflow, scheduler, SMP-import, GitHub-publicatiearchitectuur en productiekern blijven inhoudelijk ongewijzigd.

## Harde veiligheidsgrenzen
- `finalize_month` wordt door deze route nooit aangeroepen.
- De route maakt geen eigen/parallel backupformaat; zij gebruikt uitsluitend de bestaande NAS MCP-recoverytools.
- Een restore-test schrijft uitsluitend naar `/recovery/RestoreStaging` en nooit naar de productieprojectroot.
- De draaiende productie en GitHub `main` worden pas gewijzigd nadat de releasepoort volledig groen is.
- Geen credentials, secrets, runtime options of private data worden aan GitHub/release toegevoegd.
- Als de maandworkflow actief is, start de GUI geen Crash Recovery en geeft zij een gecontroleerde busy-status terug.

## Architectuur
De HA-app krijgt een kleine, afzonderlijke Crash Recovery-controller naast de bestaande recovery-statuscontroller. Hiervoor wordt een niet-cachende MCP-action helper gebruikt, omdat create/verify/stage acties nooit door de bestaande read-only cache mogen worden onderdrukt of herhaald uit cache.

De controller gebruikt uitsluitend deze bestaande MCP-contracten:
1. `preview_month_closure(year, month)` — alleen om de door de recoverybackend vereiste bevestigingszin te verkrijgen; deze call finaliseert niets.
2. `create_complete_backup(year, month, confirmation)` — maakt de volledige `Energie_Complete_Backup_...zip`.
3. `verify_complete_backup(year, month, backup_name, deep_verify_files=True)` — voert ZIP/manifest/SHA/deep file verification uit.
4. Optioneel: `preview_backup_restore(year, month, backup_name)` gevolgd door `stage_backup_restore(year, month, backup_name, confirmation)` — uitsluitend RestoreStaging.

## GUI
Nieuwe kaart `Complete Crash Recovery` met:
- knop `Maak complete Crash Recovery`;
- status: idle/running/verified/error;
- backupnaam;
- SHA-256;
- manifest file count en verified file count;
- aantal hash failures;
- tijdstip laatste uitvoering;
- knop `Test herstel naar RestoreStaging`, alleen beschikbaar na een geslaagde deep verify.

De GUI toont expliciet dat augustus/lopende maand niet wordt afgesloten en dat geen productiedata worden overschreven.

## API/dataflow
### Maak backup
`POST /api/crash-recovery/complete`
1. Weiger met 409 als maandworkflow of een andere Crash Recovery-actie actief is.
2. Bepaal actuele lokale `year/month` in Europe/Amsterdam.
3. Vraag via `preview_month_closure` de bestaande bevestigingszin op.
4. Roep `create_complete_backup` aan.
5. Leid `backup_name` af uit het geretourneerde backuppad.
6. Roep direct `verify_complete_backup(..., deep_verify_files=True)` aan.
7. Alleen wanneer status `valid`, `deep_verified=true`, `verified_files == manifest_file_count` en `hash_failures=[]` is de GUI-status `verified`.
8. Sla uitsluitend niet-gevoelige resultaatmetadata op in `/config/output/complete_crash_recovery_state.json`.

### Restore-staging test
`POST /api/crash-recovery/stage`
1. Alleen toegestaan voor de laatst deep-verified backup.
2. Vraag herstelpreview + bevestigingszin op.
3. Roep `stage_backup_restore` aan.
4. Accepteer alleen een resultaat onder `/recovery/RestoreStaging` met `source_project_modified=false`; anders status error.

## Foutafhandeling
- MCP timeout/netwerkfout: gecontroleerde HTTP 502/504 en zichtbare GUI-fout; HA-app blijft draaien.
- Backend weigert bevestiging: geen retry met gegokte tekst.
- Deep verify faalt: backup wordt niet als goed gemarkeerd en restore-test blijft uitgeschakeld.
- UI/API-fouten mogen geen startup-, health- of Ingress-fout veroorzaken.

## Teststrategie / vrijgavepoort
Naast bestaande regressietests komen gerichte tests voor:
- GUI rendert de nieuwe kaart zonder MCP-bereikbaarheid;
- complete-backuproute roept `finalize_month` nooit aan;
- correcte MCP-volgorde preview → create → deep verify;
- deep verify moet 1:1 aantallen en 0 hash failures eisen;
- restore-test gebruikt alleen preview → stage en eist RestoreStaging + `source_project_modified=false`;
- gelijktijdige maandworkflow geeft 409 en start geen recovery;
- fouten laten `/health` en Ingress renderen.

Daarna geldt de bestaande minimale releasepoort: volledige relevante tests, echte app-runtime, `/health` 200, GUI/Ingress 200, startup-selftest, ontbrekende credentials mogen GUI niet crashen, oude-watcher→nieuwe-release installatiesimulatie, processed-retentie, ZIP-integriteit, manifest en SHA-256.

## Releasepad
Versie: `32.0.28`.

Eén normale release-ZIP `EnergieProject_v32.0.28.zip` via de bestaande keten:
`Inbox/incoming → watcher-validatie/backup/installatie → App → HA GitHub publisher → GitHub main → Home Assistant update`.

Geen losse scripts en geen directe live patch op HA.