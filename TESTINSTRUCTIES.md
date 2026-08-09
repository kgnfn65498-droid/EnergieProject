# Testinstructies v16.0.0

1. Plaats `EnergieProject_v16.0.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Controleer dat Home Assistant alleen releasetext 16.0.0 toont.
4. Update naar 16.0.0 en controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v16_financial_report_output_contract.status = official_output_contract_active`.
7. Bij de huidige observatie van circa 4,115/7 dagen moeten prognosewaarden nog `Niet beschikbaar` blijven.
8. Leverancier-all-in blijft geblokkeerd zolang de vier officiële NextEnergy-contractcomponenten ontbreken.
9. Er mag geen handmatige gate-override bestaan.
10. Validatie-candidates mogen niet als officiële rapportwaarde verschijnen.
11. EPEX blijft uitsluitend referentie.
12. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
