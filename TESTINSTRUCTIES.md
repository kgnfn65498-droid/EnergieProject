# Testinstructies v23.2.0

1. Plaats `EnergieProject_v23.2.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v23_portfolio_ranking_runtime.status = portfolio_ranking_runtime_active_guarded`.
5. Alleen `validated_opportunity` mag in de numerieke ranking komen.
6. Rangorde moet zijn: hoogste jaarbesparing → kortste terugverdientijd → laagste implementatie-inspanning.
7. Geblokkeerde domeinen blijven zichtbaar maar hebben rank/null en financiële waarden null/`Niet beschikbaar`.
8. `validated_no_action` mag niet als besparingsactie worden gerangschikt.
9. Kandidaatwaarden mogen de ranking niet beïnvloeden.
10. De bestaande v23.0 Savings Portfolio Runtime en v23.1 Portfolio Evaluation Runtime moeten intact blijven.
11. Met huidige meetdekking onder 7 dagen blijft de observation gate gesloten.
12. Zonder officiële NextEnergy-contractcomponenten blijft supplier-all-in geblokkeerd.
13. EPEX blijft uitsluitend markt-/referentieprijs; historische juli 2026-data blijft gedeeltelijk t/m 2026-07-29.
14. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
