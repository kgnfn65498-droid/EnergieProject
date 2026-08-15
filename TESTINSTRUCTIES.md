# Testinstructies v32.2.0 — Knowledge Base

## Automatisch vóór release
- Nieuwe v32.2-structuurtest moet eerst RED zijn op ongewijzigde v32.1.3-kopie en daarna GREEN na implementatie.
- Run `pytest -q tests/test_v3220_knowledge_base_structure.py`.
- Run `pytest -q tests/test_historical_energy_excel.py tests/test_v3210_historical_energy_excel.py tests/test_v3211_startup_excel_bootstrap.py tests/test_v3212_startup_excel_live_nas.py tests/test_v3213_smp_meter_reading_totals.py`.
- Run de volledige testset `pytest -q`.
- Compile alle Python-modules/tests.
- `sh -n` op release-installer, watcher en watcher-bootstrap.
- Scan actieve writers op oude v32.1.3-paden; legacy strings zijn alleen toegestaan in `project_structure.py` en de v32.2-migratietest.
- Rebuild en valideer `SHA256SUMS.json` en `MANIFEST.sha256`.
- Test de uiteindelijke ZIP, pak hem opnieuw uit en verifieer manifest + release-identiteit uit de ZIP zelf.

## Verwachte structuur na eerste Home Assistant-start
- `Data/02_Output/Rapportages/KnowledgeBase/EnergieProject_Roadmap.md`.
- `Data/02_Output/Rapportages/KnowledgeBase/Apparatuur_index.md`.
- `Data/02_Output/Rapportages/KnowledgeBase/Mobiele_socket_meetlog.md`.
- `Data/02_Output/Rapportages/Verbruikshistorie/Energie_verbruik_historie.xlsx`.
- `Data/02_Output/Rapportages/Verbruikshistorie/Historische_data_index.md`.
- `Data/02_Output/Rapportages/Verbruikshistorie/Energie_verbruik_historie_design.md`.
- `Data/02_Output/Rapportages/Verbruikshistorie/Energie_verbruik_historie_bootstrap_status.json`.
- `Data/02_Output/Rapportages/Verbruikshistorie/Archief/Energie_verbruik_historie_2026_07.xlsx`.
- `Data/02_Output/Rapportages/KnowledgeBase/Structuurmigratie_v32.2_status.json`.
- Pre-migratie veiligheidskopie onder `Backups/StructureMigration_v32.2/pre_migration/`.

## Inhoudelijke regressie
- Juli blijft exact 156,32 kWh afname, 603,97 kWh teruglevering, -447,65 kWh netto en 33,89 m³ gas.
- Augustus blijft PARTIEEL; geen bevroren augustus-archief zolang de maand niet volledig gevalideerd is.
- Bestaande geldige master wordt bij migratie byte-identiek verplaatst en niet opnieuw opgebouwd.
- Bij oud+nieuw bestand met verschillende inhoud stopt de migratie zonder overschrijven.
- Een tweede start is idempotent.
- Automatische maandafsluiting blijft UIT; `finalize_month` wordt niet gebruikt.

## Home Assistant na installatie
- Update naar 32.2.0 via de normale NAS → GitHub → Home Assistant-keten.
- Open de GUI en controleer dat de app normaal start.
- Controleer `Structuurmigratie_v32.2_status.json`: status `completed`, canonical paths wijzen naar KnowledgeBase en Verbruikshistorie.
- Controleer de bootstrapstatus in `Verbruikshistorie/`; bij reeds geldige master + juli-archief verwacht `skipped_existing`.
- Controleer dat de oude master/roadmap/apparatuur/socketbestanden niet meer los in de rapportroot staan.

## Bestaande acceptatiecontroles blijven gelden

## Automatisch vóór release
1. Python-syntaxcontrole op alle Pythonbestanden.
2. `pytest -q tests/test_historical_energy_excel.py tests/test_v3210_historical_energy_excel.py`.
3. `pytest -q tests/test_static.py tests/test_v32037_safe_github_publication.py tests/test_v32038_automatic_publication_chain.py`.
4. XLSX-smoketest: vereiste 11 tabbladen, ZIP/XML integraal, 0 werkbladformules, 0 externe links, geen VBA, geen 2008-regressie.
5. Publicatietest: volledige maand geeft master + byte-identiek archief; partiële maand alleen master; een volgende maand behoudt alle eerdere volledig gevalideerde nieuwe maanden.
6. Release-ZIP: `unzip -t`, MANIFEST.sha256 en SHA256SUMS.json volledig verifiëren.

## Home Assistant na installatie
- Update naar 32.2.0 moet via de normale NAS → GitHub → Home Assistant-keten verschijnen.
- Open de SlimmeMeterPortal GUI en controleer dat de app normaal start.
- Automatische maandafsluiting moet UIT blijven.
- Direct na app-start moet bij ontbrekende master automatisch `Data/02_Output/Rapportages/Verbruikshistorie/Energie_verbruik_historie.xlsx` ontstaan, plus het archief van de nieuwste volledig gevalideerde maand.
- Hiervoor mag geen maandworkflow of maandafsluiting nodig zijn.
- Bij een lopende maand mag de master PARTIEEL tonen, maar er mag nog geen bevroren archiefkopie voor die maand worden gemaakt.

## Bewezen releasepad behouden
- Gebruik GEEN Home Assistant Terminal.
- Gebruik GEEN handmatige Git-commit of Git-push voor de normale release.
- Juli 2026 bevat naast de volledige SMP-maand ook historische context waarin EPEX eerder gedeeltelijk beschikbaar kon zijn; dit verandert de gevalideerde energieactuals niet.
Gebruik GEEN handmatige Git-commit of Git-push.
Historische EPEX-referentiedekking voor juli liep eerder gedeeltelijk t/m 2026-07-29; v32.1 verandert die oude referentie niet.

## Extra regressie v32.2.0
- `pytest -q tests/test_v3213_smp_meter_reading_totals.py`.
- Na installatie en app-start moet `Data/02_Output/Rapportages/Verbruikshistorie/Energie_verbruik_historie_bootstrap_status.json` status `completed` tonen.
- Daarna moeten `Energie_verbruik_historie.xlsx` en `Archief/Energie_verbruik_historie_2026_07.xlsx` bestaan.
- Juli moet exact 156,32 kWh import, 603,97 kWh export, -447,65 kWh netto en 33,89 m³ gas bevatten.

