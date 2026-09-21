# AGENTS.md — EnergieProject

Status: bindende agent-startinstructie voor ChatGPT Work en Codex.

## Verplichte startvolgorde
Lees vóór analyse, codewijziging, test, packaging, cleanup of releaseactie:
1. PROJECT_CONSTITUTION.md
2. CURRENT_HANDOVER.md
3. WORK_LEDGER.md
4. AGENT_TASK.md
5. WORK_KNOWLEDGE_BOOTSTRAP.md

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

## Coördinatie-sanity-check
- Vóór iedere overdracht naar Work of Codex controleert Spock/Chat de volledige actieve AGENT_TASK op interne tegenspraken tussen doel, fasevolgorde, scope, required_tests en stop_conditions.
- Een ontbrekende capability die in de actuele fase juist gebouwd/geïmplementeerd moet worden, mag NIET tegelijk als stopcriterium voor diezelfde fase gelden.
- Elke fase bevat expliciete preconditions: een vervolgfase mag pas starten nadat de vorige fase aantoonbaar en persistent GREEN is.
- Bij een blocker wordt eerst vastgesteld of het een echte technische/safety blocker is of een fout/tegenstrijdigheid in de taakdefinitie.
- Na elke taakwijziging volgt read-back van de effectieve AGENT_TASK voordat Work/Codex opnieuw wordt gestart.
- Reeds bewezen werk wordt niet opnieuw uitgevoerd door een coördinatiefout.


## Autonome doorwerkregel
- Work/Codex-runs stoppen niet voor gewone voortgangsrapportage, checkpointing of een ontbrekende capability die juist binnen de actieve taak gebouwd moet worden.
- Een checkpoint is persistente opslag, geen stopmoment.
- Na iedere geslaagde substap gaat de agent automatisch door naar de volgende substap.
- Stop alleen bij: expliciet vereiste protected-action approval, aantoonbare scope/safety blocker, model-policy blocker, ontbrekende harde bron/artifact die niet uit bestaande toegestane bronnen kan worden verkregen, of fase COMPLETE.
- "Niet geïnstalleerd" is geen blocker wanneer de actieve taak precies is om die capability te implementeren.
- Voor iedere BLOCKED-uitkomst voert de agent eerst een contradiction/self-causation check uit: als de blokkade door AGENT_TASK/AGENTS-formulering zelf ontstaat, corrigeert hij de interpretatie binnen doel en safety boundaries en gaat door.
- Peter is nooit de technische transportlaag tussen Chat, Work en Codex.


## Stille autonome uitvoer — bindend
- Gebruikerscommunicatie is GEEN tussenstap in development, testing, audit, build of live-observatie.
- Spock/Chat bereidt eerst alle analyse, scope, bronnen, checkpoints, acceptatiecriteria en uitvoercontracten volledig voor voordat Work wordt ingeschakeld.
- Na overdracht is Work uitvoeringsowner en blijft Work doorwerken; Work delegeert codeproblemen zelfstandig aan Codex binnen de actieve scope en neemt het resultaat daarna terug over.
- Peter krijgt GEEN voortgangscommentaar, checkpointmelding, "ik ga nu...", "verder?", tussenresultaat of herhaalde statusvraag.
- Persistente checkpoints gaan naar AGENT_RESULT/WORK_LEDGER/CURRENT_HANDOVER zonder de run te beëindigen en zonder Peter als transportlaag.
- Een agent mag niet stoppen op "taak aangemaakt", "handoff klaar", "wacht op Work", "wacht op Codex", "kan nog verder", of een capability/codegebrek dat binnen de actieve taak gerepareerd mag worden.
- Bij een oplosbare test/codefout: Work -> Codex (Terra/Medium) -> fix -> regressie -> Work hervat automatisch.
- Bij een omgevingsprobleem: eerst aantonen dat het werkelijk buiten de toegestane Work/Codex-omgeving ligt en geen instructie-/harnessprobleem is; pas daarna BLOCKED.
- Peter wordt alleen geroepen bij:
  1. een echte beschermde productieactie waarvoor expliciete toestemming contractueel vereist is;
  2. een echte onoplosbare scope/safety/artifact/model-blocker;
  3. definitief eindresultaat/acceptatie.
