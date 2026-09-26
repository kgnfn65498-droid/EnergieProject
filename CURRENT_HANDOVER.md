# CURRENT HANDOVER — EnergieProject 32.5.19

## Actuele ontwikkelpositie
- Live 32.5.18 is COMPLETE 9/9, PM rc51, maar de eerste echte Type-2 ClearUp_002 ingress-test faalde direct met `PermissionError: .../ClearUp/Runtime/results`.
- Root cause: 32.5.18 liet de embedded PM de nieuwe privileged request-scoped result-directory aanmaken. De PM-identiteit heeft daar terecht geen mkdir-recht.
- 32.5.19 verplaatst directory-ownership naar de privileged sideband bridge. PM schrijft niet meer in `ClearUp/Runtime`; hij publiceert alleen de request in Inbox en leest het exact request-id-gebonden resultaat.
- Exacte buildbasis: fysieke live 32.5.18 ZIP SHA256 `e184f9843bb1a4ce679d5bf8efbdfd5a440ba44ccd48fd1d33c9de931094f58a`.
- Geen Type-2 finalize/delete vóór externe recoveryontvangst.

## Autonome vervolgroute na installatie
1. Controleer 32.5.19 COMPLETE 9/9, PM `2.0.0-rc52` en HA/NAS alignment.
2. Voer exact ClearUp_002 recovery refresh via echte ingress→PM→privileged sideband uit en eis PM-resultaat GREEN zonder PermissionError/timeout.
3. Valideer ClearUp_002 live.
4. Refresh/deep-verify ClearUp_012; daarna 002–012 individueel deep-verify.
5. Download de echte 002–012 recovery-ZIPs naar de ChatGPT-workspace en verifieer lokaal size + SHA256.
6. Lever recovery-ZIPs aan Peter. Geen finalize/delete vóór expliciete ontvangstbevestiging.

## Harde acceptatieregel
Type-2 is pas 100% afgerond na deze live E2E plus externe recovery-download. Bij iedere nieuwe live fout wordt verder ontwikkeld; geen nieuwe klaar-claim op alleen offline tests.
