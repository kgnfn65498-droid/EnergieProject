# Testinstructies v10.5.26

1. Zet `EnergieProject_v10.5.26.zip` rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Wacht op automatische verwerking naar `processed`.
3. Update Home Assistant naar 10.5.26 en herstart SlimmeMeterPortal Import één keer.
4. Klik **Download analysedata** en stuur het JSON-bestand.

Verwacht:
- `monthly_consumption_weighted_electricity_diagnostics` bevat augustus
- `price_snapshots_found > 0`
- `import_snapshots_found > 0`
- `reader_status = weighted_ok`
- `monthly_consumption_weighted_electricity` bevat augustus
- `matched_intervals > 0`
- `observed_window_hours > 0`
- augustus is `partial_observed`
- `months_partially_costable` bevat `2026_08`
- dag-run-rate is gevuld
- `ready_for_all_in_costs = false`

Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
