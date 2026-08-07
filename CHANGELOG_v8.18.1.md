# Changelog v8.18.1

- Herstelt de Home Assistant Web UI / 502 Bad Gateway van v8.18.0.
- Oorzaak: `monitoring_snapshot()` riep de niet-bestaande functie `atomic_write_json()` aan.
- Correctie: monitoring gebruikt nu de reeds bestaande productiehelper `write_atomic_json()`.
- Monitoring v8.18 blijft inhoudelijk ongewijzigd.
- Geen wijzigingen aan workflow, scheduler, recovery, audittrail, productiecertificaten of rapportgeneratoren.
