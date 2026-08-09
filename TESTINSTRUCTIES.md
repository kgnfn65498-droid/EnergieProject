# Testinstructies v13.1.1

1. Plaats `EnergieProject_v13.1.1.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op verwerking naar `processed`.
3. Update Home Assistant naar 13.1.1.
4. Controleer direct of GUI/Ingress weer opent.
5. Download Analyse-export en release-diagnose.
6. Controleer `v13_report_field_policy.status = active_guarded`.
7. Ontbrekende financiële waarden blijven unavailable en nooit 0.
8. EPEX blijft uitsluitend referentie.
9. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
