# Testinstructies v15.1.0

1. Plaats `EnergieProject_v15.1.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Controleer dat Home Assistant alleen releasetext 15.1.0 toont.
4. Update naar 15.1.0 en controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v15_report_generator_field_contract.status = generator_field_contract_active`.
7. Prognoses blijven geblokkeerd zolang minder dan 7 waargenomen dagen beschikbaar zijn.
8. Leverancier-all-in blijft geblokkeerd zolang officiële NextEnergy-contractcomponenten ontbreken.
9. Ontbrekende financiële waarden blijven `Niet beschikbaar`; nooit 0.
10. EPEX blijft uitsluitend referentie.
11. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
