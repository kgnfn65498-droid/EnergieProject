# Changelog

## 32.3.35

- De retourknop na succesvolle historische rapportherbouw gebruikt nu de Home Assistant ingress-root uit `X-Ingress-Path`.
- Buiten Home Assistant ingress blijft `./` de veilige fallback.
- De regressietest dekt expliciet de ingress-navigatie.
