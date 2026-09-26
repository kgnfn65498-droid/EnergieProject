# CURRENT HANDOVER — EnergieProject 32.5.20

## Actuele ontwikkelpositie
- Live 32.5.19 is COMPLETE 9/9, PM rc52 en HA/NAS aligned.
- Harde live Type-2 bewijs op 32.5.19: ClearUp_002 recovery-refresh via echte ingress→PM→privileged sideband = GREEN; ClearUp_002 validate = GREEN; ClearUp_012 recovery-refresh = GREEN.
- Resterende fout zit uitsluitend in de Native-MCP externe exportverifier: `int(row.get("size") or -1)` maakte legitieme zero-byte payloads ongeldig. Daardoor rapporteerde status nog 002 en 012 als size mismatch, ondanks GREEN embedded deep verification.
- 32.5.20 corrigeert deze verifier in de runtime-hotfix source-of-truth. De Native-MCP runtime fingerprint verandert bewust zodat releasecontroller reload/readback moet bewijzen.
- Exacte buildbasis: fysieke live 32.5.19 ZIP SHA256 `7e8cb44576a3c2195164f20c5e3d8f81f990dbf0f8a2c10b1a9450b077db372b`.
- Geen Type-2 finalize/delete vóór externe recoveryontvangst.

## Autonome vervolgroute na installatie
1. Controleer 32.5.20 COMPLETE 9/9, PM `2.0.0-rc53`, HA/NAS alignment en Native-MCP fingerprint current.
2. Eis `type2_external_recovery.status=READY_FOR_EXTERNAL_DOWNLOAD`, `verified_count=11`, `failures=[]`.
3. Download echte recovery-ZIPs ClearUp_002 t/m ClearUp_012 naar de ChatGPT-workspace.
4. Verifieer lokaal per ZIP bestandsgrootte, SHA256, CRC en Type2 manifest/payload hashes.
5. Lever de recovery-ZIPs aan Peter.
6. Geen finalize/delete vóór Peters expliciete ontvangstbevestiging.

## Harde acceptatieregel
Type-2 is pas 100% afgerond wanneer de volledige live keten én externe recovery-download 002–012 werkelijk GREEN zijn. Iedere nieuwe live fout betekent verder ontwikkelen.
