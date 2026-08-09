# Testinstructies v13.1.0

1. Plaats `EnergieProject_v13.1.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Update Home Assistant naar 13.1.0.
4. Controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v13_report_field_policy`.
7. Verwacht `status = active_guarded`.
8. Bij de huidige <7 dagen blijven prognose/advies geblokkeerd.
9. Ontbrekende contractwaarden blijven unavailable en nooit 0.
10. EPEX blijft uitsluitend referentie.
11. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
