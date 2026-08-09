# Testinstructies v11.0.0

1. Plaats `EnergieProject_v11.0.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht tot de watcher de release naar `processed` verplaatst.
3. Update de Home Assistant-app naar **11.0.0**.
4. Controleer GUI/Ingress op Home Assistant **2026.8.2**.
5. Controleer dat de tegel Financiële bouwstatus nu **Financiële keten productie** toont.
6. Download Analyse-export en release-diagnose.
7. Controleer dat `production_consolidation.status` `production_ready_guarded` blijft en `major_release` `11.0` is.
8. Ontbrekende contractcomponenten moeten null/niet beschikbaar blijven; EPEX blijft referentie.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
Historische EPEX juli 2026 blijft gedeeltelijk met laatste bronrecord 2026-07-29.
