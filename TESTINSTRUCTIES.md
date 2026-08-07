# Testinstructies v9.2.0

1. Commit/push v9.2.0, kies in Home Assistant **Opnieuw bouwen**, start de app en controleer vóór de productietest dat Monitoring **0 fouten** toont en een eventueel ontbrekend v9.2.0-certificaat als **wachtstatus** behandelt.
2. Voer één keer **Test automatische maandafsluiting nu** uit voor `2026-08`. Na afronding moeten Productiestatus en Archief productiecertificaten v9.2.0 tonen.
3. Eindcontrole: Monitoring **0 fouten / 0 wachtstatussen**, Recovery `ok`, Auditintegriteit `ok`, Gezondheidsdashboard **100%**, Retry Debug `9.2.0 · verwacht 9.2.0`. In de Audittrail mag de tijdelijke certificeringsfase als `info` staan; er mag door deze normale overgang geen nieuw `warning`-record ontstaan.
