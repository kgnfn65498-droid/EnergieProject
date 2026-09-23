# CURRENT HANDOVER — EnergieProject 32.4.65

Datum: 2026-09-23
Status: DEVELOPMENT — consolidatie/hygiene opvolger van live bewezen 32.4.64.

## Live predecessor 32.4.64
- Exact artifact SHA256: `875939a6d2112b69cf0b6da37d6c36216c80494aec00bbd78fdf59c37ea6acce`.
- 63→64 live E2E is bewezen: GitHub exact, alleen `/store/reload`, `WAITING_MANUAL_HA_UPDATE`, handmatige HA-update, daarna automatisch `COMPLETE 9/9` en Processed.
- Geen overgangsbrug, publisher-state reparatie of automatische HA-update is onderdeel van de normale keten.

## 32.4.65 doel
- Geen nieuwe releaseketenarchitectuur.
- Consolideer documentatie en predecessor-provenance.
- Bind predecessor-tests aan een exact uit het V64-artifact gekopieerde `main.py`, inclusief artifact- en source-SHA.
- Houd Release Acceptance en Platform Qualification expliciet gescheiden.
- Bewijs V64→V65 en alvast V65→synthetische V66 volgens dezelfde handmatige HA-boundary.

## Releasecontract
`Incoming → Processing → GitHub exact → App target → ACCEPTED/WAITING_MANUAL_HA_UPDATE → handmatige HA-update → HA exact → settlement → Processed → COMPLETE`.

`Processing` betekent: release nog transactioneel in behandeling. `Processed` betekent: volledige release `COMPLETE`.

## Historie
Oude handover-inhoud is niet langer in dit actuele document ingebed. Historische besluiten/evidence blijven behouden in `WORK_LEDGER.md`, `CHANGELOG.md`, projectdocumentatie en de release-specifieke Projectmanager stagingmappen.
