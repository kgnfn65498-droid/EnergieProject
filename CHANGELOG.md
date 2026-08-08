# Changelog

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
