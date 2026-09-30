# AGENT_TASK — Projectmanager / Knowledge Base / Index context architecture

- mode: DEVELOPMENT
- reasoning: HIGH
- stap: 4/7
- live runtime: 32.5.29 (readback 2026-09-30)
- release-target: GEEN; 32.5.30 is expliciet buiten scope
- productieautoriteit: NEE
- active branch: `pm-kb-index-fix`
- PR: #11

## Doel
Los structureel het Projectmanager/Knowledge-Base/index-contextprobleem op dat onafhankelijk is bevestigd door de Codex 6.0 Sol High audit:
`persistent aanwezig != ontdekt != geselecteerd != geleverd != correct toegepast`.

Doelarchitectuur:
Canonical Sources -> Truth Gate -> Mandatory Core -> bounded exact/lexical Task Evidence -> Context Package -> invocation-bound Delivery Receipt -> Spock -> Behavioral/E2E Evaluation.

## Scope — wijzigen toegestaan
- `slimmemeterportal_import/rootfs/app/projectmanager_v2/context_package.py`
- `context_delivery.py`
- `context_behavior.py`
- `development_context_enforcement.py`
- `development_handover_sync.py`
- `truth_engine.py`
- `orchestrator.py`
- `conversation_runtime.py`
- `handover_snapshot.py`
- `manager_service.py`
- `projectmanager_api.py`
- `capability_registry.py`
- gerichte tests voor PM/KB/context/index/handover/resume
- AGENT_TASK / AGENT_RESULT / CURRENT_HANDOVER / WORK_LEDGER uitsluitend voor deze taakadministratie

## Expliciet niet wijzigen
- geen release-identiteit;
- geen 32.5.30 ontwikkeling;
- geen Incoming/releasecontroller/HA/GitHub-publicatiepad;
- geen productieplaatsing, restart, recreate, cleanup of destructive actie;
- geen tweede KB, ledger, runtime truth, resume-owner of parallelle orchestrator;
- geen semantische/vector/GraphRAG-laag tenzij latere meting exact/lexical onvoldoende bewijst.

## Bewezen feiten
- Beide KB-roots, Requirements, handovers, ledger, checkpoints en PM-runtime bestaan.
- FULL_KB COMPLETE bewees tot nu toe alleen aanwezigheid/discovery, niet delivery of correcte toepassing.
- Codex reproduceerde false-GREEN op requirements/context, mtime-checkpointselectie, stale handover en een 116903-byte snapshotregressie.
- PR #11 eerste versie was daarom NIET voldoende.
- De oude index/contextversies zijn persistent bewaard onder `Worklogs/PreGate0_20260930/`.
- Live Projectmanager self-audit is momenteel RED door een bestaande/noncompliant runtime development task; deze taak mag die RED niet als GREEN maskeren.

## Verplichte implementatie
1. Controlled complete inventory van beide KB-roots + Requirements + current governance.
2. Claim-level truth/freshness/supersession; gelijkwaardige current conflicts fail-closed.
3. Mandatory Core bevat actuele claims + toepasselijke bindende rules/HOT lessons; retrieval kan deze kern niet verwijderen.
4. Task Evidence is bounded exact/lexical, progressive disclosure, en optionele I/O-fout mag Mandatory Core niet breken.
5. `verder` bepaalt first_unproven_action uit governing checkpoint/runtime evidence; geen brede historie of stale next-action.
6. Context package heeft canonieke JSON-identiteit, bronhashes, bounded budget en geen stille truncatie.
7. Eén context gate voor preflight, conversation resume, handover snapshot en API/consumerprojecties.
8. Delivery receipt alleen GREEN aan echte model-invocation-grens met invocation-ID + final-input hash.
9. Behavioral evaluator gebruikt machinecontroleerbare observed output/tooltrace; acknowledgement is onvoldoende.
10. Bestaande Native-MCP resume exposure blijft LIVE_REQUIRED totdat echte cliënt-discovery/call dit contract aantoonbaar levert.

## Acceptance
- alle 12 Codex-scenario's technisch afgedekt;
- false-GREEN negatieve tests;
- corrupt/empty/equal-rank checkpoint RED;
- stale/empty handover RED;
- nieuwe dynamic requirement ontdekt;
- ClearUp/capability requirement + capabilitymap gevonden;
- mandatory-context budget: optional evidence degradeert eerst, mandatory truncation => RED;
- snapshot blijft <100k zonder Mandatory Core te verliezen;
- package hash canoniek/stabiel;
- delivery receipt kan niet zonder echte invocation binding;
- behavioral evaluator RED bij repeated proven work of forbidden route;
- bestaande relevante handover/context regressies mogen niet worden verzwakt;
- onafhankelijke Codex re-audit van nieuwe PR-head vóór merge/activatie;
- echte model/client E2E blijft vereist vóór runtime-GREEN claim.

## Stopcriteria
Stop alleen bij echte scope/safety/model blocker of wanneer code + tests + onafhankelijke audit voor deze PM/KB/index-taak gereed zijn. Geen merge, deployment of restart zonder aparte autorisatie.
