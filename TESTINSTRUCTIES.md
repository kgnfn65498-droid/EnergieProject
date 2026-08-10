# Testinstructies v20.0.0

1. Plaats `EnergieProject_v20.0.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `production_consolidation.v20_financial_report_runtime_contract.status = official_report_runtime_contract_active`.
5. Controleer dat Page 1-, Page 2- en Pagina 3-13-velden in het v20-contract aanwezig zijn.
6. Onder 7 waargenomen dagen blijven prognose- en advieswaarden geblokkeerd.
7. Na 7 dagen mag alleen de observatiegate automatisch openen; supplier-all-in blijft geblokkeerd zolang officiële NextEnergy-contractwaarden ontbreken.
8. Ontbrekende contractcomponenten blijven: vaste leverancierskosten, leveranciersopslag, terugleververgoeding en gasformule.
9. Candidate-getallen mogen geen primaire rapportwaarden worden.
10. EPEX blijft uitsluitend markt-/referentieprijs.
11. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.
12. Ontbrekende financiële waarden blijven `Niet beschikbaar`.
13. GUI, analyse-export, release-diagnose, watcher en automatische maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
