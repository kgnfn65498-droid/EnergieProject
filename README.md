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

- SlimmeMeterPortal Import 7.1.3

Zie `INSTALL.md` en de documentatie in de app-map.


## Fase 7

Versie 7.1.3 is een diagnostische hotfix op 7.1.2. Workflowfouten bewaren nu stap, fouttype, volledige traceback en doorlooptijd, worden direct zichtbaar in de operationele console en het workflowlog is downloadbaar. De stabiliteitsmaatregelen uit 7.1.2 en de bestaande rapportgeneratoren, Recovery Update-inhoud en definitieve outputnamen blijven ongewijzigd.
