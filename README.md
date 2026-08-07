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

- SlimmeMeterPortal Import 7.1.1

Zie `INSTALL.md` en de documentatie in de app-map.


## Fase 7

Versie 7.1.1 is een gerichte hotfix op 7.1.0. Gecontroleerde annuleringen worden niet meer als programmeerfout gelogd, de annuleringsreden wordt expliciet vastgelegd en de maandworkflow krijgt status `cancelled`. De bestaande rapportgeneratoren, Recovery Update-inhoud en definitieve outputnamen blijven ongewijzigd.
