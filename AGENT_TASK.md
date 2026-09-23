# AGENT_TASK — EnergieProject 32.4.63

- task_id: V63-MANUAL-HA-UPDATE-BOUNDARY-2026-09-22
- mode: DEVELOPMENT
- thinking: MEDIUM
- owner: ChatGPT/Spock
- production_authority: NO

## Doel
Maak 32.4.63 als minimale opvolger van exact 32.4.62 met een expliciete duurzame wachtfase voor Peters handmatige Home Assistant add-onupdate.

## Scope
- na GitHub target-exact uitsluitend de Home Assistant store verversen;
- geen automatische Supervisor update/install/rebuild/self-info aanroepen;
- GitHub exact + HA predecessor-runtime is `WAITING_MANUAL_HA_UPDATE`;
- GitHub exact bewijs nooit terugdraaien door HA-deliveryfout;
- Processing blijft owner totdat GitHub exact + HA runtime exact zijn; pas dan Processed/COMPLETE;
- geen tweede publisher/controller/watcher en geen nieuwe releasegate.

## Acceptatie
- release-identiteit 32.4.63 coherent;
- gerichte en bredere release-regressies GREEN;
- canonical ZIP + manifest/SHA/CRC/layout GREEN;
- exact fresh-extract regressies GREEN;
- finale artifact-audit op exact SHA;
- geen productieactie tijdens build/audit.
