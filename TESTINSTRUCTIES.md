# Testinstructies v17.3.0

1. Plaats `EnergieProject_v17.3.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Controleer dat Home Assistant alleen releasetext 17.3.0 toont.
4. Update naar 17.3.0 en controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v17_completion_gate.release_status = v17_complete_external_data_gates_remain`.
7. Controleer dat decision output, savings recommendation contract en publication gate alle drie `ready_guarded` zijn.
8. Met circa 4,146/7 waargenomen dagen moet het financiële advies nog geblokkeerd blijven.
9. Leverancier-all-in blijft geblokkeerd zolang de vier officiële NextEnergy-contractcomponenten ontbreken.
10. Geen gedeeltelijke aanbevelingen, validation candidates of EPEX-waarden mogen als leveranciersadvies verschijnen.
11. Geblokkeerde financiële waarden blijven `Niet beschikbaar`.
12. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
