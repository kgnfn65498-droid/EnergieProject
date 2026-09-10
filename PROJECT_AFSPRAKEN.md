# Vaste ontwikkelafspraken Energieproject

- Als de gebruiker zegt `bouw X.Y`, bouw daadwerkelijk een complete nieuwe productieversie op de vorige geteste versie.
- Iedere build levert: complete ZIP, changelog, kopieerbare committekst en testinstructies onderaan.
- Na iedere versie wachten op de Home Assistant-testresultaten voordat de volgende versie wordt gebouwd.
- Terugkerende testhandelingen automatiseren; normaal beoordelen via één diagnosepakket. Screenshots alleen bij visuele/interactieve problemen.
- De iMac mag weken uitstaan en mag geen noodzakelijke schakel zijn in de productieketen.
- Productiedata, maandverwerking en back-ups moeten 24/7 via Home Assistant/QNAP kunnen doorlopen.
- Recovery Manager blijft primair voor echte calamiteiten/crash recovery; noodherstel moet met een korte actuele handleiding kunnen.
- Als een chat traag/vol wordt, wordt een chat-overdracht gemaakt met status, roadmap, afspraken en open acties.
- Grote architectuurkeuzes bij voorkeur eerst kort bespreken in een spraaksessie.
- Einddoel: vragen in gewone taal; data-inname, opslag, validatie, back-up en voorbereiding verlopen automatisch.
- Financiële analyse bewaakt termijnbedrag, werkelijke kosten, historische data, terugverdientijd en marktopties; geen ongefundeerde schattingen.
- Toekomstige analyse bevat weersverwachting, dynamische prijzen en proactieve energie-/investeringssignalen.

- Normale Home Assistant-releaseprocedure: app updaten/herstarten en GUI verversen. `Opnieuw opbouwen` alleen bij aantoonbare image-/cacheproblemen of buildlaagwijzigingen.
- Gewenste korte releaseflow: gebruiker downloadt release-ZIP en plaatst die uiteindelijk alleen in een vaste NAS-inbox; verdere validatie/verwerking wordt geautomatiseerd.
- Een NAS-migratie mag nooit blind bestanden verplaatsen: eerst inventaris, daarna hashcontrole, rollback en pas daarna opruimen.

## Release-uitvoering vanaf v10.4.1
- Installer en watcher mogen nooit afhankelijk blijven van een scriptbestand in de worktree die zij vervangen.
- Beide host-side processen verplaatsen hun actieve script daarom naar `/tmp` vóór releaseverwerking.
- Een release die tijdens worktree-verwijdering faalt moet automatisch uit de vooraf gevalideerde tar-backup herstellen.

## Release- en leercontract vanaf 32.4.16
- De normale releaseflow is uitsluitend: `incoming -> processing -> processed`; tijdelijke hold-mappen of handmatige atomic accept-commando's tellen nooit als structurele oplossing.
- Een releaseclosure is pas groen nadat een opvolgende synthetische release tijdens/na acceptance automatisch kan worden opgepakt zonder gebruikersinterventie.
- Bij ieder defect worden symptoom, root cause, structurele fix en regressietest in de Projectmanager Knowledge Base vastgelegd.
- Tests die alleen de huidige release accepteren zijn onvoldoende voor ingress-closure; de volgende release moet onderdeel zijn van de E2E.
- Een release-ZIP wordt nooit rechtstreeks uit een door tests vervuilde werkboom gemaakt: eerst schone staging, expliciete uitsluiting van `.pytest_cache`, `__pycache__`, `.DS_Store`, `*.pyc` en `*.pyo`, daarna manifests, ZIP en tenslotte validatie met dezelfde atomic release-validator als productie.
- Vanaf 32.4.30 wordt een overdraagbare release-ZIP uitsluitend met `tools/release_artifact_builder.py` gebouwd; een ad-hoc ZIP-commando geldt niet als releasebewijs. De exacte uiteindelijke ZIP-bytes moeten daarna nog een volledige geïsoleerde `atomic_app_swap prepare-and-swap` simulatie doorstaan vóór handoff.

## Release- en leercontract vanaf 32.4.17

