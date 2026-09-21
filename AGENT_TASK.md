# AGENT_TASK — EnergieProject

Status: ACTIVE
Schema: v1

- task_id: REPLACEMENT-32.4.60-COMBINED-CLOSURE-2026-09-21
- mode: DEVELOPMENT
- reasoning: HOOG
- work_model: SOL-LIGHT
- codex_model: gpt-5.6-terra
- codex_reasoning: medium
- max_parallel_codex_runs: 1
- owner: WORK_AUTONOMOUS
- step: BUILD_REAL_32.4.60
- release_target: 32.4.60
- publisher_fix_source_candidate: 33bea32534c5114aefe822afe252a6555bc55e58
- publisher_fix_bundle_sha256: 06793fc120d299e065b673578a16b52d71da4ab4e5c78de74d2fd1a9b07fd5e1
- resume_checkpoint: ca7c0b427359bb4563a0f8dffbdcce0c5f17d32e

## Besluit
De aparte 32.4.59 publisher-hotfix wordt NIET meer uitgebracht. De zojuist rejected 32.4.59 ZIP is afgesloten als verkeerde releasevorm: dezelfde versie als live 59 kan volgens de standaard preflight nooit installeren.

We keren terug naar het oorspronkelijke plan:
1. bouw EEN echte replacement 32.4.60 die zowel de publisher/Incoming-correctie als alle reeds vastgelegde 32.4.60-herstelpunten bevat;
2. gebruik daarna éénmalig de eerder afgesproken gecontroleerde Work + terminal bootstrap om 32.4.60 door de huidige 32.4.59-kip-ei grens te krijgen;
3. vanaf live 32.4.60 moet de normale Incoming -> ReleaseController -> GitHub -> HA keten weer autonoom werken zonder structurele terminalroute.

## Verplichte bronnen
Work leest eerst, zonder bewezen onderzoek te herhalen:
- op NAS: `Data/03_Systeem/Projectmanager/CURRENT_HANDOVER_32_4_60_WORK_CODEX.md`
- op NAS: `Data/03_Systeem/Projectmanager/WORK_LEDGER_32_4_60.md`
- complete rejected-60 evidence/checkpoints
- bundle/candidate `33bea32534c5114aefe822afe252a6555bc55e58` voor de reeds bewezen publisherfix + repository offline guard

## Wat uit 33bea325 verplicht in 60 moet zitten
De kandidaat 33bea325 is technisch GEEN volledige 60; hij staat nog op release-identiteit 32.4.59. Hij bevat wel bewezen noodzakelijke 60-onderdelen:
- expliciete ReleaseController `PUBLISHING` fase vóór INSTALLING;
- exact fenced pre-target GitHub publication vanuit Processing;
- release_id + generation + target version + artifact SHA + target-manifest SHA + predecessor identity;
- publisher verwijdert contract niet en verplaatst niets zelf naar Processed;
- HA delivery blijft exact fenced;
- repository-wide offline pytest guard + child-process propagation.
Deze wijzigingen worden onderdeel van de echte 32.4.60, niet van een aparte live 59-hotfix.

## Wat daarnaast uit het bestaande 32.4.60 checkpoint moet komen
Work moet alle reeds vastgelegde replacement-60 eisen en defectdekking uit de NAS handover/ledger toepassen. Geen reconstructie uit chat en geen nieuw architectuuronderzoek. Oude/rejected 60 artifacts zijn evidence, niet herbruikbare releaseartifact.

## Release-identiteit
De uiteindelijke artifact moet overal coherent 32.4.60 zijn:
- VERSIE.txt
- release_test_contract/current release identity
- Home Assistant add-on config version
- app/main identity
- mode entrypoint target release
- PM/release metadata waar contractueel vereist
- changelog/build-basis/manifest/SHA256SUMS
Geen 32.4.59 artifact mag opnieuw naar Incoming.

## Ontwikkel- en acceptatiepad
1. Load exact NAS 60 checkpoint + publisherfix bundle.
2. Combineer alleen bewezen noodzakelijke changes; klein/root-cause-first.
3. TDD/regressies voor alle defectfamilies uit 60 handover.
4. Volledige pytest suite in normale Work/Codex development runtime met offline guard.
5. Geen skip/xfail/delete/weaken om GREEN te krijgen.
6. Canonical release build voor 32.4.60.
7. Exact fresh-extract.
8. ZIP CRC + manifest + SHA256SUMS + release identity + root-layout + source/extract-equivalentie.
9. Fresh-extract regressies incl. Incoming/ReleaseController/PUBLISHING/GitHub/HA contract.
10. Produceer één kandidaat `EnergieProject_v32.4.60.zip` + changelog + korte instructie.
11. STOP bij `V60_READY_FOR_ONE_TIME_BOOTSTRAP_APPROVAL`.

## Eenmalige bootstrap — alleen voorbereiden, nog niet uitvoeren
De huidige live 32.4.59 kan een N+1 candidate niet zelf pre-target publiceren. Daarom mag de echte 60 NIET worden afgekeurd omdat 59 deze nieuwe 60-functie nog niet bezit.

