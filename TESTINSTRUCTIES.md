# Testinstructies v13.3.0

1. Plaats `EnergieProject_v13.3.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Controleer het Home Assistant updatevenster: de nieuwste release 13.3.0 moet bovenaan staan.
4. Update naar 13.3.0.
5. Controleer GUI/Ingress.
6. Download Analyse-export en release-diagnose.
7. Controleer `production_consolidation.v13_completion_gate`.
8. Verwacht `release_status = v13_complete_external_data_gates_remain`.
9. Observatie- en officiële NextEnergy-contractgates blijven verplicht.
10. EPEX blijft uitsluitend referentie.
11. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
