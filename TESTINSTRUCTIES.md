# Testinstructies v15.3.0

1. Plaats `EnergieProject_v15.3.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Controleer dat Home Assistant alleen releasetext 15.3.0 toont.
4. Update naar 15.3.0 en controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v15_completion_gate.release_status = v15_complete_external_data_gates_remain`.
7. De huidige observatie is circa 4,115/7 dagen; prognosewaarden moeten daarom nog geblokkeerd zijn.
8. Leverancier-all-in blijft geblokkeerd zolang de vier officiële NextEnergy-contractcomponenten ontbreken.
9. Validatie-candidates mogen niet als financiële prognose worden gepubliceerd.
10. Ontbrekende financiële waarden blijven `Niet beschikbaar`; nooit 0.
11. EPEX blijft uitsluitend referentie.
12. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
