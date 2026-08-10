# Testinstructies v22.3.0

1. Plaats `EnergieProject_v22.3.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v22_decision_confidence_resolution_runtime.status = decision_confidence_resolution_runtime_active_guarded`.
5. De resolution order moet lopen van required gate failure naar limited, validated en pas daarna actionable.
6. Met de huidige meetdekking onder 7 dagen moet de observatiegate gesloten blijven.
7. Zonder officiële NextEnergy-contractcomponenten blijft ook de supplier-contractgate gesloten.
8. Een gesloten vereiste gate mag nooit actionable opleveren.
9. `validated` mag niet automatisch als positieve financiële businesscase gelden.
10. Kandidaatwaarden mogen de resolved confidence-state niet verhogen.
11. Ontbrekende bedragen blijven null/`Niet beschikbaar`; nooit €0.
12. EPEX blijft uitsluitend markt-/referentieprijs; historische EPEX juli 2026 blijft gedeeltelijk beschikbaar t/m 2026-07-29.
13. Volledige v20-, v21- en eerdere v22-keten moet intact blijven.
14. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
