# Changelog

## 10.6.1
- Expliciete contract/all-in-validatielaag toegevoegd bovenop de bewezen v10.6.0 financiële engine.
- `supplier_context.contract_validation` rapporteert per vereiste officiële NextEnergy-component of deze werkelijk aanwezig en gevalideerd is.
- Ontbrekende vaste kosten, leveranciersopslag, terugleververgoeding en gasformule blijven expliciet geblokkeerd; er worden geen tarieven of contractwaarden aangenomen.
- Nieuwe machineleesbare status bevat `missing_components`, componenttelling, validatiefouten en `all_required_components_present`.
- Financiële prognose-engine blijft achter dezelfde 7-dagen kwaliteitsgate; EPEX blijft uitsluitend markt-/referentieprijs.
- Bestaande GUI, Ingress, release-watcher, GitHub-publicatie, diagnose-downloads, maandworkflow, rapportgeneratoren en herstelvoorzieningen zijn behouden.

## 10.6.0
- Financiële prognose-engine geactiveerd als productiefunctionaliteit bovenop de bewezen v10.5.39-bouwblokken.
- Na minimaal 7 waargenomen dagen publiceert `financial_projection` een echte 30-dagenprognose voor import en verbruiksgewogen variabele NextEnergy-stroomkosten.
- Indien officiële vaste leverancierskosten en opslag beschikbaar zijn, worden deze afzonderlijk toegevoegd aan de 30-dagen leverancier-stroomprognose.
- Leverancier-all-in blijft bewust `null` zolang vaste kosten, opslag, terugleververgoeding of gasformule niet volledig gevalideerd zijn; ontbrekende contractwaarden worden nooit verzonnen.
- EPEX blijft expliciet markt-/referentieprijs en wordt niet als leverancier-all-in gepresenteerd.
- `projection_engine.stage` staat nu op `production_active`; resterende all-in afhankelijkheden worden dynamisch gerapporteerd.
- Bestaande GUI, Ingress, release-watcher, GitHub-publicatie, diagnose-downloads, maandworkflow, rapportgeneratoren en herstelvoorzieningen zijn behouden.

## 10.5.39
- Kritieke GUI-regressie opgelost in `build_analysis_context()`: de maandlus gebruikt nu de geldige `month`-context in plaats van de niet-bestaande variabele `item`.
- Hierdoor crasht de Home Assistant Ingress/Web UI niet meer met `NameError: name 'item' is not defined`.
- Regressiontest toegevoegd die voorkomt dat deze ongeldige variabele opnieuw in het gewogen maandblok terechtkomt.
- `/health`, achtergrondtaken, releaseketen en rapportfunctionaliteit blijven ongewijzigd.


## 10.5.37
- Ontbrekende zichtbare rapportpagina in de Home Assistant Web UI opgelost.
- Nieuwe route `reports` toegevoegd met een echte HTML-rapportpagina.
- Hoofdscherm bevat nu een duidelijke knop **Open rapportpagina**.
- Rapportstatus, maand, start/eindtijd, overdracht, generatorstatus, outputmap en laatste rapportbestanden zijn zichtbaar.
- Bestaande rapportacties zijn rechtstreeks vanaf de rapportpagina beschikbaar.
- De bestaande productie-routes en rapportgeneratorlogica zijn niet vervangen; alleen de GUI-ontsluiting is hersteld.

## 10.5.36
- Contractformulemotor toegevoegd voor terugleververgoeding en gas.
- Teruglevering ondersteunt een expliciet vast contracttarief of `market_price_minus_markup`.
- Gas ondersteunt expliciet `fixed` of `market_price_plus_markup`.
- Formules rekenen uitsluitend met gevalideerde contractwaarden; ontbrekende of onbekende waarden leveren `null` plus reden op.
- Per maand is `contract_formula_preview` toegevoegd zodat analyse/diagnose direct laat zien waarom export- of gaskosten wel/niet berekenbaar zijn.
- Formule-uitkomsten worden nog niet stilzwijgend in leverancier-all-in opgenomen; activatie blijft gated richting v10.6.

## 10.5.35
- Contractkostenlaag uitgebreid met echte berekeningslogica voor leveranciercomponenten.
- Bij geldige vaste leveringskosten + opslag wordt een waargenomen leverancier-stroomkost berekend over exact dezelfde meetperiode.
- 30-dagen kandidaatprojectie bevat afzonderlijk marktprijs, opslag, vaste leveringskosten en leverancier-stroomtotaal.
- Alle leverancierberekeningen blijven expliciet `electricity_only_not_all_in`: gas, teruglevering en netbeheerkosten worden niet stilzwijgend meegerekend.
- Dynamische teruglevering wordt ondersteund via `export_compensation_formula` met type `market_price_minus_markup`; een vast bedrag blijft ondersteund.
- `financial_status` schakelt contractkosten/export/readiness voortaan dynamisch op basis van gevalideerde contractconfiguratie en de 7-dagenkwaliteitsgate.

## 10.5.34
- Veilige NextEnergy-contractkostenlaag toegevoegd richting v10.6.
- Nieuwe optionele bron: `00_Config/nextenergy_contract_costs.json`.
- Vaste leverancierskosten, opslag per kWh, terugleververgoeding en gasformule worden alleen geactiveerd wanneer geldige officiële waarden aanwezig zijn.
- Onbekende waarden blijven `null`; er worden geen tarieven of aannames verzonnen.
- `supplier_context.contract_costs` toont bron, geldigheid en validatiefouten.
- Voorbeeldbestand `00_Config/nextenergy_contract_costs.example.json` toegevoegd.
- Bestaande gewogen prijs-, prognose- en diagnoseketen blijft werken wanneer het contractkostenbestand ontbreekt.

## 10.5.33
- Financiële gereedheidsmatrix toegevoegd richting v10.6.
- Technische/contractuele bouwblokken worden expliciet als gereed/niet-gereed gerapporteerd.
- `financial_readiness.progress_pct` en `next_required_components` maken zichtbaar wat nog ontbreekt.
- Kandidaat-30-dagen variabele stroomkosten worden nu naast het maandvoorschot van €150 gezet, uitsluitend als context.
- De vergelijking met het voorschot is expliciet gemarkeerd als `variable_electricity_only_not_all_in`; er wordt dus geen onterechte all-in conclusie getrokken.
- All-in blijft geblokkeerd tot vaste leverancierskosten, opslag, terugleververgoeding en gasformule zijn gekoppeld.

## 10.5.32
- Nieuwe knop **Download release-diagnose** in de Web UI.
- Release-diagnose werkt ook wanneer een release niet geslaagd is en bevat alleen relevante watcher-, publicatie- en runtimestatus.
- Historische release-locaties uit `incoming`, `processing`, `processed` en `failed` worden meegenomen; via `?version=X.Y.Z` kan ook een oudere release gericht worden onderzocht.
- `runtime_diagnostics` toont uptime, PID, actieve threads en backend-health zodat 0% CPU niet meer met 'app staat stil' wordt verward.
- Stale `.git/index.lock` wordt alleen gerapporteerd, niet automatisch verwijderd.
- Geen P1-, Enphase-, EPEX-, rapport-, token- of wachtwoorddata in de release-diagnose.

## 10.5.31
- v10.6-prognose-engine kan vóór het openen van de 7-dagengate intern worden gevalideerd.
- `projection_candidate_validation` berekent kandidaat-30-dagenwaarden, maar markeert ze als niet-publiceerbaar zolang de kwaliteitsgate niet is gehaald.
- Officiële `projection_preview` blijft onder zeven dagen geblokkeerd en `null`.
- De vier resterende leverancier-all-in afhankelijkheden worden expliciet gerapporteerd.

