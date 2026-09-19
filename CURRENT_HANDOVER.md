# CURRENT HANDOVER — EnergieProject 32.4.57

Datum: 2026-09-18
Status: ARCHITECTURE-FIRST OVERLAY GEHARDEND T/M CHECKPOINT 16; PRODUCTIE NOG 32.4.56

## Nieuwe-chat / crash-resume
Lees eerst:
1. PROJECT_CONSTITUTION.md
2. CURRENT_HANDOVER.md
3. WORK_LEDGER.md
4. hoogste relevante checkpoint en later gewijzigde staging-evidence

Als Peter zegt “opnieuw”, “verder na crash” of equivalent: eerst persistente state/checkpoints lezen en vanaf het hoogste werkelijk opgeslagen punt hervatten. Geen bewezen onderzoek of bouwstappen opnieuw doen zonder nieuw bewijs.

Laatste bewezen checkpoint:
Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_16_2026-09-19.md

Belangrijk: checkpointnummer alleen is niet voldoende. Controleer altijd ook stagingbestanden met een latere modified timestamp.

## Bindende volgorde
1. Sluit live 32.4.56 minimaal en veilig.
2. Bouw/test 32.4.57 vanaf de canonieke 32.4.56 ZIP.
3. Installeer 32.4.57 via de bestaande Incoming-route.
4. Geen nieuwe rescueketen.

## Live 32.4.56 blocker
- transition generation f08ccc1bf56cbb5d20f841329c870bdc
- phase NATIVE_RUNTIME_CURRENT / WAITING_RESULT
- bestaande native_mcp_reload protected action PENDING
- Native MCP guard RELOAD_REQUIRED
- atomic LIVE_ACCEPTANCE
- release hold actief

Geen tweede command/decision aanmaken. Geen state fabriceren.

## 32.4.57 doelarchitectuur
Één ReleaseController met persisted waarheid:
Inbox/release_controller/current.json

Fasen:
DETECTED -> VERIFIED -> INSTALLING -> INSTALLED -> RUNTIME_ALIGNING -> VERIFYING -> ACCEPTED -> COMPLETE

Status:
ACTIVE / WAITING / BLOCKED / COMPLETE / ROLLED_BACK

Geen release-critical afhankelijkheid van:
- operating mode;
- release_validation_hold;
- oude 14-fasen release_transition;
- Project CR / NAS CR;
- CLEARUP/hygiene;
- PM FINAL/self-audit;
- watcher contract/heartbeat;
- CommandIngress clean;
- stale PM tasks.

## Behouden primitives
- atomic_app_swap.py;
- manifest/hash/ZIP-integriteit;
- Control Plane uitsluitend als allowlisted actuator;
- Native MCP fingerprint + directe readback;
- bestaande GitHub publisher;
- processed release-archief.

## 56 -> 57 migratie
De eerste 57-installatie wordt nog door de 56-installer uitgevoerd.
Legacy adoption is exact en éénmalig:
- from_version exact 32.4.56;
- App/VERSIE exact 32.4.57;
- atomic journal exact LIVE_ACCEPTANCE of ACCEPTED naar 32.4.57;
- artifact SHA geldig;
- canonieke processed ZIP bestaat en SHA exact matcht;
- Incoming en Processing niet ambigu;
- symlink/non-regular atomic authority wordt niet geaccepteerd.

32.4.58+ mag nooit opnieuw legacy transition/hold als lifecycleauthority adopteren.
Oude transition/hold mogen bij 56->57 alleen als historische evidence worden gezien en worden niet gespiegeld.

