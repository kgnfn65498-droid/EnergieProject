# AGENT_TASK — EnergieProject

Status: ACTIVE
Schema: v1

- task_id: PLATFORMTEST-CAPABILITY-V1-2026-09-21
- mode: DEVELOPMENT
- reasoning: HOOG
- work_model: SOL-LIGHT
- usage_guard: CONSERVE
- codex_model: gpt-5.6-terra
- codex_reasoning: medium
- codex_model_fallback: FORBIDDEN
- owner: WORK_AUTONOMOUS_UNTIL_REAL_BLOCKER_OR_PHASE_COMPLETE
- step: IMPLEMENT_AND_VERIFY_PLATFORMTEST_CAPABILITY
- goal: Bouw en test nu daadwerkelijk de reeds goedgekeurde narrow platformtest_run capability in de bestaande QNAP handoff/control-plane. NIET opnieuw controleren of de intent al bestaat; het ontbreken ervan is de RED-baseline en juist het implementatiedoel.
- exact_resume_checkpoint: ca7c0b427359bb4563a0f8dffbdcce0c5f17d32e
- projectmanager_ingress_id: 28494cbae40341e788aa569b2361bf6e
- projectmanager_ingress_status: INFORMATIONAL_ONLY_NOT_A_GATE
- candidate_sha: 33bea32534c5114aefe822afe252a6555bc55e58

- scope:
  1. Lees AGENTS.md en deze AGENT_TASK.md.
  2. Delegeer direct één begrensde Codex-taak op Terra/Medium voor de implementatie.
  3. Wijzig alleen de bestaande standaard QNAP handoff/control-plane route.
  4. Voeg exact één fixed-function allowlisted intent/action toe: platformtest_run.
  5. Gebruik de bestaande request/result boundary onder Inbox/control_plane.
  6. Geen generieke shell-, docker- of command-passthrough.
  7. Testuitvoering moet hard NETWORK=NONE / NetworkMode=none afdwingen.
  8. Alleen bestaande goedgekeurde testimage/runtime; geen pull/build/install tijdens handoff.
  9. Exact candidate SHA + vast testprofiel in request/result; mismatch fail-closed.
  10. Alleen tijdelijke geïsoleerde testworkspace + immutable evidence output.
  11. Geen writes naar productie/runtime/HA/Incoming/Processing/Processed.
  12. Geen restart/recreate/reboot, geen host-python, geen privilegeverbreding.
  13. Bestaande watcher_recreate en native_mcp_reload blijven ongewijzigd en onbereikbaar vanuit platformtest_run.

- required_tests:
  - RED: bestaande handoff weigert platformtest_run.
  - GREEN: platformtest_run wordt exact geaccepteerd binnen allowlist/schema.
  - NETWORK: NetworkMode=none is verplicht en regressiegedekt.
  - IDENTITY: candidate/testprofiel mismatch faalt gesloten.
  - SIDE_EFFECTS: verboden paden/actions blijven onmogelijk.
  - REGRESSION: watcher_recreate/native_mcp_reload blijven GREEN.
  - READBACK: broncode + gerichte tests bewijzen dat capability daadwerkelijk bestaat.

- do_not_do:
  - GEEN full-suite starten.
  - GEEN publisher/full-suite analyse herhalen.
  - GEEN offline-guardwerk herhalen.
  - GEEN live QNAP source-sync of restart uitvoeren.
  - GEEN 32.4.59/32.4.60 releasecode veranderen buiten wat strikt nodig is voor deze capability.

- acceptance_criteria:
  - platformtest_run source implementation bestaat.
  - alle capability-regressies GREEN.
  - exacte verwachte control-plane runtime fingerprint bepaald.
  - AGENT_RESULT.md bevat changed_files, tests, commit/SHA en bewijs.
  - daarna STOP met exact: STOP_FOR_PLATFORMTEST_DEPLOY_APPROVAL.

- stop_conditions:
  - implementation vereist generieke shell/docker/NAS-capability of productie-write: BLOCKED_SCOPE_EXPANSION.
  - Codex niet Terra/Medium: BLOCKED_MODEL_POLICY.
  - alleen na succesvolle implementatie/test: STOP_FOR_PLATFORMTEST_DEPLOY_APPROVAL.

- production_authority: NO
- architecture_authority: APPROVED_NARROW_PLATFORMTEST_RUN_ONLY
- checkpoint_writeback_required: YES

## Belangrijk
Het ontbreken van platformtest_run is GEEN blocker in deze taak. Dat is de starttoestand die nu gecodeerd moet worden.
Work mag deze taak niet afsluiten met "intent niet geïnstalleerd" zonder eerst de implementatie + gerichte tests uit te voeren.


## AUTONOME UITVOERREGEL — bindend
- Work start bij deze taak DIRECT met uitvoering. Geen nieuwe availability-check, handoff-check, ingress-check of "bestaat de intent al?"-check als aparte stopstap.
- Het ontbreken van `platformtest_run` is de RED-baseline en moet in dezelfde Work-run worden opgelost.
- Work delegeert zo nodig direct aan Codex (Terra/Medium), leest daarna het resultaat terug en gaat zelfstandig door met de volgende stap.
- Work stopt NIET voor tussentijdse statuscommentaren, checkpoints of omdat een eerder benoemde capability nog niet bestaat.
- Checkpoints worden tussentijds persistent geschreven zonder de run te beëindigen.
- Work gaat door totdat één van deze echte eindtoestanden is bereikt:
  1. `STOP_FOR_PLATFORMTEST_DEPLOY_APPROVAL`: capability broncode + gerichte tests volledig GREEN; alleen protected live activatie ontbreekt.
  2. `BLOCKED_SCOPE_EXPANSION`: de gevraagde fixed-function capability blijkt technisch onmogelijk zonder generieke shell/docker/NAS-capability of productie-write buiten goedgekeurde scope.
  3. `BLOCKED_MODEL_POLICY`: Terra/Medium kan aantoonbaar niet worden afgedwongen.
  4. COMPLETE voor deze ontwikkelfase.
- Geen andere BLOCKED-status is toegestaan zolang het probleem met code/tests binnen de goedgekeurde scope oplosbaar is.
- Een blocker mag niet voortkomen uit de taaktekst zelf. Bij tegenstrijdige instructies geldt: doel + safety boundaries + deze autonome uitvoerregel hebben voorrang; corrigeer de interne interpretatie en ga door.
- Peter hoeft geen technische tekst, checkpoint, commando of handoff tussen Chat/Work/Codex te transporteren.
