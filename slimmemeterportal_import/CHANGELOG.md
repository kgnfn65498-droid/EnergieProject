# Changelog

## 6.9.1

- Workflow-lock wist actieve starttijd, maand en stap zodra de workflow klaar is.
- Laatste workflowduur wordt apart opgeslagen.
- HomeWizard-discovery toont direct de gekoppelde apparaatnamen en bestandsnamen.
- Discovery-resultaat wordt na Home Assistant-koppeling opnieuw opgeslagen.
- Rapportgeneratie controleert vooraf alle tien verplichte CSV-bestanden op aanwezigheid en inhoud.
- Eindsamenvatting blijft `completed` na een geslaagde audit en publicatie.
- Deze versie is de stabiele afsluiting van fase 6 vóór versie 7.0.


## 6.9.0

- Globale workflow-lock voorkomt dubbele volledige maandworkflows.
- Een tweede start krijgt status `busy` met actieve maand, stap en starttijd.
- De workflow wacht gecontroleerd op een reeds actieve SlimmeMeterPortal-import.
- Een bestaande afgeronde import voor dezelfde maand kan veilig worden hergebruikt.
- Dubbele-importmelding wordt niet meer als oude fout in de eindsamenvatting meegenomen.
- Workflow-lockstatus, actieve stap en importcoördinatie zijn zichtbaar via een nieuw endpoint.
- Alle locks worden na succes of fout vrijgegeven.
- De werkende rapport-, Recovery_Update- en publicatieketen blijft ongewijzigd.


## 6.8.0

- Automatische retentie toegevoegd voor rapportservice `work`, `output` en `logs`.
- Standaard blijven de laatste drie maandversies bewaard.
- Definitieve bestanden in `02_Output` worden nooit door deze retentie verwijderd.
- Na een geslaagde eindcontrole wordt een compacte workflow-samenvatting opgeslagen.
- Nieuw endpoint en UI-link `Samenvatting` toegevoegd.
- Retentie en samenvatting worden alleen uitgevoerd na een volledig geslaagde workflow.
- Bestaande import-, rapport-, Recovery_Update- en publicatielogica blijft ongewijzigd.


## 6.7.0

- End-to-end eindcontrole toegevoegd na iedere geslaagde maandworkflow.
- Eindcontrole verifieert validatie, runtime, generatoren, adapter, merge en publicatie.
- Exact twee definitieve outputbestanden worden gecontroleerd op naam, grootte en SHA-256.
- Een mislukte eindcontrole zet de rapportworkflow alsnog op `failed`.
- Pagina 1-status wordt tijdens de volledige workflow correct bijgewerkt.
- Nieuw statusendpoint `workflow-audit-status` en link `Eindcontrole` toegevoegd.
- De werkende import-, rapport- en publicatieketen is verder ongewijzigd.


## 6.6.3

- ReportLab en pypdf worden met pip geïnstalleerd in `/usr/local/bin/python3`.
- Dit is dezelfde Python-runtime waarmee de officiële generatorwrappers worden gestart.
- De Docker-build controleert direct of beide modules importeerbaar zijn.
- Nieuwe runtimecontrole toont moduleversies, Python-pad en importlocaties.
- Zelftest blokkeert rapportgeneratie wanneer ReportLab of pypdf ontbreekt.
- Nieuwe knop `Controleer rapportmodules` toegevoegd.
- Geen wijzigingen aan generatorcode, maanddata, bestandsnamen of mappenstructuur.


## 6.6.2

- `sys` wordt nu als echte top-level import geladen.
- De controle kijkt alleen naar de importsectie en niet naar wrappertekst.
- Rapportfouten sluiten de status af als `failed`.
- Geen wijzigingen aan generatoren, databronnen, bestandsnamen of mappen.


## 6.6.1

- Ontbrekende `sys`-import toegevoegd voor het starten van de officiële generatorwrappers.
- Geen wijzigingen aan databronnen, generatorbestanden, outputnamen of mappenstructuur.


