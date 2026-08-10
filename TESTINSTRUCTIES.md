# Testinstructies v23.4.0

1. Plaats `EnergieProject_v23.4.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v23_portfolio_recommendation_runtime.status = portfolio_recommendation_runtime_active_guarded`.
5. Actionable advies vereist een geselecteerde, volledig gevalideerde positieve besparingsactie.
6. Geblokkeerde selectie moet `waiting_for_data` blijven.
7. Kandidaatwaarden mogen nooit als advies worden gepubliceerd.
8. Ontbrekende financiële waarden blijven null/`Niet beschikbaar`; nooit €0.
9. De v23.0 t/m v23.3 keten moet intact blijven.
10. Historische EPEX juli 2026 blijft gedeeltelijk beschikbaar t/m 2026-07-29 en uitsluitend referentieprijs.
11. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
