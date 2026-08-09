# Testinstructies v10.5.31
1. ZIP rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Update Home Assistant naar 10.5.31 en herstart de add-on één keer.
4. Klik **Download analysedata** en stuur het JSON-bestand.

Verwacht:
- bestaande gewogen analyse blijft `weighted_ok`
- `projection_engine.stage = prepared_gated`
- `component_readiness.weighted_electricity_import = true`
- `component_readiness.observation_quality_gate = true`
- `component_readiness.thirty_day_variable_projection = true`
- leveranciersopslag, vaste kosten, terugleververgoeding en gasformule blijven `false`
- bij minder dan 7 dagen blijven 30-dagenprojectiewaarden `null`
- `ready_for_all_in_costs = false`

Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