- Een watchercontainer die `Up` is is geen bewijs van een gezonde watcher; heartbeat en voortgang moeten vers blijven.
- Externe helpers in een kritieke watcher-hoofdlus mogen nooit onbeperkt kunnen blokkeren; zij zijn bounded en fail-closed.
- Runtime-health is release-scoped: historische publisherfouten mogen een nieuwere bewezen release niet rood maken.
- Een safety-hold mag zijn eigen validatie niet circulair blokkeren. Alleen de exact verwachte eigen transition-state mag tijdelijk als acceptance-context gelden.
- Bij release-audits worden containerstatus, heartbeat, atomic state, hold, publisher/publication en volgende-ingress als één E2E-keten gecontroleerd.
- Packaging gebeurt uitsluitend vanuit een schone stagingboom; cache/junk is een harde releasefout.
## Release- en leercontract vanaf 32.4.18

- Release-hold en atomic journal worden als één herstelbare state-machine behandeld; alle relevante combinaties moeten na restart idempotent convergeren.
- Normale veilige closurevolgorde: validatie groen -> atomic `ACCEPTED` -> release-hold vrijgeven.
- `inactive hold + LIVE_ACCEPTANCE` mag alleen automatisch herstellen wanneer de persisted hold een normale eerdere validatie (`validation_status=ok`, `reconcile_status=ok`, geen emergency) bewijst en een verse validatie opnieuw groen is.
- GitHub-publicatie heeft één canonieke actuele statusbron per release. Historische statusbestanden mogen niet als actuele waarheid concurreren.
- Heartbeat-kritieke subprocessen hebben een harde bovengrens: TERM, korte grace, daarna KILL; fail-closed blijft verplicht.
- Voor closure zijn **twee opeenvolgende releases** plus restart/crash-vensters een verplichte regressie; alleen een losse current-release acceptance is onvoldoende.
- Release-acceptance mag niet gekoppeld zijn aan algemene energie-operatiehealth. Sensor-/kwartierdata-RED blijft zichtbaar en actionable, maar alleen release-chain health en de expliciete release-validatiechecks mogen de release-hold blokkeren.



## Release-health contract vanaf 32.4.19
- Een heartbeat-bestand met expliciete Unix-epoch payload gebruikt die payload als canonieke liveness-truth; NAS/SMB-mtime mag geen verse watcher tot RED degraderen.
- Een parseerbare stale heartbeat-payload blijft fail-closed RED, ook als bestandsmetadata vers is.
- Shell-gates bewaren de echte child-returncode voordat conditionele shellcontrol-flow die waarde kan overschrijven; capability-denial en technische fout worden verschillend behandeld.
- Release-closure wordt pas groen verklaard nadat live is bewezen dat `LIVE_ACCEPTANCE -> ACCEPTED` zonder handmatig accept-commando gebeurt en een opvolgende ingress wordt vrijgegeven.
## Release-health contract vanaf 32.4.20
- Liveness tussen verschillende hosts mag niet uitsluitend op absolute wall-clock timestamps worden gebaseerd; QNAP en Home Assistant kunnen klokskew hebben.
- Wanneer heartbeat-epoch stale of future lijkt, moet de collector een begrensde pulsverandering waarnemen. Een veranderende payload is clock-onafhankelijk bewijs dat de watcher leeft.
- Geen puls binnen het probevenster blijft fail-closed RED; clock-skew mag nooit worden omzeild door een algemene GREEN-exceptie.
- Release-closure mag pas doorgaan nadat watcher-liveness, publication, hold-state en atomic transition ieder via hun eigen broncontract zijn bewezen.
- Verschillende namespace-paden (`/share/...` in Home Assistant versus QNAP-lokaal) zijn geen split-brain wanneer zij dezelfde fysieke NAS-share representeren; filesystem-identiteit moet op bronmountniveau worden beoordeeld.



## Self-audit provenance contract vanaf 32.4.21

- Release-acceptance mag self-audit freshness niet afleiden uit de schrijfvolgorde/mtime van losse runtimebestanden.
- `self_audit/current.json.status_updated_at` moet exact overeenkomen met `status/current.json.updated_at`. Dit is de canonieke bewijsrelatie dat de audit bij de actuele PM-status hoort.
- Ontbrekende of afwijkende provenance is fail-closed.
- File-mtime mag niet opnieuw als generation/provenance-gate worden ingevoerd voor PM status/audit closure.

- Release-artifact mag geen regressietest bevatten die de meegeleverde productiecode zelf niet haalt; dit wordt vóór packaging expliciet op de fresh extract gecontroleerd.
- Watcher-heartbeatupdates behouden inode-identiteit voor NAS/SMB-observers en publiceren tevens `Inbox/watcher_heartbeat.v2`; readers prefereren v2 wanneer aanwezig.


