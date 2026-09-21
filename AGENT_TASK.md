# AGENT_TASK — EnergieProject

Status: ACTIVE
Schema: v1

- task_id: INCOMING-CHAIN-32.4.59-PUBLISHER-FIX-2026-09-20
- release: 32.4.59-PUBLISHER-FIX
- mode: DEVELOPMENT
- reasoning: HOOG
- work_model: SOL-LIGHT
- usage_guard: CONSERVE
- usage_signal: current post-reset budget not yet reported; remain in CONSERVE mode
- max_parallel_codex_runs: 1
- usage_execution_rule: one bounded active task only; no broad re-analysis; checkpoint before each next large phase
- duplicate_pr_head_review: FORBIDDEN
- codex_model: gpt-5.6-terra
- codex_reasoning: medium
- codex_plan_reasoning: medium
- codex_model_fallback: FORBIDDEN
- step: 3/3
- owner: WORK
- goal: Maak eerst de bestaande Incoming-keten structureel werkend door de minimale noodzakelijke publisher-correctie op de werkelijk actieve 32.4.59-voorganger te ontwikkelen en volledig te verifiëren. Replacement 32.4.60 blijft daarna pas aan de beurt.
- scope:
  0. REPOSITORY-WIDE OFFLINE TEST GUARD is explicitly approved by Peter for test infrastructure only. Implement one deterministic default-deny network guard for the test suite so tests cannot contact private/external endpoints unless an individual test explicitly uses a local-only fixture/fake approved by the test contract.
  0. Hermetic full-suite unblock is now the immediate next step. Do not revisit the already-GREEN publisher implementation unless the isolated test exposes a real regression.
  1. Hervat vanaf het reeds door Work geladen NAS-checkpoint en de rejected-60 evidence. Geen brede heranalyse.
  2. Leg vóór codewijziging het bewezen blockercheckpoint duurzaam vast: actieve ongewijzigde 32.4.59-publisher kan alleen de actieve versie uit Processed publiceren en kan daardoor geen volgende candidate uit Processing publiceren vóór installatie.
  3. Markeer commit 398b2aa expliciet als REJECTED/DO_NOT_USE omdat de test ten onrechte toekomstige aangepaste code als actieve 59-code gebruikte.
  4. Behoud checkpoint a59780d als inhoudelijk hervatpunt waar beschikbaar; als die lokale commit niet meer bereikbaar is, reconstrueer alleen de bewezen checkpointfeiten uit de persistente NAS-evidence, niet het afgekeurde patchwerk.
  5. Codex maakt op een geïsoleerde branch uitsluitend de minimale 32.4.59-publisherfix die een exact geverifieerde volgende release-candidate vanuit Processing kan publiceren binnen de bestaande ReleaseController-eigenaarschap en identity fencing.
  6. TDD verplicht: eerst een regressietest die faalt tegen de werkelijk ongewijzigde 32.4.59-publisher, daarna minimale implementatie, daarna gerichte regressies.
  7. Behoud bestaande invarianten: Incoming is release-authority; Processing blijft eigenaar van niet-voltooide candidate; Processed betekent COMPLETE; geen version-only GREEN; exacte release_id/generation/version/artifact SHA/target-manifest identiteit blijft verplicht.
  8. Ontwerp GEEN release-onafhankelijke bootstrap-actuator, tweede publisher, tweede lifecycle-owner, rescueketen of parallel releasepad.
  9. Na gerichte GREEN: relevante release/publisher regressiefamilies draaien, daarna volledige vereiste suite en fresh-extract volgens bestaand buildcontract.
  10. Alleen als alle ontwikkel- en artifactgates GREEN zijn: maak een gecontroleerde 32.4.59 publisher-fix kandidaat klaar. NIET live installeren zonder nieuwe expliciete productieautoriteit van Peter.
  11. Pas na gecontroleerde live installatie + bewezen Incoming E2E GREEN mag replacement 32.4.60 worden hervat vanaf het bestaande NAS-checkpoint.
- do_not_change:
  - replacement 32.4.60 implementatie zolang 59-publisherfix niet live bewezen is
  - rejected-60 evidence
  - historische regressie-evidence
  - ReleaseController single-owner architectuur buiten de minimale publishercorrectie
  - NAS/HA/productie tijdens ontwikkeling
  - model- en Usage Guard-beleid
- proven_facts:
  - Work reported exact predecessor ZIP verified: EnergieProject_v32.4.59(2).zip, 5,968,217 bytes, SHA256 42a70f18…d68715c, ZIP integrity GREEN with 536 files, version 32.4.59, manifest SHA 21c22a6c…bc06f1, predecessor 32.4.58 hotfix SHA c9d67b5a…9755e4.
  - Work reported preparation checkpoint 1aed641.
  - Work/Codex reported publisher-fix checkpoint 0f79011.
  - TDD RED was proven against the unchanged exact 32.4.59 ZIP.
  - Minimal publisher fix was implemented; targeted regressions 83/83 GREEN; compilation and diff control GREEN.
  - 398b2aa remained excluded.
  - No candidate ZIP was built and no NAS/HA/Incoming/production/restart action occurred.
  - Full suite was not run because one test would contact private NAS endpoint 192.168.1.200:8000; that live-network dependency must be removed from the test path rather than granted access.
  - Peter heeft optie 1 expliciet gekozen: eerst afzonderlijke voorganger-/publisher-update voor 59; daarna replacement 60.
  - Hoogste prioriteit is een werkelijk werkende Incoming-keten.
  - NAS-checkpoints en volledige rejected-60 evidence zijn door Work geladen.
  - De actieve ongewijzigde 32.4.59-publisher kan alleen de actieve versie uit Processed publiceren.
  - Daardoor kan de huidige publisher geen 32.4.60-candidate uit Processing vóór installatie publiceren.
  - De eerste voorgestelde repair/test gebruikte aangepaste toekomstige code alsof die al actief was in 59 en is daarom ongeldig.
  - Commit 398b2aa is REJECTED en mag niet worden gebruikt.
  - Laatste Work-checkpoint is a59780d; branch was op dat moment niet gepusht en er was geen PR.
  - Geen ZIP, NAS-write, HA-write, Incoming-write, productieactie, restart of terminalactie vond bij die blocker plaats.
  - Baseline vóór deze fix: App 59 / HA 59 / GitHub 59 / Processing leeg.
