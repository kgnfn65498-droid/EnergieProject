# Changelog

## 32.5.18 — Type-2 request-scoped watcher result protocol

- Bouwt uitsluitend voort op de exacte 32.5.17 ZIP (`d86071a825f43d6c1c65368cf5d61782ed7df9c6dd26045c607adeed9af6670d`).
- Verwijdert de single-slot Type-2 result-mailbox uit het synchronisatieprotocol. Iedere PM-call krijgt een unieke result-path op basis van zijn 32-hex request-id.
- De privileged sideband bridge mag alleen naar `Data/03_Systeem/Projectmanager/ClearUp/Runtime/results/<zelfde-request-id>.json` schrijven; mismatches en onveilige paden worden fail-closed geweigerd.
- Het vaste canonical result-bestand is alleen nog auditkopie na succesvolle exacte readback en kan de volgende operatie niet meer blokkeren door stale inode/cachegedrag.
- Succesvolle request-scoped resultaten worden na canonical auditkopie opgeruimd; fout/timed-out evidence blijft voor forensische analyse staan.
- Bestaande recovery-, cutover-, path-rebinding-, externe-recovery- en finalize/delete-gates blijven intact. Geen destructive Type-2 actie wordt automatisch uitgevoerd.