## Automatische maandafsluiting idempotency vanaf 32.4.22

- De canonieke RecoveryManager-status `MonthClosure_<YYYY_MM>=CLOSED` heeft voor automatische maandafsluiting voorrang op ontbrekende of verloren lokale Home Assistant completion-state.
- Een automatische scheduler mag een bewezen CLOSED maand nooit opnieuw starten.
- Na app-start blijft alleen automatische maandafsluiting fail-closed geblokkeerd totdat startup recovery/reconciliation is teruggekeerd; andere workflows worden hierdoor niet onnodig geblokkeerd.
- Een exception in startup recovery opent de automatische maandafsluitingsgate niet.
- Restart-idempotency wordt expliciet getest met `CLOSED + geen lokale marker` voordat een release wordt verpakt.

## Audit- en securitycontract vanaf 32.4.23

- Automatische muterende workflows mogen onbekende bronwaarheid nooit als OPEN behandelen: `UNKNOWN` is altijd fail-closed. Alleen aantoonbaar `OPEN` mag automatisch starten; `CLOSED_VALID` vereist deep-verified RecoveryManager-bewijs.
- Dynamische maandclosure-status mag niet als onbeperkte generieke MCP-cachewaarheid worden hergebruikt. Scheduler, preflight en executor controleren de closure-grens onafhankelijk.
- Elke inhoudelijke wijziging aan scheduler/preflight/executor/certificeringskern verhoogt `PRODUCTION_CORE_REVISION`; voor 32.4.23 is dat `9.4-core2`. Release-acceptance en automatische productiekern hebben expliciete certificeringsgates.
- ngrok blijft behouden voor externe PM-communicatie, maar nooit als tunnel naar de volledige Home Assistant/NAS-webserver of volledige poort 8099. Alleen expliciet toegestane dedicated PM-route(s) mogen extern worden gepubliceerd.
- Externe caller-identiteit komt uitsluitend uit server-side geverifieerde edge-authenticatie (principal + client/channel); `source_channel`, `session_id` of een naam uit de requestpayload is geen identiteitsbewijs. Beschermde productie-/architectuuracties blijven daarnaast hun expliciete tweede bevestiging vereisen.
- `voice-live-acceptance` en `new-chat-handover-live` zijn verplichte live gates vóór 32.5/Cowork. Een unit-/stringtest zonder echte gebruikersroute is daarvoor geen acceptancebewijs.
- Security- en certificeringstests moeten gedrag bewijzen; broncode-stringpresence alleen mag geen safety-acceptance groen maken.



## Maintenance-lessen vanaf 32.4.24

- Legacy lifecycle-status en nieuwe RecoveryManager-status zijn beide closure-evidence; conflict of ontbrekende secundaire truth bij een vermeend OPEN resultaat is `UNKNOWN` en dus fail-closed.
- Certificering van een nieuwe productiekern mag nooit vereisen dat een reeds afgesloten echte maand opnieuw wordt verwerkt; daarvoor is de non-mutating core-safety acceptance de standaardroute.
- Systeemroadmap-migraties mogen niet aannemen dat de Home Assistant-add-on nieuwe tempbestanden kan maken in `Data/03_Systeem`; permission-denial moet runtime-safe blijven en persistence-required expliciet maken.
- Voor 32.4.24 is de productiekern `9.4-core3`.


## Cross-chat ontwikkelcontract vanaf 32.4.31
- Een nieuwe ChatGPT-, Voice- of Nomad-chat mag ontwerpen, oplossingen bedenken en ontwikkelen wanneer de taak dat vereist; een chatwissel reset echter nooit bestaande ontwikkelregels, architectuurbesluiten, veiligheidsgrenzen of platformconstraints.
- Vóór relevante ontwerp-, terminal-, code-, test-, cleanup-, packaging- of releaseactie worden de actuele runtime-truth, PM/handover, actieve taak/roadmap, relevante Knowledge Base-lessen en deze ontwikkelafspraken toegepast.
- Bij ontbrekende of conflicterende bronwaarheid blijft risicovolle uitvoering fail-closed; geen gok of shortcut.
- QNAP-hostconstraint: `python3` mag niet als aanwezige hostdependency worden verondersteld en hoeft niet als shortcut op de host te worden geïnstalleerd. Python-taken op de NAS lopen via de afgesproken container/runtime waarin Python beschikbaar is.
- Nieuwe fouten worden na bewezen oplossing teruggeschreven naar Knowledge Base + Projectmanager en waar praktisch als regressietest/gate vastgelegd, zodat een nieuwe chat dezelfde basale fout niet opnieuw introduceert.


