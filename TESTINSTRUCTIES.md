# Testinstructies v22.4.0

1. Plaats `EnergieProject_v22.4.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v22_decision_publication_runtime.status = decision_publication_runtime_active_guarded`.
5. Mapping: blocked→blocked, limited→informational, validated→informational, actionable→publishable.
6. Alleen actionable confidence mag een switch/koop/vervang/shift-advies publiceren.
7. Limited en validated mogen bewijs/context tonen, maar geen wijzigingsadvies.
8. Met huidige meetdekking onder 7 dagen moet publicatie geblokkeerd blijven.
9. Zonder officiële NextEnergy-contractcomponenten mag supplier-all-in geen advies opleveren.
10. Kandidaatwaarden mogen niet als financieel advies worden gepubliceerd.
11. Ontbrekende bedragen blijven null/`Niet beschikbaar`; nooit €0.
12. EPEX blijft uitsluitend markt-/referentieprijs. Historische EPEX juli 2026 blijft **gedeeltelijk** beschikbaar t/m 2026-07-29.
13. Volledige v20-, v21- en eerdere v22-keten moet intact blijven.
14. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
