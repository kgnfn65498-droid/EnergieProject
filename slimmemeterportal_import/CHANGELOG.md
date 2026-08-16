# Changelog

## 32.3.3 - Assistant runtime mount-timing hotfix
- Wacht vóór de assistant self-probe op de werkelijk bestaande QNAP-projectmount en resolveert het acceptance-pad pas daarna.
- Voorkomt een stale import-time NAS-pad wanneer de HA-netwerkmount tijdens app-import nog niet beschikbaar was.
- Fail-closed: geen lokale fallbackstructuur, Voice blijft gesloten bij ontbrekende mount.
- Geen wijziging aan assistant-inhoud, energieactuals, automatische maandafsluiting, `finalize_month`, MCP-rechten of system-pad guard.
