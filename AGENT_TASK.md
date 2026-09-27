# AGENT_TASK — EnergieProject 32.5.24 replacement

- task_id: V32524-PM-TYPE2-LIVE-TRUTH-CLOSURE-2026-09-26
- mode: DEVELOPMENT
- thinking: HIGH
- owner: ChatGPT/Spock
- production_authority: NO

## Doel
Lever één vervangende 32.5.24 die de noodzakelijke N+1 control-plane activatie behoudt én de bindende 32.5.24 Project Manager/Type-2 eisen technisch afdwingt zonder nieuwe watcher/controller/statusketen.

## Scope
- exact fysieke 32.5.23 ZIP als buildbasis;
- predecessor-controller/N+1 control-plane activatie behouden;
- PM versie 2.0.0-rc58;
- LIVE_REQUIRED functioneel nooit definitief sluiten zonder LIVE_PROVEN;
- new-chat/handoff/status/task/intake/acceptance runtime-first houden;
- Step X/Y + elapsed/ETA technisch afdwingen en tonen;
- uitzonderlijke terminalfallback alleen compliant met terminal, stap, duur, maximale wachttijd, succes-/stopmarker en retourvereiste;
- versie-opstapeling/carry-forward proactief signaleren;
- historische Type-2 recovery-ontvangst scheiden van actuele recoveryset-integriteit;
- ClearUp_002..012 volledige E2E: prepare -> export verify -> migrate -> path activation -> validate -> external recovery gate -> finalize -> delete-readback -> restore;
- ClearUp_007 expliciet bewijzen met canonieke control-plane writer-handoff en quiescente legacy bron.

## Veiligheidsgrenzen
- geen NAS/HA restart tijdens build;
- geen live Type-2 finalize/delete tijdens build;
- geen nieuwe lifecycle-owner/watcher/publisher;
- geen versoepeling van recovery-, validation- of releasegates;
- destructive live Type-2 pas na actuele plan/recovery/validation/live-proof exact GREEN.

## Acceptatie
- 32.5-regressiefamilie volledig GREEN;
- oudere PM/handoff/build-contract regressies relevant voor deze scope GREEN;
- static suite GREEN;
- canonical release builder filtert caches/pyc en weigert verboden ZIP-members;
- exact fysieke ZIP fresh-extract: CRC, manifest, SHA256SUMS, compile en dezelfde relevante regressies GREEN;
- live-only functional gates blijven LIVE_REQUIRED tot installatiebewijs aanwezig is.

- De bestaande host-capability Platform Qualification blijft een apart bewijscontract naast release acceptance; geen testverzwakking.
