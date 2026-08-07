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

- SlimmeMeterPortal Import 7.3.0

Zie `INSTALL.md` en de documentatie in de app-map.


## Fase 7

Versie 7.3.0 bouwt rechtstreeks voort op de stabiele v7.2.0-workflow. Deze release wijzigt uitsluitend de workflowvisualisatie: de voortgang wordt gewogen op basis van de gemeten stapduur, reset direct bij een nieuwe run en toont actieve stap, detail en een indicatieve resterende tijd. De importlogica, rapportgeneratoren, Recovery Update-inhoud en definitieve outputnamen blijven ongewijzigd.

### v7.3.0
- Gewogen voortgang over acht vaste hoofdphasen.
- Directe 0%-reset bij start, hervatten en historische verwerking.
- Vloeiende animatie tijdens lange stappen.
- Actieve stap, subactiviteit en indicatieve resterende tijd zichtbaar.
- Historische runs gebruiken dezelfde 8-fasen telling als de actuele workflow.
- Geen wijzigingen aan import-, rapport- of Recovery Update-backend.
