# Changelog

## 32.3.6 - Assistant quarter-hour prewarm/cache hotfix
- De actuele kwartierreeks wordt één keer vóór de runtime-acceptance volledig gevalideerd en in geheugen gecachet.
- Latere assistantvragen herlezen bestaande snapshots niet; alleen nieuw toegevoegde kwartierbestanden worden incrementeel verwerkt.
- De bestaande 5-seconden probe en alle kwaliteit-/write/action-guards blijven ongewijzigd.
- Geen rechtenverruiming, brondatawrite, device-control, contractmutatie, maandafsluiting of `finalize_month`.
