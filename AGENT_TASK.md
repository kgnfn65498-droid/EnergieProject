# AGENT_TASK — EnergieProject 32.4.66

- task_id: V66-OBSERVABILITY-AND-HANDOVER-CLOSURE-2026-09-23
- mode: DEVELOPMENT
- thinking: MEDIUM
- owner: ChatGPT/Spock
- step: 1/1
- production_authority: NO

## Doel
Los de twee niet-blokkerende V65-auditbevindingen op zonder de live-bewezen releasearchitectuur te wijzigen.

## Scope
- CURRENT_HANDOVER state-neutraal maken; runtime JSON is statusautoriteit;
- shared GitHub publication state na controller-settlement expliciet bijwerken;
- legacy `publication_contract_removed` compatibel houden maar ondubbelzinnige settlementvelden toevoegen;
- runtime_sources laten rapporteren op expliciete controller-settlementtruth;
- release acceptance en host-capability Platform Qualification strikt gescheiden houden;
- exact V65 predecessor-artifact/source fixture en 65→66 regression;
- V66→synthetische V67 N+1 regression;
- manual-HA, Processing/Processed en single-owner invarianten behouden.

## Niet wijzigen
- geen automatische HA update/install/rebuild;
- geen tweede publisher/controller/watcher;
- geen transition bridge;
- geen cleanup/CR/mode releasegate;
- geen productie/NAS/HA/Incoming actie tijdens build/audit.

## Acceptatie
- settlement observability exact/idempotent en identity-fenced;
- statische handover bevat geen mutable live-statusclaim;
- release-regressies source + fresh extract GREEN;
- canonical ZIP/CRC/manifest/SHA256SUMS/identity GREEN;
- finale artifact-audit op exact SHA.
