# AGENT_TASK — EnergieProject 32.4.65

- task_id: V65-CONSOLIDATION-AND-PROVENANCE-2026-09-23
- mode: DEVELOPMENT
- thinking: MEDIUM
- owner: ChatGPT/Spock
- step: 1/1
- production_authority: NO

## Doel
Maak 32.4.65 als consolidatie-/hygienerelease bovenop exact V64, zonder nieuwe releaseketenarchitectuur.

## Scope
- CURRENT_HANDOVER terugbrengen tot één actuele status;
- predecessor-provenance verbeteren: exact V64 `main.py` als frozen fixture plus artifact/source SHA;
- V64→V65 predecessor-boundary testen met die exacte fixture;
- V65→synthetische V66 N+1-regressie;
- release acceptance en host-capability Platform Qualification verder expliciteren;
- bestaande Processing/Processed- en manual-HA-semantiek ongewijzigd behouden.

## Niet wijzigen
- geen tweede publisher/controller/watcher;
- geen automatische Home Assistant update/install/rebuild;
- geen transition bridge;
- geen cleanup/CR/mode als releasegate;
- geen productie/NAS/HA/Incoming actie tijdens build/audit.

## Acceptatie
- exacte V64 predecessor-source fixture cryptografisch gebonden;
- gerichte V65 regressies GREEN;
- moderne release-regressies GREEN;
- source + exact fresh-extract;
- canonical ZIP, CRC, manifest, SHA256SUMS en release-identiteit GREEN;
- finale onafhankelijke artifact-audit op exact SHA;
- geen wijziging na finale audit.

## Stop
V65_READY_FOR_INCOMING of echte safety/artifact blocker.
