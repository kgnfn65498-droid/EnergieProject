# Testinstructies v20.6.0

1. Plaats `EnergieProject_v20.6.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v20_savings_action_handoff.status = savings_action_handoff_active_guarded`.
5. Controleer dat `v20_completion_gate` opportunity, priority en action handoff als `ready_guarded` toont.
6. Ontbrekende data moet `wait_for_data`/`Niet beschikbaar` geven, nooit €0.
7. De 7-dagen prognosegate en supplier-all-in gate blijven ongewijzigd.
8. EPEX blijft markt-/referentieprijs.
9. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.
10. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
