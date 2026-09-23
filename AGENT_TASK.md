# AGENT_TASK — EnergieProject 32.4.64

- task_id: V64-RELEASE-CHAIN-CLOSURE-2026-09-23
- mode: DEVELOPMENT
- thinking: MEDIUM
- owner: ChatGPT/Spock
- step: 1/1
- production_authority: NO

## Doel
Maak 32.4.64 als complete afsluiting van de Incoming/GitHub/HA-releaseketen, zodat opvolgende releases geen nieuwe releaseketenreparaties nodig hebben.

## Scope
- echte V63-predecessorgrens als frozen fixture/contract bewijzen;
- 63→64: GitHub exact, uitsluitend `/store/reload`, geen update/install/rebuild;
- duurzame `WAITING_MANUAL_HA_UPDATE` zolang HA predecessor draait;
- Processing blijft owner tot GitHub exact + HA runtime exact;
- settlement naar Processed/COMPLETE exact één keer;
- N+1-proef: V64 als predecessor naar synthetische V65;
- crash/restart/idempotency rond PUBLISHING, manual-wait, archive en COMPLETE;
- oude releasepaden actief uitsluiten;
- release acceptance en host-capability Platform Qualification expliciet scheiden.

## Niet wijzigen
- geen tweede publisher/controller/watcher;
- geen automatische Home Assistant update/install/rebuild;
- geen cleanup/CR/mode als releasegate;
- geen productie/NAS/HA/Incoming actie.

## Acceptatie
- gerichte releaseketenregressies GREEN;
- bredere release-auditregressies GREEN;
- source + exact fresh-extract;
- canonical ZIP, CRC, manifest, SHA256SUMS en release-identiteit GREEN;
- finale onafhankelijke artifact-audit op exact SHA;
- geen wijziging na finale audit.

## Stop
V64_READY_FOR_INCOMING of echte safety/artifact blocker.
