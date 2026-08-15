# Testinstructies v32.1.2

## Automatisch vóór release
1. Python-syntaxcontrole op alle Pythonbestanden.
2. `pytest -q tests/test_historical_energy_excel.py tests/test_v3210_historical_energy_excel.py`.
3. `pytest -q tests/test_static.py tests/test_v32037_safe_github_publication.py tests/test_v32038_automatic_publication_chain.py`.
4. XLSX-smoketest: vereiste 11 tabbladen, ZIP/XML integraal, 0 werkbladformules, 0 externe links, geen VBA, geen 2008-regressie.
5. Publicatietest: volledige maand geeft master + byte-identiek archief; partiële maand alleen master; een volgende maand behoudt alle eerdere volledig gevalideerde nieuwe maanden.
6. Release-ZIP: `unzip -t`, MANIFEST.sha256 en SHA256SUMS.json volledig verifiëren.

## Home Assistant na installatie
- Update naar 32.1.2 moet via de normale NAS → GitHub → Home Assistant-keten verschijnen.
- Open de SlimmeMeterPortal GUI en controleer dat de app normaal start.
- Automatische maandafsluiting moet UIT blijven.
- Direct na app-start moet bij ontbrekende master automatisch `Data/02_Output/Rapportages/Energie_verbruik_historie.xlsx` ontstaan, plus het archief van de nieuwste volledig gevalideerde maand.
- Hiervoor mag geen maandworkflow of maandafsluiting nodig zijn.
- Bij een lopende maand mag de master PARTIEEL tonen, maar er mag nog geen bevroren archiefkopie voor die maand worden gemaakt.

## Bewezen releasepad behouden
- Gebruik GEEN Home Assistant Terminal.
- Gebruik GEEN handmatige Git-commit of Git-push voor de normale release.
- Juli 2026 bevat naast de volledige SMP-maand ook historische context waarin EPEX eerder gedeeltelijk beschikbaar kon zijn; dit verandert de gevalideerde energieactuals niet.
Gebruik GEEN handmatige Git-commit of Git-push.
Historische EPEX-referentiedekking voor juli liep eerder gedeeltelijk t/m 2026-07-29; v32.1 verandert die oude referentie niet.
