# EnergieProject v10.5.34

v10.5.6 bouwt voort op de in Home Assistant geteste v10.5.5-analysebasis en de bewezen stabiele releaseketen.

Deze release voegt de eerste echte stap van de v10.5 conversatie-/analysebasis toe: een gestandaardiseerde, read-only analysecontext uit de reeds aanwezige maanddata. Via `analysis-context` zijn maand-, kwartaal- en kalenderjaarwaarden machineleesbaar beschikbaar, inclusief kwaliteitsmetadata en markering van onvolledige perioden.

De automatische releaseketen QNAP -> GitHub -> Home Assistant, de maandworkflow, scheduler, retry/finalization, rapportgeneratoren en productiekern `9.4-core1` zijn niet gewijzigd.


## v10.5.7
De analysecontext bevat nu ook read-only historische EPEX-prijscontext per maand: aantal prijsrecords, gemiddelde, minimum en maximum voor elektriciteit en gas. Er worden bewust geen all-in energiekosten berekend zolang leverancierstarieven, belastingen en dekking niet volledig bewezen zijn.


## v10.5.8
De historische analyse leest EPEX nu uit de echte projectbron `05_Maanddata/EPEX`, inclusief de volledigheidsstatus uit `EPEX_index.csv`.


## v10.5.9
EPEX-pad wordt nu automatisch opgelost voor de daadwerkelijke Home Assistant NAS-mount; het gebruikte pad staat in `price_context.resolved_path`.

## v10.5.10
EPEX leest nu primair uit de echte `Energie_NAS/05_Maanddata/EPEX` productieboom.

## v10.5.11
De automatische QNAP-releaseketen is race-safe gemaakt met een atomisch watcher-lock. Recente ZIP's in `processing` worden niet meer ten onrechte als verweesd naar `failed` verplaatst.


## v10.5.12
EPEX wordt automatisch gezocht onder de Home Assistant opslagroots; niet-bestaande fallbackpaden worden niet meer als gevonden gemeld.


## v10.5.14
De releaseketen is nu zelfherstellend en herstart de watcher autonoom na installatie. EPEX kan daarnaast read-only via de bestaande Energie MCP worden gelezen wanneer de NAS-map niet rechtstreeks in de Home Assistant add-on is gemount.


## v10.5.15
De release-watcher wacht niet alleen op stabiele grootte/mtime, maar valideert de ZIP ook zelf vóór de installer. Onvolledige Finder/SMB-kopieën blijven veilig in `incoming`.


## v10.5.16
EPEX-diagnostiek scheidt bronbereikbaarheid van maandbeschikbaarheid.


## v10.5.17
De release-watcher is voorbereid als eigen Container Station-service. Daarmee bewaakt Container Station het proces en herstart het automatisch. De vier bestaande Energie-containers worden niet gewijzigd.


## v10.5.18
Eerste conservatieve financiële analysebasis: alleen kosten bij bewezen overlap van meet- en prijsdata; geen verzonnen terugleververgoeding of leverancier-all-in bedrag.


## v10.5.19
NextEnergy is nu als leveranciercontext gekoppeld. Live prijsdata wordt gebruikt als telemetrie, niet als vervanging voor ontbrekende contractcomponenten.


## v10.5.20
NextEnergy-prijstelemetrie wordt nu ook historisch uit de kwartier-snapshots gelezen. Dit vormt de basis voor latere tijdgewogen en verbruikgewogen financiële analyse.


## v10.5.21
De historische NextEnergy-prijsreader gebruikt nu de werkelijke NAS-bron via de read-only Energie MCP. Daarmee wordt de eerder lege historische prijsreeks beschikbaar zonder bestanden te dupliceren.


## v10.5.22
P1-importdelta's worden nu gekoppeld aan de NextEnergy-prijs uit dezelfde kwartiersnapshots voor een echte verbruikgewogen prijs.


## v10.5.23
De bewezen verbruikgewogen NextEnergy-kosten zijn nu onderdeel van de financiële maandcontext.


## v10.5.24
De financiële analyse kent nu naast geobserveerde kosten ook de exacte meetduur en dag-run-rate, zonder die als volledige maandprognose te misbruiken.


## v10.5.25
De kwartierreader is robuuster gemaakt: volledige snapshot-JSON via MCP is nu leidend. Daarmee wordt de regressie waarbij de gewogen reeks in 10.5.24 leeg werd structureel aangepakt.


## v10.5.26
De NAS/MCP-reader gebruikt nu de echte toolnamen `search_files` en `read_text_file` en leest `matches` correct uit.


## v10.5.27
Herstelt de ontbrekende `timezone`-import die in 10.5.26 pas na succesvol laden van de 307+307 snapshots zichtbaar werd.


## v10.5.28
Financiële run-rates krijgen nu een harde kwaliteitsdrempel: pas vanaf zeven dagen echte waarneming wordt een maand prognosegeschikt gemarkeerd. Er wordt nog niet automatisch geëxtrapoleerd.


## v10.5.29
De financiële analyse toont nu hoe ver de echte meetdekking richting de 7-dagendrempel is gevorderd, zonder al te extrapoleren.


## v10.5.30
De kern van de v10.6 prognose-engine staat nu klaar achter de 7-dagen kwaliteitsgate. Er worden vóór die drempel bewust geen projectiewaarden gepubliceerd.


## v10.5.31
De 10.6-projectielogica kan nu tegen echte data worden gevalideerd zonder de 7-dagenbeveiliging te omzeilen.


## v10.5.32
De Web UI kan nu een compacte release-diagnose downloaden voor actuele én oudere mislukte releases, zonder energiedata of geheimen.


## v10.5.33
Financiële bouwstatus richting 10.6 wordt nu expliciet gemeten. De €150 maandtermijn wordt alleen vergeleken met de kandidaat variabele stroomkosten en nooit als all-in conclusie gebruikt.


## v10.5.34
Officiële NextEnergy-contractcomponenten kunnen nu veilig via een apart configuratiebestand in de financiële motor worden opgenomen. Ontbrekende waarden blijven null.
