# Changelog

## 4.2.0

- Automatische HomeWizard-detectie binnen één expliciet of automatisch bepaald IPv4-/24-netwerk.
- P1-meter, Energy Socket en overige HomeWizard-apparaten worden via de lokale API herkend.
- Detectieresultaten bevatten IP-adres, apparaatinfo, voorbeeldmeting, voorgestelde rol en uitvoernaam.
- Detectieresultaten worden opgeslagen als `homewizard_discovery.json`.
- Webinterface bevat de knop `Detecteer HomeWizard-apparaten`.
- Netwerkscan is bewust beperkt tot maximaal één /24-netwerk.
- Bestaande apparaatconfiguratie wordt niet automatisch gewijzigd.


## 4.1.0

- Automatische HomeWizard-sampling voor P1-meter en Energy Sockets.
- Per apparaat worden zowel `/api`-apparaatgegevens als `/api/v1/data`-metingen vastgelegd.
- Maandelijkse CSV-reeksen worden vanaf installatie continu opgebouwd.
- P1-elektriciteit wordt opgeslagen als `P1e.csv`.
- Gas uit de P1-meter wordt opgeslagen als `P1g.csv`.
- Energy Sockets worden opgeslagen met het geconfigureerde `output_name` of `<label> Skt.csv`.
- Ruwe snapshots blijven daarnaast als JSON en JSONL beschikbaar.
- Status bevat nu apparaatcount en aangemaakte maand-CSV-bestanden.
- Er worden geen bestaande bestanden hernoemd; uitvoernamen zijn expliciet en case-sensitive.


## 4.0.0

- Productieversie van de SlimmeMeterPortal-maandimport.
- Uitgeschakelde HomeWizard-, Enphase- en EPEX-bronnen veroorzaken geen onterechte centrale waarschuwing meer.
- Alleen daadwerkelijk geactiveerde bronnen worden als vereiste bron gevalideerd.
- Bewust uitgeschakelde rapporttrigger geldt niet langer als zelftestwaarschuwing.
- Automatische zelftest wordt na iedere start uitgevoerd.
- `Installatie gereed` wordt automatisch bijgewerkt op basis van configuratie, opslag en API-bereikbaarheid.
- Experimentele status verwijderd na geslaagde GitHub-, installatie-, API-, import- en integriteitstest.


## 3.9.4

- Manifest wordt pas gemaakt nadat alle inhoudelijke maandbestanden definitief zijn.
- `integrity_report.json` en `report_trigger_result.json` zijn uitgesloten van de zelfreferentiële integriteitsketen.
- Overdrachtspakket wordt pas na manifest- en integriteitscontrole gebouwd.
- Bestaande v3.9.2/v3.9.3-maanden met uitsluitend de bekende drie volgordefouten worden veilig hersteld zonder nieuwe API-import.
- Andere hash-, grootte- of ontbrekende-bestandsfouten blijven ongewijzigd als echte integriteitsfout gemeld.


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