## 6.6.0

- Lokale rapportservice staat standaard ingeschakeld.
- De maandworkflow voert automatisch alle drie officiële generatoren uit.
- Rapportdelen worden samengevoegd tot `Energierapport_YYYY_MM.pdf`.
- Recovery_Update bevat uitsluitend `03_Systeem/` en `04_Scripts/`.
- Definitief rapport en Recovery_Update worden gepubliceerd naar `02_Output/YYYY_MM`.
- Publicatie controleert bestandsgrootte en SHA-256-checksum.
- Technische status toont outputmap en gepubliceerde bestanden.


## 6.5.0

- Maanddata-adapter toegevoegd voor pagina 1, pagina 2 en pagina 3-13.
- Adapter leest P1e, P1g en Enphase uit de gevalideerde `01_Input`-map.
- Gemeten verbruik, teruglevering, gas, productie en zelfverbruik worden in generatorschema's gezet.
- De drie officiële generatoren worden automatisch uitgevoerd.
- PDF-delen worden met pypdf samengevoegd tot `Energierapport_YYYY_MM.pdf`.
- Uitvoer wordt gekopieerd naar de lokale rapportservice-outputmap.
- Recovery_Update-handoff ZIP wordt gemaakt; de definitieve projectinhoud blijft voor Recovery Manager.
- Nieuwe handmatige knop toegevoegd om uitsluitend de data-adapter te testen.


## 6.4.0

- De drie aangeleverde officiële generatorpakketten zijn in de app opgenomen.
- Generatorpakketten worden automatisch naar `/share/Energie_Rapportservice/generators/packages` geïnstalleerd.
- Exacte, case-sensitive wrappers worden aangemaakt met de officiële generatornamen.
- Pagina 1, pagina 2 en pagina 3-13 worden hierdoor door de service gedetecteerd.
- ReportLab wordt als runtime-afhankelijkheid geïnstalleerd.
- Nieuwe installatieknop en technische installatiestatus toegevoegd.
- Wrappers stoppen veilig wanneer de maanddata-adapterbestanden nog ontbreken.


## 6.3.0

- Gefaseerde koppeling voor de officiële pagina 1-generator toegevoegd.
- Service onderscheidt `page_1_ready` van volledige generatorgereedheid.
- Nieuwe testknop voert uitsluitend pagina 1 uit.
- Pagina 1 krijgt een eigen resultaatbestand, log en technische statusvelden.
- Uitvoer wordt gecontroleerd op `Energierapport_Pagina1_YYYY_MM.pdf`.
- Ontbrekende pagina 1-generator geeft veilig `waiting_for_page_1`.
- Volledige rapportservice kan pagina 1 alvast uitvoeren terwijl pagina 2 en 3-13 nog ontbreken.


## 6.2.0

- Lokale Rapport Generator Service toegevoegd onder `/share/Energie_Rapportservice`.
- Vaste mappen voor generatoren, werkbestanden, output en logs.
- Officiële generatorbestanden worden case-sensitive gecontroleerd.
- Generatoren worden via een vast CLI-contract aangeroepen.
- Uitvoer wordt gecontroleerd op definitief PDF-rapport en Recovery_Update ZIP.
- Ontbrekende generatoren geven `waiting_for_generators`.
- Configuratie en webknop voor servicecontrole toegevoegd.


## 6.1.0

- Rapportaanvraag wordt ingelezen en technisch gevalideerd.
- Officiële generatornamen en outputcontract worden vóór koppeling gecontroleerd.
- Nieuwe statusvelden volgen start, einde en resultaat van de rapportgeneratie.
- Volledige maandworkflow voert automatisch de rapportgenerator-koppeling uit.
- Bij uitgeschakelde rapportservice blijft de aanvraag veilig op `ready`.
- Nieuwe webknop en statusendpoint toegevoegd voor handmatige test.
- Bij ingeschakelde rapportservice wordt de bestaande beveiligde HTTP-trigger gebruikt.


