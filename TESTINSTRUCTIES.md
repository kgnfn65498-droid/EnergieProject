# Testinstructies v10.5.30
1. ZIP rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Update Home Assistant naar 10.5.30 en herstart de add-on één keer.
4. Klik **Download analysedata** en stuur het JSON-bestand.

Verwacht bij de huidige ~3,2 dagen:
- bestaande gewogen analyse blijft `weighted_ok`
- `projection_engine.stage = prepared_gated`
- `projection_engine.target_release = 10.6`
- `thirty_day_variable_projection_logic_ready = true`
- `projection_preview.status = blocked_insufficient_observation`
- beide 30-dagenprojectiewaarden zijn nog `null`
- supplier-all-in projectie blijft `false`
- bestaande 7-dagen voortgang blijft correct

Geen Terminal of handmatige Git-acties.

Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