## Runtime-/crash-hardening
- canonical StateStore weigert symlink/non-regular/corrupte state;
- DETECTED is observationeel; eerste persistente lifecycle-state is VERIFIED;
- INSTALLING wordt persistent vóór atomic install side effect;
- RUNTIME_ALIGNING wordt persistent vóór release-scoped Native-MCP request;
- Control Plane wordt alleen on-demand voorbereid wanneer Native runtime mismatch dit werkelijk vereist;
- stale Control-Plane heartbeat is geen gate als Docker healthy en loaded fingerprint exact is;
- PM-health behandelt stale/missing CP-heartbeat bij 57+ als ORANGE observability; echte loaded fingerprint mismatch blijft RED;
- echte CP fingerprint mismatch gebruikt uitsluitend één bounded restart van de bestaande energie-control-plane per expected fingerprint, geen recreateketen;
- Native MCP restart is attempt-fenced: één exact request_id kan maximaal één automatische restart veroorzaken; daarna uitsluitend readback/reconcile;
- Native MCP reconcile valideert opnieuw actuele release_id/generation/artifact/version/fingerprint voordat GREEN mogelijk is;
- Native MCP reload blijft exact release_id/generation/artifact/version/fingerprint-fenced;
- één exact Native-MCP request_id kan maximaal één automatische restart veroorzaken; daarna alleen readback/reconcile;
- een gefencede RED wordt native_mcp_reload_unproven BLOCKED en opent geen tweede side effect;
- na atomic ACCEPTED kan een crash vóór controller-save idempotent hervatten; een reeds ACCEPTED App wordt niet teruggerold;
- pre-activation rollback verwijdert uitsluitend de exact eigen candidate en zet PREPARED duurzaam op ROLLED_BACK;
- orphan Processing en stabiel corrupte Incoming worden bounded binnen dezelfde controller gereconcilieerd/gequarantaineerd;
- HA delivery is idempotent; WAITING veroorzaakt geen rollback;
- na atomic ACCEPTED kan delivery nooit de App rollbacken;
- na COMPLETE van N+1 re-exec't de controller exact de watcher uit de geaccepteerde App;
- Control-Plane source-sync evidence staat canoniek onder Inbox/release_controller/control_plane_source_sync.json, niet onder een historische versienaam;
- legacy ownership index wordt éénmaal streaming geladen per migratie/indexinstantie.

## Historische regressies
Pre-57 implementation fixtures omvatten:
- release_installer.sh
- release_preflight.py
- release_watcher.sh
- mode_entrypoint.py
- control_plane.py
- control_plane_runtime_guard.py
- qnap_control_plane_bootstrap.py
- embedded_pm_runtime_guard.py

Historische testfamilies blijven bestaan; implementatiegebonden verwachtingen worden tegen deze fixtures bewezen, niet tegen de 57-runtime waar orchestrators bewust retired zijn.

## Staging
Definitieve overlay:
Data/03_Systeem/Projectmanager/Staging/32457_release_overlay/

Buildgate:
Data/03_Systeem/Projectmanager/Staging/32457_release_overlay/BUILD_32457.py

Canonieke buildbasis:
Inbox/processed/EnergieProject_v32.4.56.zip
size=5657772
verwachte SHA256:
e3bc19550c3116ace3a862aa837b6077d47ff2e4a912820db419b3a0470c5f61

## Test- en dekkingsbewijs
Ouder uitgevoerd bewijs:
- architectuur/prototype: 34/34 GREEN;
- controller/service: 10/10 GREEN;
- atomic pre-reconciled rollback: 2/2 GREEN;
- verplichte architectuurset vóór laatste hardening: 15/15 GREEN.

Definitieve overlay structureel:
- 12/12 live defectclusters gemapt;
- 11/11 historische contractfamilies gemapt;
- 15/15 verplichte 32.4.57 acceptatiecases aanwezig;
- 1 extra next-release-herhaaltest aanwezig;
- 36 specifieke 32.4.57 architectuurtests aanwezig;
- aanvullende 32.4.55 orphan/corrupt Incoming regressies aanwezig.

De checkpoint-11 delta is nog NIET uitgevoerd met pytest.
Volledige overlay/fresh-extract suite is nog NIET uitgevoerd met de canonieke ZIP en mag niet als GREEN worden gerapporteerd.
Echte NAS/HA live E2E blijft daarna apart verplicht.

Coverage-matrix:
Data/03_Systeem/Projectmanager/Worklogs/2026-09-18_32457_PROBLEM_REGRESSION_COVERAGE_MATRIX.md

## Eerstvolgende uitvoer
1. Ontwerp/implementeer eerst de smalle evidence-bound 32.4.56 -> 32.4.57 legacy-transition finalize/supersede brug uit checkpoint 16 + TDD; geen directe state-edit, geen tweede Native request en geen oude CR/CLEARUP/hygiene keten opnieuw afspelen.
2. Checkpoint + CURRENT_HANDOVER + WORK_LEDGER opslaan.
3. Daarna BUILD_32457.py uitvoeren in een geïsoleerde omgeving die de canonieke NAS-ZIP binary kan lezen en pytest kan draaien.
4. full overlay pytest GREEN.
5. artifact bouwen + exacte manifest/SHA256SUMS.
6. exact artifact fresh-extract pytest GREEN.
7. pas daarna EnergieProject_v32.4.57.zip als kandidaat opleveren.
8. productieinstallatie alleen na expliciete autorisatie.

