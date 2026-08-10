# Testinstructies v20.2.0

1. Plaats `EnergieProject_v20.2.0.zip` in `EnergieProject_Inbox/incoming` en wacht op `processed`.
2. Update in Home Assistant en controleer GUI/Ingress.
3. Download Analyse-export en release-diagnose.
4. Controleer `production_consolidation.v20_report_publication_state.status = official_report_publication_state_active`.
5. De observatiegate moet met de huidige 4,583/7 dagen nog gesloten blijven.
6. Page 2 projectiewaarden blijven daarom `Niet beschikbaar`.
7. Supplier-all-in blijft geblokkeerd zolang de vier officiële NextEnergy-contractcomponenten ontbreken.
8. Page 1 financieel advies en Page 2 voorschotadvies blijven geblokkeerd zolang de complete beslisgate niet publiceerbaar is.
9. Candidate-getallen mogen geen primaire rapportwaarden worden.
10. Handmatige gate-override blijft verboden; automatische overgang na externe gates blijft actief.
11. EPEX blijft uitsluitend markt-/referentieprijs.
12. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.
13. GUI, analyse-export, release-diagnose, watcher en maandworkflow moeten blijven werken.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
