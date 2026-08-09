# Testinstructies v12.3.0

1. Plaats `EnergieProject_v12.3.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op verwerking naar `processed`.
3. Update de Home Assistant-app naar 12.3.0.
4. Controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v12_completion_gate`.
7. Verwacht `release_status = v12_complete_external_data_gates_remain`.
8. Zolang de observatieperiode korter dan 7 dagen is, blijft financieel advies geblokkeerd.
9. Leverancier-all-in blijft ook daarna geblokkeerd zolang officiële contractcomponenten ontbreken.
10. EPEX blijft uitsluitend markt-/referentieprijs.
11. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
