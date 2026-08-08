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
