# WORK_KNOWLEDGE_BOOTSTRAP.md — EnergieProject

Status: bindende retrieval- en ontwikkelcontext voor Work en Codex.

## Doel
Work gebruikt niet alleen de actuele handover, maar ook de opgebouwde projectkennis, zodat eerder bewezen fouten, mislukte ontwikkelpaden en architectuurlessen niet opnieuw worden uitgevonden.

Deze file kopieert de Knowledge Base niet. Hij bepaalt welke canonieke bronnen eerst worden geïnventariseerd en hoe historische kennis wordt gebruikt zonder oude status als actuele waarheid te behandelen.

## Canonieke kennislagen

### A. Project Knowledge Base
Root:
`Data/02_Output/Rapportages/KnowledgeBase/`

Inventariseer minimaal, indien aanwezig:
- `Knowledge_Base_Master_Index.md`
- `ACTUELE_STATUS.md`
- `Knowledge_Base.md`
- `Knowledge_Base_Besluiten_ADR.md`
- `Knowledge_Base_Projectgeschiedenis.md`
- `Knowledge_Base_Feature_Catalogus.md`
- `Knowledge_Base_Wijzigingslog.md`
- `Knowledge_Base_Chat_Bronregister.md`
- `EnergieProject_Roadmap.md`
- alle gespecialiseerde Knowledge Base-bestanden waarnaar de Master Index verwijst.

### B. Projectmanager engineering lessons
Root:
`Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/`

Lees altijd:
- `00_ACTIVE_DEVELOPMENT_CONTEXT.md`
- `00_DEVELOPMENT_MANIFEST.md`
- `01_UNIFIED_DEVELOPMENT_LEDGER.md`
- `03_AUTONOMOUS_NO_TERMINAL_RELEASE_ROUTE.md`
- `04_32440_LIVE_AUDIT_AND_32441_ARCHITECTURE.md`

Lees daarnaast alle latere Development_Lessons die in `00_DEVELOPMENT_MANIFEST.md` staan en inhoudelijk raken aan de actieve taak. De manifestlijst is leidend; bestandsnamen niet gokken.

### C. Harde requirements
Root:
`Data/03_Systeem/Projectmanager/Requirements/`

Voor release-/ontwikkelwerk minimaal:
- `HARD_REQUIREMENT_AUTONOMOUS_UNTIL_VERIFIED_ZIP.md`
- `HARD_REQUIREMENT_MODE_AS_DEVELOPMENT_METADATA.md`
- `HARD_REQUIREMENT_RELEASE_AUDIT_RECURRENCE_BADGES.md`
- `HARD_REQUIREMENT_32457_SIMPLE_RELEASE_ARCHITECTURE.md`
- `HARD_REQUIREMENT_LIVE_HANDOVER_NEW_CHAT.md`
- `HARD_REQUIREMENT_NEW_CHAT_RUNTIME_FIELDS.md`
- overige actieve HARD_REQUIREMENT-bestanden uit index/manifest/handover.

### D. Architectuur- en failure-history
Lees bij 32.4.x releasewerk minimaal:
- `Data/03_Systeem/Projectmanager/Worklogs/ARCHITECTUURAUDIT_32.4.56_NAAR_32.4.57_2026-09-18.md`
- `Data/03_Systeem/32.4.56_AUTONOOM_WERKLOG_2026-09-18.md` — minimaal relevante checkpoints 45-62
- actuele `CURRENT_HANDOVER_32_4_60_WORK_CODEX.md`
- actuele `WORK_LEDGER_32_4_60.md`
- rejected-release evidence die in de actuele handover wordt aangewezen.

## Hoge-waarde ontwikkellessen
Historische lessons zijn ontwerp- en regressieconstraints; actuele handover/runtime blijft statusautoriteit.

