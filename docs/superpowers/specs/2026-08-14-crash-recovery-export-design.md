# Crash Recovery export naar browser/iCloud — ontwerp v32.0.29

Datum: 2026-08-14
Branch: `feature/v32.0.29-crash-recovery-export`
Basis: productie `32.0.28`

## Doel

Maak van **Complete Crash Recovery** een gebruikersbackup die niet als blijvende backup op de NAS achterblijft. De normale interne NAS-backups met retentie 3 blijven ongewijzigd.

Gewenste eindbediening:

- gebruiker geeft de opdracht `maak complete crash recovery`, of gebruikt de HA-knop;
- systeem maakt de bestaande RecoveryManager-backup;
- systeem deep-verifieert alle bestanden;
- systeem voert een geïsoleerde RestoreStaging-test uit;
- systeem levert één herstelvriendelijke ZIP als browserdownload;
- gebruiker zet die ZIP zelf in iCloud;
- na een volledig geslaagde download worden alleen de tijdelijke artefacten van deze export van de NAS verwijderd;
- bij een echte crash zet de gebruiker de ZIP terug in de share `AI Projecten` en pakt hem uit; resultaat moet één map `EnergieProject/` zijn.

## Niet-doelen

- Geen automatische iCloud-upload.
- Geen live restore over `/project`.
- Geen `finalize_month`.
- Geen release-ZIP en nooit naar `Inbox/incoming`.
- Geen wijziging van de bestaande interne backupretentie.
- Geen wijziging van maandworkflow, rapportage of data-import.

## Gekozen aanpak

De bestaande, bewezen RecoveryManager blijft de bron van waarheid.

1. `create_complete_backup`
2. `verify_complete_backup(deep_verify_files=True)`
3. `preview_backup_restore`
4. `stage_backup_restore`
5. controleer dat de bron niet is gewijzigd en dat het stagingpad uitsluitend onder `RestoreStaging` ligt;
6. bepaal of de geverifieerde bron-ZIP al precies één top-level map `EnergieProject/` bevat;
7. zo ja: gebruik die ZIP rechtstreeks als export;
8. zo nee: bouw vanuit de geverifieerde RestoreStaging-inhoud een tijdelijke export-ZIP met exact één top-level map `EnergieProject/`;
9. valideer de export-ZIP opnieuw met ZIP-integriteitstest en SHA-256;
10. maak de export beschikbaar via een downloadroute in de HA-add-on;
11. stream de ZIP naar de browser met `Content-Type: application/zip` en `Content-Disposition: attachment`;
12. pas na volledige succesvolle stream: verwijder uitsluitend de tijdelijke bestanden die door deze export-run zijn aangemaakt.

Deze aanpak voorkomt een tweede recovery-engine: RecoveryManager blijft create/verify/stage doen. Alleen de laatste gebruiksvriendelijke exportlaag komt erbij.

## Waarom niet de andere opties

### Alleen de huidige RecoveryManager-ZIP downloaden

Voordeel: minste code en geen extra ZIP-stap.

Nadeel: alleen acceptabel als de ZIP al gegarandeerd exact `EnergieProject/` als top-level map bevat. Dat mag niet worden aangenomen. De gebruiker moet de ZIP vanuit `AI Projecten` kunnen uitpakken zonder losse `App`, `Data`, `Backups`, `Inbox` of `Infra` naast elkaar te krijgen.

### Een tweede volledige backup-engine in Home Assistant bouwen

Voordeel: volledige controle over ZIP-opbouw.

Nadeel: dupliceert RecoveryManager, vergroot risico op verschillen tussen backup- en herstelgedrag en maakt het eerdere 1267/1267-bewijs minder relevant. Daarom afgewezen.

## Artefacten en opslag

### Blijvend

Alleen kleine statusmetadata in Home Assistant:

- exportstatus;
- bestandsnaam;
- export-SHA-256;
- aantal geverifieerde bestanden;
- datum/tijd;
- downloadstatus;
- cleanupstatus.

Geen bevestigingsteksten of geheimen worden opgeslagen.

### Tijdelijk

Per export-run mogen tijdelijk bestaan:

- de door RecoveryManager gemaakte complete backup-ZIP;
- bijbehorend manifest;
- één RestoreStaging-directory;
- indien nodig één gebruiksvriendelijke export-ZIP.

Deze paden worden vóór cleanup exact uit de runstate afgeleid en moeten onder de vooraf toegestane backup-/RestoreStaging-locaties vallen. Geen glob-delete en geen retentie-cleanup gebruiken voor deze export.

## Download- en cleanupgedrag

De HA-kaart krijgt na succesvolle create/verify/stage een knop **Download Crash Recovery ZIP**.

De downloadroute:

- accepteert alleen de laatst volledig geverifieerde export-run;
- controleert de export-SHA opnieuw vóór streaming;
- streamt in blokken en laadt niet de hele ZIP in geheugen;
- verwijdert niets vóór de response volledig is verzonden;
- bij `BrokenPipeError`, `ConnectionResetError` of andere streamfout blijft de tijdelijke export beschikbaar voor retry;
- bij succesvolle stream wordt de run als `downloaded` gemarkeerd en wordt cleanup uitgevoerd;
- cleanup verwijdert alleen de exact geregistreerde bestanden/directories van deze run;
- cleanup-fout maakt de download niet ongeldig maar wordt zichtbaar als waarschuwing en kan via de expliciete cleanup-route opnieuw worden geprobeerd.

## Herstelvriendelijke ZIP

De ZIP die de gebruiker downloadt moet structureel voldoen aan:

```text
EnergieProject_Complete_Crash_Recovery_<timestamp>.zip
└── EnergieProject/
    ├── App/
    ├── Data/
    ├── Backups/
    ├── Inbox/
    └── Infra/
```

De vijf hoofdmappen moeten aanwezig zijn. Extra geldige projectbestanden binnen `EnergieProject/` zijn toegestaan. Er mogen geen bestanden buiten `EnergieProject/` in de export-ZIP staan.

Het doelherstel is bewust eenvoudig:

1. iCloud-ZIP terugplaatsen in `AI Projecten`;
2. een eventueel beschadigde bestaande `EnergieProject` eerst veilig apart zetten;
3. ZIP uitpakken;
4. `AI Projecten/EnergieProject/` staat weer terug.

## API/GUI

Bestaande routes blijven compatibel:

- `GET /api/crash-recovery/state`
- `POST /api/crash-recovery/complete`
- `POST /api/crash-recovery/stage`

Nieuw:

- `POST /api/crash-recovery/export` — complete flow create + deep verify + RestoreStaging + export-preparatie;
- `GET /api/crash-recovery/download` — stream de laatst voorbereide export;
- `POST /api/crash-recovery/cleanup` — uitsluitend beschikbaar wanneer een eerdere automatische cleanup van dezelfde run niet volledig is geslaagd.

De bestaande twee diagnosehandelingen blijven intern/API-compatibel. In de normale GUI wordt **Maak complete Crash Recovery** de primaire actie voor de hele create/verify/stage/export-flow en verschijnt daarna **Download Crash Recovery ZIP**. Een aparte RestoreStaging-knop mag zichtbaar blijven onder diagnose, maar is niet meer nodig in de normale gebruikersflow.

De latere spraak/commandolaag hoeft alleen `POST /api/crash-recovery/export` aan te roepen en de download-URL terug te geven. Die koppeling is niet onderdeel van v32.0.29.

## Veiligheidsregels

- `WORKFLOW_LOCK` en `COMPLETE_CRASH_RECOVERY_LOCK` blijven verplicht.
- Geen recovery-export starten tijdens een actieve maandworkflow.
- Nooit `finalize_month` aanroepen.
- Nooit live projectdata overschrijven.
- Geen delete buiten strikt gevalideerde tijdelijke paden van deze run.
- Een deep verify met `verified_files != manifest_file_count` is altijd fout.
- Een RestoreStaging-resultaat is alleen geldig bij `source_project_modified is False` en een pad onder `/recovery/RestoreStaging`.
- Browserdownload wordt pas aangeboden als alle veiligheidschecks groen zijn.

## Teststrategie

TDD en releasegate moeten minimaal bewijzen:

1. incomplete deep verify wordt geweigerd;
2. RestoreStaging buiten het veilige pad wordt geweigerd;
3. `source_project_modified=True` wordt geweigerd;
4. export-ZIP heeft exact top-level `EnergieProject/`;
5. `App`, `Data`, `Backups`, `Inbox`, `Infra` zitten in de export;
6. export-SHA klopt vóór download;
7. succesvolle download streamt byte-identiek en triggert cleanup;
8. afgebroken download verwijdert niets en is opnieuw downloadbaar;
9. cleanup kan nooit buiten de run-specifieke allowlist verwijderen;
10. `finalize_month` komt niet voor in de nieuwe flow;
11. bestaande v32.0.28 recoverytests blijven groen;
12. volledige statische suite en HA startup/selftest blijven groen;
13. productie blijft 32.0.28 tot de volledige v32.0.29-releasegate geslaagd is.

## Acceptatiecriteria

De feature is pas gereed wanneer een echte HA-run aantoonbaar:

- create + deep verify volledig groen uitvoert;
- RestoreStaging volledig groen uitvoert;
- één downloadbare herstel-ZIP oplevert;
- die ZIP na uitpakken precies `EnergieProject/` oplevert;
- browserdownload geen blijvende Crash-Recovery-ZIP op de NAS achterlaat;
- de normale NAS-backups/retentie niet wijzigt;
- augustus/lopende maand niet afsluit;
- productie niet overschrijft.