Huidige chattooling kan stagingtekst en NAS-metadata lezen/schrijven, maar niet de binaire canonieke ZIP openen of pytest/build op NAS uitvoeren. Niet omzeilen met rescue- of reconstructieroute.

## Verboden
- geen productie-write vanuit ontwikkelstaging;
- geen tweede release transition/hold;
- geen release_recover/rescueketen;
- geen mode/CR/CLEARUP als releasegate;
- geen kandidaat-ZIP vóór full suite + fresh-extract GREEN.


## Checkpoint 12 — 2026-09-19
- Laatste worklog: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_12_2026-09-19.md
- NativeRuntimeCoordinator ruimt nu een achtergebleven Native reload-request alleen op bij exact release/generation/artifact/version/fingerprint-fence.
- Nieuwe regressietest toegevoegd; specifieke 57-architectuurtests nu 37 aanwezig (nog niet uitgevoerd als volledige pytest-run).
- PM/orchestrator audit: >=32.4.57 is Incoming CONTROLLER_OWNED; oude validation/mode-route is geen release-authority.
- OPEN vóór release-seal: vastgelegde architectuur plaatst GitHub/HA in RUNTIME_ALIGNING vóór ACCEPTED, huidige staging doet HA-delivery na atomic ACCEPTED. Niet stilzwijgend wijzigen; eerst resterende vragen/tests en gekozen simpele contractvolgorde vastleggen.
- Gebruiker wil 57 nog niet definitief releaseklaar maken voordat extra vragen/tests zijn behandeld.


## Checkpoint 13 — 2026-09-19
- Worklog: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_13_2026-09-19.md
- HA/ACCEPTED-volgorde herbeoordeeld: latere checkpoints 5/6 bepalen atomic ACCEPTED eerst, daarna GitHub/HA delivery; COMPLETE pas bij exact HA target. Geen fase-herarchitectuur.
- Oude pm-startup-recovery thread verwijderd uit 57 mode_entrypoint omdat PM niet releasekritiek is en deze thread zelfstandig Supervisor restart kon aanvragen.
- Historische pre-57 fixture blijft behouden; nieuwe architectuurtest toegevoegd.
- Specifieke test_32457_* architectuurtests aanwezig: 38 (nog niet volledige pytest-run uitgevoerd).
- Open vóór publicatie: 56->57 HA bootstrap exact bewijzen/minimaal sluiten; build/full pytest/fresh-extract; daarna live Incoming->COMPLETE.
- Werkwijze: regelmatig checkpointen en chatlengte/handover actief bewaken.


## Checkpoint 14 — 2026-09-19
- Worklog: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_14_2026-09-19.md
- Live 56 read-only bevestigd: bestaande HA publisher consumeert ha_publication_required, publiceert GitHub, doet /addons/reload + /addons/self/rebuild.
- KISS: geen extra HA release-daemon toegevoegd; bestaande 56->57 publisher/rebuild handover hergebruiken.
- Nieuwe architectuurtest toegevoegd; 39 specifieke test_32457_* architectuurtests aanwezig (nog geen volledige pytest-run).
- Resterend voor publicatie: build tegen canonieke 56 ZIP, full pytest, fresh-extract regressie, daarna live Incoming->COMPLETE.


## Checkpoint 15 — 2026-09-19
- Worklog: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_15_2026-09-19.md
- Kritiek bewezen: live 56 watcher weigert een eerste 57 ZIP zolang atomic 56 LIVE_ACCEPTANCE is; live 56 preflight eist daarnaast terminal transition + settled hold + diverse legacy healthgates.
- Actuele transition blijft NATIVE_RUNTIME_CURRENT generation f08ccc1bf56cbb5d20f841329c870bdc, decision PENDING.
- Dit is eenmalige 56->57 bootstrap/migratie, NIET opnemen in 57 steady-state architectuur.
- Volgende gate: uitsluitend bestaande 56 terminal/supersede/cancel-route onderzoeken; geen productie-mutatie.