## 10.5.30
- Voorbereiding op v10.6: de 30-dagen variabele-stroomprojectielogica is ingebouwd achter de bestaande 7-dagen kwaliteitsdrempel.
- `projection_preview` blijft leeg zolang de observatiedrempel niet is gehaald.
- Zodra de drempel gehaald is, kan de engine 30-dagen import en variabele stroomkosten berekenen uit de echte dag-run-rate.
- Leverancier-all-in projectie blijft apart geblokkeerd totdat opslag, vaste kosten, terugleververgoeding en gasformule gekoppeld zijn.
- `projection_engine` rapporteert expliciet de v10.6-gereedheid.

## 10.5.29
- Prognosekwaliteitsdrempel uit 10.5.28 uitgebreid met voortgangsmeting.
- Per maand worden `coverage_progress_pct` en `remaining_observation_days` gerapporteerd.
- Supplier cost model bevat een compacte `projection_observation_status`.
- Nog steeds geen voortijdige extrapolatie: pas na minimaal 7 waargenomen dagen wordt de maand prognosegeschikt.

## 10.5.28
- De herstelde verbruikgewogen NextEnergy-keten uit 10.5.27 is nu voorzien van een expliciete prognosekwaliteitsdrempel.
- `observed_coverage_days` en `projection_eligibility` toegevoegd per financiële maand.
- Minimaal 7 dagen echte kwartierwaarnemingen vereist voordat een maand überhaupt prognosegeschikt wordt gemarkeerd.
- Nog steeds geen automatische maand- of contractjaarextrapolatie; leverancier-all-in componenten ontbreken nog.
- Supplier cost model toont voortaan `projection_ready_months` en de gehanteerde projection policy.

## 10.5.27
- Runtimefout uit 10.5.26 hersteld: `timezone` wordt nu correct uit `datetime` geïmporteerd.
- De 10.5.26-diagnostiek bewees dat zowel 307 prijs- als 307 P1-importsnapshots correct worden geladen; de MCP-reader zelf is dus goed.
- Verbruikgewogen berekening en run-rate kunnen nu na `series_loaded` daadwerkelijk worden afgerond.

## 10.5.26
- Oorzaak van de lege verbruikgewogen reeks vastgesteld en hersteld.
- Werkelijke Energie MCP-toolnamen gebruikt: `search_files` en `read_text_file`.
- `search_files`-response wordt correct uit `matches` gelezen.
- Verbruikgewogen diagnostiek wordt altijd geëxporteerd, ook als de berekening niet beschikbaar is.
- Reader-status en aantallen prijs/importsnapshots maken regressies direct zichtbaar.

## 10.5.25
- Regressie uit 10.5.24 hersteld: verbruikgewogen NextEnergy-reader leest snapshots nu primair als volledig JSON-bestand via MCP.
- `search_content` blijft alleen compatibiliteitsfallback; contextregels worden niet meer blind als entiteitsstate geïnterpreteerd.
- Diagnostiek toegevoegd: aantallen gevonden prijs- en importsnapshots.
- Run-rate uit 10.5.24 blijft behouden zodra de robuuste reader geldige gekoppelde intervallen levert.

## 10.5.24
- Verbruikgewogen financiële waarneming uitgebreid met exacte geobserveerde tijdsduur.
- Veilige dag-run-rate toegevoegd voor import-kWh en variabele stroomkosten.
- Run-rate blijft expliciet een observatie van de beschikbare periode en wordt niet als volledige maandprognose gepresenteerd.
- Basis gelegd voor latere contractjaarprognose zodra voldoende representatieve dekking beschikbaar is.

## 10.5.23
- Verbruikgewogen NextEnergy-resultaten geïntegreerd in de financiële maandcontext.
- Maanden met echte geobserveerde kwartierkosten krijgen `partial_observed`.
- `months_partially_costable` bevat nu ook deze maanden.
- Geobserveerde import-kWh, verbruikgewogen stroomprijs en variabele stroomkosten worden direct financieel beschikbaar.
- Geen extrapolatie naar volledige maand en nog geen leverancier-all-in kosten.

## 10.5.22
- Eerste echte verbruikgewogen financiële analyse toegevoegd.
- NextEnergy-kwartierprijs wordt gekoppeld aan de delta van `sensor.p1_meter_energie_import` uit dezelfde NAS-snapshot.
- Levert geobserveerde import-kWh, verbruikgewogen EUR/kWh en geobserveerde importkosten.
- Dekking blijft expliciet `partial_observed_window`; nog geen volledig leverancier-all-in maandbedrag.

## 10.5.21
- Historische NextEnergy-reader gecorrigeerd voor de werkelijke NAS-opslaglocatie.
- Home Assistant leest kwartier-snapshots nu read-only via Energie MCP `search_content` uit `01_Input/YYYY_MM/HomeAssistant/QuarterHour`.
- Lokale filesystem-reader blijft uitsluitend als fallback bestaan.
- `supplier_price_history_transport` maakt zichtbaar via welke route de historische prijsdata is gevonden.
- Geen wijzigingen aan de stabiele release-watcherketen.

## 10.5.20
- Historische NextEnergy-prijstelemetrie toegevoegd vanuit Home Assistant kwartier-snapshots.
- Per beschikbare maand worden observatieaantal, gemiddelde, minimum, maximum en eerste/laatste timestamp berekend.
- `supplier_price_history_connected` maakt zichtbaar of historische leverancier-prijsdata daadwerkelijk beschikbaar is.
- Historische prijsstatistiek wordt expliciet als ongewogen prijstrend gemarkeerd; nog niet als verbruikgewogen energiekost.
- Bestaande NextEnergy live-koppeling en conservatieve all-in blokkering blijven intact.

## 10.5.19
- NextEnergy-contractcontext toegevoegd aan de analysecontext.
- Bekende contractgegevens vastgelegd: start 15-07-2026, dynamische stroom, variabel gas, voorschot €150, opzegtermijn 5 werkdagen.
- Live NextEnergy-stroomprijs wordt via de bestaande Home Assistant-entiteit uitgelezen en als prijstelemetrie gerapporteerd.
- `financial_status` toont nu of live leverancier-prijstelemetrie verbonden is.
- Leveranciersopslag, vaste kosten, terugleververgoeding en gasformule blijven bewust onbekend totdat officiële contractwaarden zijn gekoppeld.
- Sneloverzicht toont NextEnergy direct bovenaan.

## 10.5.18
- Eerste echte financiële analyse-laag toegevoegd.
- Marktvariabele stroom- en gaskosten worden alleen berekend wanneer meetdata en EPEX-prijsdata voor dezelfde maand beschikbaar zijn.
- Terugleververgoeding, leveranciersopslag, vaste kosten en all-in kosten blijven expliciet leeg totdat contractdata officieel is gekoppeld.
- `financial_status` toont direct welke maanden financieel berekenbaar zijn.
- Release-watchercontainer uit v10.5.17 blijft ongewijzigd.

## 10.5.17
- Release-watcher kan nu als aparte Container Station-container `energie-release-watcher` draaien met `restart=unless-stopped`.
- Nieuwe gedeelde heartbeat maakt singleton-detectie betrouwbaar tussen QNAP-hostprocessen en Docker PID-namespaces.
- Stale `.watcher.lock` wordt na 30 seconden zonder heartbeat automatisch hersteld.
- ZIP-validatie heeft een Python fallback (`tools/release_zip.py`), zodat de watcher-container geen extra `unzip`-pakket hoeft te installeren.
- Eenmalige bootstrap `tools/bootstrap_release_watcher_container.sh` maakt/stopt/herstart de container zonder de vier bestaande Energie-containers te wijzigen.
- EPEX-MCP en analyseverbeteringen uit v10.5.16 blijven behouden.

## 10.5.16
- EPEX-bronstatus onderscheidt nu een bereikbare bron van een nog ontbrekend maandbestand.
- Huidige maand zonder EPEX-bestand geeft `source_found=true` en `coverage.status=month_not_available`.
- Analysedownload toont bovenaan `price_status` met bronbereikbaarheid en beschikbare prijsmaanden.
- Releaseketen v10.5.15 blijft ongewijzigd; ZIP rechtstreeks naar `incoming`.
- Geen wijziging aan productiekern `9.4-core1`, maandworkflow of scheduler.

