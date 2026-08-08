# Testinstructies v10.5.19

1. Zet `EnergieProject_v10.5.19.zip` rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Geen Terminal, geen hernoemen, geen tussenextensie.
3. Controleer automatische verwerking naar `processed`.
4. Installeer 10.5.19 in Home Assistant en herstart SlimmeMeterPortal Import één keer.
5. Controleer bovenaan **Sneloverzicht analyse**: tegel `Leverancier` moet `NextEnergy` tonen.
6. Klik **Download analysedata** en stuur het JSON-bestand.

Verwacht in JSON:
- `supplier_context.contract.supplier = NextEnergy`;
- `contract_start = 2026-07-15`;
- `monthly_advance_eur = 150.0`;
- `financial_status.supplier_live_price_connected = true` als de NextEnergy-entiteit beschikbaar is;
- `supplier_context.live_electricity_price.price_eur_per_kwh` bevat de actuele HA-prijs;
- `ready_for_all_in_costs` blijft false totdat ontbrekende contractcomponenten officieel zijn gekoppeld.

Geen Terminal nodig voor de release.

Gebruik GEEN Home Assistant Terminal.
Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
Gebruik GEEN handmatige Git-commit of Git-push.
