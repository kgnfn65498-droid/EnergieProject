# EnergieProject v9.1.0

Deze release verfijnt de operationele productieconsole van v9.0.0 zonder de gecertificeerde workflowkern te wijzigen. Productiegereedheid en systeemgezondheid worden duidelijker van elkaar onderscheiden.

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

- SlimmeMeterPortal Import 9.1.0

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


### v7.9.0
Fix voor de veilige productietest: `automatic_test` is nu een geldige centrale workflow-trigger.


### v8.0.0
Productiebaseline met versiegebonden scheduler-gate en centrale productiestatus.


### v8.1.0
Upgradeveilige scheduler-gate, leesbare planning en automatische maandhistorie.


### v8.2.0
Direct opgeslagen scheduler-schakelaar, side-effect-vrije productietest en outputintegriteitscontrole.


### v8.3.0
Directe acceptatietest van de echte automatische schedulerroute.


### v8.4.0
Auditbare schedulerhistorie en expliciete Aan/Uit-invariant voor acceptatietests.


### v8.5.0
Append-only automatische runhistorie.


### v8.5.1
Scheduler-acceptatietest voert ontbrekende actuele productietest automatisch veilig uit voordat de productie-schedulerroute wordt gesimuleerd.


### v8.6.0
Duurzame restart- en dubbelstartbeveiliging voor echte automatische maandafsluitingen.


### v8.7.0
Zichtbare automatische retry-/herstelstatus en duidelijkere scheduler-acceptatietekst.


### v8.8.0
Conservatieve opschoning van verouderde retry-state met expliciete retry-maand, reden en oorsprong.


### v8.9.0
Persistente retry-state-machine met veilige migratie op basis van productie-auditbewijs.


### v8.9.1
Bugfix: legacy retry-migratie controleert ook volledig geslaagde historische automatische workflowresultaten.


### v8.10.0
Diagnoseversie voor legacy retry: volledige bron- en beslistrace zonder functionele wijziging van de retrylogica.


### v8.10.1
Finalisatie-diagnose: volledige trace van workflow_result tot completion-marker, automatische historie en workflow-lock.


### v8.11.0
Legacy voltooiingsfix voor retry-evidence en consistente terminale stapstatussen.


### v8.12.0
Productiefix voor definitieve afsluiting van bewezen afgeronde legacy retries.

### v8.13.0
Duurzame productieacceptatie na een geslaagde veilige productietest van exact de actieve versie.


### v8.14.0
Production Lifecycle Manager met persistent gehasht productiecertificaat en runtime-validatie.
