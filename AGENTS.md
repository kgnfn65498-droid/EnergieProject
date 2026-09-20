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