## CLEARUP destination-preflight vanaf 32.4.32
- Een nieuw cleanup-/quarantainepad wordt nooit pas tijdens de mutatiefase voor het eerst aangemaakt. De uitvoerende runtime moet de exacte bestemming vooraf aantoonbaar kunnen gebruiken.
- `EnergieProject/CLEARUP` blijft de canonieke quarantaine-root; geen stille relocatie naar Inbox/Backups als permissie-shortcut.
- Rootniveau-directoryvoorbereiding gebeurt via de QNAP-side release/watcherlaag die daarvoor al bevoegd is; Home Assistant krijgt geen extra projectrootrechten.
- De HA CLEARUP-gate controleert vóór dure hashes: geen symlink, zelfde filesystem en echte create/fsync/unlink write-probe. Fout = vroeg fail-closed, geen move/delete.
- Nieuwe chat/implementatie moet platformpermissions als ontwerpinvoer behandelen en een nieuwe destination live/prod-equivalent preflighten vóór release.


## CLEARUP source-parent permission contract vanaf 32.4.33
- Een same-filesystem rename vereist niet alleen een bruikbare bestemming maar ook mutatierecht op de oudermap van de bron. Beide zijden van iedere nieuwe mutatiegrens worden vóór release productie-equivalent bewezen; schrijfbaarheid van een andere rootmap is geen bewijs.
- Root-level CLEARUP-bronnen worden niet oplosbaar gemaakt door `chmod`/`chown` van de projectroot of door een stillere alternatieve quarantaine. De canonieke bestemming blijft `EnergieProject/CLEARUP`.
- Home Assistant blijft eigenaar van plan, dependency/symlink-audit, hashes, approvals, timeout en no-delete safety; alleen de uiteindelijke hard-rename/restore mag via een strikt releasegebonden en expirerend request aan de bestaande watchercontainer worden gedelegeerd. Geen directe HA-fallback bij bridgefout.
- Control-plane request/result-bestanden die noodzakelijkerwijs kandidaathaden bevatten mogen uitsluitend als exact benoemde observationele bronnen uit dependency-blocking worden gehouden; een algemene Inbox-uitzondering is verboden.
- Containerrechten en filesystemrechten worden afzonderlijk bewezen. Dat een container één root-level directory kan aanmaken bewijst niet dat hij bestaande root-level entries kan hernoemen.
- Releaseontwikkeling gebruikt voor de finale kandidaat een unieke schone staging/workspace; vóór packaging wordt gecontroleerd dat geen achtergebleven proces die werkmap nog kan wijzigen. Exacte release-ZIP en fresh extract blijven de eindwaarheid.


## MAINTENANCE approval transition vanaf 32.4.34

- Een door Peter expliciet goedgekeurde MODE_CHANGE naar MAINTENANCE moet de user-confirmation doorgeven tot in de operating-mode runtime.
- Vanuit een actieve DEVELOPMENT-sessie mag alleen een bevestigde overgang atomair de ontwikkelsessie sluiten en MAINTENANCE activeren.
- Een onbevestigde DEVELOPMENT -> MAINTENANCE/USER overgang blijft fail-closed met development_session_requires_explicit_close.
- Een goedgekeurde PM-moduswissel geldt pas als geslaagd nadat de authoritative operating_mode_state dezelfde effectieve modus rapporteert; alleen een verwerkt request-id is onvoldoende bewijs.


