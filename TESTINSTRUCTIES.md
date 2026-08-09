# Testinstructies v18.1.0

1. Plaats `EnergieProject_v18.1.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `production_consolidation.v18_financial_explanation_runtime.status = financial_explanation_runtime_active`.
5. Onder 7 waargenomen dagen moet de uitleg melden dat nog onvoldoende waarnemingsdagen beschikbaar zijn.
6. Supplier-all-in en contractcomponenten blijven afzonderlijke gates.
7. Candidate-data mag alleen context zijn en mag geen aanbeveling sturen.
8. EPEX blijft uitsluitend markt-/referentieprijs.
9. Ontbrekende financiële waarden blijven `Niet beschikbaar`.
10. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