- required_tests:
  - OFFLINE GUARD RED: prove at least one representative test would attempt a real network connection without the guard.
  - OFFLINE GUARD GREEN: repository-wide test execution blocks outbound/private network connections by default.
  - LOCAL TEST TRAFFIC: localhost/in-process fakes may be allowed only where required by deterministic fixtures; no access to 192.168.1.200:8000 or other live NAS/HA endpoints.
  - NO WEAKENING: no skip, xfail, deletion, assertion weakening, or conditional bypass of existing behavioral tests.
  - GUARD REGRESSION: add a regression proving live/private-network attempts fail closed during tests.
  - TEST ISOLATION GATE: identify the exact test/path that would contact 192.168.1.200:8000. Make the test hermetic using a local fixture/mock/fake or dependency injection while preserving the same behavioral assertions. Do NOT skip, xfail, delete, weaken, or conditionally bypass the test.
  - NETWORK SAFETY: full suite/build/fresh-extract must run with no live NAS/HA/private-network dependency. Unexpected external-network access is a test failure.
  - ISOLATION REGRESSION: add/retain proof that the tested publisher behavior is exercised against deterministic local evidence and cannot silently fall back to a live NAS.
  - AFTER ISOLATION: rerun the affected test(s), the 83 targeted regressions if impacted, then the complete required suite.
  - ONLY AFTER FULL SUITE GREEN: canonical publisher-fix build and exact fresh-extract verification.
  - PREDECESSOR ARTIFACT ACCESS GATE: before any Codex/code work, verify that the exact canonical 32.4.59 predecessor ZIP named/identified by the NAS handover is directly readable. If readable, use it and continue. If not readable, STOP as BLOCKED_PREDECESSOR_ARTIFACT_MISSING and request that exact ZIP from Peter; do not substitute GitHub source, runtime copy, reconstructed tree, or another artifact.
  - USAGE GATE: hergebruik geladen evidence; geen brede heranalyse; geen parallelle subagents; één Codex-lijn.
  - RED: reproduceer met werkelijk ongewijzigde 32.4.59-publisher dat een exact geldige next-release candidate in Processing niet gepubliceerd kan worden.
  - GREEN: minimale publisherfix maakt exact die case mogelijk zonder Processed/COMPLETE-semantiek te verzwakken.
  - NEGATIVE: foreign/unproven/stale candidate blijft fail-closed.
  - IDENTITY: release_id, generation, version, artifact SHA en target-manifest SHA blijven exact gefenced.
  - OWNERSHIP: geen tweede lifecycle-owner/publisherpad.
  - REGRESSION: bestaande 32.4.59 publisher/releasecontroller en relevante historische releasefamilies blijven GREEN.
  - ARTIFACT: canonical build + fresh-extract gates uitsluitend nadat source/regressions GREEN zijn.
  - CODEX MODEL GATE: gpt-5.6-terra + medium; anders BLOCKED_MODEL_POLICY.
- acceptance_criteria:
  - Root cause is met ongewijzigde 32.4.59-code RED bewezen.
  - 398b2aa wordt nergens als buildbasis of oplossing gebruikt.
  - Minimale publisherfix is gericht GREEN en bewaart alle identity/ownership/Processing-invarianten.
  - Vereiste regressies + fresh-extract zijn GREEN.
  - Er is hoogstens een gecontroleerde publisher-fix kandidaat; geen live installatie zonder expliciete goedkeuring.
  - Na latere live installatie moet een echte Incoming E2E aantonen dat volgende-release-publicatie werkt voordat 32.4.60 hervat.
- stop_conditions:
  - Test isolation would require production credentials, live NAS/HA access, disabling assertions, skip/xfail, or broad architecture change: BLOCKED_TEST_ISOLATION.
  - UI/Peter reports <=25% remaining before a new large phase: checkpoint and STOP unless Peter explicitly authorizes continued spend.
  - Fix vereist alsnog een tweede releasepad/bootstrap-actuator of bredere architectuurwijziging: BLOCKED_SCOPE_EXPANSION.
  - Exacte 32.4.59 buildbasis/identity ontbreekt: BLOCKED_PREDECESSOR_IDENTITY.
  - Productie-installatie/restart/recreate/NAS live mutation nodig: STOP_FOR_PRODUCTION_APPROVAL.
  - Codex kan Terra + medium niet afdwingen: BLOCKED_MODEL_POLICY.
- production_authority: NO
- architecture_authority: YES_LIMITED_TO_EXISTING_59_PUBLISHER_FIX_AND_TEST_INFRA_OFFLINE_GUARD
- predecessor_artifact_required: YES
- predecessor_artifact_identity: MUST_USE_EXACT_VERIFIED_32.4.59_BASIS_FROM_NAS_HANDOVER
- checkpoint_writeback_required: YES

## Bindend besluit
Incoming-keten werkend krijgen is nu prioriteit 1. Replacement 32.4.60 wordt niet verder gebouwd totdat de actieve 32.4.59-publishercorrectie gecontroleerd is ontwikkeld, getest en later met expliciete productieautoriteit live bewezen is.
