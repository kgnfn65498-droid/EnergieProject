# Testinstructies v21.3.0

1. Plaats `EnergieProject_v21.3.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v21_financial_action_readiness.status = financial_action_readiness_active_guarded`.
5. Controleer de vier actietypen: contractwissel, thuisbatterij, apparaatvervanging en load shifting.
6. Elke actie moet zijn eigen vereiste inputs en ontbrekende inputs hebben.
7. Contractwissel blijft geblokkeerd zolang meetgate en officiële leverancier-all-in gegevens ontbreken.
8. Batterij/apparaat/load-shifting mogen pas financieel beoordeeld worden met complete gevalideerde inputs.
9. Ontbrekende bedragen blijven `Niet beschikbaar`/null; nooit €0.
10. EPEX blijft uitsluitend markt-/referentieprijs.
11. Historische EPEX juli 2026 blijft gedeeltelijk t/m 2026-07-29.
12. Bestaande v20 savings-keten en v21 runtime/gates/dependency runtime moeten intact blijven.
13. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
