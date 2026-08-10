# Testinstructies v22.5.0

1. Plaats `EnergieProject_v22.5.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v22_decision_publication_payload_runtime.status = decision_publication_payload_runtime_active_guarded`.
5. Controleer dat blocked en informational als actie `wait_for_data` gebruiken.
6. Alleen publishable mag een gevalideerd positief financieel wijzigingsadvies dragen.
7. Kandidaatwaarden mogen nooit in de actiepayload terechtkomen.
8. Ontbrekende financiële waarden blijven null/`Niet beschikbaar`; nooit €0.
9. Met meetdekking onder 7 dagen moet de financiële publicatie nog geblokkeerd blijven.
10. Zonder officiële NextEnergy-contractcomponenten blijft supplier-all-in geblokkeerd.
11. EPEX blijft uitsluitend markt-/referentieprijs. Historische EPEX juli 2026 blijft **gedeeltelijk** beschikbaar t/m 2026-07-29.
12. Volledige v20-, v21- en eerdere v22-keten moet intact blijven.
13. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
