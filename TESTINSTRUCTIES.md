# Testinstructies v20.3.0

1. Plaats `EnergieProject_v20.3.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `production_consolidation.v20_completion_gate.release_status = v20_complete_external_data_gates_remain`.
5. Controleer `next_major_release = 21.0.0`.
6. De huidige observatiegate blijft terecht gesloten zolang minder dan 7 dagen dekking beschikbaar is.
7. Supplier-all-in blijft geblokkeerd zolang de vier officiële NextEnergy-contractcomponenten ontbreken.
8. Financiële advieswaarden blijven `Niet beschikbaar` zolang hun publicatiegate gesloten is.
9. Candidate-getallen mogen geen primaire rapportwaarden worden; ontbrekende waarden mogen niet als nul verschijnen.
10. Handmatige override blijft verboden; automatische overgang na externe gates blijft actief.
11. EPEX blijft uitsluitend markt-/referentieprijs.
12. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.
13. GUI, analyse-export, release-diagnose, watcher en maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
