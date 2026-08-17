# Changelog

## 32.3.7 - Assistant full analysis cache hotfix
- De volledige gevalideerde assistant-analyse wordt vóór runtime-acceptance opgebouwd en daarna read-only uit geheugen geleverd.
- Herhaalde vragen herlezen geen SMP raw-, EPEX- of maandanalysebronnen binnen de request-gate.
- Achtergrondrefresh iedere 15 minuten houdt de context actueel; bij fout blijft de laatst geldige cache behouden.
- De bestaande 5-seconden probe en alle kwaliteit-/write/action-guards blijven ongewijzigd.
- Geen rechtenverruiming, brondatawrite, device-control, contractmutatie, maandafsluiting of `finalize_month`.
