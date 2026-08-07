# Energie Home Assistant Apps

Home Assistant app-repository voor het Energieproject.

## Repository toevoegen

Voeg deze openbare repository toe in Home Assistant:

`https://github.com/kgnfn65498-droid/EnergieProject`

## Veiligheid

- API-sleutels staan uitsluitend in de Home Assistant-appconfiguratie.
- `.env`-bestanden, maanddata, rapporten en back-ups horen niet in GitHub.
- De productieketen GitHub → Home Assistant Green → UserAPI → maandpakket is gevalideerd.
- De webinterface is uitsluitend via Home Assistant Ingress bereikbaar.

## Beschikbaar

- SlimmeMeterPortal Import 7.2.0

Zie `INSTALL.md` en de documentatie in de app-map.


## Fase 7

Versie 7.2.0 bouwt voort op de stabiele 7.1.6-backend. Deze release wijzigt uitsluitend de operationele gebruikersinterface: het live workflowlog wordt nu rechtstreeks via de operationele status meegeleverd en weergegeven, statuspillen en gezondheidschecks verversen live, en de volledige zelftest krijgt een leesbare resultaatpagina in plaats van ruwe JSON. Rapportgeneratoren, Recovery Update-inhoud en definitieve outputnamen blijven ongewijzigd.

### v7.2.0
- Betrouwbare live logweergave via `operation-status` zonder tweede log-fetch.
- Automatische statuskleur- en gezondheidsrefresh tijdens workflowruns.
- Leesbare HTML-uitvoer voor **Voer volledige zelftest uit**.
- Geen wijzigingen aan import-, rapport- of Recovery Update-backend.
