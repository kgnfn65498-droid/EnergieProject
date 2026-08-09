# Testinstructies v17.2.0

1. Plaats `EnergieProject_v17.2.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op `processed`.
3. Controleer dat Home Assistant alleen releasetext 17.2.0 toont.
4. Update naar 17.2.0 en controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v17_recommendation_publication_gate.status = recommendation_publication_gate_active`.
7. Met circa 4,135/7 waargenomen dagen moet `recommendation_publishable` nog false zijn en het advies geblokkeerd blijven.
8. Controleer dat geen gedeeltelijk advies verschijnt: decision, verschilbedrag, aanbevolen voorschot en adviessterkte moeten samen beschikbaar zijn.
9. Leverancier-all-in blijft geblokkeerd zolang de vier officiële NextEnergy-contractcomponenten ontbreken.
10. Validatie-candidates en EPEX mogen geen leveranciersbeslissing sturen.
11. Geblokkeerde aanbevelingen blijven `Niet beschikbaar`.
12. Historische EPEX juli 2026 blijft gedeeltelijk: brondata loopt t/m 2026-07-29.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
