# Release Acceptance — 32.5.20

Doel: de laatste live externe Type-2 recovery-downloadblokkade verwijderen zonder de inmiddels GREEN bewezen PM↔privileged-watcher keten te wijzigen.

Verplicht GREEN vóór aanbieding:
1. Exacte buildbasis: fysieke live 32.5.19 SHA256 `7e8cb44576a3c2195164f20c5e3d8f81f990dbf0f8a2c10b1a9450b077db372b`.
2. Alle release-identiteiten 32.5.20; PM `2.0.0-rc53`.
3. Native-MCP Type-2 verifier behandelt `size=0` als 0 en nooit als ontbrekende waarde.
4. De release-hotfix source-of-truth publiceert exact dezelfde gecorrigeerde `tools_clearup_export.py`.
5. Zero-byte Type-2 recovery ZIP verifieert GREEN; size/hash mismatch blijft fail-closed.
6. Bestaande Type-2 002–012, PM↔sideband, static, fresh-extract, compile, manifest/CRC/hash/safe-entry en directe atomic 32.5.19→32.5.20 blijven GREEN.
7. Native-MCP fingerprint moet door de wijziging verschillen zodat releasecontroller reload/readback afdwingt.
8. Geen Type-2 finalize/delete door deze release.

Live eindacceptatie na installatie:
- release COMPLETE 9/9; PM rc53; HA/NAS 32.5.20 aligned; Native MCP runtime fingerprint exact current;
- `projectmanager_status.type2_external_recovery` = `READY_FOR_EXTERNAL_DOWNLOAD`, `verified_count=11`, `failures=[]`;
- download alle 002–012 recovery-ZIPs, controleer lokale size + SHA256 en lever ze aan Peter;
- pas na Peters expliciete ontvangstbevestiging destructive finalize/delete hervatten.
