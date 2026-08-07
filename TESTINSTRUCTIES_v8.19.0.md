# Testinstructies v8.19.0

1. Commit/push, **Opnieuw bouwen** en start v8.19.0 in Home Assistant. Open de Web UI en controleer dat de koppen **Recovery v8.19.0**, **Monitoring v8.19.0** en **Audittrail v8.19.0** tonen.
2. Voer eenmaal **Test automatische maandafsluiting nu** uit voor `2026-08`. Laat de pagina openstaan: na afronding moet Productiestatus zonder handmatige paginaverversing omslaan naar **Productieklaar** met een geldig **v8.19.0** productiecertificaat; ook de certificaathistorie moet v8.19.0 tonen.
3. Controleer daarna in één keer: Monitoring `ok` met 0 waarschuwingen, Recovery `ok`, Auditintegriteit `ok` en Gezondheidsdashboard 100%.

Stuur daarna screenshots van Productiestatus en van Recovery/Monitoring/Audittrail/Gezondheidsdashboard.
