# Testinstructies v22.1.0

1. Plaats `EnergieProject_v22.1.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v22_decision_evidence_runtime.status = decision_evidence_runtime_active_guarded`.
5. Financiële beslissingen moeten traceerbare broninputs en een berekeningsbasis vereisen.
6. Meetvenster, contractvalidatiestatus en externe gate-status moeten behouden blijven in de auditlogica.
7. Zolang externe gates dichtstaan moet de beslissing `wait_for_data` blijven.
8. Kandidaatwaarden mogen niet als bewijs dienen.
9. Ontbrekende bedragen blijven null/`Niet beschikbaar`; nooit €0.
10. EPEX blijft uitsluitend markt-/referentieprijs.
11. Historische EPEX juli 2026 blijft gedeeltelijk t/m 2026-07-29.
12. Volledige v20-, v21- en v22.0-keten moet intact blijven.
13. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
