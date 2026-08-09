# Testinstructies v10.5.36

1. Zet `EnergieProject_v10.5.36.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Installeer de Home Assistant-update.
4. Download **analysedata** en **release-diagnose** en stuur beide hier.

Verwacht:
- versie 10.5.36;
- watcher/installatie blijft normaal werken;
- gewogen NextEnergy-analyse blijft `weighted_ok`;
- `contract_formula_preview` staat bij augustus;
- zonder officieel contractkostenbestand zijn export en gas `available=false` met expliciete reden;
- er worden geen tarieven aangenomen;
- `ready_for_all_in_costs=false` zolang contractcomponenten ontbreken;
- release-diagnose blijft werken.

Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
