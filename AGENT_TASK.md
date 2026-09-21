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
- owner: SPOCK_PENDING_PROTECTED_ACTIVATION_APPROVAL
- step: STOP_FOR_PLATFORMTEST_DEPLOY_APPROVAL
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


## SPOCK IMPLEMENTATION BLUEPRINT — bewezen lokaal op kandidaat 33bea325
Spock heeft de ontbrekende capability inmiddels zelf uitgewerkt op exact kandidaat `33bea32534c5114aefe822afe252a6555bc55e58`. Work/Codex hoeft dit NIET opnieuw te ontwerpen; voer dit blueprint uit, test en commit.

Exacte codepunten:
1. `slimmemeterportal_import/rootfs/app/projectmanager_v2/command_gateway.py`
   - voeg veilige intent toe: `platformtest_run -> action platformtest_run -> allowed_without_approval=True`.
2. `command_ingress.py`
   - sta alleen extra velden `candidate_sha` en `test_profile` toe.
3. Nieuw: `platform_test_service.py`
   - fixed schemas `energie_platformtest_run_request_v1` / `energie_platformtest_run_result_v1`;
   - exact profiel `publisher_full_suite_v1`;
   - candidate SHA exact 40 hex;
   - workspace exact onder `Data/03_Systeem/Projectmanager/Staging/PlatformTest/<candidate_sha>`;
   - request exact naar `Inbox/control_plane/requests/platformtest_run.json`;
   - non-blocking PENDING/result readback; geen shell/image/path input van caller.
4. `command_processor.py`
   - injecteer `platform_test_service`;
   - route `platformtest_run` non-blocking; PENDING => requeue;
   - alleen GREEN accepteren als `production_modified is False` en `network_mode == 'none'`.
5. `orchestrator.py`
   - configureer `ConfiguredPlatformTestService(config.project_root)` en injecteer in CommandProcessor.
6. `tools/control_plane/control_plane.py`
   - `ALLOWED_ACTIONS` uitbreiden met exact `platformtest_run`;
   - vaste image `energie-filesystem-mcp:runtime-v1`;
   - vast profiel `publisher_full_suite_v1`;
   - vaste command `python3 -m pytest -q -p no:cacheprovider`;
   - Docker client alleen uitbreiden met fixed `wait_container` en `container_logs`;
   - validator weigert onbekende velden, fout schema/action/SHA/profiel;
   - host workspace exact `/share/Energie_NAS/EnergieProject/Data/03_Systeem/Projectmanager/Staging/PlatformTest/<sha>`;
   - create payload: bind workspace read-only naar `/workspace`, `NetworkMode=none`, `ReadonlyRootfs=True`, `CapDrop=['ALL']`, `no-new-privileges`, alleen tmpfs /tmp;
   - geen pull/build/install API;
   - containernaam `energie-platformtest-<request_id-prefix>`;
   - resultaat bevat candidate/profile/image/container/network_mode/exit_code/test_counts/logs_sha256/production_modified=False;
   - nonzero exit => RED; container altijd cleanup.
7. Nieuw: `tests/test_platformtest_capability.py`
   - gateway route;
   - canonical workspace + request;
   - bad SHA/profile/missing workspace fail-closed;
   - exact image/profile/network none/ro/capdrop/no-new-privileges;
   - extra fields + identity mismatch fail-closed;
   - nonzero pytest exit => RED;
   - CommandProcessor non-blocking route.
8. `tests/test_v32457_required_acceptance.py`
   - bestaande GreenAdapter-fixture aanvullen met `pre_target_publication`; verwachte calls inclusief `publish`. Dit is testfixture-alignment met reeds bestaande publisherfix, geen nieuwe productarchitectuur.

Spock-local verificatie:
- capability gericht: 7/7 GREEN;
- control-plane/PM gerichte set: 58/58 GREEN;
- brede relevante PM/control-plane/release subset: 969 passed, 2 skipped, 0 failed;
- python compile GREEN.
- eerdere 6 failures in `test_v32457_required_acceptance.py` waren uitsluitend stale fixture-mismatch door de reeds toegevoegde PUBLISHING-fase; na fixture-alignment volledig GREEN.
- patch inhoud SHA256 vanaf basis `c36866b97ce9779d46c2b7a96c2cac942a729430` exclusief coördinatiedocs: `a9e2afd2d53e92cf14682460560c34b59443fcd7def46a62ea52d1300b8eea3e`.

### Verplichte Work-uitvoering vanaf nu
- Start NIET met opnieuw onderzoeken of platformtest_run bestaat.
- Implementeer bovenstaande blueprint op de bestaande kandidaatbranch/checkpoint.
- Gebruik één Codex-lane Terra/Medium.
- Draai eerst de 7 capabilitytests, daarna de relevante control-plane/PM/release regressies.
- Bij GREEN: commit de capability en schrijf exact changed_files + commit SHA + testbewijs terug.
- Daarna STOP uitsluitend met `STOP_FOR_PLATFORMTEST_DEPLOY_APPROVAL`.
- Geen full-suite, NAS-sync, restart of productieactie vóór die approval.


## EXECUTABLE HANDOFF NOW AVAILABLE
- Development branch: `platformtest-executor-v1`
- Draft PR: #10
- Head SHA: `33f0788b479600ffe39e978df7168991dc5d26d7`
- This branch contains the missing fixed-function container executor itself. Therefore Work MUST NOT query the live QNAP connector for a pre-existing containerexecutor before testing this branch.
- Work action now:
  1. check out/read PR #10 branch;
  2. run `tests/test_platformtest_capability.py`;
  3. run relevant control-plane/PM/release regressions;
  4. correct any failures on the same branch;
  5. continue until capability source/tests are GREEN;
  6. persist exact test evidence and final branch SHA;
  7. then STOP only at `STOP_FOR_PLATFORMTEST_DEPLOY_APPROVAL`.
- The live QNAP connector is intentionally NOT used until after source/tests are GREEN and explicit protected live activation approval is granted.
- A result saying "QNAP connector has no containerexecutor" is INVALID for this phase, because implementing that executor is the current branch task.

## VERIFIED PRE-WORK EVIDENCE
- Exact transferred candidate 33bea325 was materialized and PR10 replayed locally.
- 8/8 new platformtest tests GREEN.
- 128/128 relevant control-plane/PM/release regressions GREEN.
- Do not repeat those suites unless PR10 changes further.
- Local ChatGPT container cannot be used as final full-suite authority for offline-child bootstrap because /opt/python-hooks/sitecustomize.py shadows repository sitecustomize.py.
- Final full-suite authority remains the approved QNAP image with NETWORK=NONE.

## PR10 MERGED
- PR #10 merged to main.
- Merge SHA: ff480024ea74b237f4088b578db98e22ad9ac63d
- Narrow platformtest_run source implementation is now in main.
- Development/source phase is complete enough to reach the protected activation boundary.
- DO NOT ask Work to retry live QNAP execution yet.
- Next action requires Peter approval for the already-defined protected activation only:
  1. canonical control-plane source sync;
  2. at most one bounded restart of existing energie-control-plane if loaded fingerprint mismatches;
  3. health + loaded fingerprint readback;
  4. platformtest preflight;
  5. then Work resumes candidate 33bea325 at checkpoint ca7c0b427359bb4563a0f8dffbdcce0c5f17d32e for the NETWORK=NONE full suite.
