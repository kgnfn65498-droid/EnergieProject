# Testinstructies v22.6.0

1. Plaats `EnergieProject_v22.6.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v22_completion_gate.status = v22_complete_external_data_gates_remain`.
5. Controleer `roadmap_state = v22_complete_guarded_auditable_decision_publication_chain_ready_for_v23`.
6. Alle zes v22-ketencomponenten moeten `ready_guarded` zijn.
7. `next_major_release` moet `23.0.0` zijn.
8. De huidige meetgate mag nog gesloten zijn zolang minder dan 7 dagen zijn gemeten.
9. Ontbrekende officiële NextEnergy-contractcomponenten moeten de supplier-all-in gate gesloten houden.
10. Blocked/informational blijft `wait_for_data`; ontbrekende bedragen blijven null/`Niet beschikbaar`.
11. Kandidaatwaarden mogen geen financieel wijzigingsadvies veroorzaken.
12. EPEX blijft uitsluitend markt-/referentieprijs; historische juli-data blijft gedeeltelijk t/m 2026-07-29.
13. Volledige v20-, v21- en v22-keten moet intact blijven.
14. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
