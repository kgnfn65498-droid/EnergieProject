# Testinstructies v10.5.34

1. Zet `EnergieProject_v10.5.34.zip` rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Wacht op automatische verwerking naar `processed`.
3. Installeer de Home Assistant-update naar 10.5.34.
4. Download **analysedata** en **release-diagnose** en stuur beide hier.

Verwacht zonder handmatig contractkostenbestand:
- versie 10.5.34;
- gewogen NextEnergy-analyse blijft `weighted_ok`;
- `supplier_context.contract_costs.available = false`;
- `supplier_context.contract_costs.valid = false`;
- validatiefout bevat `contract_costs_file_not_found`;
- vaste kosten/opslag/terugleververgoeding/gasformule blijven `known=false`;
- `ready_for_all_in_costs = false`;
- bestaande financiële readiness blijft correct;
- release-diagnose blijft werken.

Release bevat:
`00_Config/nextenergy_contract_costs.example.json`

Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
