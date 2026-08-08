# Testinstructies v10.5.22

1. Zet `EnergieProject_v10.5.22.zip` rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Controleer verwerking naar `processed`.
3. Update Home Assistant naar 10.5.22 en herstart SlimmeMeterPortal Import één keer.
4. Klik **Download analysedata** en stuur het JSON-bestand.

Verwacht in `monthly_consumption_weighted_electricity` voor 2026_08:
- `available = true`
- `matched_intervals > 0`
- `import_kwh_observed > 0`
- `weighted_average_eur_per_kwh > 0`
- `observed_import_cost_eur > 0`
- `coverage = partial_observed_window`
- `quality = consumption_weighted_observed`

`ready_for_all_in_costs` blijft false.
Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
