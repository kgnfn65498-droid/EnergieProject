# Release Acceptance — 32.5.19

Doel: de live 32.5.18 cross-identity permissionfout in de request-scoped Type-2 IPC structureel verwijderen.

Verplicht GREEN vóór aanbieding:
1. Exacte buildbasis: fysieke live 32.5.18 SHA256 `e184f9843bb1a4ce679d5bf8efbdfd5a440ba44ccd48fd1d33c9de931094f58a`.
2. Alle release-identiteiten 32.5.19; PM `2.0.0-rc52`.
3. Embedded PM voert geen mkdir/write uit onder `Data/03_Systeem/Projectmanager/ClearUp/Runtime/results` of naar de canonical Type-2 auditkopie.
4. Privileged sideband bridge maakt de vaste request-scoped result-root veilig aan, controleert symlink/path/request-id en zet cross-identity IPC-permissies expliciet.
5. Privileged bridge publiceert de canonical auditkopie pas na executor-resultaat; PM completion blijft uitsluitend request-scoped.
6. Live 32.5.18 PermissionError is als regressietest gereproduceerd en GREEN na fix.
7. Volledige Type-2 002–012 sequence-E2E blijft GREEN.
8. 32.5-suite, static regressies, fresh-extract, compile, manifest/CRC/hash/safe-entry en directe atomic 32.5.18→32.5.19 moeten GREEN zijn.
9. Geen Type-2 finalize/delete door deze release.

Live eindacceptatie na installatie:
- echte ClearUp_002 refresh ingress→PM→privileged sideband geeft GREEN zonder permissionfout/timeout;
- ClearUp_002 validate GREEN; ClearUp_012 refresh GREEN;
- 002–012 exports deep-verify GREEN en werkelijk extern gedownload/gehasht;
- pas daarna Type-2 100% klaar.
