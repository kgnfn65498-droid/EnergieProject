# Testinstructies v10.6.1

1. Zet `EnergieProject_v10.6.1.zip` in `EnergieProject_Inbox/incoming`.
2. Laat de QNAP release-watcher de release verwerken.
3. Installeer v10.6.1 in Home Assistant; alleen herstarten wanneer HA dat zelf vraagt.
4. Open de Web UI en controleer versie **10.6.1**.
5. Voer **Analyse-export** uit.
6. Controleer in de JSON `supplier_context.contract_validation`:
   - `policy = official_contract_values_only_no_assumptions`;
   - ontbrekende officiële contractcomponenten staan in `missing_components`;
   - `all_required_components_present = false` zolang het echte contractbestand ontbreekt/onvolledig is.
7. Controleer dat `financial_projection.engine_version = 10.6.1`, de 7-dagen gate behouden blijft en EPEX alleen referentie is.
8. Download release-diagnose en stuur analyse-JSON + diagnose-ZIP terug.

Historische regressievoorwaarden: Gebruik GEEN Home Assistant Terminal. EPEX juli 2026 mag volgens de bestaande bronstatus gedeeltelijk zijn.
Gebruik GEEN handmatige Git-commit of Git-push.
Bestaande EPEX-juli validatie: gedeeltelijk t/m 2026-07-29 is toegestaan.
