# CURRENT_HANDOVER — 32.4.56

Datum: 18 september 2026
Release: 32.4.56
Projectmanager: 2.0.0-rc44
Status: PRE-INSTALLATIE GREEN; live E2E nog niet geautoriseerd/uitgevoerd.

## Doel en bewezen dekking
Incoming/releaseketen structureel normaal, stabiel en autonoom maken zonder Peter als transportlaag. De rc44-build dekt 12/12 bekende defectclusters uit 32.4.53/54/55 en behoudt de 11/11 historische contract-/regressiefamilies. Reeds bewezen onderzoek niet opnieuw uitvoeren.

## Buildbasis
De oude afgekeurde 32.4.56 / rc43 was uitsluitend read-only bronreferentie. De rc44-kandidaat is als afzonderlijke staging/build opgebouwd. `NEXT_CHAT_V7.md` is vervangen door de drie persistente lagen PROJECT_CONSTITUTION / CURRENT_HANDOVER / WORK_LEDGER.

## Structurele rc44-delta
- shared RuntimeV2/publication permissies fail-safe;
- same-version GitHub-publicatie gevolgd door officiële Supervisor store reload + self rebuild;
- transition-owned PROJECT_CR → MAINTENANCE bridge;
- exact executor-ticket settlement vóór brede health-doorgang;
- identieke verse CLEARUP-plan-id niet langer kunstmatige fout;
- CLEARUP candidate hashcache met bounded retry/checkpoints;
- Project CR: één deep verify tijdens creatie + onafhankelijke shallow SHA/ZIP-readback;
- CR snapshot release-debt scope met behoud van actuele atomic rollback/actieve hold-gates;
- stale Project-CR worker marker/fence bounded self-heal na 30 minuten, terwijl executor-timeout 20 minuten is;
- PROJECT_CONSTITUTION / CURRENT_HANDOVER / WORK_LEDGER als nieuwe-chatcontinuïteit.

## Pre-installatiebewijs
- rc44-specifieke familie: 39/39 GREEN.
- Totale pytest-collectie: 1.868 tests.
- Volledige regressie: 1.866 passed, 2 skipped, 0 failed.
- Canonical builder, manifest/SHA256SUMS en ZIP CRC zijn op het exact geleverde artifact GREEN; de externe werklog bevat de uiteindelijke artifact-SHA zodat dit document niet circulair zijn eigen ZIP-hash hoeft te bevatten.
- Exacte final-ZIP is na de laatste document-sync opnieuw fresh-extract getest met dezelfde 1.868-test suite: 1.866 passed, 2 skipped, 0 failed.

## Live uitgangstoestand vóór 56-E2E
Live App is 32.4.55. Atomic is ACCEPTED. Project CR en NAS Container CR zijn GREEN. De oude 55-transition staat nog ACTIVE / CLEARUP / PENDING. Geen handmatige state-reparatie toepassen; 56-E2E mag deze keten alleen via de normale geautoriseerde releaseweg overnemen.

## Eerstvolgende stap
Na finale artifact/readback en fresh-extract GREEN: uitsluitend afzonderlijke expliciete productie-/releaseautoriteit vragen voor de normale live 32.4.56 end-to-end acceptatie. Daarna Incoming → watcher/installer → hold → atomic acceptance → Project CR → NAS Container CR → CLEARUP → HYGIENE → LIVE_PROVEN → RESTORE_DEVELOPMENT → COMPLETE → Incoming-ready. Rapporteer tussentijds alleen bij een echte blokkade.