1. Root-cause-first; geen vierde symptoomfix na drie echte mislukte reparatierondes voor dezelfde oorzaak.
2. TDD RED -> GREEN -> regressie; geen skip/xfail/delete/weaken om GREEN te krijgen.
3. Exact dezelfde artifactbytes die worden vrijgegeven moeten via fresh-extract zijn getest.
4. Een release is niet klaar omdat code/build GREEN is: live acceptance en exacte runtime-readback blijven nodig.
5. Peter is geen transportlaag; Terminal standaard nul en rescue-scripts zijn auditmateriaal, geen standaard ontwikkelroute.
6. Eén ReleaseController bezit lifecycle; watcher/controller niet opnieuw laten uitgroeien tot tweede orchestrator.
7. Atomic installer is primitive, niet lifecycle-owner.
8. Control Plane alleen bounded actuator/on-demand readback; niet als extra lifecycle/heartbeat-truth.
9. CR/CLEARUP/hygiene horen niet in release-critical path behalve concrete corruption/security/path-collision.
10. Globale mode-gates mogen releaseflow niet kunstmatig blokkeren waar action-level safety al de bedoelde architectuur is.
11. Oude approvals/requests/results/generations mogen nooit een nieuwe release satisfyen; exact identity fencing.
12. RuntimeV2/document atomic replace kan permissies kapotmaken: gedeelde RuntimeV2 JSON eindmode exact 0666 waar contractueel vereist; bestaande gedeelde documentmodus bewaren; symlink fail-closed.
13. Temporary/AI workspaces zijn nooit bron van waarheid; canonieke KB/roadmap/status/ADR blijven leidend.
14. Historische kennis is context, geen current-state authority; current handover + live readback winnen.
15. Als een capability binnen de actieve task gebouwd moet worden, is het ontbreken ervan RED-baseline en geen zelfstandige blocker.
16. Checkpoints zijn persistente opslag, geen reden om Work/Codex te stoppen.
17. Geen parallelle nieuwe architectuurroute maken wanneer de bewezen standaardroute het probleem kan oplossen.
18. Release-architectuur moet eenvoudiger worden, niet telkens meer guards/rescue-/compatibilitylagen krijgen.
19. Een normale release moet uiteindelijk zijn: ZIP -> Incoming -> één ReleaseController -> install/rollback primitive -> runtime-align -> verify -> ACCEPTED -> GitHub/HA delivery -> COMPLETE.
20. Projectkennis bewaart niet alleen wat is besloten, maar ook waarom, welke alternatieven zijn verworpen, welke gevolgen gelden en welke open acties blijven.

## Work retrieval-procedure
Bij start van een grote release-/architectuurtaak:
1. Lees AGENTS.md, PROJECT_CONSTITUTION.md, CURRENT_HANDOVER.md, WORK_LEDGER.md, AGENT_TASK.md en dit bestand.
2. Inventariseer Master Index + Development Manifest.
3. Maak intern één compacte taakrelevante readset van actuele requirements, lessons, ADRs, worklogs en roadmapitems.
4. Lees die readset volledig vóór implementatie.
5. Schrijf in AGENT_RESULT/WORK_LEDGER welke canonieke bronnen daadwerkelijk zijn gelezen en welke constraints/regressies zijn overgenomen.
6. Herlees daarna niet telkens de hele KB; alleen bij nieuwe root cause, architectuurkeuze, auditbevinding of conflict.
7. Conflictvolgorde:
   PROJECT_CONSTITUTION / expliciete actuele AGENT_TASK / actuele live runtime
   > actuele hard requirements / current handover
   > Development Lessons / ADR
   > historische handovers/worklogs.
8. Historische instructies die inmiddels vervangen routes voorschrijven worden niet gereactiveerd zonder expliciete actuele beslissing.

## Specifiek voor 32.4.60
Vóór nieuwe code:
- volledige KB-inventaris uitvoeren via Master Index + Development Manifest;
- taakrelevante release-/Incoming-/publisher-/RuntimeV2-/permission-/control-plane-/autonomie-lessons vanaf 32.4.40 tot nu in de readset opnemen;
- defectfamilies uit 32.4.53/54/55/56 en architectuuraudit 56->57 als regressiedekking meenemen;
- daarna pas het bestaande 60-checkpoint + publisherfix combineren;
- geen tussentijds gebruikerscommentaar: dit is voorbereidende Work-uitvoering.
