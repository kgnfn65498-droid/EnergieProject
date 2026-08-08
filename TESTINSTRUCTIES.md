# Testinstructies v10.5.28
1. ZIP rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Update Home Assistant naar 10.5.28 en herstart de add-on één keer.
4. Klik **Download analysedata** en stuur het JSON-bestand.

Verwacht nu:
- augustus blijft `partial_observed`
- gewogen NextEnergy-reeks blijft beschikbaar
- `observed_coverage_days` is ongeveer 3,18 dagen
- `projection_eligibility.eligible = false`
- reden = `insufficient_observation_window`
- `projection_ready_months = []`
- minimum = 7 dagen
- automatische maand- en contractjaarextrapolatie blijven `false`
- `ready_for_all_in_costs = false`

Dit is bewust: de huidige 76,25 uur is nog te kort voor een betrouwbare prognose.
Geen Terminal of handmatige Git-acties.

Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
