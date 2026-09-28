# Release Acceptance — 32.5.28

## Pre-install verplicht
- exact 32.5.27 buildbasis SHA256 `ea3674ebc32067a7c71b5798f33cb3e9de03f1d1c178dcb96e0f73e7dc4e89f2`;
- recovery-first prepare/export/confirm/apply-gates GREEN;
- live source mutation na recovery => fail-closed;
- privileged executor herverifieert recovery + plan + sourcebytes vóór mutatie;
- `Inbox/processing` permanente mailbox; nooit cleanup-item;
- twee opeenvolgende releases Incoming -> Processing -> HA exact -> Processed GREEN;
- exact predecessor-boundary 32.5.27 -> 32.5.28 GREEN zonder manual reconciliatie/rename/move/Terminal;
- split-state tussen live/predecessor/target/publication/HA wordt fail-closed gedetecteerd en mag nooit als COMPLETE worden gepresenteerd;
- always-current handover generation/freshness + ManagerService auto-sync GREEN;
- volledige toepasselijke regressie zonder open failures; compileall/shell syntax GREEN;
- exacte ZIP CRC/unique/safe paths/MANIFEST/SHA256SUMS GREEN;
- fresh-extract herhaalt dezelfde acceptance.

## Live-required na installatie
1. Incoming -> Processing -> HA exact -> Processed; 32.5.28 exact.
2. Processing blijft daarna bestaan en is leeg.
3. Canonieke publication-state blijft onder Data/03_Systeem; geen legacy Inbox-publication-state.
4. ReleaseController/post-live audit GREEN.
5. Eerst recovery-ZIP van exact finale Inbox-cleanupplan in chat leveren/downloaden en extern exact bevestigen.
6. Pas daarna live cleanup: `failed` plat, allowlist-restanten reversibel quarantaine, `Inbox/projectmanager_v2` als laatste; Processing onaangeroerd.
7. 20 s resurrection soak + post-cleanup readback GREEN.

Geen PRE-INSTALL bewijs mag als LIVE_PROVEN worden gepresenteerd.
