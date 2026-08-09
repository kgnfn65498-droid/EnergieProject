# Testinstructies v10.5.32

1. Zet `EnergieProject_v10.5.32.zip` rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Wacht op automatische verwerking naar `processed`.
3. Laat Home Assistant de update automatisch zien en installeer 10.5.32.
4. Open de Web UI.
5. Controleer dat **Download release-diagnose** zichtbaar is naast/onder **Download analysedata**.
6. Download de release-diagnose en stuur die ZIP hier.

Verwacht:
- Web UI toont versie 10.5.32.
- Release-diagnose downloadt zonder Terminal/Container Station.
- ZIP bevat `release_diagnostics.json`, `runtime_diagnostics.json`, `watcher_relevant.log`, `watcher_tail.log`, `README.txt` en `MANIFEST.json`.
- `runtime_diagnostics.json` bevat `backend_alive=true`, uptime, PID en threads.
- Diagnose bevat release-statussen uit incoming/processing/processed/failed indien beschikbaar.
- Diagnose bevat geen P1-, Enphase-, EPEX-, rapport-, token- of wachtwoorddata.
- `Download analysedata` blijft ongewijzigd werken.
- Bestaande NextEnergy gewogen analyse blijft `weighted_ok`.
- Geen Home Assistant Terminal nodig.
- Geen handmatige Git-commit of Git-push nodig.

Gebruik GEEN Home Assistant Terminal.
Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
Gebruik GEEN handmatige Git-commit of Git-push.
