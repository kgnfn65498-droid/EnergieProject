# Testinstructies v23.1.0

1. Plaats `EnergieProject_v23.1.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v23_portfolio_evaluation_runtime.status = portfolio_evaluation_runtime_active_guarded`.
5. Controleer dat alle vier domeinen een eigen gate-contract hebben.
6. De eerste niet-gehaalde verplichte gate moet primaire blocker zijn; alle ontbrekende inputs blijven zichtbaar.
7. Kandidaatwaarden mogen blockers niet oplossen.
8. Alleen complete gevalideerde inputs mogen `financially_evaluable` worden.
9. Alleen positieve gevalideerde jaarbesparing mag `validated_opportunity` worden.
10. Nul of negatieve besparing moet `validated_no_action` opleveren.
11. De bestaande `v23_savings_portfolio_runtime` moet intact blijven.
12. Met huidige meetdekking onder 7 dagen blijft de observation gate gesloten.
13. Zonder officiële NextEnergy-contractcomponenten blijft supplier-all-in geblokkeerd.
14. EPEX blijft uitsluitend markt-/referentieprijs; historische juli 2026-data blijft gedeeltelijk t/m 2026-07-29.
15. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
