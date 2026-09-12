# EnergieProject 32.4.43

32.4.43 is de structurele stabilisatiebuild voor Projectmanager V2. De release sluit de bewezen runtime-contractfouten uit 32.4.42: cross-runtime permissions, stale releasecommands, split project-close state, PM-cycle provenance, statische document-sync, approval truth en health-semantiek.

De bestaande architectuur en releaseketen blijven leidend: **ZIP → Incoming/Home Assistant → watcher → live controle**. Er is geen alternatieve GitHub- of reconstructieroute als buildbasis.

## Veiligheidsgrenzen

- Productieplaatsing vereist expliciete goedkeuring.
- Protected restarts/deploys blijven approval-bound.
- CR/CLEARUP-mutaties zijn alleen toegestaan bij exact current `project_close=REQUESTED`.
- `DEFERRED`, ontbrekende of stale project-close state is fail-closed.
- Geen directe delete voor CR-retentie/CLEARUP; quarantine-first/no-delete blijft leidend.

## Bouwbasis

Exact geverifieerde `EnergieProject_v32.4.42.zip`, SHA256 `a5cf6a3135580df504a1a70b71708b477ba247141d8262585c4f544423b2f9fc`. Zie `docs/32.4.43-build-basis.json`.