## 10.5.15
- Finder/SMB release-inname verder gehard: watcher controleert nu bestandsgrootte én wijzigingstijd over meerdere polls.
- De watcher voert vóór de installer zelf `unzip -tqq` uit; een nog onvolledige ZIP blijft in `incoming` en wordt niet meer naar `failed` verplaatst.
- Terminalvrije self-refresh en stale-lock herstel uit v10.5.14 blijven behouden.
- EPEX read-only MCP-brug uit v10.5.14 blijft behouden.
- Geen wijziging aan productiekern `9.4-core1`, maandworkflow of scheduler.

## 10.5.14
- Release-watcher herstart zichzelf na een succesvolle installatie rechtstreeks vanuit de nieuw geïnstalleerde release; QNAP cron/Terminal is niet meer nodig.
- Achtergebleven `.watcher.lock` en `.watcher.pid` worden automatisch hersteld wanneer de PID niet meer leeft.
- Finder/SMB ZIP-stabiliteitscontrole uit v10.5.13 blijft behouden.
- EPEX-analyse krijgt een tweede, werkelijke gegevensroute: read-only via de bestaande Energie MCP op de QNAP (`192.168.1.200:8000/mcp`) wanneer geen lokale HA-mount beschikbaar is.
- Geen wijziging aan productiekern `9.4-core1`, maandworkflow of scheduler.

## 10.5.13
- Release-watcher wacht nu op een volledig gekopieerde en stabiele ZIP voordat de installer start.
- Voorkomt Finder/QNAP-race waarbij een ZIP tijdens SMB-kopiëren al werd verplaatst en als corrupt werd afgekeurd.
- EPEX-autodetectie uit v10.5.12 blijft behouden.
- Race-safe singleton-lock uit v10.5.11 blijft behouden.

## 10.5.12
- EPEX-brondetectie uitgebreid met begrensde autodetectie onder Home Assistant `/share` en `/media`.
- Alleen een werkelijk bestaand `EPEX_index.csv` geldt nog als gevonden bron; `resolved_path` is anders null.
- Race-safe releaseketen uit v10.5.11 blijft behouden.
- Geen wijziging aan productiekern, maandworkflow of scheduler.

## 10.5.11
- Verhelpt de race condition waardoor meerdere QNAP release-watchers tegelijk dezelfde ZIP konden detecteren.
- De watcher gebruikt nu een atomische directory-lock (`.watcher.lock`) in plaats van alleen een niet-atomische PID-controle.
- Een ZIP in `processing` wordt niet meer direct als verweesd naar `failed` verplaatst; alleen processing-ZIP's ouder dan 10 minuten worden automatisch in quarantaine gezet.
- Hiermee wordt voorkomen dat een tweede watcher een ZIP wegneemt terwijl de eerste installer hem nog valideert of uitpakt.
- De EPEX-correctie uit v10.5.10 blijft volledig behouden.
- Geen wijziging aan productiekern `9.4-core1`, maandworkflow of scheduler.

## 10.5.10
- Corrigeert de EPEX-bronlocatie op basis van de feitelijke Home Assistant netwerkshare: `/share/Energie_NAS/05_Maanddata/EPEX`.
- De reader controleert `EPEX_index.csv` voordat een kandidaatpad als geldig wordt gebruikt.
- Legacy locaties onder `EnergieProject` blijven als fallback ondersteund.
- `resolved_path` blijft in analysedata zichtbaar voor productiecontrole.
- Geen wijziging aan productiekern, maandworkflow, scheduler of automatische releaseketen.

## 10.5.9
- Corrigeert de EPEX-padresolutie voor Home Assistant: ondersteunt zowel een mount die direct op `05_Maanddata` staat als een mount op de volledige projectroot.
- `price_context.resolved_path` toegevoegd zodat de werkelijk gebruikte productiebron direct controleerbaar is.
- EPEX-formaat, dekkingscontrole en prijsdefinities uit v10.5.8 blijven ongewijzigd.
- Geen wijziging aan productiekern, maandworkflow, scheduler of automatische releaseketen.

## 10.5.8
- Corrigeert de EPEX-analysebron: leest de bestaande productiegegevens uit `05_Maanddata/EPEX/YYYY` in plaats van uit `01_Input/YYYY_MM`.
- Ondersteunt het werkelijke EPEX-v6 formaat: UTF-8 BOM, puntkomma en de kolommen `prijs_excl_btw`, `prijs_incl_btw` en `prijs_incl_btw_en_eb`.
- Neemt dekking uit `EPEX_index.csv` mee zodat gedeeltelijke maanden en bronhiaten expliciet zichtbaar blijven.
- Hoofdstatistiek gebruikt `prijs_incl_btw_en_eb`; dit wordt nadrukkelijk niet als leverancier-all-in prijs gepresenteerd.
- Geen wijziging aan productiekern, maandworkflow, scheduler of automatische releaseketen.

## 10.5.7
- Analysecontext uitgebreid met historische EPEX-prijscontext uit reeds aanwezige maandbestanden.
- Per maand worden voor elektriciteit en gas aantal observaties, gemiddelde, minimum en maximum beschikbaar gemaakt.
- Geen nieuwe databron en geen wijziging aan de maandworkflow of releaseketen.
- Geen all-in kostenberekening zolang leverancierstarief, belasting en volledige periode-dekking niet bewezen zijn.

## 10.5.6
- Sneloverzicht analyse bovenaan toegevoegd.
- Downloadknop voor analysedata toegevoegd.
- Ontbrekende analysewaarden worden `null` in plaats van `0.0`.
- Inconsistente zonne-brondekking blokkeert afgeleide zonne-KPI's en wordt expliciet gemarkeerd.
- Productiekern 9.4-core1 en releaseketen ongewijzigd.

## 10.5.5
- Read-only `analysis-context` endpoint toegevoegd voor gestandaardiseerde maand-, kwartaal- en jaaranalyse uit bestaande maandinput.
- Bronkwaliteit en onvolledige perioden worden expliciet in de JSON-context opgenomen.
- Link `Analysecontext` toegevoegd aan de operationele console.
- Productiekern `9.4-core1` en bestaande productie-/releaseketen blijven ongewijzigd.

## 10.4.5
- QNAP-veilige release-installatie zonder metadata-/timestamp-preservering.
- Preflight controleert schrijven, normaal kopiëren en verwijderen vóór de worktree wordt vervangen.
- Rollback pakt de backup eerst uit in `/tmp` en kopieert daarna zonder metadata-preservering terug naar de QNAP-share.
- Gitloze QNAP-modus en 5-seconden release-watcher blijven actief.
- Productiekern `9.4-core1` blijft ongewijzigd.

## 10.4.3
- Praktijktest voor volledig automatische releaseverwerking door de reeds draaiende NAS release-watcher.
- Geen wijziging aan productiekern `9.4-core1`; release-installer en watcher blijven functioneel gelijk aan de bewezen v10.4.1-basis.
- Versie-update maakt zichtbaar of ZIP-detectie, validatie, backup, installatie, GitHub-push en archivering zonder Terminal-commando verlopen.

## 10.4.1

- Automatische NAS release watcher toegevoegd.
- Productiekern ongewijzigd: 9.4-core1.

## 10.3.1
- Release-inbox installer gehardend met volledige tar-rollback en strengere eindcontrole.
- Geen functionele wijziging aan maandworkflow of rapportgeneratoren; productiekern blijft `9.4-core1`.

## 10.3.0
- Release-inbox en NAS-master integratie toegevoegd.
- Host-side installatiepad met staging, SHA256-validatie, backup en Git push.
- Productiekern `9.4-core1` ongewijzigd.

