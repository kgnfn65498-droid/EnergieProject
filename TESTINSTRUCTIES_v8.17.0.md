# Home Assistant testinstructies v8.17.0

Doel: in één compacte productietest zowel de v8.16.1 navigatiefix als de nieuwe Recovery v8.17 controleren.

1. Commit/push en deploy v8.17.0. Open SlimmeMeterPortal en controleer dat **versie 8.17.0** zichtbaar is. Controleer op dezelfde pagina dat **Recovery v8.17** na de add-onstart een recente controle toont en dat de bestaande audittrail nog `ok` is.
2. Voer één keer **Test automatische maandafsluiting nu** uit voor `2026-08`. Wacht op `completed`. Daarna moeten Productiegereedheid **Productieklaar**, certificaat **v8.17.0 afgegeven**, auditintegriteit `ok` en gezondheid 100% zijn.
3. Klik daarna één keer **Controleer / herstel productiecertificaat**. De pagina moet gewoon zichtbaar blijven: géén zwarte/lege pagina en géén losse JSON-pagina. De melding moet **Certificaat gecontroleerd — geldig** tonen.
4. Klik aansluitend één keer **Controleer recovery nu**. Dit mag geen maandworkflow starten. Recovery moet `ok` of een duidelijke `attention` met reden tonen; bij een normale installatie wordt 0 herstelacties verwacht. De audittrail moet een `recovery_controller`-record bevatten.

Stuur daarna één of twee screenshots waarop tegelijk Productiestatus/Recovery en Audittrail/Gezondheidsdashboard zichtbaar zijn. Daarna wordt pas de volgende versie gebouwd.