## 6.0.0

- Nieuwe rapportoverdrachtfase toegevoegd na een geslaagde maandimport.
- Iedere overdracht bevat nu `report_request.json` en een SHA-256-manifest.
- Rapportaanvraag bevat doelmaand, bronpaden, centrale validatie en officiële generatornamen.
- Outputcontract voor definitief rapport en Recovery_Update is vastgelegd.
- Volledige workflow controleert expliciet of de rapportoverdracht gereed is.
- Bestaande HTTP-rapporttrigger kan het handoff-object meesturen wanneer die later wordt ingeschakeld.


## 5.5.0

- Uitgeschakelde EPEX-bronnen worden niet meer als verwachte maandbestanden opgenomen.
- `EPEX stroom.csv` en `EPEX gas.csv` worden alleen verwerkt wanneer die bron expliciet is ingeschakeld.
- Schone maandmap eindigt nu definitief als `completed`.
- Oude `completed_info`-status door uitgeschakelde EPEX wordt automatisch opgeschoond.
- Nord Pool en NextEnergy blijven de actieve prijsbronnen.
- Import-, validatie- en overdrachtslogica blijven verder ongewijzigd.


## 5.4.0

- Genormaliseerde technische statussen worden nu ook permanent opgeslagen.
- `month_input_last_status` wordt na een schone run definitief `completed`.
- Uitgeschakelde EPEX-bronnen worden tijdens iedere workflow teruggezet naar `not_configured`.
- Oude EPEX-foutstatussen worden automatisch opgeschoond.
- Technische status en workflowstatus blijven nu gelijk na herstart.
- Import- en overdrachtslogica blijven ongewijzigd.


## 5.3.0

- Maandmap krijgt alleen `completed_info` wanneer er daadwerkelijk informatiepunten zijn.
- Optionele ontbrekende of lege bestanden worden expliciet vermeld in `infos`.
- Uitgeschakelde EPEX-bronnen krijgen status `not_configured` in plaats van `error`.
- Verouderde EPEX-foutvelden worden automatisch opgeschoond in de technische status.
- Technische status normaliseert oude `completed_info` naar `completed` wanneer geen info-items bestaan.
- Werkende import- en workflowlogica blijft ongewijzigd.


## 5.2.0

- Workflowstatussen volledig gelijkgetrokken: `completed`, `completed_info`, `completed_warning` en `failed`.
- Ontbrekende optionele EPEX-bestanden zijn voortaan informatie en geen waarschuwing.
- Maandmap eindigt als `completed_info` wanneer alleen optionele bronnen ontbreken.
- Volledige workflow eindigt als `completed` zolang alle vereiste bronnen correct zijn.
- Technische status toont EPEX standaard als `not_configured` in plaats van `error`.
- Workflowresultaat bevat een apart `infos`-veld.


## 5.1.0

- Bronafhankelijke validatieprofielen toegevoegd.
- SlimmeMeterPortal-elektriciteit en gas worden correct als één dagrecord per dag gevalideerd.
- HomeWizard- en Nord Pool-profielen zijn afzonderlijk vastgelegd voor vervolgvalidatie.
- De 62 onterechte SlimmeMeterPortal-waarschuwingen verdwijnen.
- Workflowstatussen zijn verduidelijkt naar `completed`, `completed_warning` en `failed`.
- Maandsamenvatting bevat voortaan ook `info_count`.


## 5.0.4

- Volledige maandworkflow kan dezelfde maand veilig opnieuw uitvoeren.
- Bestaande overdrachtsmap wordt alleen binnen de volledige workflow gecontroleerd vervangen.
- Nieuwe overdracht wordt eerst naar een stagingmap gekopieerd en volledig geverifieerd.
- Bestaande overdracht blijft als tijdelijke backup beschikbaar tot de nieuwe kopie en ZIP zijn gecontroleerd.
- Bij iedere fout wordt automatisch teruggedraaid naar de vorige geldige overdracht.
- Losse knop `Maak overdrachtspakket` blijft standaard niet-overschrijvend.
- Workflowresultaat vermeldt of een bestaande overdracht is vervangen.