## 10.2.0
- Veilige NAS-migratievoorbereiding toegevoegd zonder automatische verplaatsingen of verwijderingen.
- Oude projectstructuur (`00_Config` t/m `99_Archief`) wordt automatisch herkend zodra `Energie_NAS` in Home Assistant is gekoppeld.
- Nieuwe v10-doelstructuur wordt read-only geïnventariseerd: `Releases_Inbox`, `Releases_Archief`, `Data`, `Rapporten`, `Project`, `Recovery` en `Archief`.
- Nieuwe release-inboxcontrole valideert ZIP-integriteit en leest `VERSIE.txt` zonder ZIP-bestanden uit te pakken of te installeren.
- Nieuwe GUI-kaart **NAS migratie & release-inbox** toont migratiestatus, oude mappen en inboxstatus.
- Diagnosepakket bevat `nas_migration_status.json` en `release_inbox_status.json`.
- Technische endpoint `/migration-status` toegevoegd voor volledige machineleesbare inventaris.
- iMac-bron blijft expliciet onaangeroerd; migratie voert in v10.2 exact 0 moves en 0 deletes uit.
- Roadmap aangepast: gecontroleerde migratie en ZIP-verwerking volgen pas nadat deze inventaris in Home Assistant is gevalideerd.
- Productiekern `9.4-core1` en maandworkflow blijven ongewijzigd.

## 10.1.0
- 24/7 infrastructuurfundament toegevoegd; de iMac is geen noodzakelijke schakel meer voor maanddata of projectback-ups.
- Nieuwe QNAP-opslagcontrole voor een Home Assistant netwerkshare met naam `Energie_NAS` onder `/share/Energie_NAS`.
- Na iedere geslaagde volledige maandworkflow wordt, zodra de QNAP-share beschikbaar is, automatisch een sidecarback-up naar `EnergieProject_Backups` geschreven.
- Projectback-ups bevatten herstelrelevante maand-/runtimegegevens en SHA-256, maar nooit `options.json` of API-sleutels.
- Automatische retentie houdt maximaal 24 projectback-ups aan.
- Nieuwe UI-kaart **24/7 infrastructuur** toont QNAP-bereikbaarheid, back-updoel en laatste back-upstatus.
- Diagnosepakket bevat nu ook `infrastructure_status.json` en de laatste projectback-upstatus.
- Nieuwe knop **Download chat-overdracht** maakt een ZIP met nieuwe-chat startbestand, vaste ontwikkelafspraken, roadmap, noodherstelhandleiding en actuele projectstatus.
- `NOODHERSTEL.md`, `PROJECT_AFSPRAKEN.md` en `ROADMAP_V10.md` toegevoegd aan de release.
- De bestaande maandworkflowuitkomst, scheduler, retry, certificering en rapportgeneratoren blijven inhoudelijk ongewijzigd; productiekern blijft `9.4-core1`.

## 10.0.0
- Eerste stabiele productierelease op basis van de volledig gevalideerde v9.9.0 Release Candidate.
- Productiekern `9.4-core1` blijft ongewijzigd; geen nieuwe maandafsluitingstest nodig voor deze promotie.
- Diagnosepakket rapporteert `Releasefase: Stable` en automatische GO/NO-GO blijft leidend voor technische releasevalidatie.
- Recovery, Monitoring, Audittrail, scheduler, certificaatvalidatie en gezondheidsdashboard blijven onderdeel van de productiecontrole.
- Geen functionele wijziging aan maandworkflow, rapportgeneratoren of bronimport.

## 9.9.0
- Release Candidate voor v10.0.0 op basis van de goedgekeurde v9.8.0-productiebasis.
- Diagnosepakket vermeldt expliciet `Releasefase: Release Candidate` en `Doelrelease: 10.0.0`.
- `test_summary.json` bevat `release_stage=release_candidate` en `target_stable_release=10.0.0`.
- Productiekern blijft `9.4-core1`; workflow, scheduler, retry/finalization, Recovery, Audittrail, Monitoring en rapportgeneratoren zijn inhoudelijk ongewijzigd.
- Geen nieuwe automatische maandafsluitingstest nodig zolang het bestaande kerncertificaat geldig blijft.
- Documentatie en versieaanduidingen opgeschoond voor de eindvalidatie richting v10.0.0.

## 9.8.0
- Diagnosepakket maakt het hergebruik van een geldig kerncertificaat expliciet en begrijpelijk.
- `samenvatting.txt` toont nu softwareversie, gebruikte productiekern, geldigheid van het kerncertificaat, oorspronkelijke certificeringsrelease en of het certificaat voor deze release wordt hergebruikt.
- `test_summary.json` schema 3 en `beoordeling.json` schema 2 bevatten `core_certificate_reused` en `core_certificate_origin_release`.
- Productiekern blijft `9.4-core1`; workflow, scheduler, retry/finalization, Recovery, Audittrail, Monitoring en rapportgeneratoren zijn inhoudelijk ongewijzigd.
- Geen nieuwe automatische maandafsluitingstest nodig zolang het bestaande `9.4-core1`-certificaat geldig is.

## 9.7.0
- Diagnosepakket bevat nu `beoordeling.json` met een expliciete automatische technische **GO/NO-GO** en de afzonderlijke releasecriteria.
- `samenvatting.txt` begint met dezelfde technische beoordeling en gebruikt ondubbelzinnige labels voor softwareversie, gecertificeerde productiekern en de release waaronder het certificaat is afgegeven.
- Diagnose-schema verhoogd naar 2; niet geslaagde criteria worden expliciet vermeld in plaats van uit losse statusvelden afgeleid te moeten worden.
- Productiekern blijft `9.4-core1`; maandworkflow, scheduler, retry/finalization, Recovery, Audittrail, Monitoring en rapportgeneratoren zijn inhoudelijk niet gewijzigd. Een nieuwe automatische maandafsluitingstest is daarom niet nodig.

## 9.6.0
- **Download testpakket** hernoemd naar **Download diagnosepakket**; de oude download-URL blijft als compatibiliteitsalias werken.
- Diagnosepakket bevat nu `samenvatting.txt` met release, productiekern, testmaand, productiegereedheid, healthscore, certificaatstatus, monitoring, Recovery, Audittrail en schedulerstatus.
- Nieuw `SHA256SUMS.txt` bevat SHA-256 hashes van alle opgenomen diagnose- en bewijsbestanden, zodat het pakket inhoudelijk controleerbaar is.
- ZIP-bestandsnaam gewijzigd naar `Energieproject_diagnosepakket_v9.6.0.zip`.
- API-key en `options.json` blijven uitgesloten.
- Productiekern blijft `9.4-core1`; workflow, scheduler, retry/finalization, Recovery, Audittrail, Monitoring en rapportgeneratoren zijn inhoudelijk niet gewijzigd. Daardoor is geen nieuwe volledige automatische maandafsluitingstest nodig.

## 9.5.0
- Operationele console vereenvoudigd zonder wijziging van de gecertificeerde productiekern `9.4-core1`.
- Archief productiecertificaten, Recovery, Audittrail en Live workflowlog zijn standaard ingeklapt; Retry Debug is niet langer standaard geopend.
- Monitoring houdt de compacte samenvatting zichtbaar en plaatst detailregels en bediening in een inklapbaar blok.
- Nieuwe knop **Download testpakket** maakt één ZIP met test_summary, operationele status, health, certificaatvalidatie, monitoring, recovery, auditvalidatie en de beschikbare duurzame bewijs-/debugbestanden.
- Het testpakket bevat geen API-key en geen `options.json`.
- Omdat workflow/scheduler/retry/certificeringskern niet zijn gewijzigd, blijft een geldig certificaat voor `9.4-core1` bruikbaar en is voor v9.5.0 geen nieuwe volledige automatische maandafsluitingstest vereist.

