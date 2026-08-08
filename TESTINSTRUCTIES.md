# Testinstructies v10.5.20

1. Zet `EnergieProject_v10.5.20.zip` rechtstreeks in `EnergieProject_Inbox/incoming`.
2. Controleer automatische verwerking naar `processed`.
3. Installeer/update 10.5.20 in Home Assistant en herstart SlimmeMeterPortal Import één keer.
4. Klik **Download analysedata** en stuur het JSON-bestand.

Verwacht:
- versie `10.5.20`;
- `financial_status.supplier_live_price_connected = true`;
- `financial_status.supplier_price_history_connected = true`;
- `supplier_context.monthly_electricity_price_telemetry` bevat augustus 2026;
- augustus bevat meerdere observaties met gemiddelde/minimum/maximum;
- `quality = observed_unweighted`;
- `ready_for_all_in_costs` blijft false.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
