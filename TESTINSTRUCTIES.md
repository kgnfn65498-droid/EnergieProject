# Testinstructies v19.0.0

1. Plaats `EnergieProject_v19.0.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `production_consolidation.v19_financial_report_decision_presentation.status = financial_report_decision_presentation_active`.
5. Met circa 4,177/7 waargenomen dagen moet de presentatiestatus nog geblokkeerd blijven en `Nog geen financieel advies` tonen.
6. Een toekomstig advies mag pas verschijnen na een volledige v17-aanbeveling én v18-uitlegcontext.
7. Supplier-all-in blijft geblokkeerd zolang de vier officiële NextEnergy-contractcomponenten ontbreken.
8. Candidate-data blijft indicatief en mag geen beslissing sturen.
9. EPEX blijft uitsluitend markt-/referentieprijs.
10. Ontbrekende financiële waarden blijven `Niet beschikbaar`.
11. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