- Zodra Peter een exact beschermde actie goedkeurt, geldt die toestemming voor de volledige vooraf omschreven bounded keten; niet na iedere substap opnieuw vragen.
- Na protected approval voert Work de gehele goedgekeurde keten uit en observeert tot terminale GREEN/COMPLETE of een echte blocker. Geen tussentijdse commentaren.

## Dubbele eind-audit voor releases
- Een releasekandidaat is nog NIET klaar voor Peter zodra build/tests alleen GREEN zijn.
- Eerst voert Work zijn eigen acceptance/self-audit uit op bron, regressies, full-suite, artifact, fresh-extract en release-identiteit.
- Daarna voert Spock een onafhankelijke grondige audit uit op diff/scope, regressiedekking, release-architectuur, artifact-identiteit, fresh-extract, Incoming/ReleaseController/GitHub/HA-contract en bootstrapplan.
- Daarna voert Codex exact één onafhankelijke bounded audit uit met Terra/Medium, mits geen door UI/Peter gemelde budgetgrens dit volgens Usage Guard verbiedt. Codex wijzigt niets tijdens audit zonder concrete bevinding; bij een echte bevinding gaat die terug naar Work voor fix -> retest -> re-audit.
- Als geen laag-budgetsignaal bestaat, wordt de Codex-audit uitgevoerd; quota worden niet vooraf verbrand aan brede duplicatieve reviews.
- Peter wordt pas benaderd nadat alle beschikbare verplichte audits GREEN zijn en het exacte artifact-SHA vaststaat.

## Knowledge Base retrieval — verplicht voor Work
- Voor grote release-/architectuurtaken inventariseert Work eerst de canonieke Knowledge Base volgens `WORK_KNOWLEDGE_BOOTSTRAP.md`.
- Alleen CURRENT_HANDOVER/WORK_LEDGER lezen is onvoldoende wanneer Development_Lessons, HARD_REQUIREMENT, ADR of architecture-audit relevant kan zijn.
- Work leest eerst `Knowledge_Base_Master_Index.md` en `00_DEVELOPMENT_MANIFEST.md`, maakt daarna één taakgerichte readset en gebruikt die als ontwerp-/regressieconstraint.
- De volledige KB wordt niet bij iedere substap opnieuw gelezen; één inventaris + gerichte retrieval voorkomt token-/tijdverspilling.
- Als NAS-readback tijdelijk niet beschikbaar is, mag Work niet doen alsof de canonieke KB is gelezen. Het legt exact vast welke bronreadback nog ontbreekt vóór definitieve architectuur/release-acceptatie.


## Tijdelijke GitHub Full Access — extra veiligheidscontrole
- GitHub staat tijdelijk op `Allow all actions` uitsluitend voor de actieve 32.4.60-ontwikkeling en stabilisatie.
- Vóór iedere GitHub-schrijfactie voert Spock/Work/Codex twee controles uit:
  1. pre-write: juiste repository, branch/ref, doelbestand(en), actuele SHA/base, scope en beoogde wijziging controleren; geen bredere write dan nodig;
  2. post-write: exact commit-/contentresultaat teruglezen en controleren op onverwachte bestanden, branch, scope of side-effects.
- Bij twijfel over target, branch, scope, merge, delete, force/update of beschermde release-/productiegrens: niet schrijven totdat de ambiguïteit is opgelost.
- `Allow all actions` is geen verruiming van productie-, NAS-, HA-, restart- of releaseautoriteit.
- Na aantoonbaar live COMPLETE van 32.4.60 moet GitHub terug naar `Use my default` / normale `Allow low-risk actions`.
