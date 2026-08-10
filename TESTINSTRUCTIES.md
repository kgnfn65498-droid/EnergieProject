# Testinstructies v23.3.0

1. Plaats `EnergieProject_v23.3.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v23_portfolio_selection_runtime.status = portfolio_selection_runtime_active_guarded`.
5. Alleen rank 1 met `validated_opportunity` en positieve jaarbesparing mag worden geselecteerd.
6. Geblokkeerde domeinen en `validated_no_action` mogen nooit als besparingsactie worden geselecteerd.
7. Zonder gevalideerde ranked opportunity blijft de actie `wait_for_data` of `keep_current`.
8. Kandidaatwaarden mogen de selectie niet beïnvloeden.
9. Ontbrekende bedragen blijven null/`Niet beschikbaar`; nooit €0.
10. De v23.0-, v23.1- en v23.2-keten moet intact blijven.
11. Met meetdekking onder 7 dagen blijft de observation gate gesloten.
12. Zonder officiële NextEnergy-contractcomponenten blijft supplier-all-in geblokkeerd.
13. EPEX blijft uitsluitend markt-/referentieprijs; historische juli 2026-data blijft gedeeltelijk t/m 2026-07-29.
14. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
