# AGENT_TASK — EnergieProject 32.4.62

- task_id: V62-AUDIT-CLOSURE-AUTONOMOUS-SUCCESSOR-2026-09-22
- mode: DEVELOPMENT
- thinking: MEDIUM
- owner: ChatGPT/Spock
- production_authority: NO

## Doel
Maak 32.4.62 als schone opvolger van live 32.4.61 en neem de volledige V61-auditclosure op.

## Scope
- stale rebuild-regressies structureel vervangen door V61/V62 store-update invariant;
- exact failing Supervisor endpoint diagnosticeren;
- 61→62 pre-target bootstrap expliciet bewijzen vanuit predecessorpublisher;
- GitHub exact bewijs nooit terugdraaien door HA-deliveryfout;
- Processing blijft owner totdat GitHub exact + HA runtime exact zijn; pas dan Processed/COMPLETE;
- geen tweede publisher/controller/watcher en geen nieuwe releasegate.

## Acceptatie
- release-identiteit 32.4.62 coherent;
- gerichte en bredere release-regressies GREEN;
- canonical ZIP + manifest/SHA/CRC/layout GREEN;
- exact fresh-extract regressies GREEN;
- finale artifact-audit op exact SHA;
- geen productieactie tijdens build/audit.
