# CURRENT HANDOVER — EnergieProject 32.4.58

Datum: 2026-09-19
Status: REVISED RECOVERY-BUILD PREBUILD GREEN; LIVE 57 HERSTELD COMPLETE/IDLE; NIEUW FINAL ARTIFACT + FRESH-EXTRACT + 58 LIVE E2E NOG OPEN

## Nieuwe-chat / crash-resume
Lees eerst:
1. PROJECT_CONSTITUTION.md
2. CURRENT_HANDOVER.md
3. WORK_LEDGER.md
4. hoogste `ARCHITECTURE_32458_CHECKPOINT_*` worklog
5. daarna alleen stagingbestanden met latere modified timestamp.

Niet opnieuw beginnen met reeds bewezen onderzoek of tests. Hervat vanaf het hoogste werkelijk opgeslagen bewijs.

## Canonical buildbasis
- Live productie: 32.4.57.
- Canonical processed basis: `Inbox/processed/EnergieProject_v32.4.57.zip`.
- Grootte: 5.735.133 bytes.
- SHA256: `6e81f14297d47a86f9dec896dcb69a0314dd45ed6929ff356977a38d4d64a2c9`.
- Lokale staging is uitsluitend uit exact dit artifact opgebouwd.

## 32.4.58 kern
- Eén ReleaseController blijft de enige Incoming lifecycle-owner.
- Geen legacy_install_adoption meer in 58 normale controllerflow.
- Evidence is idempotent gededupliceerd.
- Globale USER/DEVELOPMENT/MAINTENANCE startup/GUI-gates zijn uit actieve runtime verwijderd.
- Geen automatische post-release/startup CLEARUP-thread.
- Oude release_validation_hold/release_transition/watcher-heartbeat zijn geen actuele release-healthauthority.
- Releasecontroller runtime is de livenessbron.
- PM-health is gescheiden in release/runtime, energiedata/live sources, onderhoud/backup/hygiëne en PM/observability.
- Lege kwartiersnapshot is collector/snapshotfout en veroorzaakt geen fictieve live-source-uitval.
- Home Assistant delivery gebruikt Supervisor `/store/reload` + `/addons/self/rebuild`, met `hassio_api: true` en `hassio_role: manager`.
- Historische contracten blijven exact bewaard onder `tests/fixtures/legacy57`.
- N→N+1 atomic journal rollover accepteert uitsluitend een fysiek bewezen direct-vorige `ACCEPTED` journal als historische predecessor; overige mismatches blijven fail-closed.

## Teststatus
- 25 specifieke 32.4.58 simplification/regressietests aanwezig en GREEN.
- Live ontdekt N→N+1 journal-defect eerst met nieuwe RED-test gereproduceerd en daarna structureel gerepareerd.
- Volledige actuele revised prebuild-collectie inclusief ingebedde rapportgenerator-tests:
  - 1.953 passed
  - 2 skipped
  - 0 failed
  - 1.955 totaal
- Langzame watcher-soak is afzonderlijk per testnode uitgevoerd om platformtime-outs te vermijden; timingflap is herhaald GREEN gesloten zonder testversoepeling.

## Productiestatus
- Eén expliciet geautoriseerde normale restart van `energie-release-watcher` heeft de 57-controller correct als PID1/IDLE laten overnemen; daarna geen extra restart/recreate uitgevoerd.
- Exact eerste 58-artifact werd via Incoming correct geclaimd naar Processing, maar live 57 blokkeerde fail-closed in INSTALLING op `rollback_unproven`.
- Root cause: live 57 interpreteerde het nog geldige vorige 56→57 `ACCEPTED` atomic journal als current 57→58 journalmismatch.
- Het eerste 58-artifact werd pre-activation geblokkeerd; de oude generatie en stale publication fence zijn daarna reversibel gearchiveerd, zonder current.json handmatig groen te zetten.
- De draaiende 57-controller reconstrueerde vervolgens zelf de canonieke 32.4.57 lifecycle naar `COMPLETE` en runtime `IDLE`; Incoming en Processing zijn leeg.
- De recovery-build bevat extra evidence-bound pre-activation self-recovery zodat deze foutklasse vanaf 58 niet opnieuw handmatig hoeft te worden losgemaakt.
- Het eerdere artifact SHA `c98c0806...` en het tussentijdse artifact SHA `5419ba...` zijn vervallen en mogen niet opnieuw worden aangeboden.

## Eerstvolgende harde gates
1. Revised metadata/manifest deterministisch regenereren en nieuw final ZIP bouwen.
2. ZIP-integriteit + MANIFEST.sha256 + SHA256SUMS.json bewijzen.
3. Exact revised artifact fresh-extracten en volledige 1.955-testcollectie GREEN sluiten.
4. Exact revised 58 artifact opnieuw via Incoming laten lopen.
5. COMPLETE vereist exact GitHub target, HA runtime 32.4.58, processed exact artifact, lege Incoming/Processing en blijvend levende 58-controller klaar voor 59 zonder restart/script/state-reset.
6. Daarna als laatste steady-state bewijs controleren dat controller `IDLE` blijft en 59 zonder restart/script/state-reset kan worden aangeboden.
