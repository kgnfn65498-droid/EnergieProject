# Changelog

## 32.4.23 — audit-closure maandveiligheid en PM-ingress

- Tri-state RecoveryManager-truth `CLOSED_VALID / OPEN / UNKNOWN`; UNKNOWN blokkeert automatische maandafsluiting fail-closed.
- Deep-verified CLOSED-predicate gedeeld tussen scheduler en Projectmanager-health; dynamische closure-status wordt vers opgevraagd.
- Onafhankelijke scheduler-, preflight- en executor-guards plus sterkere startup readiness.
- Productiekern `9.4-core2` en productiecertificaatbewuste release-hold.
- Projectmanager V2 `2.0.0-rc20`: semantische roadmap/cycle-validatie, Voice/new-chat gates vóór 32.5 en beperkte authenticated externe PM-ingress voor ngrok.
- Geen publieke exposure van de volledige 8099-webserver; atomic/watcher/publisher blijven ongewijzigd.
