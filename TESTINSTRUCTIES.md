# Testinstructies v9.6.0

1. Commit/push v9.6.0, kies in Home Assistant **Opnieuw bouwen**, open de Web UI en controleer dat **Productieklaar** zichtbaar is. Download daarna **Download diagnosepakket** en stuur mij alleen dat ZIP-bestand. Een extra screenshot is alleen nodig als de Web UI zelf afwijkend oogt. Er is géén nieuwe **Test automatische maandafsluiting nu** nodig zolang productiekern `9.4-core1` geldig blijft.

Goedkeuringscriteria: het diagnosepakket opent zonder fout, bevat `samenvatting.txt` en `SHA256SUMS.txt`, en de samenvatting meldt geldige kerncertificering, 100%/gezonde status zonder echte fouten en een actieve scheduler.
