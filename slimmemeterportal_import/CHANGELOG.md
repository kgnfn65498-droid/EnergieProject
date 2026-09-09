# Changelog

## 32.4.20 — clock-skew-onafhankelijke watcher-liveness

- Watcher-liveness gebruikt bij cross-host clock skew een begrensde heartbeat pulse-probe in plaats van absolute wall-clock leeftijd.
- Geen puls blijft fail-closed RED; een veranderende heartbeat bewijst live watcher zonder tijdsynchronisatie te veronderstellen.
- Release-closure behoudt de transactionele 32.4.18 state-machine en de 32.4.19 correcte gate-returncodes.
- Projectmanager V2 2.0.0-rc17.
