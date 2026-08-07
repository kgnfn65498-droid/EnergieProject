# Testinstructies v9.0.0

1. Commit/push v9.0.0, kies in Home Assistant **Opnieuw bouwen**, start de app en open de Web UI. Controleer dat overal versie 9.0.0 zichtbaar is.
2. Voer één keer **Test automatische maandafsluiting nu** uit voor `2026-08`. Na afronding moeten Productiestatus en Productiecertificaten zonder handmatige refresh v9.0.0 tonen.
3. Eindcontrole: Recovery v9.0.0 `ok`, Monitoring v9.0.0 `ok` met 0 waarschuwingen, Audittrail v9.0.0 integriteit `ok`, Gezondheidsdashboard 100%, Retry Debug `FOUND · geldig JA` en `9.0.0 · verwacht 9.0.0`.
