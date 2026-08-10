# Testinstructies v23.5.0 — v23 afronding

1. Plaats `EnergieProject_v23.5.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v23_completion_publication_gate.status = v23_complete_external_data_gates_remain`.
5. Controleer `roadmap_state = v23_complete_guarded_savings_portfolio_chain_ready_for_v24`.
6. Alle vijf v23-ketencomponenten moeten `ready_guarded` zijn.
7. Een wijzigingsadvies mag uitsluitend bij een volledig gevalideerde positieve financiële case worden gepubliceerd.
8. Geblokkeerde/incomplete cases blijven `wait_for_data`; ontbrekende bedragen blijven null/`Niet beschikbaar`, nooit €0.
9. EPEX blijft uitsluitend markt-/referentieprijs en nooit leverancier-all-in.
10. De observation gate blijft minimaal 7 geobserveerde dagen; externe gates hoeven voor technische v23-afronding niet open te zijn.
11. Historische EPEX juli 2026 blijft gedeeltelijk beschikbaar t/m 2026-07-29.
12. GUI, analyse-export, release-diagnose, watcher, automatische maandworkflow en officiële rapportgeneratoren moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
