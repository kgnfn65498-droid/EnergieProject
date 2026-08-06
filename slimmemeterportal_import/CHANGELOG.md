# Changelog

## 3.9.3

- Startscript naar de app-hoofdmap verplaatst.
- Zichtbare launcher- en Python-startlogging toegevoegd.
- Python ongebufferd gestart zodat fouten direct in Home Assistant verschijnen.
- Logging bij initialisatie geforceerd geactiveerd.


## 3.9.2

- Blokkerende opstartfout in de maandimport opgelost.
- Resultaatstatus wordt pas opgeslagen nadat validatie en bundelvorming bestaan.
- Configureerbaar UserAPI-pad voor dagdata toegevoegd.
- API-fouten vermelden nu het gebruikte pad, zonder de API-sleutel te loggen.
- Extra regressietests tegen gebruik van variabelen vóór initialisatie.


## 3.9.1

- GitHub-repository-URL gecorrigeerd.
- Dockerlabels toegevoegd voor lokale Home Assistant-builds.
- Ingress-webserver beperkt tot de Home Assistant Ingress-gateway.
- Watchdog-healthcheck toegevoegd.
- Experimentele status vastgelegd tot de Green-praktijktest is geslaagd.
- Git-uitsluitingen voor geheimen en tijdelijke bestanden aangescherpt.


## 3.9.0

- Volledige ingebouwde zelftest toegevoegd.
- Controle op configuratie, opslag, SlimmeMeterPortal API en workflowbronnen.
- Installatiestatus zichtbaar in de webinterface en healthcheck.
- Definitieve installatiehandleiding toegevoegd.
- Extra regressietests voor zelftest en installatiegereedheid.


## 3.8.0

- Centrale maandvalidatie toegevoegd.
- `central_validation.json` per maand.
- Controle op gereedheid van alle ingeschakelde kernbronnen.
- Configureerbare rapporttrigger via HTTP POST.
- Bearer-tokenondersteuning voor rapporttrigger.
- `report_trigger_result.json` per maand.
- Handmatige knop **Voer centrale validatie uit**.
- Centrale validatie en rapporttrigger zichtbaar in webinterface en healthcheck.
- Extra regressietests voor validatie en rapporttrigger.


## 3.7.0

- Enphase-adapter toegevoegd via configureerbare HTTPS-bron.
- Optionele Bearer-token voor Enphase.
- EPEX-elektriciteitsadapter toegevoegd.
- EPEX-gasadapter toegevoegd.
- Bronnen slaan JSON, CSV of binaire inhoud op zonder stil verlies.
- Handmatige importknoppen per externe bron.
- Status en fouten opgenomen in webinterface en healthcheck.
- Extra regressietests voor Enphase- en EPEX-configuratie.


## 3.6.0

- HomeWizard-adapter toegevoegd via de lokale `/api/v1/data`-interface.
- Configuratie voor P1, gas, sockets en overige HomeWizard-apparaten.
- Automatische snapshots met instelbaar interval.
- Handmatige knop **Maak HomeWizard snapshot**.
- Verplichte en optionele apparaten worden apart behandeld.
- JSON- en JSONL-opslag per maand.
- HomeWizard-status opgenomen in webinterface en healthcheck.
- Extra regressietests voor HomeWizard-configuratie en endpoints.


## 3.5.0

- Centrale workflowmodus toegevoegd.
- Bronstatusmodel voor SlimmeMeterPortal, HomeWizard, Enphase en EPEX.
- Automatisch overdrachtspakket `Energie_Maandimport_YYYY_MM.zip`.
- Overdrachtspakket en bronstatus zichtbaar in webinterface en healthcheck.
- Voorbereiding op volledige maandworkflow zonder bestaande SMP-functionaliteit te breken.
- Extra regressietests voor workflow- en bundelfuncties.


## 3.4.0

- Detectie en rapportage van dubbele records.
- `month_summary.json` met totalen per aansluiting en maand.
- Automatische numerieke veldsamenvatting.
- Records en duplicaten zichtbaar in de webinterface.
- Healthcheck uitgebreid met maandsamenvatting.
- Extra regressietests voor duplicaten en maandtotalen.


## 3.3.0

- Integriteitscontrole na iedere import.
- `integrity_report.json` per maand.
- Handmatige knop om de laatste maand opnieuw te verifiëren.
- Uitgebreidere healthcheck.
- Optioneel falen bij validatiefouten.
- Nieuwe regressietests voor manifest- en integriteitsfuncties.


## 3.2.0

- Hervatten van onvolledige maandimport op basis van reeds opgeslagen dag-JSON.
- Voortgangsregistratie per dag en aansluiting.
- Annuleerknop voor actieve imports.
- SHA-256 manifest per maanduitvoer.
- Instelbare retentie van maandmappen.
- `.incomplete`-markering tijdens lopende imports.
- Extra regressietests voor configuratie en broncode.


## 3.1.0

- Kritieke deadlock in statusopslag opgelost.
- API-verbindingstest toegevoegd.
- Healthcheck-endpoint toegevoegd.
- Maanduitvoer rechtstreeks als ZIP downloadbaar.
- Atomaire status- en JSON-opslag.
- Afzonderlijke waarschuwingen en fouten in validatierapport.
- Extra validatie van configuratiewaarden.
- Robuustere foutafhandeling en logging.

## 3.0.0

- Productierepository voor normale Home Assistant-updates.
- Officiële UserAPI, zonder externe library.
- Handmatige importknop en maandkeuze.
- Automatische maandplanning.
- Ruwe JSON, CSV, JSONL en validatierapport.
- DST-bewuste recordcontrole.
