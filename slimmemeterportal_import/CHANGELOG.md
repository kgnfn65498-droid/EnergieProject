# Changelog

## 32.3.37

- Browserformulier voor historische rapportherbouw toont nu altijd een voortgangspagina onder Home Assistant Ingress; ruwe JSON blijft alleen voor expliciete fetch/API-aanroepen.
- De voortgangspagina pollt automatisch naar de succes/fout-resultaatpagina en behoudt de ingress-veilige retourroute.
- De JavaScript/fetch-route vraagt expliciet JSON, zodat zowel Safari fallback als de bestaande async-consoleflow correct werken.
