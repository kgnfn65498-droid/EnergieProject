# Home Assistant testinstructies v8.18.0

Doel: in één compacte testronde de nieuwe monitoring én de bestaande productieketen controleren.

1. Commit/push en deploy v8.18.0. Open SlimmeMeterPortal en controleer dat **versie 8.18.0** zichtbaar is. De nieuwe kaart **Monitoring v8.18** moet aanwezig zijn. Voor de productietest mag Monitoring tijdelijk `warning` tonen omdat het v8.18.0-certificaat nog ontbreekt.
2. Voer één keer **Test automatische maandafsluiting nu** uit voor `2026-08`. Wacht op `completed`. Klik daarna één keer **Controleer monitoring nu**. Verwacht: Productiegereedheid **Productieklaar**, productiecertificaat **v8.18.0**, Monitoring **ok**, 0 actieve waarschuwingen, Audittrail `ok` en Gezondheidsdashboard 100%.
3. Controleer in de Audittrail dat minimaal één `monitoring`-record aanwezig is en dat de bestaande recovery/auditrecords behouden zijn. Klik desgewenst **Download monitoringhistorie**; het bestand moet `monitoring_history.jsonl` heten.

Stuur screenshots waarop **Productiestatus + Monitoring** en **Audittrail + Gezondheidsdashboard** zichtbaar zijn. Daarna eerst beoordeling voordat de volgende versie wordt gebouwd.
