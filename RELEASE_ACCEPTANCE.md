# Release Acceptance — 32.5.27

## Pre-install verplicht
- exact 32.5.26 buildbasis SHA256 `e0ffa48b93e42b8ef09319775b1a54b8e25a9e7719a30d347762c1dcdeed71f5`;
- Processing-contract: permanente mailbox, idle aanwezig en leeg;
- HA delivery archiveert alleen de ZIP naar Processed en verwijdert Processing niet;
- ingress recovery en ReleaseController herstellen/handhaven de permanente Processing-map;
- finale Type-3/Inbox-cleanup bevat geen actie voor `Inbox/processing`;
- canonieke ClearUp_011 publication-state blijft uitsluitend onder `Data/03_Systeem/Projectmanager/ReleaseController/Publication`;
- completed-release reconciliation normaliseert het cross-identity writercontract naar directory 0777 / statefiles 0666;
- relevante release/Type-3/failed/PM regressies, static, compileall en shell syntax GREEN;
- exacte ZIP CRC/unique/safe paths/MANIFEST/SHA256SUMS GREEN;
- fresh extract herhaalt dezelfde acceptance.

## Live-required na installatie
1. Incoming -> Processing -> Processed; 32.5.27 exact.
2. Processing blijft daarna bestaan en is leeg.
3. Canonieke publication-state blijft onder Data/03_Systeem; geen legacy Inbox-publication-state.
4. Publication writer-contract readback is 0777/0666.
5. ReleaseController/post-live audit GREEN.
6. Finale Type-3/Inbox cleanup maakt `failed` plat, ruimt de allowlist-restanten op en verwijdert `projectmanager_v2` als laatste; Processing blijft onaangeroerd.
7. Resurrection soak/readback GREEN.

Geen PRE-INSTALL bewijs mag als LIVE_PROVEN worden gepresenteerd. De bestaande split-state gate blijft bindend: NAS/HA/GitHub/PM/runtime moeten exact worden gereconcilieerd voordat LIVE_PROVEN wordt afgegeven.
