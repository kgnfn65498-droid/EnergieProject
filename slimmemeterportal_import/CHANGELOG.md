# Changelog

## 4.7.0

- EPEX v6-elektriciteit en gas gekoppeld via configureerbare bron-URL's.
- CSV-dialect, tekencodering en datum-/tijdkolom worden automatisch herkend.
- Validatie controleert kalendermaand, ontbrekende dagen, dubbele tijdstempels en lege bestanden.
- EPEX-resultaten worden case-sensitive opgeslagen als `EPEX stroom.csv` en `EPEX gas.csv`.
- `EPEX_validation.json` wordt per maand aangemaakt.
- EPEX-bestanden worden automatisch toegevoegd aan de maandmap.
- Nord Pool en NextEnergy blijven aanvullende controlebronnen.
- Nieuwe knop `Importeer en valideer EPEX` in de Web UI.
- Ontbrekende URL's worden expliciet als `not_configured` gemeld.


## 4.6.0

- Eerste volledige maandmap-opbouw toegevoegd onder `/config/output/01_Input/YYYY_MM/`.
- HomeWizard-, Enphase-, Nord Pool- en NextEnergy-maandbestanden worden samengebracht.
- Dubbele records worden per tijdstempel verwijderd.
- Enphase MWh wordt automatisch naar kWh omgerekend.
- Negatieve nulprijzen worden genormaliseerd naar `0.0`.
- Verplichte en optionele bronnen worden afzonderlijk gevalideerd.
- Elke maandmap krijgt `month_input_validation.json` en `month_input_manifest.json`.
- Automatisch ZIP-pakket `01_Input_YYYY_MM.zip` toegevoegd.
- Nieuwe knop `Bouw maandmap` in de Web UI.
- Bestaande bronbestanden worden niet hernoemd of gewijzigd.


## 4.5.0

- Automatische sampling van Home Assistant-energiebronnen toegevoegd.
- Enphase-opwek wordt uit de bestaande Home Assistant Envoy-entiteit gelezen.
- Nord Pool-elektriciteitsprijs wordt automatisch per meetmoment opgeslagen.
- NextEnergy actuele stroomprijs wordt als aanvullende controlebron opgeslagen.
- Maandbestanden worden case-sensitive opgebouwd als `Enphase.csv`, `Nordpool elektriciteit.csv` en `NextEnergy actuele stroomprijs.csv`.
- De bestaande EPEX v6-module blijft de officiële maandprijsbron; Nord Pool en NextEnergy zijn aanvullende actuele bronnen.
- Nieuwe knop `Maak HA energiesnapshot` in de Web UI.
- Sampling draait standaard iedere 15 minuten.


## 4.4.0

- HomeWizard-apparaten worden automatisch gekoppeld aan hun bestaande Home Assistant-namen.
- Koppeling gebruikt actuele cumulatieve kWh-standen en de bestaande Home Assistant `friendly_name`.
- Het HomeWizard-serienummer is de stabiele identiteit; het IP-adres blijft alleen het actuele bereikadres.
- DHCP-wijzigingen kunnen via een nieuwe detectiescan worden bijgewerkt zonder apparaatnamen te verliezen.
- Automatische mapping wordt opgeslagen in `homewizard_mapping.json`.
- P1, Airco, Mobiel en heaters krijgen automatisch de afgesproken case-sensitive uitvoernamen.
- HomeWizard-sampling gebruikt automatisch de opgeslagen mapping wanneer geen handmatige apparaatlijst is ingevuld.
- Home Assistant API-toegang verloopt via de officiële interne Supervisor-proxy en `SUPERVISOR_TOKEN`.


## 4.3.0

- HomeWizard-scan gebruikt standaard het werkelijke thuisnetwerk `192.168.1.0/24`.
- Het interne Home Assistant-netwerk `172.30.0.0/16` wordt expliciet uitgesloten.
- Automatische netwerkbepaling accepteert alleen bruikbare particuliere IPv4-adressen.
- Bij onduidelijk netwerk volgt een concrete configuratiemelding in plaats van een verkeerde scan.
- Detectiestatus en actief scanbereik zijn zichtbaar in de Web UI.
- Bestaande handmatige CIDR-configuratie blijft leidend.


## 4.2.2

- Centrale `CONFIG_ROOT`, `OUTPUT_ROOT`, `STATE_PATH` en `OPTIONS_PATH` toegevoegd.
- HomeWizard-detectie schrijft nu via één vaste opslaglocatie.
- Opslagmappen worden vóór gebruik gecontroleerd en zo nodig aangemaakt.
- Duidelijke foutmelding toegevoegd wanneer de Home Assistant-configopslag niet beschikbaar is.
- Detectieresultaat en aantal gevonden apparaten worden in het log vastgelegd.
- Backendfouten bevatten nu ook het fouttype.


## 4.2.1

- Ontbrekende `ipaddress`-import in de HomeWizard-detectie hersteld.
- Runtime-controle toegevoegd zodat een ontbrekende standaardmodule direct bij opstart wordt gemeld.
- Detectielogica opnieuw statisch en syntactisch gevalideerd.


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
