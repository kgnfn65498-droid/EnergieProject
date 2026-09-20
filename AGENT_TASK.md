# AGENT_TASK — EnergieProject

Status: ACTIVE
Schema: v1

- task_id: AGENT-BRIDGE-SMOKE-2026-09-20
- release: INFRA-AGENT-BRIDGE-V1
- mode: DEVELOPMENT
- reasoning: HOOG
- step: 1/2
- owner: WORK
- goal: Bewijs de persistente Chat/Spock → Work → Codex koppeling zonder 32.4.60 of productie te wijzigen.
- scope:
  1. Lees AGENTS.md, PROJECT_CONSTITUTION.md, CURRENT_HANDOVER.md en WORK_LEDGER.md.
  2. Bevestig dat GitHub-repository kgnfn65498-droid/EnergieProject toegankelijk is.
  3. Schrijf alleen bridge-evidence naar AGENT_RESULT.md op een aparte branch.
  4. Maak, indien de accountfunctie beschikbaar is, een GitHub-PR-event-triggered Work-taak die toekomstige Codex-PR's in deze repository beoordeelt op AGENTS/AGENT_TASK scope, tests en acceptatiecriteria.
  5. Zet na GREEN Work-read/write bewijs deze taak door naar owner CODEX, step 2/2, met exact dezelfde beschermingsgrenzen.
  6. CODEX-fase: lees opnieuw de verplichte bestanden via AGENTS.md, maak uitsluitend een tijdelijke docs-probe op een aparte codex-branch, open een PR en wijzig geen releasecode.
- do_not_change:
  - 32.4.60 broncode of artifacts
  - releasecontroller/runtime/HA/NAS state
  - tests of productiecode
  - CURRENT_HANDOVER_32_4_60_WORK_CODEX.md op NAS
  - WORK_LEDGER_32_4_60.md op NAS
  - rejected-60 evidence
- proven_facts:
  - Agent bridge v1 staat op main.
  - AGENTS.md, AGENT_TASK.md en AGENT_RESULT.md bestaan.
  - PROJECT_CONSTITUTION bevat het bindende Chat/Work/Codex-contract.
  - PR #8 is gemerged.
  - 32.4.60 wordt na deze smoke test hervat vanaf NAS-checkpoint; niet opnieuw ontwerpen of zomaar een ZIP bouwen.
  - Bronwaarheid voor dat latere hervatpunt: App 59 / HA 59 / GitHub 59 / Processing leeg.
- required_tests:
  - WORK: read-back van alle verplichte files en aantoonbare GitHub write op aparte branch.
  - CODEX: aantonen dat AGENTS.md vóór uitvoering is toegepast.
  - CODEX: alleen tijdelijke docs-probe; geen source/test/runtime wijzigingen.
  - PR-diff moet uitsluitend bridge-probe/resultaat bevatten.
  - WORK-review van Codex-PR via event-trigger indien beschikbaar; anders expliciet BLOCKED op die capability, niet omzeilen.
- acceptance_criteria:
  - Work leest de persistente regels zonder dat Peter ze kopieert.
  - Work kan een begrensde GitHub-resultaatwrite doen.
  - Codex leest AGENTS.md en AGENT_TASK.md en respecteert scope.
  - Codex opent een geïsoleerde PR zonder releasecodewijzigingen.
  - Work kan de Codex-PR beoordelen via GitHub; event-trigger is GREEN indien beschikbaar, anders capability-blocker expliciet vastgelegd.
  - Peter hoeft geen inhoud tussen Work en Codex te kopiëren.
- stop_conditions:
  - Elke vraag om productie/NAS/HA/restart/terminal.
  - Elke poging 32.4.60 te wijzigen tijdens de smoke test.
  - Ontbrekende of conflicterende projectwaarheid.
  - Work of Codex kan GitHub niet lezen/schrijven.
- production_authority: NO
- architecture_authority: YES
- predecessor_artifact_required: NO
- predecessor_artifact_identity: N/A
- checkpoint_writeback_required: YES

## NAS-resume na succesvolle koppeling
Na volledige GREEN smoke test wordt deze bridge-taak afgesloten en wordt 32.4.60 hervat vanaf:
- Data/03_Systeem/Projectmanager/CURRENT_HANDOVER_32_4_60_WORK_CODEX.md
- Data/03_Systeem/Projectmanager/WORK_LEDGER_32_4_60.md
- volledige rejected-60 evidence

Niet opnieuw beginnen. Niet eerst zomaar een ZIP bouwen.