## Development Build Contract vanaf 32.4.34
- Iedere release/build krijgt vóór de eerste implementatiestap een expliciete denksetting **MIDDEL** of **HOOG**. Die keuze wordt gemeld en in de Projectmanager-buildmetadata vastgelegd.
- Iedere build start met **Stap X/Y**, totaal aantal geplande stappen, een oorspronkelijke totale raming, een raming per stap en geplande test-/verificatietijd. De oorspronkelijke totale raming wordt later niet stilzwijgend herschreven.
- Tijdens ontwikkeling blijven verstreken actieve ontwikkeltijd, geschatte resterende tijd, test-/verificatietijd, afwijking en planningstrend/leercurve onderdeel van dezelfde buildtruth. Testtijd telt volledig mee.
- Een chatwissel, nieuwe Voice-chat of Nomad-ingang reset deze contracttruth nooit. De actuele handover bevat de Development Build Contract-versie en moet vóór verdere ontwikkeling worden geladen.
- `sla dit op` of een equivalente expliciete opslagopdracht betekent: daadwerkelijke write + read-back-verificatie; geen succesclaim op alleen intentie.
- Voor uitspraken als `klaar`, `serie dicht`, `wat hierna` of een roadmapwijziging worden eerst actuele roadmap, Knowledge Base, open taken, beslissingen en afhankelijkheden gecontroleerd.
- Relevante afspraken uit chat/Voice/Nomad worden via de PM-intake gerouteerd en gededupliceerd; zij mogen niet alleen in chatcontext blijven hangen.
- UX is deel van groen: geen onnodige Terminal-, sudo-, wachtwoord- of dubbele handmatige stappen voor Peter wanneer de bestaande veilige systeemroute dit autonoom kan.
- Geen QNAP host-`python3`-aanname. Python op de NAS loopt alleen via de afgesproken container/runtime.
- Geen autonome reboot/reset van NAS, Home Assistant, containers of services en geen destructief beheer zonder expliciete opdracht.
- Bekende defecten en hun root cause/fix worden vóór closure als regressietest/gate en in KB + Projectmanager vastgelegd.
- Een expliciet gemarkeerde build zonder complete Development Build Contract-metadata is **niet release-compliant** en mag niet als definitief groen worden gepresenteerd.
## Autonome operationele modusroutering vanaf 32.4.35

- DEVELOPMENT en MAINTENANCE zijn operationele PM-modi en mogen door de Projectmanager autonoom worden gekozen/gecorrigeerd binnen een bestaande, begrensde taak.
- Hiervoor mag geen extra MODE_CHANGE-goedkeuringskaart worden toegevoegd wanneer de opdracht via de begrensde PM remote ingress komt.
- Productieplaatsing en architectuurwijzigingen blijven expliciet beschermd en vereisen gebruikersgoedkeuring.
- Bestaande pre-32.4.35 pending modebeslissingen blijven backward-compatible; nieuwe modeopdrachten gebruiken de directe auditbare mode-route.
- DEVELOPMENT→MAINTENANCE moet end-to-end aantoonbaar de ontwikkelsessie afsluiten, maintenance_requests activeren en na de taak de correcte normale modus herstellen.
## 32.4.36 CR/CLEARUP closurecontract
- Project-managed Crash Recovery houdt maximaal één volledig geldige set per CR-type; oude geldige set pas reduceren na volledige GREEN-verificatie van de nieuwe set.
- Canonieke CR-naam: `YYYY-MM-DD HH.MM <runtimeversie> CR <type>`.
- NAS Container CR gebruikt de lokale QNAP-route; Docker TLS/certificaatsetup is geen actieve/user-facing route.
- CLEARUP gebruikt bij stale plan exact één verse dependency-audit en alleen het verse plan; CLEARUP blijft hard-move/quarantaine en voert geen delete uit.
- Native-MCP bronmigratie kan een expliciete latere procesreload vereisen; releases voeren die restart niet autonoom uit.


## 32.4.37 regressiepreventie
- Een watcher-code-refresh via `exec` is geen container-recreate: wijzigingen in mounts, capabilities, network mode of security options vereisen een apart containercontract en live reconciliation.
- Broncode op disk is geen runtimebewijs voor een langlevend Pythonproces; native MCP gebruikt een bron/runtimefingerprint en een expliciet beschermde reload van exact één container.
- CR-retentie verwijdert een oude geldige set niet direct. Eerst wordt de volledige set atomisch naar `Backups/CRRetentionQuarantine/<type>` verplaatst met herkomstmanifest; definitieve delete valt buiten de CR-commit.
- Post-release acceptance mag geen startup-RED maskeren met een latere generieke `WATCHER_ACTIVE`-status. De overgang naar MAINTENANCE is eenmalig/idempotent.
- CLEARUP blijft: verse dependency/reference-audit, stale plan weigeren, hard move, old path absent, restoremanifest, symlink/live-reference checks en `delete_capability=false`.

