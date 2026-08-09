# Testinstructies v12.1.0

1. Plaats `EnergieProject_v12.1.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op verwerking naar `processed`.
3. Update de Home Assistant-app naar 12.1.0.
4. Controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Controleer `production_consolidation.v12_decision_support`.
7. Zolang minder dan 7 waargenomen dagen beschikbaar zijn, verwacht:
   - `recommendation_publishable = false`
   - `reason = waiting_for_minimum_observation_quality`
8. Ook na 7 dagen blijft leverancier-all-in advies geblokkeerd zolang officiële contractcomponenten ontbreken.
9. EPEX blijft uitsluitend referentieprijs.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.
Historische EPEX juli 2026 blijft gedeeltelijk (bron t/m 2026-07-29).
