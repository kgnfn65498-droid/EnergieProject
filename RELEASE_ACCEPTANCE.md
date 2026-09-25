# Release Acceptance — 32.5.15

Status vóór live installatie: RELEASE CANDIDATE, niet live bewezen.

Verplicht GREEN vóór aanbieding:
1. exacte buildbasis 32.5.14 SHA `78694b39e8d7f290f93148c1e2d0cdb5fb45d27339ec9257f67b2aad11541e3b`;
2. alleen bedoelde functionele wijzigingen plus release-identiteit/documentatie; geen oude/onverwante code;
3. post-migrate recovery-refresh: bron en gemigreerde bestemming byte-/boomgewijs onaangeroerd;
4. recovery-ZIP payload-voor-payload grootte + SHA-256 verificatie;
5. één defecte ZIP blokkeert sibling-downloads niet; delete_allowed blijft false;
6. Native MCP gebruikt canonieke `/system/Projectmanager/RuntimeV2` ook wanneer oude env-alias aanwezig is;
7. control-plane release-authority werkt vóór én na Type2-padmigratie, weigert split-state fail-closed en bevat geen productie App/VERSIE.txt file-bind;
8. volledige 32.5.x regressies GREEN en historische Incoming/control-plane regressies zonder nieuwe rode tests;
9. fresh-extract compile/tests + ZIP manifest/CRC;
10. atomic 32.5.14 → 32.5.15 prepare/swap/acceptance GREEN.

Live eindacceptatie voor ClearUp is pas GREEN nadat de echte recovery-ZIP's 002–012 naar ChatGPT zijn gedownload en lokaal opnieuw op grootte/SHA-256 zijn gecontroleerd. Geen finalize/delete vóór expliciete gebruikersbevestiging.