Na kandidaat-GREEN wordt één exact gecontroleerd terminal/Work-bootstrapplan gebruikt, zoals eerder afgesproken:
- geen permanente alternatieve releaseketen;
- geen tweede publisher/lifecycle owner;
- geen handmatige state-fabricatie;
- alleen de minimale eenmalige stap die nodig is om exact geverifieerde 32.4.60 over de 59 bootstrapgrens te krijgen;
- daarna neemt de 32.4.60 ReleaseController/publisher de standaardketen over;
- elke terminalactie benoemt terminal, stap X/Y en exacte readback;
- maximaal drie terminalcommando's;
- geen host-python op QNAP;
- geen NAS/HA reboot;
- productie-uitvoering pas na één expliciete bootstrap-approval voor exact SHA256 van de GREEN 60 ZIP.

## Na live 60
Verplicht live bewijs:
`Incoming/claim -> Processing -> PUBLISHING exact -> INSTALLING -> INSTALLED -> RUNTIME_ALIGNING -> VERIFYING -> ACCEPTED -> Processed -> GitHub exact -> HA exact -> COMPLETE`.
Daarna moet een volgende release weer zonder terminal-bootstrap via Incoming kunnen lopen.

## Niet toegestaan
- aparte 32.4.59 publisher-hotfix opnieuw bouwen/installeren;
- rejected 32.4.59 ZIP opnieuw gebruiken;
- permanente platformtest/containerexecutor-route als releasevoorwaarde;
- nieuwe parallelle publisher;
- nieuwe lifecycle-owner;
- rechtenwijzigingen;
- handmatige JSON/state fabrication;
- Peter als technische transportlaag;
- tussentijds stoppen voor gewone commentaar/checkpoints.

## Stopvoorwaarden
Work werkt autonoom door tot:
- `V60_READY_FOR_ONE_TIME_BOOTSTRAP_APPROVAL`; of
- een echte code/artifact/safety blocker die niet door taaktekst of ontbrekende implementatie-instructie wordt veroorzaakt.


## Communicatie- en auditcontract voor deze 32.4.60
- SILENT_MODE=ON.
- Spock rondt vóór Work-handoff alle voorbereidende analyse/instructies af; daarna geen nieuwe ontwerpvragen aan Peter.
- Work is end-to-end uitvoeringsowner vanaf handoff tot `V60_READY_FOR_ONE_TIME_BOOTSTRAP_APPROVAL`.
- Code/testproblemen binnen scope worden door Work zelfstandig naar één Codex-lane Terra/Medium gestuurd, opgelost, opnieuw getest en door Work hervat.
- Work stopt niet voor gewone status, checkpoints, handoffs, "volgende stap", of omdat Codex klaar is.
- Voor Peter zichtbaar eindpunt vóór productie is pas bereikt na:
  1. full-suite GREEN;
  2. canonical build GREEN;
  3. exact fresh-extract GREEN;
  4. Work self-audit GREEN;
  5. Spock onafhankelijke grondige audit GREEN;
  6. één Codex onafhankelijke audit GREEN als Usage Guard dat toelaat;
  7. exact ZIP-SHA256 + bounded bootstrapplan vastgelegd.
- Bij een auditbevinding: terug naar Work/Codex fix-loop; Peter niet tussentijds informeren tenzij echte blocker.
- Daarna één compacte vraag aan Peter voor exact de bounded bootstrap van exact die ZIP/SHA.
- Na akkoord: Work voert de volledige eenmalige bootstrap uit en observeert zonder tussencommentaar tot live keten `Incoming/Processing/PUBLISHING/INSTALLING/INSTALLED/RUNTIME_ALIGNING/VERIFYING/ACCEPTED/Processed/GitHub/HA/COMPLETE` aantoonbaar GREEN is.
- Als live een codefout blijkt: Work legt evidence vast, Codex repareert binnen scope, Work retest/rebuildt; Peter wordt pas opnieuw benaderd wanneer een NIEUWE protected productieactie voor een gewijzigd artifact nodig is.

## Verplichte Knowledge Base preflight voor 32.4.60
Vóór verdere implementatie:
1. lees `WORK_KNOWLEDGE_BOOTSTRAP.md`;
2. inventariseer de canonieke Project-KB via `Knowledge_Base_Master_Index.md`;
3. inventariseer Projectmanager `Development_Lessons` via `00_DEVELOPMENT_MANIFEST.md`;
4. lees alle taakrelevante lessons/requirements/ADR/worklogs voor release, Incoming, publisher, RuntimeV2, permissions, control-plane, autonomie en 53/54/55/56 defectfamilies;
5. leg éénmalig de daadwerkelijk gelezen bronpaden + overgenomen constraints vast in WORK_LEDGER/AGENT_RESULT;
6. pas daarna code aan.
Dit is voorbereidend werk en GEEN stop-/commentaarmoment voor Peter.
