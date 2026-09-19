# CURRENT HANDOVER — EnergieProject 32.4.58

Datum: 2026-09-19
Status: LIVE NAS 32.4.58 ATOMIC ACCEPTED; HA NOG 32.4.57; REPOSITORY-LAYOUT HOTFIX SOURCE-SUITE GREEN; NIEUW FINAL ARTIFACT + FRESH-EXTRACT + SAME-VERSION GITHUB REPUBLISH NOG OPEN

## Nieuwe-chat / crash-resume
Lees eerst:
1. PROJECT_CONSTITUTION.md
2. CURRENT_HANDOVER.md
3. WORK_LEDGER.md
4. hoogste `ARCHITECTURE_32458_CHECKPOINT_*` worklog
5. daarna alleen stagingbestanden met latere modified timestamp.

Niet opnieuw beginnen met reeds bewezen onderzoek of tests. Hervat vanaf het hoogste werkelijk opgeslagen bewijs.

## Live waarheid
- NAS `App/VERSIE.txt` = 32.4.58.
- Live 58 artifact dat lokaal werd geaccepteerd: SHA256 `3c097b869adc7c8f9000533e7dce4c090084c88cb445e22cef3a946a3574b91c`.
- Atomic state = ACCEPTED voor 32.4.57 -> 32.4.58.
- Final 58 ZIP staat in `Inbox/processed`; Incoming/Processing zijn leeg.
- GitHub main bevat 32.4.58, maar de gepubliceerde repository-layout is defect omdat ook `tests/fixtures/legacy57/config.yaml` werd gepubliceerd.
- Home Assistant runtime blijft daardoor 32.4.57 en toont geen update.
- ReleaseController staat in ACCEPTED/delivery-blocked op de publicatieketen; dit is geen lokale installatiefout.

## Root cause Home Assistant update-onzichtbaar
Home Assistant Supervisor scant een app-repository recursief op `config.yaml`. De gepubliceerde 58 bevatte twee bestanden met die gereserveerde naam:
- `slimmemeterportal_import/config.yaml` — echte 32.4.58 add-onconfig.
- `tests/fixtures/legacy57/config.yaml` — historische 32.4.57 fixture met dezelfde slug.
Deze repository-layoutfout verklaart waarom GitHub 58 bevat maar HA geen update toont.

## Structurele fix in staging
- Werkboom: `/mnt/data/32458_hotfix`.
- Historische fixture hernoemd naar `tests/fixtures/legacy57/config_legacy57.yaml`.
- Alle historische testreferenties daarop aangepast.
- Nieuwe regressie `test_58_22_github_repository_exposes_only_one_home_assistant_config_yaml`.
- Exact één `config.yaml` blijft over: `slimmemeterportal_import/config.yaml`.

## Teststatus corrected source
Actuele collectie: 1.956 tests.
- top-level: 1.945 passed, 2 skipped, 0 failed.
- geneste rapportgeneratoren: 9 passed, 0 failed.
- totaal: 1.954 passed, 2 skipped, 0 failed.
- watcher practical soak afzonderlijk 6/6 GREEN.
- Een gemiste historische identity-testreferentie werd tijdens de volledige suite gevonden, gerepareerd en het betrokken blok is daarna opnieuw GREEN uitgevoerd.

## Artifactstatus
- Tussentijdse repo-hotfix ZIP SHA `373e7f0d...` is VERVALLEN omdat daarna nog één testreferentie werd gecorrigeerd.
- Bouw pas nu een nieuw final same-version 32.4.58 artifact met de canonieke `tools/release_artifact_builder.py`.
- Daarna exact fresh-extract van die nieuwe bytes en volledige 1.956-testcollectie opnieuw sluiten.

## Eerstvolgende harde gates
1. Metadata/manifests regenereren en nieuw final 32.4.58 repo-hotfix artifact bouwen.
2. CRC, MANIFEST.sha256, SHA256SUMS.json, exact één `config.yaml`, versie en symlink/path-gates bewijzen.
3. Exact artifact fresh-extracten; collect-only exact 1.956 en volledige suite GREEN.
4. Same-version GitHub-repository veilig corrigeren zonder live state te fabriceren. Beschikbare Energie_NAS/HA connectors kunnen geen GitHub-write of binary NAS-upload uitvoeren; gebruik uitsluitend een bestaande fail-closed projectroute of benoem de kleinste noodzakelijke eenmalige transportactie.
5. HA repository refresh/update naar 32.4.58; daarna `ha_runtime/current.json = 32.4.58`.
6. ReleaseController naar COMPLETE en daarna blijvend PID1/IDLE, Incoming/Processing leeg.
7. Vervolgens N+1-readiness bewijzen zonder restart/script/state-reset.

## Niet doen
- Oude artifacts `c98c0806...`, `5419ba90...`, `3c097b86...` of tussentijdse repo-hotfix SHA `373e7f0d...` opnieuw als nieuwe release aanbieden.
- Geen `current.json` of atomic state handmatig groen maken.
- Geen nieuwe watcher-restart/recreate zonder aantoonbare noodzaak en expliciete autorisatie.
- Geen nieuwe releaseversie starten alleen om deze GitHub-layoutfout te maskeren zolang same-version 58-correctie nog technisch oplosbaar is.