## 9.4.0
- Productiecertificering is losgekoppeld van iedere afzonderlijke UI-/diagnostiekrelease en gekoppeld aan een expliciete **productiekern-revisie** (`9.4-core1`).
- Een productietest certificeert vanaf v9.4 de inhoudelijke kern: maandworkflow, scheduler, retry/finalization en certificeringscontract.
- Releases die deze productiekern niet wijzigen mogen hetzelfde geldige kerncertificaat hergebruiken; daardoor is niet meer na iedere cosmetische release een volledige automatische maandafsluitingstest nodig.
- Certificaatformaat verhoogd naar schema 3 en bevat `production_core_revision`; integriteitscontrole blijft SHA-256 beschermd.
- Scheduler en Monitoring controleren voortaan kerncompatibiliteit in plaats van een identiek releaseversienummer.
- Archief productiecertificaten toont naast de release ook de gecertificeerde productiekern. Legacy-certificaten blijven zichtbaar maar gelden niet als v9.4-kerncertificaat.
- Retry Debug toont afzonderlijk certificaatrelease en productiekern.
- v9.4.0 vereist één laatste productietest om `9.4-core1` te certificeren. Daarna hoeft een volgende release met ongewijzigde kern niet opnieuw die route te doorlopen.
- Bestaande audittrail en certificaathistorie worden niet herschreven.

## 9.3.0
- Diagnostiek en historie zijn verduidelijkt zonder wijzigingen aan de workflow-, scheduler-, retry-, Recovery- of certificeringslogica.
- **Historische runs** tonen het afrondmoment voortaan compact in lokale Nederlandse tijd in plaats van een ruwe ISO-timestamp.
- **Retry Debug** noemt de oude legacy-status voortaan expliciet **Legacy bronstatus (historisch)** en markeert deze als uitsluitend diagnosebewijs.
- Extra toelichting maakt duidelijk dat actuele productiestatus wordt bepaald door `workflow_result` en productiecertificaatvalidatie, niet door oude legacy-velden.
- Bestaande audittrail, monitoringhistorie, productiecertificaten en oude records worden niet herschreven.
- Deze release raakt de maandworkflow niet; eventuele productietest is alleen nodig omdat productiecertificaten nog strikt aan de actieve softwareversie zijn gekoppeld.

## 9.2.0
- Verwachte overgangstoestanden tijdens versiecertificering worden intern als `pending` behandeld in plaats van als waarschuwing/aandachtstatus.
- Monitoring toont voortaan **Wachtstatussen** naast echte fouten; een ontbrekend certificaat direct na een upgrade is daarmee expliciet een tijdelijke lifecycle-status.
- Nieuwe monitoring-auditrecords schrijven een normale wachtstatus als `info` in de append-only audittrail, met de werkelijke lifecycle-status (`pending`) in de details. Hierdoor lijkt een verwachte certificeringsfase niet meer op een historische fout.
- Gezondheidsdashboard weegt `pending` als tijdelijke status en blijft onderscheid maken tussen normale certificeringswachttijd en echte storingen.
- Bestaande v8/v9 auditrecords worden niet herschreven; de hashketen en historische waarheid blijven volledig intact.
- Workflow, schedulerlogica, retry-state, Recovery, certificaatuitgifte en officiële rapportgeneratoren blijven inhoudelijk ongewijzigd.

## 9.1.0
- Productiestatus gebruikt duidelijke tekst **Nog niet gecertificeerd** wanneer de actieve versie nog een eigen productietest nodig heeft.
- Monitoring onderscheidt echte fouten van normale aandachtspunten; een versie-upgrade zonder nieuw certificaat is geen systeemfout.
- Gezondheidsdashboard weegt aandachtspunten beperkt mee, zodat een gezonde maar nog niet gecertificeerde upgrade niet als zwaar defect wordt gepresenteerd.
- Certificaatversie toont expliciet laatste certificaat en doelversie.
- Productiecertificaattabel hernoemd naar **Archief productiecertificaten** en verduidelijkt dat alleen het certificaat van de actieve versie productiegereedheid bepaalt.
- Recovery, scheduler, retry-state, workflow-lock, auditketen, maandworkflow en officiële rapportgeneratoren blijven inhoudelijk ongewijzigd.
- Root-documentatie vereenvoudigd: één doorlopende `CHANGELOG.md` en één actuele `TESTINSTRUCTIES.md`; losse v8.x releasebestanden worden niet meer meegeleverd.

## 9.0.0
- Eerste hoofdrelease van het Energieproject-productieplatform, gebaseerd op de volledig geteste v8.19.1-keten.
- Actieve applicatieversie, Home Assistant app-metadata, productiecertificering, Recovery, Monitoring, Audittrail en Retry Debug zijn naar 9.0.0 overgezet.
- De gecertificeerde kernworkflow blijft inhoudelijk ongewijzigd: scheduler, retry-state, workflow-lock, maandverwerking en officiële rapportgeneratoren zijn niet gerefactord.
- v9 markeert de overgang van bouwfase naar stabiel productieplatform; verdere uitbreidingen moeten bovenop deze basis plaatsvinden.

## 8.19.1
- Retry Debug gebruikt live dezelfde productiecertificaatvalidatie als Productiestatus en Gezondheidsdashboard.
- Productiecertificaathistorie krijgt de ontbrekende live-update hook, zodat een nieuw certificaat zonder paginaverversing zichtbaar wordt.
- Verouderde vaste Retry Debug-versieverwijzingen vervangen door de actieve applicatieversie.
- Geen wijzigingen aan workflow, scheduler, recovery, monitoring, auditlogica of rapportgeneratoren.

## 8.19.0

- Operationele console afgerond met consistente versieaanduidingen voor Recovery, Monitoring en Audittrail.
- Productiecertificaatkaart wordt tijdens statuspolling live bijgewerkt na certificaatuitgifte of herstel.
- Productiecertificaathistorie wordt live bijgewerkt zonder volledige paginaverversing.
- Verouderde v8.15-uitleg bij certificaten vervangen door versie-onafhankelijke tekst.
- Geen nieuwe subsystemen; workflow, scheduler, recovery, monitoring, audittrail en rapportgeneratie blijven inhoudelijk ongewijzigd.

## 8.18.1

- Fix startup/Web UI crash in monitoring: use existing `write_atomic_json()` helper instead of undefined `atomic_write_json()`.
- Monitoring functionality from v8.18.0 remains unchanged.
- No changes to workflow, scheduler, recovery, certificates or report generation.

## 8.18.0

- Productiemonitoring toegevoegd voor API, workflow, productiecertificaat, audittrail, recovery, scheduler en bronstatus.
- Monitoringstatus wordt maximaal iedere 30 seconden geëvalueerd tijdens normale consolepolling.
- Alleen echte statuswijzigingen worden append-only opgeslagen in `/config/output/monitoring_history.jsonl`.
- Laatste monitoringsnapshot wordt duurzaam opgeslagen in `/config/output/monitoring_state.json`.
- Statuswisselingen worden tevens in de bestaande audittrail vastgelegd wanneer de auditketen geldig is.
- Nieuwe compacte consolekaart **Monitoring v8.18** met handmatige controle en download van monitoringhistorie.
- Gezondheidsdashboard neemt monitoring mee in de projectscore.
- Audittrailtitel generiek gemaakt; bestaande auditinhoud en hashketen blijven ongewijzigd.
- Recovery, scheduler, maandworkflow, retry-state en rapportgeneratoren inhoudelijk ongewijzigd.

## 8.17.0

- Recovery-controller toegevoegd voor veilige automatische reconciliatie uit bestaand hard bewijs.
- Achtergebleven persistente workflow-lockstatus na herstart wordt veilig genormaliseerd wanneer geen echte lock actief is.
- Retry-state wordt automatisch gereconcilieerd op basis van append-only historie, workflow_result en completion-marker.
- Productiecertificaat kan tijdens recovery uitsluitend worden hersteld uit een geslaagde productietest van exact dezelfde versie.
- Recovery-resultaat en historie worden duurzaam opgeslagen en in de audittrail vastgelegd.
- Certificaatbeheer gebruikt nu fetch binnen de Home Assistant-ingresspagina; de zwarte/lege redirectpagina vervalt.
- Geen automatische maandworkflow tijdens recovery en geen automatische wijziging van een ongeldige auditketen.

## 8.16.1

