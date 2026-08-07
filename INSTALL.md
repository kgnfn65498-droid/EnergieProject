# Definitieve installatie op Home Assistant Green

## Eenmalige installatie

1. Plaats deze repository op een openbare HTTPS Git-repository.
2. Voeg de repository-URL toe in Home Assistant:
   **Instellingen → Apps → App-winkel → Repositories**.
3. Installeer **SlimmeMeterPortal Import**.
4. Vul minimaal de API-key in.
5. Start de app.
6. Open de webinterface.
7. Klik **Voer volledige zelftest uit**.
8. De installatie is gereed wanneer:
   - `Installatie gereed` = `Ja`
   - Zelftestpagina toont **ALLE TESTS GESLAAGD** of een duidelijke waarschuwing
   - SlimmeMeterPortal API = `ok`

## Eerste productietest

1. Zet planning tijdelijk uit.
2. Importeer één afgeronde kalendermaand.
3. Controleer:
   - `validation_report.json`
   - `integrity_report.json`
   - `central_validation.json`
   - `month_summary.json`
   - overdrachtspakket ZIP
4. Zet daarna de maandplanning aan.

## Updates

Na publicatie via een Git-repository worden nieuwe versies via de normale
Home Assistant-knop **Update** aangeboden.
