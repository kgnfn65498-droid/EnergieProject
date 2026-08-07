# Changelog v8.18.0

- Nieuwe productiemonitoring voor API, workflow, productiecertificaat, audittrail, recovery, scheduler en bronstatus.
- Monitoring wordt tijdens normale consolepolling maximaal iedere 30 seconden opnieuw beoordeeld; dit voorkomt onnodige schrijfacties.
- Alleen echte statuswijzigingen worden append-only opgeslagen in `/config/output/monitoring_history.jsonl`.
- De laatste monitoringsnapshot wordt duurzaam opgeslagen in `/config/output/monitoring_state.json`.
- Statuswijzigingen worden, zolang de auditketen geldig is, ook als `monitoring`-event in de bestaande audittrail vastgelegd.
- Nieuwe compacte kaart **Monitoring v8.18** met totaalstatus, actieve waarschuwingen, laatste controle en controles per subsysteem.
- Nieuwe knop **Controleer monitoring nu** en download van de monitoringhistorie.
- Gezondheidsdashboard neemt de monitoringstatus mee in de projectscore.
- De oude titel `Audittrail v8.16` is generiek gemaakt tot **Audittrail**; inhoud en hashketen zijn niet gewijzigd.
- Recovery v8.17 blijft intact; maandworkflow, scheduler, retry-state, productiecertificaatlogica en rapportgeneratoren zijn inhoudelijk ongewijzigd.
