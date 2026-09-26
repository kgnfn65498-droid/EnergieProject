# Release Acceptance — 32.5.18

Doel: de foutklasse achter de live Type-2 PM↔watcher time-outs architectonisch verwijderen, niet opnieuw omzeilen.

Verplicht GREEN vóór aanbieding:
1. Exacte buildbasis is fysieke 32.5.17 SHA256 `d86071a825f43d6c1c65368cf5d61782ed7df9c6dd26045c607adeed9af6670d`.
2. Alle release-identiteiten zijn 32.5.18; PM-identiteit is `2.0.0-rc51`.
3. Iedere Type-2 watcher-call gebruikt een cryptografisch unieke result-path onder `.../ClearUp/Runtime/results/<request_id>.json`; geen fixed-result inode wordt gebruikt om completion waar te nemen.
4. Sideband bridge accepteert die dynamische result-path uitsluitend als schema Type2 is én de bestandsnaam exact aan dezelfde request_id is gebonden.
5. Stale canonical results, verkeerde request-id, symlink/collision en timeoutgevallen zijn regressiegetest en fail-closed.
6. Volledige Type-2 002–012 sequence-E2E blijft GREEN met request-scoped resultaten.
7. Geen Type-2 finalize/delete wordt door deze release zelf uitgevoerd.
8. 32.5-suite, static/atomic regressies, fresh-extract, compile, manifest/CRC/hash/safe-entry en geïsoleerde atomic upgrade moeten GREEN zijn.

Live eindacceptatie na installatie:
- echte ClearUp_002 refresh via ingress→PM→request-scoped watcher-result geeft GREEN zonder timeout;
- ClearUp_002 validate GREEN; ClearUp_012 refresh GREEN;
- 002–012 exports deep-verify GREEN en worden werkelijk extern gedownload/gehasht;
- pas daarna is Type-2 als 100% werkend afgesloten.