- Correctie: audittrailweergave wordt nu live bijgewerkt via de bestaande operationele statuspoll.
- Correctie: productiecertificaatbeheer keert na geldige controle/herstel direct terug naar de console in plaats van ruwe JSON te tonen.
- Console toont de laatste certificaatbeheerstatus expliciet.
- Geen wijziging aan audit-hashketen, workflow-, scheduler-, retry- of rapportlogica.

## 8.16.0

- Nieuwe append-only audittrail in `/config/output/audit_trail.jsonl`.
- Elk auditrecord bevat een eigen SHA-256 en `previous_hash`; samen vormen de records een controleerbare hashketen.
- Auditregistratie toegevoegd voor maandworkflow-afronding, veilige productietests, schedulerinstellingen, scheduler-acceptatietests en productiecertificaatuitgifte/-beheer.
- Gezondheidsdashboard controleert de audittrail en de integriteit van de volledige keten.
- Operationele console toont recente auditrecords en biedt download van de volledige JSONL-audittrail.
- Schrijven van nieuwe auditrecords wordt geblokkeerd wanneer de bestaande hashketen beschadigd is.
- Bestaande workflow-, scheduler-, retry- en certificaatlogica blijft functioneel ongewijzigd.
- Geen wijzigingen aan rapportgeneratoren, definitieve outputnamen of Recovery Update-contract.

## 8.15.0

- Productiecertificaat wordt automatisch uitgegeven na een geslaagde veilige productietest van exact dezelfde softwareversie.
- Nieuw veilig certificaatbeheer: controle/herstel kan alleen vanuit hard opgeslagen testbewijs van v8.15.0; zonder geldig bewijs blijft de status `test_required`.
- Certificaatformaat uitgebreid naar schema 2 met uniek `certificate_id`, uitgiftebron en test-evidence.
- Append-only certificaathistorie bevat nu ook certificaat-ID en uitgiftebron.
- Nieuw beheerbestand `production_certificate_management.json` met laatste controle/herstelactie.
- Nieuw UI-beheer: **Controleer / herstel productiecertificaat** en download van het actuele certificaat.
- Schedulerbeveiliging blijft ongewijzigd: automatisch inschakelen kan alleen met een integraal geldig certificaat van exact v8.15.0.
- Geen wijzigingen aan centrale maandworkflow, retry-state, workflow-lock, rapportgeneratie of historische verwerking.

## 8.14.0
- Production Lifecycle Manager bovenop v8.13.
- Persistent productiecertificaat in `/config/output/production_certificate.json`.
- SHA-256 integriteitscontrole over certificaatinhoud.
- Runtime-validatie bij readiness/statuscontrole.
- Scheduler uitsluitend actief met geldig certificaat van exact de actieve versie.
- Append-only historie in `/config/output/production_certificate_history.jsonl`.
- Health Dashboard toont certificaatstatus, integriteit en versie.
- Retry Debug toont validiteit, versie, integriteit en bestandspad.
- Operationele console toont certificaathistorie.
- Retry-finalizer, import, rapportgeneratoren en Recovery Update inhoudelijk ongewijzigd.

## 8.13.0
- Duurzame productieacceptatie na een volledig geslaagde veilige productietest.
- Acceptatie geldt uitsluitend voor exact de actieve softwareversie.
- Vereist preflight ok, workflow completed/completed_warning, finalization ok en ongewijzigde schedulerplanning.
- Productiestatus toont `Productiegeaccepteerd` en het productiecertificaat met versie en acceptatietijd.
- Scheduler wordt pas effectief wanneer de actuele versie aantoonbaar gereed is.
- Retry-finalizer, import, rapportgeneratoren en Recovery Update inhoudelijk ongewijzigd.

## 8.12.0
- Productiefix voor blijvende `2026_07 legacy_retry`.
- Productie-audit en Retry Debug gebruiken dezelfde voltooiingssemantiek.
- `ok`, `info`, `warning` en `skipped` gelden als afgeronde terminale statussen.
- Centrale retry-finalizer zet bewezen afgeronde retry naar `COMPLETED`.
- Oude retryvelden worden gewist.
- Scheduler, import, rapportgeneratoren en Recovery Update inhoudelijk ongewijzigd.

## 8.11.0
- Fix voor foutieve `all_steps_completed`-beoordeling van legacy workflowresultaten.
- `ok`, `info`, `warning` en `skipped` zijn nu alle vier geldige terminale stapstatussen.
- Nieuwe workflowresultaten schrijven expliciet `all_steps_completed`.
- Retry-evidence herberekent voltooiing uit de opgeslagen individuele stappen wanneer die beschikbaar zijn.
- Oude `steps_completed`-tellers blijven fallback voor resultaten zonder stappenlijst.
- Scheduler, importlogica, rapportgeneratoren en Recovery Update-contract inhoudelijk ongewijzigd.
- Finalization Debug blijft beschikbaar.

## 8.10.1
- Gerichte finalisatie-diagnose bovenop v8.10.0.
- Retry-, scheduler- en productielogica inhoudelijk ongewijzigd.
- Nieuw append-only `/config/output/logs/finalization_debug.log`.
- Traceert `workflow_result` vóór en na atomisch schrijven, inclusief alle individuele stapstatussen.
- Logt zowel huidig `steps_completed` als het aantal geaccepteerde stappen inclusief `skipped`.
- Traceert workflow-lock afsluiting.
- Traceert automatische executor, finalization, retry-state, completion-marker en append-only automatische historie.
- Retry Debug toont het laatste finalization-event en de recente eventketen.
- Rapportgeneratoren en Recovery Update inhoudelijk ongewijzigd.

## 8.10.0
- Zuivere diagnoseversie voor de persistente `2026_07 legacy_retry`.
- Retry-, scheduler- en migratiebeslislogica inhoudelijk ongewijzigd ten opzichte van v8.9.1.
- Nieuw append-only diagnosebestand `/config/output/logs/retry_debug.log`.
- Logt of de migratie wordt aangeroepen, of een bestaande retry-state direct wordt teruggegeven en welke bewijsbronnen reconciliation aantreft.
- Nieuw zichtbaar `Retry Debug v8.10`-blok onder Diagnostiek en beheer.
- Toont statebestand, legacy state, completion-marker, append-only historie, workflow_result, afzonderlijke workflow-checks en uiteindelijke evidence.
- Geen wijzigingen aan rapportgeneratoren, Recovery Update, schedulerroute of productieworkflow.

## 8.9.1
- Gerichte bugfix voor legacy retry-migratie uit v8.9.0.
- Naast completion-marker en append-only historie wordt nu ook `workflow_results/<maand>/workflow_result.json` als backwards-compatible auditbron gecontroleerd.
- Een historisch workflowresultaat geldt alleen als bewijs bij trigger `automatic`, status `completed`/`completed_warning`, geen failed_step, geen errors en alle workflowstappen voltooid.
- Een door v8.9.0 reeds als `OPEN` opgeslagen retry wordt opnieuw beoordeeld; een bestaande retry-state file blokkeert de bugfix dus niet.
- Daarmee kan een aantoonbaar afgeronde oudere automatische maand zoals 2026_07 alsnog veilig naar `COMPLETED` migreren.
- Echte onvolledige/mislukte productie-retries blijven OPEN.
- Schedulerroute, rapportgeneratoren, Recovery Update en dubbelstartbeveiliging inhoudelijk ongewijzigd.

## 8.9.0
- Expliciete persistente retry-state-machine met `OPEN`, `RUNNING`, `COMPLETED`, `CANCELLED` en `EXPIRED`.
- Legacy retryvelden worden gemigreerd naar `automatic_retry_state.json`.
- Migratie controleert append-only historie op een echte `Automatisch`-run voor dezelfde maand met completed/completed_warning en eindcontrole ok.
- Een oude retry wordt alleen afgesloten op basis van productie-auditbewijs of een duurzame completion-marker.
- Echte automatische runs sturen de state-machine; scheduler-tests wijzigen deze productie-state niet.
- `Automatisch herstel` leest uitsluitend de retry-state-machine.
- Schedulerroute, dubbelstartbeveiliging, rapportgeneratoren en Recovery Update inhoudelijk ongewijzigd.

