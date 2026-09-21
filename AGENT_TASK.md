# AGENT_TASK — EnergieProject

Status: ACTIVE
Schema: v1

- task_id: STANDARD-V60-CANDIDATE-CLOSURE-2026-09-21
- mode: DEVELOPMENT
- reasoning: HOOG
- work_model: SOL-LIGHT
- codex_model: gpt-5.6-terra
- codex_reasoning: medium
- max_parallel_codex_runs: 1
- owner: WORK_AUTONOMOUS
- step: FULL_SUITE_TO_CANDIDATE_ZIP
- candidate_sha: 33bea32534c5114aefe822afe252a6555bc55e58
- resume_checkpoint: ca7c0b427359bb4563a0f8dffbdcce0c5f17d32e

## Doel
Ga terug naar de bewezen standaard ontwikkel-/releasevoorbereidingsroute die honderden eerdere ZIPs gebruikte:
candidate source -> normale geïsoleerde Work/Codex testomgeving -> full pytest suite -> canonical build -> exact fresh-extract -> validatie -> kandidaat-ZIP.
Pas daarna, na de normale release-approval, gaat de ZIP via Incoming -> ReleaseController -> Processing -> installatie/runtime-align -> VERIFYING -> ACCEPTED -> COMPLETE.

## Bindende route
1. Gebruik de reeds aanwezige kandidaat/overdracht voor `33bea32534c5114aefe822afe252a6555bc55e58`.
2. Gebruik GEEN QNAP platformtest/containerexecutor als ontwikkelvoorwaarde.
3. Gebruik GEEN `platformtest_run`, control-plane source-sync of control-plane restart voor deze v60-candidate.
4. PR #10 / merge `ff480024ea74b237f4088b578db98e22ad9ac63d` is NIET onderdeel van de v60-candidate en mag niet naar QNAP worden geactiveerd.
5. Draai de full pytest suite in de normale Work/Codex development runtime met de reeds ingebouwde repository offline guard. Externe/private netwerktoegang moet fail-closed blijven.
6. Als een test faalt door de Work-hostomgeving zelf, herstel uitsluitend de test-harness/guard zodat dezelfde veiligheidsassertie behouden blijft; geen skip/xfail/delete/weaken.
7. Herhaal NIET het reeds bewezen publisher TDD-onderzoek of de 83/83 regressies tenzij een nieuwe full-suite failure rechtstreeks naar die code wijst.
8. Bij full-suite GREEN: voer de bestaande canonical build uit.
9. Fresh-extract exact de gebouwde ZIP en draai de voorgeschreven release-/incoming-/manifest-/integriteitsregressies op die extractie.
10. Verifieer ZIP CRC, manifest/SHA256, release-identiteit, root-layout en source/fresh-extract-equivalentie.
11. Lever één kandidaat-ZIP + changelog + korte instructie op.
12. STOP pas bij:
   - `CANDIDATE_ZIP_READY_FOR_RELEASE_APPROVAL`, of
   - een echte code/artifact/safety blocker die na concrete uitvoering overblijft.

## Niet toegestaan
- geen nieuwe architectuur;
- geen nieuwe executor/handoff/containerroute;
- geen QNAP/HA/productiewijziging;
- geen NAS-upload;
- geen rechtenwijziging;
- geen host-python op QNAP;
- geen restart/recreate/reboot;
- geen handmatige technische transporttaak voor Peter;
- geen tussentijdse stop voor gewone checkpoints/status.

## Reeds bewezen
- canonical 32.4.59 artifact identity/integrity GREEN;
- publisherfix targeted regressions 83/83 GREEN;
- full suite collection 1,974 tests;
- repository offline guard ontwikkeld en gericht GREEN;
- candidate bundle SHA256 06793fc120d299e065b673578a16b52d71da4ab4e5c78de74d2fd1a9b07fd5e1;
- candidate SHA 33bea32534c5114aefe822afe252a6555bc55e58.

## Autonome doorwerkregel
Work/Codex gaat zonder tussentijdse gebruikersactie door van full suite naar build naar fresh-extract naar kandidaat-ZIP zolang er geen echte blocker ontstaat. Checkpoints worden persistent opgeslagen zonder de run te beëindigen.

## 2026-09-21 — Peter approved exact 32.4.59 publisher-fix release
- Explicit release approval granted for artifact: EnergieProject_v32.4.59_publisher_fix_final.zip
- Exact SHA256: 23b9814d916c84d82ce4690291ec894c7550306a92a4eec494b6797a60a1a741
- Approved ingress: standard Inbox/incoming only.
- Do not rename, unpack, mutate, or substitute the artifact.
- After placement, existing ReleaseController owns the chain autonomously.
