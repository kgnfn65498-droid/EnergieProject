# Release Acceptance — 32.5.25 replacement

## Pre-install verplicht
- exact 32.5.24 buildbasis bewezen;
- writer-leak statische audit voor alle ClearUp_002..012 sources;
- alle Type-2 regressies GREEN inclusief concrete 11-batch finalize/delete-readback en late-writer reappearance RED-test;
- GitHub-publisher legacy binding detect/recreate/rollback contract GREEN;
- FULL_KB + Decision Log + Development Changelog + Spock + index/inventory tests GREEN;
- new-chat preflight `ready/verder/manual_reexplanation_required` GREEN/FAIL-CLOSED tests;
- volledige regressie + static + compileall + shell syntax GREEN;
- exact finale ZIP CRC/unique/safe paths/manifest/SHA256SUMS GREEN;
- finale fresh-extract herhaalt relevante Type-2/PM/continuïteitstests.

## Live-required na installatie
1. Incoming → Processing → live 32.5.25 → Processed; NAS/HA/GitHub exact aligned.
2. ReleaseController COMPLETE en publisher binding canonical GREEN.
3. Bekende oude writerpaden gedurende soak quiescent.
4. ClearUp_002..012 fresh live validation 11/11 GREEN en recovery gate exact confirmed.
5. Sequentiële finalize 002→012: per batch source absent + destination present + reappearance soak GREEN; stop on first RED.
6. Na alle batches globale legacy-source absence soak/readback.
7. PM FULL_KB COMPLETE, self-audit GREEN, Decision/Changelog/Spock/index pointers aanwezig.
8. Echte nieuwe chat met alleen `verder` hervat juiste live release/checkpoint/next action zonder heruitleg.

Geen PRE-INSTALL bewijs mag als LIVE_PROVEN worden gepresenteerd.

De bestaande split-state gate blijft bindend: NAS/HA/GitHub/PM/runtime moeten exact worden gereconcilieerd voordat LIVE_PROVEN wordt afgegeven.
