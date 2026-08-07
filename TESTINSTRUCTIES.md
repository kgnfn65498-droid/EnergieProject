# Testinstructies v9.1.0

1. Commit/push v9.1.0, kies in Home Assistant **Opnieuw bouwen**, start de app en open de Web UI. Vóór de v9.1.0-productietest mag de console **Nog niet gecertificeerd** tonen; Monitoring hoort daarbij 0 fouten en alleen aandachtspunten te melden. Het Gezondheidsdashboard hoort duidelijk hoger te blijven dan de oude 75%-weergave.
2. Voer één keer **Test automatische maandafsluiting nu** uit voor `2026-08`. Laat de pagina open; na afronding moeten Productiestatus en **Archief productiecertificaten** automatisch v9.1.0 tonen.
3. Eindcontrole: Recovery v9.1.0 `ok`, Monitoring v9.1.0 `ok` met **0 fouten / 0 aandachtspunten**, Audittrail v9.1.0 integriteit `ok`, Gezondheidsdashboard **100%**, Retry Debug `FOUND · geldig JA` en `9.1.0 · verwacht 9.1.0`.
