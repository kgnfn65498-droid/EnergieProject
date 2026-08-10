# Testinstructies v22.2.0

1. Plaats `EnergieProject_v22.2.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v22_decision_confidence_runtime.status = decision_confidence_runtime_active_guarded`.
5. Confidence-states moeten zijn: blocked, limited, validated en actionable.
6. Met de huidige gesloten observatie- en contractgates mag geen actionable beslissing ontstaan.
7. Alleen complete traceerbare evidence mag validated opleveren.
8. Actionable vereist daarnaast een complete positieve gevalideerde financiële businesscase.
9. Kandidaatwaarden mogen confidence niet verhogen.
10. Ontbrekende bedragen blijven null/`Niet beschikbaar`; nooit €0.
11. EPEX blijft uitsluitend markt-/referentieprijs; historische EPEX juli 2026 blijft gedeeltelijk beschikbaar t/m 2026-07-29.
12. Volledige v20-, v21- en eerdere v22-keten moet intact blijven.
13. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
