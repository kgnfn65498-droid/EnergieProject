# Changelog

## 32.4.16 — automatische ingress/acceptance closure

- Sluit de combinatie van exact één wachtende `incoming`-ZIP en de huidige geldige `LIVE_ACCEPTANCE` automatisch af zonder handmatige hold of accept-commando's.
- Houdt watcher-ingress fail-closed tot de atomic state canoniek `ACCEPTED` is; daarna kan de volgende ZIP via `processing` naar `processed` doorstromen.
- Legt de releasefout, root cause en regressiepreventie vast in de Projectmanager Knowledge Base, roadmap en ontwikkelafspraken.
- Projectmanager V2 2.0.0-rc13.
