# Testinstructies v18.0.0

1. Plaats `EnergieProject_v18.0.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Controleer dat Home Assistant alleen releasetext 18.0.0 toont.
4. Update naar 18.0.0 en controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v18_financial_explainability_contract.status = financial_explainability_contract_active`.
7. De huidige observatie is circa 4,146/7 dagen; financieel advies moet daarom nog geblokkeerd blijven.
8. De explainability-laag moet zowel geblokkeerde als toekomstige publiceerbare adviezen kunnen verklaren.
9. Candidate-waarden mogen alleen uitleg/context zijn en mogen geen beslissing sturen.
10. Leverancier-all-in blijft geblokkeerd zolang de vier officiële NextEnergy-contractcomponenten ontbreken.
11. EPEX blijft uitsluitend markt-/referentieprijs.
12. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
