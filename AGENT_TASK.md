# AGENT_TASK — EnergieProject 32.4.67

- task_id: V67-COMPLETE-SETTLEMENT-RECONCILIATION-2026-09-23
- mode: DEVELOPMENT
- thinking: MEDIUM
- owner: ChatGPT/Spock
- step: 1/1
- production_authority: NO

## Doel
Los de V66 live-auditfout volledig op: settlement-observability moet ook na predecessor-COMPLETE exact, self-healing, idempotent en generation-fenced zijn, zonder nieuwe lifecycle-owner of automatische HA-update.

## Scope
- exact V66 predecessor-artifact/source als frozen executor-fixture;
- 66→67 testen met echte V66 executor-boundary;
- COMPLETE reconciliation altijd via de productie-delivery-adapter uitvoeren, ook zonder contractmarker;
- ontbrekende settlement-observability alleen backfillen bij exact COMPLETE/App/HA/Processed/GitHub/manifest/evidence-bewijs;
- atomair/idempotent settlementvelden normaliseren;
- foreign/mismatched/ambiguous evidence fail-closed;
- Projectmanager settlement-status generation/release-fenced maken;
- crash/restart/idempotency en negatieve matrix testen;
- V67→synthetische V68 N+1-regressie.

## Niet wijzigen
- geen automatische Home Assistant update/install/rebuild;
- geen tweede publisher/controller/watcher;
- geen transition bridge;
- geen CR/CLEARUP/mode releasegate;
- Processing/Processed-semantiek niet versoepelen;
- geen productie/NAS/HA/Incoming actie tijdens build/audit.

## Acceptatie
- exact V66 predecessor-provenance cryptografisch bewezen;
- echte V66-executor 66→67 simulatie GREEN;
- marker-loze COMPLETE self-heal GREEN en idempotent;
- negatieve identity/fencing matrix GREEN;
- oude releaseketenregressies GREEN;
- observability/runtime_sources regressies GREEN;
- host-capability Platform Qualification apart gerapporteerd;
- source + exact fresh-extract GREEN;
- canonical ZIP/CRC/MANIFEST/SHA256SUMS/release-identiteit GREEN;
- finale onafhankelijke artifact-audit op exact SHA.
