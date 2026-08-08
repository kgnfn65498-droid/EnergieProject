# EnergieProject v10.5.18

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