## 8.8.0
- Verouderde retry-state wordt alleen opgeschoond wanneer aantoonbaar is dat de betreffende productiemaand definitief is afgerond of de retry uit een test/acceptatiesimulatie afkomstig is.
- Echte openstaande productie-retries worden nooit gewist door een geslaagde productietest.
- Nieuwe retry-metadata bewaart maand, reden en oorsprong van iedere toekomstige retry.
- Een succesvolle echte automatische maandafsluiting wist retry-tijd en retry-metadata expliciet.
- Scheduler-acceptatietest bewaart en herstelt ook de nieuwe retry-metadata.
- `Automatisch herstel` toont bij echte retries maand, tijdstip, oorsprong en reden.
- Schedulerroute, idempotency-beveiliging, rapportgeneratoren en Recovery Update inhoudelijk ongewijzigd.

## 8.7.0
- Duidelijkere scheduler-acceptatietekst met simulatiemoment, doelmaand, voorbereidende productietest en ongewijzigde schedulerinstelling.
- Nieuwe zichtbare status `Automatisch herstel` in de productiestatus.
- Bij blocked/error/failed wordt aangegeven of en wanneer een retry gepland staat.
- Definitief afgeronde maanden tonen dat een duurzame completion-marker aanwezig is.
- Geen wijziging aan schedulerroute, idempotency-beveiliging, rapportgeneratoren of Recovery Update.

## 8.6.0
- Duurzame idempotency-beveiliging voor echte automatische maandafsluitingen.
- Na een volledig geslaagde automatische run wordt atomisch een maandmarker opgeslagen in `automatic_completed_months.json`.
- De scheduler controleert deze marker vóór de gewone state en voert een reeds geslaagde maand daardoor niet opnieuw uit na een Home Assistant restart.
- Mislukte en geblokkeerde runs krijgen géén completion marker en blijven volgens de ingestelde retry opnieuw uitvoerbaar.
- Scheduler-acceptatietests gebruiken dezelfde productiecode maar schrijven nooit een echte completion marker.
- Append-only historie, productietest en rapportagecontract blijven ongewijzigd.

## 8.5.1
- Scheduler-acceptatietest voert na een upgrade automatisch eerst de verplichte veilige productietest van dezelfde softwareversie uit.
- Alleen na een geslaagde voorbereidende productietest wordt de echte schedulerroute gesimuleerd.
- De knop `Simuleer volgende scheduler-run nu` eindigt daardoor niet meer direct op `error` uitsluitend omdat de actuele versie nog niet productiegereed was.
- Scheduler Aan/Uit, planning en schedulerboekhouding blijven beschermd en ongewijzigd.
- Append-only historie registreert zowel de voorbereidende productietest als de scheduler-test afzonderlijk.
- Centrale maandworkflow, rapportgeneratoren en Recovery Update inhoudelijk ongewijzigd.

## 8.5.0
- Append-only automatische runhistorie in `automatic_run_history.jsonl`.
- Iedere productietest, scheduler-test en echte automatische run blijft afzonderlijk bewaard.
- Meerdere runs voor dezelfde maand overschrijven elkaar niet meer.
- Scheduler-simulaties worden niet dubbel als echte automatische run geregistreerd.
- Legacy-weergave blijft beschikbaar totdat de eerste v8.5-run is vastgelegd.

## 8.4.0
- Automatische historie onderscheidt `Test`, `Scheduler-test` en echte `Automatisch` runs.
- Historie toont softwareversie en eindcontrole.
- Scheduler-acceptatietest verifieert expliciet dat Aan/Uit ongewijzigd blijft.
- Productietrigger blijft `automatic`; onderscheid gebeurt uitsluitend in de auditlaag.
- Schedulerroute, maandworkflow, rapportgeneratoren en Recovery Update inhoudelijk ongewijzigd.

## 8.3.0
- Nieuwe scheduler-acceptatietest simuleert de eerstvolgende geplande automatische maandafsluiting direct.
- Productiescheduler en acceptatietest gebruiken exact dezelfde gedeelde executor.
- Acceptatietest gebruikt de echte due-beslissing en trigger `automatic`.
- Schedulerboekhouding en schedulerconfiguratie worden na de simulatie hersteld.
- Hierdoor kan de echte automatische route worden getest zonder te wachten op de volgende maand.

## 8.2.0
- P1-fix: Aan/Uit van automatische maandafsluiting wordt direct opgeslagen.
- Starten van de productietest kan daardoor geen niet-opgeslagen UIT-stand meer terugzetten naar de vorige AAN-stand.
- Productietest bewaakt de opgeslagen schedulerconfig byte-voor-byte en herstelt deze bij iedere onbedoelde wijziging.
- Finalization vereist exact de twee officiële outputbestanden.
- PDF-header en Recovery Update ZIP-integriteit worden gecontroleerd voordat automatische productie gereed wordt verklaard.
- Centrale maandworkflow en officiële rapportgeneratoren inhoudelijk ongewijzigd.

## 8.1.0
- Scheduler-runtimegate: na upgrade wordt een bewaarde AAN-stand pas uitvoerbaar na een geslaagde productietest van v8.1 zelf.
- Productiestatus onderscheidt ingestelde planning van werkelijk actieve scheduler.
- Datum/tijd van de volgende automatische run wordt leesbaar weergegeven.
- Nieuwe compacte historie van productietests en echte automatische maandafsluitingen.
- Centrale maandworkflow, rapportgeneratoren en Recovery Update inhoudelijk ongewijzigd.

## 8.0.0
- Start van de stabiele productielijn op basis van bewezen v7.9.0.
- Nieuwe centrale productiestatus in de operationele console.
- Automatische scheduler kan alleen AAN na een geslaagde productietest van dezelfde softwareversie.
- Console toont volgende automatische run en laatste definitieve output.
- Bestaande maandworkflow, rapportgeneratoren en Recovery Update blijven inhoudelijk ongewijzigd.

## 7.9.0
- Herstel workflow-triggercontract voor de veilige productietest.
- `automatic_test` is nu een geldige trigger naast manual, historical, automatic en resume.
- Productietest gebruikt dezelfde volledige maandworkflow als de automatische scheduler.
- Schedulerstatus blijft tijdens de productietest onaangeroerd.
- Geen wijziging aan rapportgeneratoren, Recovery Update of historische verwerking.

## 7.8.0
- Productieteststatus is versiegebonden; oude foutstatussen worden `Opnieuw testen`.
- Nieuwe productietest wordt direct als `running` zichtbaar vóór de achtergrondthread start.
- Nieuwe status `Automatische gereedheid`: pas groen na actuele preflight + workflow + finalization.
- Foutdetail van de laatste productietest is rechtstreeks zichtbaar in de console.
- Auditgeschiedenis blijft behouden; oude resultaten worden niet verwijderd.
- Onderliggende maandworkflow en rapportketen ongewijzigd.

## 7.7.0
- Duidelijke groene/grijze Aan/Uit-schakelaar voor automatische maandafsluiting.
- Planningvelden overzichtelijk gegroepeerd en knop hernoemd naar `Instellingen opslaan`.
- Workflowstartknoppen worden tijdens een actieve workflow uitgeschakeld.
- Hervatten wordt alleen aangeboden wanneer de laatste workflow echt is mislukt.
- Automatische status, preflight, finalization en productietest worden live bijgewerkt.
- Onderliggende maandworkflow en rapportketen ongewijzigd.

## 7.6.0
- Bedien automatische maandafsluiting rechtstreeks vanuit de operationele console.
- Aan/uit, dag, uur en retryperiode zijn instelbaar zonder handmatig configbestand.
- Veilige knop `Test automatische maandafsluiting nu`.
- Productietest gebruikt echte preflight, workflow en finalization maar verandert de schedulermaandstatus niet.
- Preflight-, finalization- en teststatus zichtbaar in de console.
- Bestaande maandworkflow en officiële rapportgeneratoren ongewijzigd.

