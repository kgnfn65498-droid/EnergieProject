# Testinstructies v10.5.13

Omdat de huidige live watcher (10.5.11) een `.zip` al kan oppakken terwijl Finder nog kopieert:
1. Download `EnergieProject_v10.5.13.upload`.
2. Sleep dit bestand volledig naar `EnergieProject_Inbox/incoming`.
3. Wacht tot Finder klaar is.
4. Hernoem IN `incoming` alleen de extensie `.upload` naar `.zip`.
5. Daarna doet de QNAP alles automatisch.
6. Installeer 10.5.13 in Home Assistant en herstart SlimmeMeterPortal Import één keer.
7. Klik **Download analysedata** en stuur het JSON-bestand.

Vanaf 10.5.13 mag een volgende `.zip` weer rechtstreeks naar `incoming`: de watcher wacht dan zelf tot de kopie compleet is.

Gebruik GEEN Home Assistant Terminal. Gebruik GEEN handmatige Git-acties.
Verwacht bij bereikbare EPEX-bron voor juli 2026: `gedeeltelijk` t/m `2026-07-29`, 2784 stroomrecords en 696 gasrecords.
Gebruik GEEN handmatige Git-commit of Git-push.
