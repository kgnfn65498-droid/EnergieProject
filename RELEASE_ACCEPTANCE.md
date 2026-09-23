# Release Acceptance — 32.4.67

Verplicht:
- exact V66 artifact SHA `507ab36206578351621089c4c430caeb386b2005dbb637c9a9c8cfdeaa57107b`;
- byte-exact V66 executor-fixtures met provenance-hashes;
- V66 publisher naar V67 gebruikt alleen `/store/reload`;
- geen automatische HA update/install/rebuild;
- V66 executor bewijst WAITING_MANUAL_HA_UPDATE terwijl HA=66 en settlement wanneer HA=67;
- COMPLETE reconciliation werkt ook wanneer `ha_publication_required.json` al ontbreekt;
- backfill vereist exact COMPLETE, App/HA target, exact Processed hash, exact GitHub release/generation/artifact/manifest/head en verplichte controller-evidence;
- backfill zet atomair/idempotent `publication_contract_removed=true`, `publication_contract_settled=true`, `publication_contract_active=false`, `contract_settled_by=release_controller`, exact `settled_release_id` en `settled_generation`;
- identity mismatch/foreign marker/malformed evidence blijft fail-closed zonder artifact-mutatie;
- Projectmanager accepteert expliciete settlement alleen wanneer release_id/generation/version overeenkomen met huidige COMPLETE state;
- V67→synthetische V68 N+1 contract GREEN.

Platform Qualification blijft apart; repository-wide full-suite GREEN wordt niet geclaimd als bekende restricted-host beperkingen reproduceren.
