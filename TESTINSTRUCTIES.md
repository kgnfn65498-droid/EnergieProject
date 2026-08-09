# Testinstructies v17.0.0

1. Plaats `EnergieProject_v17.0.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Controleer dat Home Assistant alleen releasetext 17.0.0 toont.
4. Update naar 17.0.0 en controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v17_financial_decision_output.status = financial_decision_output_guard_active`.
7. Bij de huidige 4,125/7 waargenomen dagen mag nog geen voorschotadvies worden gepubliceerd.
8. Leverancier-all-in blijft geblokkeerd zolang de vier officiële NextEnergy-contractcomponenten ontbreken.
9. Het maandvoorschot blijft €150 referentiecontext; geen advies zonder volledige gates.
10. Validatie-candidates en EPEX mogen geen leveranciersbeslissing sturen.
11. Geblokkeerde financiële beslissingen blijven `Niet beschikbaar`.
12. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
