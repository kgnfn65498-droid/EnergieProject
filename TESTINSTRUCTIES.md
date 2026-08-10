# Testinstructies v21.5.0

1. Plaats `EnergieProject_v21.5.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v21_financial_action_selection.status = financial_action_selection_active_guarded`.
5. Alleen complete financiële evaluaties mogen in de actieselectie komen.
6. Selectievolgorde: hoogste gevalideerde jaarbesparing → kortste terugverdientijd → laagste implementatie-inspanning.
7. Onvolledige/geblokkeerde acties moeten uitgesloten blijven.
8. Zolang huidige externe gates dichtstaan moet selectie `wait_for_data` blijven en bedragen null/`Niet beschikbaar`.
9. EPEX blijft uitsluitend markt-/referentieprijs.
10. Historische EPEX juli 2026 blijft gedeeltelijk t/m 2026-07-29.
11. Bestaande v20 savings-keten en alle eerdere v21 runtime/readiness/evaluation-lagen moeten intact blijven.
12. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
