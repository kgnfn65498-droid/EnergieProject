# Testinstructies v10.5.35

1. Zet `EnergieProject_v10.5.35.zip` rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Installeer de Home Assistant-update.
4. Download **analysedata** en **release-diagnose** en stuur beide hier.

Verwacht zonder ingevuld contractkostenbestand:
- versie 10.5.35;
- bestaande gewogen NextEnergy-analyse blijft `weighted_ok`;
- contractkosten blijven `available=false`, `valid=false`;
- nieuwe `observed_supplier_component_costs` bestaat maar `available=false`;
- kandidaatprojectie bevat nieuwe leveranciercomponentvelden, maar die blijven `null`;
- `supplier_contract_costs_connected=false`;
- `export_credit_connected=false`;
- `ready_for_all_in_costs=false`;
- geen verzonnen contracttarieven;
- release-diagnose blijft werken.

Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
