# AGENT_TASK — EnergieProject

Status: ACTIVE
Schema: v1

- task_id: RELEASE-32.4.60-RESUME-2026-09-20
- release: 32.4.60
- mode: DEVELOPMENT
- reasoning: HOOG
- work_model: SOL-LIGHT
- usage_guard: CONSERVE
- usage_signal: >=33% consumed before replacement-60 coding; minimize orchestration overhead immediately
- max_parallel_codex_runs: 1
- duplicate_pr_head_review: FORBIDDEN
- codex_model: gpt-5.6-terra
- codex_reasoning: medium
- codex_plan_reasoning: medium
- codex_model_fallback: FORBIDDEN
- step: 1/2
- owner: WORK
- goal: Hervat de vervangende 32.4.60 exact vanaf het bewezen NAS-checkpoint na de geslaagde Chat/Work/Codex-koppeling. Begin niet opnieuw.
- scope:
  1. Lees eerst AGENTS.md, PROJECT_CONSTITUTION.md, CURRENT_HANDOVER.md en WORK_LEDGER.md.
  2. Laad daarna exact de persistente NAS-bronnen:
     - Data/03_Systeem/Projectmanager/CURRENT_HANDOVER_32_4_60_WORK_CODEX.md
     - Data/03_Systeem/Projectmanager/WORK_LEDGER_32_4_60.md
     - volledige rejected-60 evidence
  3. Bepaal op basis van die bronnen het hoogste bewezen 32.4.60-checkpoint en de eerstvolgende nog niet uitgevoerde stap.
  4. Herhaal geen reeds bewezen onderzoek, tests of ontwerpwerk.
  5. Bouw niet eerst zomaar een ZIP.
  6. Schrijf na volledige bronhydratie het exacte hervatpunt terug naar AGENT_RESULT.md en update AGENT_TASK.md naar de werkelijke volgende ontwikkelstap/scope indien de NAS-handover dat voorschrijft.
  7. Start Codex pas daarna en alleen wanneer de handover aantoonbaar codewerk vereist.
- do_not_change:
  - productie/runtime/NAS/HA state tijdens checkpoint-hydratie
  - bewezen rejected-60 evidence
  - historische bewijsbestanden
  - release-architectuur buiten wat de NAS-handover expliciet vereist
  - modelbeleid
- proven_facts:
  - Chat/Work/Codex bridge smoke test is COMPLETE_GREEN.
  - PR #9 is open, mergeable en bewust ongemerged als bridge-evidence.
  - Work PR-eventreview is actief en heeft aantoonbaar gedraaid.
  - Codex bridge-probe gebruikte gpt-5.6-terra + medium zonder fallback.
  - Huidige 32.4.60-basis volgens de vastgelegde checkpointwaarheid: App 59 / HA 59 / GitHub 59 / Processing leeg.
  - De oude/rejected 60 is teruggetrokken en blijft bewijs; de vervangende 60 moet vanaf de NAS-handover worden hervat.
- required_tests:
  - USAGE GATE: reuse existing evidence; no broad re-analysis, no duplicate unchanged-head review, no parallel subagents.
  - WORK: bewijs dat alle drie NAS-bronnen werkelijk zijn gelezen; geen reconstructie uit herinnering.
  - WORK: rapporteer het hoogste bewezen checkpoint en exact eerstvolgende open stap.
  - WORK: controleer dat geen productie/NAS/HA-mutatie of ZIP-build plaatsvond tijdens hydratie.
  - CODEX MODEL GATE: effective model must be gpt-5.6-terra with medium reasoning; otherwise BLOCKED_MODEL_POLICY.
  - CODEX: geen uitvoering vóór Work de exacte NAS-handover heeft geladen en AGENT_TASK daarop is bijgewerkt.
- acceptance_criteria:
  - NAS-handover, NAS-ledger en rejected-60 evidence zijn exact geladen.
  - Geen bewezen werk is opnieuw uitgevoerd.
  - Geen ZIP is blind gebouwd.
  - Het exacte hervatpunt is machine- en mensleesbaar vastgelegd.
  - Daarna is de volgende taak begrensd genoeg voor Codex of expliciet als Work-only gemarkeerd.
- stop_conditions:
  - UI/Peter reports <=25% remaining session/week budget before a new large phase: checkpoint and STOP unless Peter explicitly authorizes continued spend.
  - NAS-bronnen niet rechtstreeks bereikbaar of niet volledig leesbaar: BLOCKED_NAS_CHECKPOINT_ACCESS.
  - Conflict tussen NAS-handover en repositorywaarheid: BLOCKED_SOURCE_CONFLICT.
  - Elke vraag om productie/restart/terminal voordat de handover die stap expliciet vereist.
  - Codex kan Terra + medium niet afdwingen: BLOCKED_MODEL_POLICY.
- production_authority: NO
- architecture_authority: NO
- predecessor_artifact_required: AS_DEFINED_BY_NAS_HANDOVER
- predecessor_artifact_identity: MUST_BE_READ_FROM_NAS_HANDOVER
- checkpoint_writeback_required: YES

## Bindende hervatregel
Niet opnieuw beginnen. Niet eerst zomaar een ZIP bouwen. NAS-handover is voor 32.4.60 de technische bronwaarheid.
