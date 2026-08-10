# Testinstructies v23.0.0

1. Plaats `EnergieProject_v23.0.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v23_savings_portfolio_runtime.status = savings_portfolio_runtime_active_guarded`.
5. Controleer de vier domeinen: energy_contract, home_battery, appliance_replacement en load_shifting.
6. Alleen gevalideerde complete kansen mogen in de financiële rangschikking komen.
7. Jaarbesparing moet primaire prioriteit zijn; terugverdientijd secundair; implementatie-inspanning tiebreaker.
8. Kandidaatwaarden mogen de rangschikking niet beïnvloeden.
9. Geblokkeerde domeinen moeten zichtbaar blijven; ontbrekende bedragen blijven null/`Niet beschikbaar`.
10. De bestaande v22 completion gate moet intact blijven.
11. Met huidige meetdekking onder 7 dagen blijft de observation gate gesloten.
12. Zonder officiële NextEnergy-contractcomponenten blijft supplier-all-in geblokkeerd.
13. EPEX blijft uitsluitend markt-/referentieprijs; historische EPEX juli 2026 blijft gedeeltelijk beschikbaar t/m 2026-07-29.
14. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
