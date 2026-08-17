# Changelog

## 32.3.8 - Home Assistant conversation transport
- Nieuwe read-only `/api/assistant/respond`-route met exact dezelfde requestlimiet en payloadguard als de geaccepteerde contextroute.
- Secret-free Supervisor discovery met `hassio_api: true` / `hassio_role: default` voor `energie_assistant` op de interne app-poort 8099; geen externe poortmapping.
- De bestaande zeven-check runtimeacceptatie, analyse-/kwartiercaches en 5-seconden requestgate blijven ongewijzigd.
- Geen device-control, contractmutatie, projectwrite, rechtenverruiming, maandafsluiting of `finalize_month`.
