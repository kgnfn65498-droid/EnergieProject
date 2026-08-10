# Testinstructies v19.1.0

1. Plaats `EnergieProject_v19.1.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `production_consolidation.v19_report_action_mapping.status = report_action_mapping_active`.
5. Met circa 4,198/7 waargenomen dagen moet de financiële actie nog `Nog geen financieel advies` blijven.
6. Geblokkeerde bedragen en adviessterkte mogen niet als 0 worden weergegeven.
7. Een verschilbedrag en aanbevolen voorschot mogen pas verschijnen wanneer de aanbeveling volledig publiceerbaar is.
8. Supplier-all-in blijft geblokkeerd zolang de vier officiële NextEnergy-contractcomponenten ontbreken.
9. Candidate-data blijft indicatief en mag de actie niet sturen.
10. EPEX blijft uitsluitend markt-/referentieprijs.
11. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
