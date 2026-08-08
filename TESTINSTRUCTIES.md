# Testinstructies v10.5.24

1. ZIP rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Update Home Assistant naar 10.5.24 en herstart de add-on één keer.
4. Klik **Download analysedata** en stuur het JSON-bestand.

Verwacht voor augustus:
- `financial_context.status = partial_observed`
- `observed_window_hours > 0`
- `observed_daily_import_run_rate_kwh > 0`
- `observed_daily_variable_cost_run_rate_eur > 0`
- bestaande verbruikgewogen prijs en €5,11 geobserveerde kosten blijven aanwezig
- `ready_for_all_in_costs = false`

Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
