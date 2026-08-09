# Testinstructies v16.1.0

1. Plaats `EnergieProject_v16.1.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Controleer dat Home Assistant alleen releasetext 16.1.0 toont.
4. Update naar 16.1.0 en controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v16_output_activation_state.status = activation_state_bound_to_runtime_gates`.
7. Bij circa 4,125/7 waargenomen dagen moet `projection_eligibility.eligible = false` blijven en prognose-uitvoer geblokkeerd zijn.
8. Leverancier-all-in blijft geblokkeerd zolang de vier officiële NextEnergy-contractcomponenten ontbreken.
9. De overgang naar publiceerbare waarden moet automatisch zijn; geen handmatige override.
10. EPEX blijft uitsluitend referentie.
11. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
