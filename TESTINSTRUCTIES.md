# Testinstructies v13.0.0

1. Plaats `EnergieProject_v13.0.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op verwerking naar `processed`.
3. Update de Home Assistant-app naar 13.0.0.
4. Controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v13_reporting_financial_handoff`.
7. Verwacht `release_status = v13_reporting_handoff_active`.
8. Bij minder dan 7 waargenomen dagen blijven prognose- en adviesvelden geblokkeerd.
9. Leverancier-all-in blijft geblokkeerd zolang officiële NextEnergy-contractcomponenten ontbreken.
10. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.
11. EPEX blijft uitsluitend referentieprijs.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
