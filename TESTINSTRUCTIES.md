# Testinstructies v16.2.0

1. Plaats `EnergieProject_v16.2.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Controleer dat Home Assistant alleen releasetext 16.2.0 toont.
4. Update naar 16.2.0 en controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v16_output_runtime_validation.status = runtime_validation_active`.
7. Controleer dat de prognosegate nog geblokkeerd is zolang `projection_eligibility.eligible = false`.
8. Controleer dat de leverancier-all-in-gate de ontbrekende officiële contractcomponenten als blokkeerreden behoudt.
9. Geblokkeerde financiële waarden blijven `Niet beschikbaar`; nooit 0.
10. EPEX blijft uitsluitend referentie.
11. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
