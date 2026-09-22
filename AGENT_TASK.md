# AGENT_TASK — EnergieProject 32.4.61

- task_id: V61-FAST-ROOT-CAUSE-2026-09-22
- mode: DEVELOPMENT
- thinking: MEDIUM
- owner: ChatGPT/Spock
- step: 1/1
- production_authority: NO

## Doel
Maak één minimale 32.4.61 die de bewezen V60 publisher/HA-delivery fout structureel oplost.

## Scope
- GitHub exact bewijs nooit terugdraaien door HA delivery/rebuild fout.
- Gebruik officiële Supervisor store update-route; geen `/addons/self/rebuild`.
- Delivery-status apart van `published/target_exact`.
- Exact GitHub + exact HA runtime mag controller settlement GREEN sluiten.
- Native opvolger gebruikt 9 fasen met PUBLISHING vóór INSTALLING.
- Geen nieuwe publisher/controller/watcher, cleanup of productieactie.

## Acceptatie
- gerichte regressies GREEN;
- release-identiteit 32.4.61 coherent;
- canonical ZIP + manifest/SHA/CRC/layout GREEN;
- exact fresh-extract gerichte regressies GREEN;
- finale onafhankelijke artifact-audit op exact ZIP-SHA;
- geen wijziging na finale audit.

## Stop
V61_READY_FOR_RELEASE_APPROVAL of echte safety/artifact blocker.
