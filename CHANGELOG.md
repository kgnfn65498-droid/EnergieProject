# Changelog

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
