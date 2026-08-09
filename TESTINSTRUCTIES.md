# Testinstructies v11.3.0

1. Plaats `EnergieProject_v11.3.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op verwerking naar `processed`.
3. Update de Home Assistant-app naar 11.3.0.
4. Controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v11_completion_gate`.
7. Verwacht `release_status = v11_complete_external_data_gates_remain`.
8. De observation gate blijft wachten tot 7 dagen; leverancier-all-in blijft wachten op officiële contractwaarden.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
Historische EPEX juli 2026 blijft gedeeltelijk (bron t/m 2026-07-29).
