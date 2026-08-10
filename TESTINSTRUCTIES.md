# Testinstructies v21.0.0

1. Plaats `EnergieProject_v21.0.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v21_financial_action_runtime.status = financial_action_runtime_active_guarded`.
5. Controleer de vier runtime-toestanden: observation, contract data, opportunity inputs en actionable.
6. Zolang de 7-dagen meetgate niet gehaald is, mag geen financieel actiebedrag worden gepubliceerd.
7. Zolang officiële NextEnergy-contractcomponenten ontbreken, blijft supplier-all-in geblokkeerd.
8. Ontbrekende bedragen blijven `Niet beschikbaar`/null en worden nooit €0.
9. EPEX blijft uitsluitend markt-/referentieprijs.
10. Historische EPEX juli 2026 blijft **gedeeltelijk**: brondata loopt t/m 2026-07-29.
11. Controleer dat de bestaande v20 opportunity-, priority- en action-handofflagen intact blijven.
12. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
