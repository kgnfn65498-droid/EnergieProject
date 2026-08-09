# Testinstructies v10.9.1

1. Plaats `EnergieProject_v10.9.1.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht op verwerking naar `processed`.
3. Update de Home Assistant-app naar **10.9.1** en controleer GUI/Ingress.
4. Download **Analyse-export** en **release-diagnose**.
5. Verwacht in de analyse een `production_consolidation`-blok met guarded production readiness.
6. Ontbrekende NextEnergy-contractcomponenten moeten nog steeds ontbreken/null blijven.
7. De prognose moet bij minder dan 7 waargenomen dagen geblokkeerd blijven.
8. EPEX mag nergens leverancier-all-in worden genoemd.

Gebruik GEEN Home Assistant Terminal en GEEN handmatige Git-commit of Git-push.

Gebruik GEEN Home Assistant Terminal.
Historische EPEX juli 2026 blijft gedeeltelijk met laatste bronrecord 2026-07-29.
Gebruik GEEN handmatige Git-commit of Git-push.
