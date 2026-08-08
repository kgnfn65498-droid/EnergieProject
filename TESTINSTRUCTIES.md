# Testinstructies v10.5.15

Eenmalige veilige overgang vanaf de huidige live watcher:
1. Download `EnergieProject_v10.5.15.ready`.
2. Kopieer dit bestand naar `EnergieProject_Inbox/incoming`.
3. Wacht tot Finder volledig klaar is.
4. Hernoem in Finder alleen de extensie `.ready` naar `.zip`.
5. Daarna niets meer doen: QNAP moet de release automatisch verwerken.
6. Installeer 10.5.15 in Home Assistant en herstart SlimmeMeterPortal Import één keer.
7. Klik **Download analysedata** en stuur het JSON-bestand.

Vanaf v10.5.15 mogen volgende `.zip`-bestanden weer rechtstreeks naar `incoming`.
Gebruik GEEN Home Assistant Terminal. Gebruik GEEN handmatige Git-commit of Git-push.

Verwacht in de analysedata voor juli 2026 bij werkende EPEX-brug:
- `source_found = true`
- `coverage.status = gedeeltelijk`
- `last_date = 2026-07-29`
- stroom: 2784 observaties
- gas: 696 observaties
