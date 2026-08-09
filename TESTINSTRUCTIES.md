# Testinstructies v14.0.0

1. Plaats `EnergieProject_v14.0.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Controleer dat Home Assistant de update 14.0.0 aanbiedt.
4. Update naar 14.0.0.
5. Controleer GUI/Ingress.
6. Download Analyse-export en release-diagnose.
7. Controleer `production_consolidation.v14_report_generation_activation.status = production_active_guarded`.
8. Bij minder dan 7 waargenomen dagen blijven prognosevelden geblokkeerd.
9. Leverancier-all-in blijft geblokkeerd zolang officiële NextEnergy-contractcomponenten ontbreken.
10. Ontbrekende financiële waarden mogen nooit als 0 worden weergegeven.
11. EPEX blijft uitsluitend referentie.
12. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
