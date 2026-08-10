# Testinstructies v21.6.0

1. Plaats `EnergieProject_v21.6.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v21_completion_gate.status = v21_complete_external_data_gates_remain`.
5. Controleer `roadmap_state = v21_complete_guarded_financial_action_chain_ready_for_v22`.
6. Alle zes v21-lagen moeten `ready_guarded` zijn.
7. De vier actietypen moeten intact blijven: contractwissel, thuisbatterij, apparaatvervanging en load shifting.
8. Externe meet-, contract- en opportunity-inputgates mogen niet worden omzeild.
9. Ontbrekende bedragen blijven null/`Niet beschikbaar`; nooit €0.
10. EPEX blijft uitsluitend markt-/referentieprijs.
11. Historische EPEX juli 2026 blijft gedeeltelijk t/m 2026-07-29.
12. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