## 7.5.0
- Productie-preflight vóór automatische maandafsluiting.
- Controle op lokale opslag, overdrachtsmap en rapport-runtime vóór een onbemande run.
- Geblokkeerde preflight start geen workflow en gebruikt de veilige retryperiode.
- Eindcontrole verifieert workflow, pre-report-validatie, rapportgeneratie, PDF en Recovery Update.
- Automatische maand wordt pas voltooid gemarkeerd als de volledige keten gereed is.

## 7.4.0
- Automatische Enphase-bronimport wanneer deze expliciet is ingeschakeld voor de actuele doelmaand.
- Nieuwe doelmaandgebonden eindvalidatie vóór overdracht en rapportage.
- Actuele rapportage wordt geblokkeerd als vereiste rapportinput onvolledig is.
- Historische runs blijven bronbeschikbaarheid-gestuurd en gebruiken geen actuele live-data als historie.
- Laatste pre-report-validatie wordt opgeslagen in status en workflowresultaten.

## 7.3.6

- Classificeert het bewust overslaan van live snapshots bij historische maanden als informatie in plaats van waarschuwing.
- Een foutloze historische run eindigt daardoor als `completed`; echte warnings blijven `completed_warning`.
- Geen wijzigingen aan import, rapportgeneratoren, Recovery Update of outputcontract.

## 7.3.6

- Classificeert een gecontroleerde historische rapport-skip als informatie in plaats van waarschuwing.
- Een geslaagde historische import zonder volledige detailbronnen eindigt nu als `completed`.

- Historische recovery doorzoekt nu ook recursief de echte maandboom achter `YYYY_MM als archief downloaden` (`/config/output/YYYY_MM`).
- Reeds bewaarde ZIP-archieven met de maandcode in de bestandsnaam worden automatisch als extra read-only bron ontdekt.
- Herstelde bestanden worden uitsluitend bij exact case-sensitive overeenkomende bestandsnaam overgenomen; niets wordt hernoemd.
- Bestaande doelbestanden worden nooit overschreven.
- Elke succesvolle historische bronrecovery wordt met bestandsnaam, bron en doel in het workflowlog vastgelegd.
- Actuele live snapshots worden niet gebruikt om historische maanden kunstmatig aan te vullen.
- Geen wijzigingen aan rapportgeneratoren, Recovery Update-contract of vaste outputnamen.

## 7.3.1

- Historische workflow draait op de achtergrond en keert terug naar de operationele console.
- API-test keert na succes terug naar de operationele console.
- Bestaande `01_Input`-bestanden kunnen bij historische runs worden hergebruikt.

## 7.3.0

- Gewogen workflowvoortgang over acht hoofdphasen.
- Directe 0%-reset bij start, hervatten en historische run.
- Vloeiende voortgang, actieve stap, subactiviteit en indicatieve resterende tijd.

## 7.2.0

- Workflowmeldingen losgekoppeld van overdrachtsmeldingen.
- Start-/eindmeldingen en veilige automatische retry na mislukte maandafsluiting.

## 7.1.7

- Live workflowlog via `operation-status`.
- Statuspillen en gezondheidschecks verversen live.
- Zelftest toont leesbare tabel in plaats van ruwe JSON.

## 7.1.6

- Herstelt de JavaScript-syntax van de operationele console: newline-escapes in traceback- en logweergave worden nu correct als `\n` aan de browser geleverd.
- Daardoor werkt de 2,5-seconden polling van status, voortgang en live workflowlog weer daadwerkelijk.
- Live workflowlog scrolt na verversen automatisch naar de nieuwste regel.
- Geen wijzigingen aan backend-workflow, rapportgeneratoren, Recovery Update of outputcontract.

## 7.1.5

- Wis oude workflowfoutdiagnostiek direct bij de start van een nieuwe run.
- Zet de actuele runstatus op `running` en reset oude voortgang naar 0/0.
- Gezondheidsdashboard behandelt een normaal actieve workflow-lock niet langer als storing.
- Behoudt de v7.1.4-fix voor de dubbele `message`-parameter.
- Geen wijzigingen aan rapportgeneratoren, Recovery Update-contract of definitieve outputnamen.

## 7.1.4

- Herstelt de heartbeat-logaanroep die `message` zowel positioneel als benoemd doorgaf.
- `workflow_heartbeat()` schrijft de detailtekst nu als `heartbeat_message`, zonder botsing met het hoofdbericht van `append_workflow_log()`.
- Nieuwe statische regressietest controleert alle `append_workflow_log()`-aanroepen op dubbele `message`-argumenten.
- Geen wijzigingen aan workflowlogica, rapportgeneratoren, Recovery Update-contract of definitieve outputnamen.

## 7.1.3

- Workflowfouten bewaren stapnaam, fouttype, fouttekst, doorlooptijd en volledige Python-traceback.
- De operationele console toont de laatste workflowfout direct in een apart diagnoseblok.
- Het live workflowlog toont tracebacks en blijft automatisch verversen.
- Workflowlogs zijn downloadbaar via `download-workflow-log?month=YYYY_MM`.
- Succesvolle of gecontroleerd geannuleerde workflows wissen verouderde foutdiagnostiek.
- Geen wijzigingen aan rapportgeneratoren, Recovery Update-contract of definitieve outputnamen.

# Changelog

## 7.1.2
- Huidige kalendermaand vraagt nooit meer toekomstige dagen op bij SlimmeMeterPortal; verwerking stopt bij vandaag.
- Workflowstappen krijgen een bewaakte maximale looptijd; standaard 900 seconden.
- SlimmeMeterPortal maandimport schrijft per dag een heartbeat en voortgang naar het live workflowlog.
- Achtergrondworkflow heeft een failsafe die een achtergebleven workflow-lock altijd vrijgeeft.
- Staplog bevat voortaan looptijd en ingestelde timeout.
- Geen wijzigingen aan rapportgeneratoren, Recovery Update-contract of definitieve outputnamen.

## 7.1.1
- Gecontroleerde annulering is geen foutstatus of Python-traceback meer.
- Annuleringsreden wordt vastgelegd als `user_requested` of `service_shutdown`.
- Maandworkflow krijgt status `cancelled` en behoudt de add-on als draaiende service.
- Workflowlog, operationele status en Home Assistant-melding onderscheiden annulering van een echte fout.
- Geen wijzigingen aan rapportgeneratoren, Recovery Update-contract of definitieve outputnamen.

## 7.1.0
- Centrale knop voor maandverwerking start de volledige workflow op de achtergrond.
- Hervatten na een mislukte/onvolledige workflow hergebruikt reeds geslaagde stappen.
- Persistente workflowlog per maand met live weergave in de operationele console.
- Gezondheidsdashboard met compacte projectscore en technische deelcontroles.
- Workflow-lock blijft dubbele runs blokkeren; teller van geweigerde starts is zichtbaar via operation-status.
- Bestaande rapportketen, Recovery Update-contract en definitieve outputnamen ongewijzigd.

## 7.0.1
- Nieuwe operationele console boven de bestaande fase-7 workflow.
- Statuskaarten voor workflow, laatste maand, laatste run en automatische maandafsluiting.
- Live voortgangsweergave via bestaande status-endpoints, zonder nieuwe workflowlogica.
- Historische workflowresultaten als tabel met status, stappen, duur en mislukte stap.
- Bediening logisch gegroepeerd; technische functies blijven beschikbaar onder diagnostiek/beheer.
- Bestaande rapportketen, Recovery Update-contract en outputnamen ongewijzigd.

## 7.0.0
- Fase-7 besturingslaag toegevoegd boven de bestaande maandworkflow.
- Optionele automatische maandafsluiting op instelbare dag en uur.
- Historische maandselectie via de Ingress-interface, zonder live snapshots aan oude maanden toe te voegen.
- Compact endpoint `operation-status` met actuele workflowstatus en recente maandhistorie.
- Bestaande rapportketen, bestandsnamen en Recovery Update-inhoud blijven ongewijzigd.

## 6.9.1
- Stabiele afsluiting van fase 6.
