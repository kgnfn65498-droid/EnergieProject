# Testinstructies v21.2.0

1. Plaats `EnergieProject_v21.2.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `production_consolidation.v21_blocked_dependency_runtime.status = blocked_dependency_runtime_active_guarded`.
5. De eerste blocker moet bij minder dan 7 meetdagen de observatiegate blijven.
6. Controleer dat resterende meetdagen expliciet beschikbaar zijn.
7. Controleer dat ontbrekende NextEnergy-contractcomponenten afzonderlijk zichtbaar blijven.
8. Candidate-waarden en aannames mogen geen gate openen of financieel advies veroorzaken.
9. EPEX blijft uitsluitend markt-/referentieprijs.
10. Historische EPEX juli 2026 blijft **gedeeltelijk**: brondata loopt t/m 2026-07-29.
11. Bestaande v20 savings-keten en v21 runtime/gate-resolution moeten intact blijven.
12. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
