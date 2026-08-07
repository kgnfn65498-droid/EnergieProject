# Testinstructies v9.7.0

1. Commit/push v9.7.0, kies in Home Assistant **Opnieuw bouwen**, open de Web UI en controleer dat **Productieklaar** zichtbaar is. Download daarna **Download diagnosepakket** en stuur mij alleen die ZIP. Een screenshot is alleen nodig als de Web UI afwijkend oogt. Er is géén nieuwe **Test automatische maandafsluiting nu** nodig zolang productiekern `9.4-core1` geldig blijft.

Goedkeuringscriteria: `samenvatting.txt` meldt **Automatische technische beoordeling: GO**, `beoordeling.json` bevat `"verdict": "GO"`, alle criteria staan op `true`, `SHA256SUMS.txt` is aanwezig en de healthscore is 100 zonder echte fouten.
