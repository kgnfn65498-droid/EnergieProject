# CURRENT HANDOVER — EnergieProject 32.4.67

Datum: 2026-09-23
Documentrol: statische release-handover voor artifact 32.4.67.

## Runtime-statusautoriteit
Dit document bevat geen mutable live-status. Actuele lifecycle/status komt uitsluitend uit:
- `Inbox/release_controller/current.json`;
- `Inbox/release_controller/runtime.json`;
- `Inbox/ha_runtime/current.json`;
- `Inbox/github_publication_state.json`.

## Exact predecessor 32.4.66
- artifact SHA256: `507ab36206578351621089c4c430caeb386b2005dbb637c9a9c8cfdeaa57107b`;
- frozen byte-exact executor-bronnen onder `tests/fixtures/v66_predecessor/`;
- exacte hashes staan in `tests/fixtures/v66_predecessor/PROVENANCE.json`;
- V65→V66 releaseketen live GREEN, maar V66-audit vond dat de nieuwe settlement-observability niet kon draaien tijdens 65→66 omdat de executor nog V65 was.

## 32.4.67 oplossing
- predecessor-boundary wordt expliciet gemodelleerd: 66→67 wordt door frozen V66-code uitgevoerd;
- na COMPLETE voert de actieve release altijd exact settlement-reconciliation uit via de productie-delivery-adapter;
- ontbrekende observability mag alleen worden aangevuld bij exact COMPLETE + App target + HA target + exact Processed artifact + exact GitHub identity/head + exact target-manifest + verplichte controller-evidence;
- reconciliation is atomair, idempotent en generation/release-fenced;
- stale/foreign settlementvelden zijn geen actuele Projectmanager-proof;
- manual HA update en `/store/reload`-only publisher blijven ongewijzigd.

## Releasecontract
`Incoming → Processing → GitHub exact → App target → ACCEPTED/WAITING_MANUAL_HA_UPDATE → handmatige HA-update → HA exact → predecessor/controller settlement → Processed → COMPLETE → actieve target-controller exact reconciliation → IDLE`.
