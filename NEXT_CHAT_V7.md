# Nieuwe-chat overdracht — EnergieProject 32.4.43

Actuele ontwikkellijn: 32.4.43 runtime-contract closure, gebouwd vanaf de exact geverifieerde 32.4.42-ZIP.

## Wat 32.4.43 structureel oplost

- control-plane shared mailboxes en cross-UID permissions;
- release-owned CR commands zonder stale side effects;
- één fail-closed project-close state voor CR/CLEARUP;
- één FINAL cycle-generation voor status/heartbeat/handover/self-audit;
- statische KB-sync mag kritieke PM-finalisatie niet meer blokkeren;
- canonical DecisionQueue is approval truth;
- workflowhealth en Projectmanager/releasehealth zijn gescheiden;
- CR-hotfix geeft predicate-voor-predicate bewijs.

## Werkwijze

Audit/root cause → TDD RED → GREEN → relevante regressie → volledige test → canonieke ZIP → fresh-extract audit → kritieke tests herhalen. Productie blijft beschermd en vereist expliciete goedkeuring.

Nieuwe chat: lees RuntimeV2-handover, Development Build Contract en Unified Development Ledger vóór ontwikkelwerk.
