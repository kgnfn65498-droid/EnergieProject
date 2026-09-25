# CURRENT HANDOVER — EnergieProject 32.5.15

## Doel
32.5.15 sluit de terugkerende ClearUp-/releaseketenfoutklasse af zonder nieuwe opslagroots of alternatieve releaseketen.

## Bindende voortgang
- Runtime-statusautoriteit: canonieke Data/03_Systeem RuntimeV2; oude Inbox-runtime is alleen legacybron en geen actieve waarheid.
- Buildbasis: exact 32.5.14 SHA `78694b39e8d7f290f93148c1e2d0cdb5fb45d27339ec9257f67b2aad11541e3b`.
- ClearUp_002 is gemigreerd, bron is bewaard, validatie is GREEN en delete/finalize is niet uitgevoerd. De oude 002 recovery-ZIP is intern inconsistent en moet post-migrate worden vernieuwd.
- ClearUp_003–012 zijn eerder GREEN geverifieerd.
- 32.5.15 voegt een fail-closed post-migrate recovery-refresh toe, diepe ZIP-payloadverificatie en onafhankelijke download-descriptors per batch.
- Native MCP gebruikt de canonieke Data/03_Systeem RuntimeV2; de oude Inbox-runtime geldt alleen als retired legacy alias.
- Control-plane release-authority gebruikt stabiele controller/atomic state vóór en na Type2-padmigratie; productiecompose bevat geen losse App/VERSIE.txt file-bind meer.

## Vervolg na installatie
1. Controleer 32.5.15 COMPLETE en Native-MCP fingerprint GREEN.
2. Voer `clearup_type2_refresh_recovery` uitsluitend voor ClearUp_002 uit.
3. Lees `projectmanager_status`; 002–012 moeten ieder een eigen verified download-descriptor hebben.
4. Download de echte ZIPs naar ChatGPT, controleer grootte + SHA-256 en lever ze hier als bestanden.
5. Stop vóór destructive finalize/delete en wacht op expliciete bevestiging van de gebruiker.
