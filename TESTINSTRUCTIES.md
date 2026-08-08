# Testinstructies v10.0.0

1. Commit/push v10.0.0, kies in Home Assistant **Opnieuw bouwen** en open de Web UI. Er is geen nieuwe **Test automatische maandafsluiting nu** nodig: de productiekern `9.4-core1` is inhoudelijk ongewijzigd en v9.9.0 is al GO beoordeeld.
2. Controleer bovenaan dat **versie 10.0.0**, **Productieklaar**, scheduler **Actief** en health **100%** zichtbaar zijn. Klik daarna **Download diagnosepakket** en stuur mij alleen die ZIP.
3. Goedkeuringscriteria: `beoordeling.json` bevat `"verdict": "GO"`; `samenvatting.txt` toont softwareversie 10.0.0, **Releasefase: Stable**, productiekern `9.4-core1` en **Kerncertificaat geldig: JA**.