## Checkpoint 16 — 2026-09-19
- Worklog: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_16_2026-09-19.md
- Na crash eerst hoogste persisted checkpoint gecontroleerd: checkpoint 15 was laatste inhoudelijke stand; geen nieuwere broncode.
- release_recover sluit 56 transition niet; CANCELLED wordt alleen herkend maar er is geen veilige coordinator cancel/supersede API.
- attempt_release_hold kan 56 atomic/hold veilig sluiten op compacte App/PM/runtime-validatie; Native/CR/CLEARUP/hygiene zijn daar geen directe blockers.
- Geen actieve release-owned tasks meer voor 32.4.54/55/56.
- Exact open punt: ontwerp kleinste evidence-bound 56->57 legacy-transition supersede/finalize brug. Geen directe state-edit, geen tweede Native request, geen oude CR/CLEARUP/hygiene keten herhalen.
- Staging blijft: 15/15 required tests + 39 specifieke test_32457_* architectuurtests aanwezig; nog geen volledige pytest/build GREEN na laatste wijzigingen.
- Canonieke base: Inbox/processed/EnergieProject_v32.4.56.zip; SHA256 e3bc19550c3116ace3a862aa837b6077d47ff2e4a912820db419b3a0470c5f61.
- Nieuwe chat moet eerst checkpoint16 + CURRENT_HANDOVER + WORK_LEDGER lezen en exact hier hervatten.


## Definitieve overdracht — 2026-09-19
Primaire nieuwe-chatstart:
Data/03_Systeem/Projectmanager/Worklogs/FINAL_HANDOVER_32.4.57_EXACT_RESUME_CHECKPOINT16_2026-09-19.md
SHA256: 8ca908ef8bd1b2ec7591c2beaf275b41ff7e0d07d7b57cabf70d6e4e1f5f5d48
Nieuwe chat: begin direct bij §10; geen brede heranalyse.


## Checkpoint 20 — 2026-09-19
- Worklog: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_20_2026-09-19.md
- Bindende eenvoudseis: één A->Z Incoming-keten; bestaande containers/watcher/publisher hergebruiken; dubbele/trippele release-authority niet behouden.
- DEVELOPMENT/MAINTENANCE/USER + Project CR/NAS CR/CLEARUP/hygiene blijven functioneel bestaan maar zijn geen algemene 57 steady-state releasegates; geen fake-GREEN.
- Staging helper legacy56_to_57_bootstrap.py + 12 TDD-regressies toegevoegd voor uitsluitend eenmalige 56->57 legacy terminalisatie.
- Helper maakt geen tweede Native request/restart en voert CR/CLEARUP/hygiene niet uit; 58+ wordt geweigerd.
- Nieuwe tests nog NIET uitgevoerd; geen pytest/build capability in huidige NAS-connector.
- Volgende gate: statische review, daarna full pytest/build/fresh-extract in uitvoerbare omgeving; productiebootstrap alleen na expliciete autorisatie.


## Checkpoint 21 — 2026-09-19
- Worklog: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_21_2026-09-19.md
- 56->57 helper gehard met exacte canonical SHA, phase/ticket fences, post-settlement atomic+hold readback en PREPARED->CANCELLED crash recovery.
- 14 gerichte nieuwe TDD-tests aanwezig; NIET uitgevoerd in huidige connector.
- 57 steady-state audit bevestigt: modes/hold/legacy transition/CR/CLEARUP/hygiene zijn geen controller/preflight/service gates; atomic install + release-scoped Native + bestaande GitHub/HA publication blijven noodzakelijke kern.
- Fysieke blokkade: geen pytest/build execution en geen binaire canonical ZIP export in huidige NAS connector.
- Exact vervolg: full pytest -> build exact 56 base -> fresh-extract pytest -> canonical 57 ZIP; pas daarna productiebootstrap met expliciete autorisatie.


## Checkpoint 22 — 2026-09-19
- Canonieke gebruiker-ZIP 32.4.56 lokaal bewezen: SHA256 e3bc19550c3116ace3a862aa837b6077d47ff2e4a912820db419b3a0470c5f61.
- Lokale 56 baseline suite foutloos door >65% tot tool-timeout; 2 bestaande skips, geen failures in dat traject. Niet als full GREEN tellen.
- Gerichte baseline batches daarna: 32.4.36-45 = 173 passed; 32.4.46-54 = 113 passed; resterende 32.4.55/56 batches tot nu toe allemaal GREEN (24 + 49 + 10 + 49 + 6 passed).
- 57 mode-isolatie opnieuw bevestigd: oude release-transition daemon en automatic release-hold worker starten niet meer; modes/CR blijven functioneel maar niet release-authority.
- Geen productieactie. NAS staging -> lokale build blijft zonder binary/export bridge; geen nieuwe transportinfrastructuur verzonnen.
- Worklog: Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTURE_32457_CHECKPOINT_22_2026-09-19.md
