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

- SlimmeMeterPortal Import 7.8.0

Zie `INSTALL.md` en de documentatie in de app-map.


## Fase 7

Versie 7.3.6 bouwt voort op de stabiele v7.3.1-workflow. Deze release herstelt historische maandverwerking zonder actuele snapshots als historische data te gebruiken. Bij een historische run worden exact benoemde bestaande maandbestanden ook recursief gezocht in de echte `/config/output/YYYY_MM`-maandboom achter de downloadknop en in reeds bewaarde maand-ZIP-archieven.

### v7.3.6

- Historische snapshot-skip is informatief; foutloze historische workflows eindigen als `completed`.

Historische verwerking eindigt nu groen wanneer alleen rapportgeneratie bewust wordt overgeslagen wegens niet-beschikbare historische detailbronnen. Deze situatie is informatief en geen waarschuwing.

- Herstel historische maanddata uit bestaande, exact benoemde bronnen.
- Zoek ook recursief in `/config/output/YYYY_MM`, het overdrachtspakket en bestaande maand-ZIP-archieven.
- Bestaande bestanden worden nooit overschreven of hernoemd.
- Actuele HomeWizard/HA-snapshots worden nooit als historische data gebruikt.
- Validatiefouten vermelden voortaan alle gecontroleerde historische bronpaden.
- Gewogen 8-fasenvoortgang uit v7.3.0 blijft behouden.
- Geen wijzigingen aan officiële rapportgeneratoren, Recovery Update-contract of vaste outputnamen.


### v7.4.0

Workflow-broncoördinatie en eindvalidatie. Voor een actuele doelmaand wordt een geconfigureerde Enphase-bron automatisch meegenomen. Direct na het bouwen van `01_Input/YYYY_MM` voert de workflow een doelmaandgebonden eindvalidatie uit vóór overdracht en rapportage. Een actueel rapport wordt alleen gestart wanneer de rapportinput compleet is. Historische runs blijven bronbeschikbaarheid-gestuurd en halen geen actuele Enphase-data op om historische maanden te vullen.


### v7.5.0

Productieharde automatische maandafsluiting met preflight en expliciete eindcontrole op rapport en Recovery Update.


### v7.7.0

Automatische maandafsluiting is nu rechtstreeks vanuit de operationele console in te stellen en gecontroleerd te testen. De test voert de echte preflight, maandworkflow en finalization uit zonder de schedulermaand als reeds automatisch verwerkt te markeren.


### v7.8.0
Versiegebonden productieteststatus en één duidelijke automatische-gereedheidscontrole.
