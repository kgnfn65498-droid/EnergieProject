# Testinstructies v22.0.0

1. Plaats `EnergieProject_v22.0.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v22_financial_decision_runtime.status = financial_decision_runtime_active_guarded`.
5. Controleer de zes beslissingen: contractwissel, batterij, apparaat, load shifting, behouden en wachten op data.
6. Een wijzigingsadvies mag alleen bij een complete positieve gevalideerde businesscase en geopende externe gates.
7. Zolang meet- of officiële contractgates dichtstaan moet de beslissing `wait_for_data` blijven.
8. Ontbrekende bedragen blijven null/`Niet beschikbaar`; nooit €0.
9. EPEX blijft uitsluitend markt-/referentieprijs.
10. Historische EPEX juli 2026 blijft gedeeltelijk t/m 2026-07-29.
11. De volledige v20- en v21-keten moet intact blijven.
12. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
