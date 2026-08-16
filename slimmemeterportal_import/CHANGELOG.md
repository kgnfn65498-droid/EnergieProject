# Changelog

## 32.3.4 - Assistant acceptance writable-handoff hotfix
- Schrijft het read-only assistant acceptance-resultaat naar `Inbox/logs/assistant_runtime_acceptance.json`, een bestaande HA-schrijfbare handoff.
- Vermijdt directe write naar de bewust 0755 Projectmanager-State-map; geen ACL/rechtenverruiming.
- Projectmanager valideert/promoveert het bewijs daarna gecontroleerd naar canonieke State.
- Geen wijziging aan assistant-inhoud, energieactuals, automatische maandafsluiting, `finalize_month`, MCP-rechten of system-pad guard.
