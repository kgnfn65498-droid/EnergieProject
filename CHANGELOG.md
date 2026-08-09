# Changelog

## v10.9.0 — productieconsolidatie financiële keten

- Consolideert de gevalideerde financiële analyse-, prognose- en rapportketen.
- Voegt expliciete productie-readiness/auditstatus toe aan de analyse-export.
- Bevestigt strikte contractgating: geen leverancier-all-in zonder gevalideerde officiële contractwaarden.
- Behoudt de 7-dagen kwaliteitsgrens en EPEX als uitsluitend markt-/referentieprijs.
- Behoudt officiële rapportintegratie uit 10.8.x, GUI, watcher, maandworkflow, diagnoses en herstelvoorzieningen.
- Voorbereid als laatste 10.x productiestap vóór v11.0.

## v10.9.0 — watcher checksum-manifest hotfix

- Herstelt verplicht `SHA256SUMS.json` dat in v10.8.1 ontbrak.
- Release-identiteit overal 10.9.0.
- Functionele inhoud van de financiële rapportintegratie ongewijzigd.

## v10.9.0 — release-identiteit hotfix

- Corrigeert de fout waardoor het v10.8.0-pakket intern nog als v10.7.0 werd gepubliceerd.
- Add-on/config-versie, APP_VERSION en financiële engine-identiteit zijn nu consistent v10.9.0.
- Functionaliteit van v10.8.0 blijft ongewijzigd: officiële financiële rapportintegratie en strikte contractgating.
- Geen wijzigingen aan watcher, GUI, maandworkflow of herstelvoorzieningen.

## v10.9.0 — officiële financiële rapportintegratie

- Verbindt de gevalideerde financiële analyse met de bestaande officiële rapportgeneratoren.
- Pagina 2 gebruikt geen financiële voorbeeldwaarden meer als productiedata.
- Alleen waargenomen/verifieerbare NextEnergy-kosten worden doorgegeven.
- Leverancier-all-in, gas, terugleververgoeding en termijnadvies blijven expliciet niet beschikbaar zolang officiële contractcomponenten ontbreken.
- EPEX blijft uitsluitend markt-/referentieprijs.
- De bestaande 7-dagen kwaliteitsgrens blijft ongewijzigd.
- Adapterresultaat bevat een auditblok `financial_report_integration`.
- Alle bestaande GUI-, watcher-, workflow-, diagnose- en herstelvoorzieningen blijven behouden.

## v10.7.0
- Prognose-engine verdiept met kalendermaand-run-rate na de bestaande 7-dagen kwaliteitsgate.
- 30-dagen variabele elektriciteitsprognose krijgt een expliciete ±15% bandbreedte voor scenarioanalyse.
- Nieuwe projection_detail-output blijft strikt elektriciteit-only en nooit leverancier-all-in zonder officiële contractcomponenten.
- EPEX blijft uitsluitend markt-/referentieprijs.
- Bestaande GUI, watcher, GitHub-publicatie, diagnoses, maandworkflow, herstel en rapportgeneratoren behouden.


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
- Nieuw **Sneloverzicht analyse** direct bovenaan de operationele console; historie, laatste analysemaand en datakwaliteit zijn zichtbaar zonder naar beneden te scrollen.
- Nieuwe knop **Download analysedata** levert de actuele analysecontext als JSON-download.
- Ontbrekende bronmetingen worden in de analysecontext voortaan `null` in plaats van misleidend `0.0`.
- Afgeleide zonne-KPI's worden niet berekend wanneer Enphase-opwek en P1-teruglevering aantoonbaar geen gelijk meetvenster vormen; dit wordt gemarkeerd als `inconsistent_period_coverage`.
- Kwartaal- en jaaraggregaties bevatten `metric_month_coverage` zodat zichtbaar is hoeveel maanden werkelijk aan iedere KPI bijdragen.
- Maandworkflow, scheduler, rapportagekern en automatische QNAP -> GitHub -> Home Assistant releaseketen zijn niet gewijzigd.

# Changelog EnergieProject

## 10.5.5
- Eerste productieverbetering van de v10.5 conversatie-/analysebasis.
- Nieuw read-only endpoint `analysis-context` bouwt een gestandaardiseerde context uit bestaande `01_Input/YYYY_MM`-maanddata.
- De context bevat maand-, kwartaal- en kalenderjaaraggregaties voor netafname, teruglevering, netto netbalans, gas, zonne-opwek, direct zonnegebruik, huishoudelijk gebruik, eigen-verbruikpercentage en zelfvoorzieningspercentage.
- Onvolledige kwartalen/jaren worden expliciet gemarkeerd; bronbeschikbaarheid en Enphase-fallback worden als kwaliteitsmetadata opgenomen.
- De operationele console bevat een directe link `Analysecontext`.
- Geen wijziging aan maandworkflow, scheduler, retry/finalization, rapportgeneratoren of automatische releaseketen.
- Productiekern blijft `9.4-core1`.

## 10.5.4
- End-to-end productietest van de volledige releaseketen.
- Geen functionele wijzigingen aan maandworkflow, scheduler, importlogica of rapportgeneratoren.
- Geen wijziging aan productiekern `9.4-core1`.
- Doel van deze release:
  `incoming -> QNAP processed -> automatische HA GitHub-publicatie -> Home Assistant update`.
- v10.5.4 mag niet handmatig via Terminal of GitHub worden gepubliceerd; daarmee wordt de automatische keten daadwerkelijk bewezen.

## v10.5.39
- Kritieke Home Assistant ingress-fix: interne proxy-IP wordt niet langer door een hardcoded allowlist geblokkeerd.
- Lost de melding “app lijkt nog niet klaar te zijn” op terwijl de app wel draait.
- Rapportpagina uit v10.5.37 blijft aanwezig.
