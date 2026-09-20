# AGENTS.md — EnergieProject

Status: bindende agent-startinstructie voor ChatGPT Work en Codex.

## Verplichte startvolgorde
Lees vóór analyse, codewijziging, test, packaging, cleanup of releaseactie:
1. PROJECT_CONSTITUTION.md
2. CURRENT_HANDOVER.md
3. WORK_LEDGER.md
4. AGENT_TASK.md

PROJECT_CONSTITUTION.md is leidend bij conflict.

## Rollen
- ChatGPT / Spock: technische regie, scope, besluiten, acceptatievoorstel.
- Work: uitvoering en orchestratie van begrensde taken.
- Codex: codewerk alleen wanneer dat aantoonbaar nodig is en uitsluitend binnen de expliciete taakscope.
- Peter: besluitvormer en expliciete autoriteit voor beschermde acties; nooit menselijke transportlaag tussen agents/systemen.

## Verboden zonder expliciete autorisatie
- productie-installatie of productieplaatsing;
- restart/recreate/reboot van NAS, Home Assistant, containers of services;
- architectuurwijziging buiten AGENT_TASK.md;
- handmatige statefabricage of het op GREEN zetten van runtime/release-state;
- regressietests verwijderen of versoepelen om een build groen te krijgen;
- reeds bewezen onderzoek opnieuw uitvoeren zonder nieuw bewijs;
- aannemen dat python3 op de QNAP-host beschikbaar is of het daar installeren als shortcut;
- GitHub/reconstructie/productiecopy gebruiken als vervangende buildbasis wanneer de exacte voorganger-ZIP volgens het projectcontract verplicht is.

## Development Build Contract
Elke ontwikkeltaak bevat vóór implementatie:
- modus;
- denksetting MIDDEL of HOOG;
- Stap X/Y;
- doel en scope;
- expliciet niet wijzigen;
- bekende bewezen feiten;
- acceptatiecriteria;
- stopcriteria;
- productieautoriteit JA/NEE.

Ontbreekt dit, dan niet implementeren maar BLOCKED rapporteren.

## Crash- en hervatprotocol
Bij onderbreking, nieuwe sessie, "opnieuw" of "verder":
1. persistent state en bovenstaande vier bestanden lezen;
2. hoogste bewezen checkpoint bepalen;
3. exact daar hervatten;
4. bewezen onderzoek niet herhalen.

## Uitvoercontract
Resultaten worden teruggeschreven naar AGENT_RESULT.md en relevante duurzame bevindingen naar WORK_LEDGER.md.
Geen succesclaim zonder read-back/verificatie van de geschreven toestand.

## Codex model lock
- Verplicht model: `gpt-5.6-terra`.
- Verplicht reasoning-niveau: `medium`.
- Dit geldt ook voor plan mode en alle subagents.
- Codex mag NIET autonoom escaleren naar GPT-6 Astra, GPT-5.6 Sol of een ander model/reasoning-niveau.
- Als Terra + medium niet beschikbaar of niet afdwingbaar is: STOP en rapporteer `BLOCKED_MODEL_POLICY`; geen stille fallback.
- Vóór iedere Codex-codewijziging wordt de effectieve modelinstelling gecontroleerd waar de omgeving dit kan rapporteren.

## Usage Guard — session/week budget
- Standaard budgetmodus: CONSERVE.
- Work blijft op SOL-LIGHT; Codex blijft op gpt-5.6-terra + medium; geen model-escalatie of fallback.
- Work leest en analyseert alleen wat voor de actuele stap nodig is. Geen brede heranalyse of herlezing van reeds bewezen evidence zonder concrete nieuwe reden.
- Codex start uitsluitend wanneer codewijziging aantoonbaar nodig is; niet voor samenvatten, plannen of statusrapportage.
- Geen parallelle Codex/subagent-runs standaard. Maximaal één begrensde Codex-uitvoerlijn tegelijk; extra subagents alleen na expliciete autorisatie van Peter.
- Dezelfde PR-head/SHA wordt niet opnieuw volledig gereviewd wanneer voor exact die head al geldige persistente review-evidence bestaat.
- Na iedere betekenisvolle ontwikkelfase eerst een persistent checkpoint schrijven voordat een nieuwe grote fase start.
- Agents verzinnen geen resterende quota. Alleen UI- of door Peter gemelde session/week-percentages gelden als budgetsignaal.
- Zodra >=25% van een session/week-budget is verbruikt vóór betekenisvol codewerk: verscherpt CONSERVE; niet-noodzakelijke analyse, reviews en subagents stoppen en rechtstreeks naar de eerstvolgende bewezen stap.
- Bij <=50% resterend budget: geen nieuwe brede onderzoeksfase; slechts één strikt begrensde actieve taak tegelijk.
- Bij <=25% resterend budget: checkpoint en STOP vóór een nieuwe grote Work/Codex-fase, tenzij Peter expliciet toestemming geeft door te gaan.
- Credits of zwaardere modellen worden nooit automatisch ingezet om een budgetgrens te omzeilen.
- Budgetbesparing mag verplichte tests, releasegates of bewijsvoering nooit verzwakken; checkpoint en stop in plaats van gates overslaan.
