# Testinstructies v20.1.0

1. Plaats `EnergieProject_v20.1.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `production_consolidation.v20_report_runtime_value_mapping.status = official_report_value_mapping_active`.
5. Page 1 managementsamenvatting moet beslissing, reden en kwaliteitscontext uit de bestaande guarded keten gebruiken.
6. Page 1 financiële KPI's mogen alleen publiceerbare verschil-, voorschot- en sterktewaarden gebruiken.
7. Met 4,583/7 waargenomen dagen blijft de observatiegate nog gesloten.
8. Supplier-all-in blijft geblokkeerd zolang de vier officiële NextEnergy-contractcomponenten ontbreken.
9. Candidate-getallen mogen geen primaire rapportwaarden worden en ontbrekende waarden blijven `Niet beschikbaar`.
10. EPEX blijft uitsluitend markt-/referentieprijs.
11. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.
12. GUI, analyse-export, release-diagnose, watcher en maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
