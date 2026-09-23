# CURRENT HANDOVER — EnergieProject 32.4.66

Datum: 2026-09-23
Documentrol: statische release-handover voor artifact 32.4.66.

## Runtime-statusautoriteit
Dit bestand bevat **geen mutable live-status** zoals DEVELOPMENT, WAITING of COMPLETE. Na installatie kan zo'n statische tekst verouderen zonder dat het artifact gewijzigd mag worden.

De actuele status komt uitsluitend uit:
- `Inbox/release_controller/current.json` — lifecycle/status/step/release identity;
- `Inbox/release_controller/runtime.json` — actuele controller-runtime;
- `Inbox/ha_runtime/current.json` — actuele HA runtimeversie;
- `Inbox/github_publication_state.json` — GitHub-publicatie en controller-settlementobservability.

## Exact predecessor 32.4.65
- artifact SHA256: `e00a7fc0dfc81d3dfe7dbac6bac3cef213a987f207ad4d0d62588450b0bc9152`;
- predecessor `main.py` SHA256: `35814b8555f2d50078ba9fcb77324b76a635530ce31f79cd1585b63463df018c`;
- frozen byte-exact source: `tests/fixtures/v65_predecessor/main.py`;
- V64→V65 live E2E is GREEN: GitHub exact, alleen `/store/reload`, handmatige HA-update, daarna automatisch COMPLETE en Processed.

## 32.4.66 doel
- los de twee V65-audit hygiene-bevindingen op zonder nieuwe releasearchitectuur;
- maak CURRENT_HANDOVER intrinsiek niet-verouderend door live status naar runtime-evidence te verwijzen;
- maak publicatiecontractobservability ondubbelzinnig: publisher opent contract, ReleaseController markeert exact settlement;
- behoud compatibilityveld `publication_contract_removed`, maar voeg expliciete `publication_contract_settled`, `publication_contract_active` en `contract_settled_by` toe;
- bewijs V65→V66 met exact predecessor-source en V66→synthetische V67.

## Releasecontract
`Incoming → Processing → GitHub exact → App target → ACCEPTED/WAITING_MANUAL_HA_UPDATE → handmatige HA-update → HA exact → controller settlement → Processed → COMPLETE`.

`Processing` = transactioneel in behandeling. `Processed` = volledige release COMPLETE.
