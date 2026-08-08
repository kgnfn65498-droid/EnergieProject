# Testinstructies v10.5.23
1. ZIP rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Update Home Assistant naar 10.5.23 en herstart de add-on één keer.
4. Klik **Download analysedata** en stuur het JSON-bestand.

Verwacht:
- `financial_status.months_partially_costable` bevat `2026_08`
- augustus `financial_context.status = partial_observed`
- `observed_import_kwh`, `observed_weighted_electricity_price_eur_per_kwh` en `observed_variable_electricity_cost_eur` zijn gevuld
- `supplier_context.cost_model.consumption_weighted_import_available = true`
- `ready_for_all_in_costs = false`

Geen Terminal en geen handmatige Git-acties.

Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
