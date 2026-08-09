# Testinstructies v10.6.0

1. Zet `EnergieProject_v10.6.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht tot de QNAP release-watcher de ZIP naar `processed` verplaatst en Home Assistant de update ziet.
3. Installeer v10.6.0. Een extra handmatige HA-herstart is niet nodig tenzij Home Assistant die zelf vraagt.
4. Open de Web UI en controleer dat versie **10.6.0** zichtbaar is en de GUI normaal opent.
5. Voer **Analyse-export** uit en download de analyse-JSON.
6. Controleer in `supplier_context.cost_model.projection_engine` dat `stage` = `production_active`.
7. Controleer bij de actuele maand `financial_context.financial_projection`:
   - na >=7 waargenomen dagen: `status` = `published` en de 30-dagen import/variabele stroomkosten zijn gevuld;
   - vóór 7 dagen: `status` = `blocked_insufficient_observation` en de officiële prognosewaarden blijven `null`.
8. Controleer dat `supplier_all_in_projection_eur` `null` blijft zolang officiële contractcomponenten ontbreken.
9. Open Rapportpagina en controleer dat deze nog normaal werkt.

Verwacht: financiële v10.6-engine actief zonder verzonnen contractwaarden en zonder regressie in GUI/release/rapportketen.

Gebruik GEEN Home Assistant Terminal en GEEN handmatige Git-commit/push.

Gebruik GEEN Home Assistant Terminal.
Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
Gebruik GEEN handmatige Git-commit of Git-push.