## 5.0.3

- Maandvalidatie `warning` wordt geaccepteerd wanneer uitsluitend optionele bestanden ontbreken.
- Ontbrekende niet-geconfigureerde EPEX-bestanden blokkeren de workflow niet meer.
- Vereiste ontbrekende of lege bestanden blijven de workflow direct blokkeren.
- Overdrachtspakket accepteert dezelfde gecontroleerde warning-status.
- Workflow eindigt als `warning` in plaats van `error` wanneer alle vereiste bronnen aanwezig zijn.
- Foutmelding noemt voortaan expliciet `missing_required` en `empty_required`.
- Home Assistant meldt een workflow met alleen waarschuwingen als gereed.


## 5.0.2

- Handmatige knop `Verwerk maanddata` heeft nu een expliciete maandkeuze.
- Handmatige tests gebruiken standaard de huidige maand, zodat live snapshots in de juiste maandmap terechtkomen.
- Voor historische maanden worden geen actuele HomeWizard- of Home Assistant-snapshots verkeerd teruggeschreven.
- Historische maanden gebruiken uitsluitend reeds opgebouwde maandbestanden.
- Dubbele foutregels en dubbele foutstappen in het workflowverslag zijn verwijderd.
- Workflowresultaat vermeldt of live snapshots zijn verzameld.


## 5.0.1

- Volledige maandworkflow gebruikt nu de bestaande functie `test_api`.
- Opstartfout `name 'test_api_connection' is not defined` hersteld.
- Regressietest toegevoegd die controleert dat alle directe workflowfuncties bestaan.


## 5.0.0

- Productie-orkestratie toegevoegd met één knop `Verwerk maanddata`.
- Workflow bepaalt standaard automatisch de vorige kalendermaand.
- SlimmeMeterPortal API-test en maandimport worden als eerste uitgevoerd.
- HomeWizard-detectie, HomeWizard-snapshot en Home Assistant-energiesnapshot volgen automatisch.
- EPEX wordt automatisch uitgevoerd wanneer de bronnen zijn geconfigureerd.
- Maandmap wordt gebouwd en verplicht op status `ok` gecontroleerd.
- Gevalideerd overdrachtspakket wordt automatisch gemaakt.
- Workflow stopt standaard direct bij een vereiste fout.
- Alle stappen, tijden, resultaten, waarschuwingen en fouten komen in één `workflow_result.json`.
- Home Assistant ontvangt een succes- of foutmelding.
- De echte NAS-projectmap wordt nog steeds niet automatisch gewijzigd.
- Losse testknoppen blijven beschikbaar voor diagnose en herstel.


## 4.8.0

- Gevalideerde maandmap kan veilig naar de Home Assistant-share worden overgedragen.
- Overdracht wordt geblokkeerd wanneer de maandvalidatie niet `ok` is.
- Standaarddoel is `/share/Energie_Overdracht/YYYY_MM/`.
- Bestaande doelmappen worden standaard nooit overschreven.
- Alle gekopieerde bestanden worden na overdracht opnieuw met SHA-256 gecontroleerd.
- Bij een mislukte verificatie wordt de onvolledige overdracht automatisch verwijderd.
- Het maand-ZIP-bestand wordt meegekopieerd en apart geverifieerd.
- `Overdracht_YYYY_MM.json` documenteert bron, doel en verificatieresultaat.
- Home Assistant krijgt een permanente melding wanneer de overdracht gereed is.
- Nieuwe knop `Maak overdrachtspakket` in de Web UI.
- De echte NAS-projectmap wordt bewust nog niet rechtstreeks gewijzigd.


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
