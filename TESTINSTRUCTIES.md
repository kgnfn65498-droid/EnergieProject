# Testinstructies v10.5.25
1. ZIP rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Update Home Assistant naar 10.5.25 en herstart de add-on één keer.
4. Klik **Download analysedata** en stuur het JSON-bestand.

Verwacht:
- `monthly_consumption_weighted_electricity` bevat augustus weer
- `price_snapshots_found > 0` en `import_snapshots_found > 0`
- `matched_intervals > 0`
- `observed_window_hours > 0`
- augustus is opnieuw `partial_observed`
- `months_partially_costable` bevat `2026_08`
- dag-run-rate is gevuld
- `ready_for_all_in_costs = false`

Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
