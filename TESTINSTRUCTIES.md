# Testinstructies v10.5.29
1. ZIP rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Update Home Assistant naar 10.5.29 en herstart de add-on één keer.
4. Klik **Download analysedata** en stuur het JSON-bestand.

Verwacht voor augustus:
- gewogen analyse blijft `weighted_ok`
- `observed_coverage_days` is circa 3,2 dagen
- `projection_eligibility.eligible = false`
- `coverage_progress_pct` is circa 45–50%
- `remaining_observation_days` is circa 3,8 dagen
- `projection_observation_status` bevat `2026_08`
- `projection_ready_months = []`
- geen automatische maand- of contractjaarextrapolatie
- `ready_for_all_in_costs = false`

Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
