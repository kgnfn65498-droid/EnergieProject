# Testinstructies v18.3.0

1. Plaats `EnergieProject_v18.3.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `production_consolidation.v18_completion_gate.release_status = v18_complete_external_data_gates_remain`.
5. Controleer dat explainability-contract, runtime-uitleg en rapport-handoff alle drie `ready_guarded` zijn.
6. Met 4,167/7 waargenomen dagen moet de prognose nog geblokkeerd blijven.
7. De blokkering moet herleidbaar blijven naar onvoldoende waarnemingsdagen.
8. Supplier-all-in blijft geblokkeerd zolang de vier officiële NextEnergy-contractcomponenten ontbreken.
9. Candidate-data mag geen aanbeveling sturen.
10. EPEX blijft uitsluitend markt-/referentieprijs.
11. Ontbrekende financiële waarden blijven `Niet beschikbaar`.
12. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
