# Release Acceptance — 32.5.30

## Pre-install verplicht
- exact 32.5.29 predecessor artifact + SHA256/size bewezen;
- alle release-identiteiten onderling consistent;
- targeted, historische regressies en volledige toepasselijke suite GREEN;
- mandatory context fail-closed bij echt ontbrekende/foutieve context; optional evidence-budget is geen mandatory failure;
- split-state tussen live/predecessor/target/publication/HA wordt fail-closed gedetecteerd;
- release-ingress recovery blijft bounded, single-owner en fail-closed bij ambiguïteit;
- exacte ZIP CRC/unique/safe paths/MANIFEST/SHA256SUMS GREEN;
- fresh-extract herhaalt dezelfde acceptance.

## Live-required na installatie
1. ReleaseController target 32.5.30 exact.
2. GitHub/publication identity exact.
3. Home Assistant handmatig bijgewerkt en runtime exact target.
4. Processing daarna leeg en artifact naar Processed met dezelfde SHA256.
5. Post-live audit en benodigde recovery/cleanup-gates GREEN.

Geen PRE-INSTALL bewijs mag als LIVE_PROVEN worden gepresenteerd.
