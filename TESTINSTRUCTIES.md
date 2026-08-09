# Testinstructies v11.1.0

1. Plaats `EnergieProject_v11.1.0.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op verwerking naar `processed`.
3. Update Home Assistant-app naar 11.1.0.
4. Controleer GUI/Ingress.
5. Download Analyse-export en release-diagnose.
6. Verwacht bij minder dan 7 waargenomen dagen nog steeds `blocked_insufficient_observation`.
7. Zodra 7 dagen vanzelf zijn bereikt moet de variabele 30-dagenprognose automatisch publiceerbaar worden; geen handmatige override nodig.
8. Leverancier-all-in blijft geblokkeerd zolang officiële contractcomponenten ontbreken.

Gebruik GEEN Home Assistant Terminal en GEEN handmatige Git-commit/push.

Gebruik GEEN Home Assistant Terminal.
Historische EPEX juli 2026 blijft gedeeltelijk (bron t/m 2026-07-29).
Gebruik GEEN handmatige Git-commit of Git-push.
