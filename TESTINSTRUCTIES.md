# Testinstructies v10.5.9

1. Plaats `EnergieProject_v10.5.9.zip` in `EnergieProject_Inbox/incoming`.
2. Installeer via de normale automatische Home Assistant-update.
3. Herstart daarna één keer **SlimmeMeterPortal Import**. Gebruik GEEN Home Assistant Terminal. Gebruik GEEN handmatige Git-commit of Git-push.
4. Controleer bovenaan versie `10.5.9` en workflow `idle`.
5. Klik **Download analysedata** en stuur alleen het JSON-bestand terug.

Verwacht voor juli 2026:
- `price_context.coverage.status = "gedeeltelijk"`
- `last_date = "2026-07-29"`
- stroom `available = true`, 2784 observaties, frequentie `kwartier`
- gas `available = true`, 696 observaties, frequentie `uur`
- `resolved_path` toont het werkelijk gebruikte EPEX-pad.

Geen maandworkflow starten.
