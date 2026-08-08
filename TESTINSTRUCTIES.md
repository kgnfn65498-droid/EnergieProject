# Testinstructies v10.5.11

1. Laat `EnergieProject_v10.5.10.zip` in `failed` staan; verplaats die NIET terug.
2. Plaats alleen `EnergieProject_v10.5.11.zip` in `EnergieProject_Inbox/incoming`.
3. Wacht op de automatische QNAP-verwerking.
4. De ZIP moet naar `processed` gaan en mag niet meer in `failed` eindigen.
5. Home Assistant moet daarna update `10.5.11` aanbieden.
6. Installeer 10.5.11 via Home Assistant en herstart daarna één keer **SlimmeMeterPortal Import**.
7. Controleer versie `10.5.11` en workflow `idle`.
8. Klik **Download analysedata** en stuur alleen dat JSON-bestand terug.

Gebruik GEEN Home Assistant Terminal. Gebruik GEEN handmatige Git-commit of Git-push.
Geen maandworkflow starten.

Verwacht in de analysedata voor juli 2026 nog steeds de v10.5.10 EPEX-correctie:
`resolved_path = /share/Energie_NAS/05_Maanddata/EPEX`, gedeeltelijke dekking t/m 2026-07-29,
2784 stroomrecords en 696 gasrecords.
