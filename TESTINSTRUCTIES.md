# Testinstructies v21.4.0

1. Plaats `EnergieProject_v21.4.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `v21_financial_evaluation_contract.status = financial_evaluation_contract_active_guarded`.
5. Controleer de vier evaluatietypen: contractwissel, thuisbatterij, apparaatvervanging en load shifting.
6. Jaarbesparing moet de primaire financiële maatstaf zijn.
7. Batterij en apparaatvervanging moeten terugverdientijd uit gevalideerde kosten en besparing gebruiken.
8. Geen koop-, wissel- of vervangadvies bij nul/negatieve of onvolledige besparing.
9. Zolang de huidige externe gates dichtstaan blijven bedragen `Niet beschikbaar`/null.
10. EPEX blijft uitsluitend markt-/referentieprijs.
11. Historische EPEX juli 2026 blijft gedeeltelijk t/m 2026-07-29.
12. Bestaande v20 savings-keten en v21 runtime/readiness moeten intact blijven.
13. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
