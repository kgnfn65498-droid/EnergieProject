# Testinstructies v13.2.0

1. Plaats `EnergieProject_v13.2.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Update Home Assistant naar 13.2.0.
4. Controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v13_official_report_render_contract.status = active`.
7. Controleer dat ontbrekende financiële waarden niet als 0 worden behandeld.
8. De huidige observatiegate mag nog niet passeren zolang minder dan 7 dagen beschikbaar zijn.
9. Leverancier-all-in blijft geblokkeerd zolang officiële NextEnergy-contractcomponenten ontbreken.
10. EPEX blijft uitsluitend referentie.
11. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
