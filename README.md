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

- SlimmeMeterPortal Import 7.1.0

Zie `INSTALL.md` en de documentatie in de app-map.


## Fase 7

Versie 7.1.0 bouwt voort op de stabiele 7.0.1-console en voegt een centrale achtergrondworkflow, hervatten na een mislukte run, een live workflowlog en een gezondheidsdashboard toe. De bestaande rapportgeneratoren, Recovery Update-inhoud en definitieve outputnamen blijven ongewijzigd.
