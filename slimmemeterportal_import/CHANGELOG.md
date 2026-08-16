# Changelog

## 32.3.5 - Assistant fast-context runtime hotfix
- `/api/assistant/context` gebruikt een begrensde maandcontext in plaats van de zware jaarbrede beheeranalyse.
- Home Assistant kwartierdata voor import/export/gas wordt in één read-only snapshotpass gelezen.
- Assistant-bronnen worden op runtime tegen de daadwerkelijk gemounte QNAP-root geresolved.
- De 5-seconden probe, fixed loopbackroutes en alle write/action-guards blijven ongewijzigd.
- Geen rechtenverruiming, device-control, contractmutatie, maandafsluiting of `finalize_month`.
