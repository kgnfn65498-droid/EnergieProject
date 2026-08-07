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

- SlimmeMeterPortal Import 7.1.5

Zie `INSTALL.md` en de documentatie in de app-map.


## Fase 7

Versie 7.1.5 bouwt daadwerkelijk voort op de geüploade 7.1.4-bron. De v7.1.4-fix voor de dubbele `message`-parameter blijft behouden. Nieuw in 7.1.5: bij de start van een nieuwe workflow worden foutstatus, traceback en oude voortgang van de vorige run direct gewist; de actuele status wordt `running`; en een normaal actieve workflow-lock telt niet langer als gezondheidsfout. Rapportgeneratoren, Recovery Update-inhoud en definitieve outputnamen blijven ongewijzigd.
