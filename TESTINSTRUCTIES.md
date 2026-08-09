# Testinstructies v10.8.2

1. Plaats `EnergieProject_v10.8.2.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht tot de QNAP release-watcher de ZIP naar `processed` heeft verplaatst.
3. Installeer/update de SlimmeMeterPortal-app in Home Assistant naar **10.8.2**.
4. Controleer dat GUI/Ingress normaal opent.
5. Voer **Analyse-export** uit.
6. Voer **release-diagnose** uit.
7. Controleer bij een rapport-/maandworkflow dat pagina 2 geen voorbeeldtarieven, fictieve gaskosten of fictief termijnadvies toont wanneer contractdata ontbreekt.
8. Lever analyse-JSON en release-diagnose aan voor validatie.

Verwacht: ontbrekende leverancier-all-in componenten blijven `null`/niet beschikbaar; EPEX blijft referentie; bestaande workflow blijft gezond.

Aanvullende regressieregels: Gebruik GEEN Home Assistant Terminal. Juli-EPEX mag historisch als gedeeltelijk gemarkeerd blijven wanneer de brondekking gedeeltelijk is.

Gebruik GEEN handmatige Git-commit of Git-push. Historische juli-EPEX-dekking eindigt in de huidige bron op 2026-07-29 en blijft daarom gedeeltelijk.
