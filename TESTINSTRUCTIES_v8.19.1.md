# Testinstructies v8.19.1

1. Commit/push, **Opnieuw bouwen** en start v8.19.1 in Home Assistant. Controleer dat de Web UI normaal opent.
2. Voer één keer **Test automatische maandafsluiting nu** uit voor `2026-08` en laat de pagina open. Na afronding moeten Productiestatus én Productiecertificaten zonder handmatige refresh v8.19.1 tonen.
3. Open onderaan **Retry Debug v8.19.1**. Daar moet staan: productiecertificaat `FOUND · geldig JA`, certificaatversie `8.19.1 · verwacht 8.19.1` en certificaatintegriteit `ok`. Gezondheidsdashboard moet 100% blijven.
