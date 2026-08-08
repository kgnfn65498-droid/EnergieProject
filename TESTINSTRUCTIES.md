# Testinstructies v10.5.27

1. ZIP rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Update Home Assistant naar 10.5.27 en herstart de add-on één keer.
4. Klik **Download analysedata** en stuur het JSON-bestand.

Verwacht voor 2026_08:
- diagnostiek: `price_snapshots_found = 307` of hoger
- diagnostiek: `import_snapshots_found = 307` of hoger
- `reader_status = weighted_ok`
- `monthly_consumption_weighted_electricity` bevat augustus
- `matched_intervals > 0`
- `observed_window_hours > 0`
- `observed_daily_import_run_rate_kwh > 0`
- `observed_daily_variable_cost_run_rate_eur > 0`
- augustus `financial_context.status = partial_observed`
- `months_partially_costable` bevat `2026_08`
- `ready_for_all_in_costs = false`

Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
