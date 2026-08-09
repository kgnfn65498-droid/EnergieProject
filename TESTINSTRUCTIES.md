# Testinstructies v11.2.0

1. Plaats `EnergieProject_v11.2.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op verwerking naar `processed`.
3. Update de Home Assistant-app naar 11.2.0.
4. Controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.report_readiness.status = guarded_ready`.
7. Bij minder dan 7 waargenomen dagen moeten prognosevelden geblokkeerd/null blijven.
8. All-in velden blijven niet beschikbaar zolang officiële contractcomponenten ontbreken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
Historische EPEX juli 2026 blijft gedeeltelijk (bron t/m 2026-07-29).
