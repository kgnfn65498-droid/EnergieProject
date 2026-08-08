# Testinstructies v10.5.8

1. Plaats `EnergieProject_v10.5.8.zip` in `EnergieProject_Inbox/incoming`.
2. Laat de automatische keten verwerken en installeer v10.5.8 via **Bijwerken**.
3. Herstart daarna één keer **SlimmeMeterPortal Import** zodat de nieuwe Python-code zeker actief is. Gebruik GEEN Home Assistant Terminal. Gebruik GEEN handmatige Git-commit of Git-push.
4. Open **Energieproject** en controleer bovenaan versie `10.5.8`, workflow `idle`, releaseketen `Automatisch` en HA-publicatie `Automatisch`.
5. Klik **Download analysedata** en stuur alleen het gedownloade JSON-bestand terug.

Verwacht voor juli 2026: EPEX stroom en gas beschikbaar, met dekking `gedeeltelijk` t/m 2026-07-29. Augustus mag nog `not_available` zijn zolang daar geen EPEX-maandbestand voor bestaat. Geen maandworkflow starten.
