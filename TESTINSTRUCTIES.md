# Testinstructies v24.0.0 — stap 1/5

1. Plaats `EnergieProject_v25.0.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v24_action_handoff_runtime.status = action_handoff_runtime_active_guarded`.
5. Controleer `roadmap_step = 1/5` en `roadmap_state = v24_step_1_of_5_action_handoff_runtime_active_guarded`.
6. Zolang de externe gates niet volledig geldig zijn, moet de handoff `waiting_for_data` blijven en financiële ontbrekende waarden null/`Niet beschikbaar`.
7. Controleer dat kandidaatwaarden geen handoff activeren en dat EPEX nooit leverancier-all-in wordt.
8. Controleer dat geen aankoop, contractwissel of apparaatsturing automatisch wordt uitgevoerd; externe actie vereist gebruikerbevestiging.
9. Historische EPEX juli 2026 blijft gedeeltelijk beschikbaar t/m 2026-07-29.
10. GUI, analyse-export, release-diagnose, watcher, automatische maandworkflow en officiële rapportgeneratoren moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
