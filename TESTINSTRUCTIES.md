# Testinstructies v10.5.2

## Eenmalige overgang
v10.5.2 moet nog één keer via de bestaande Home Assistant Git-route naar GitHub worden gepubliceerd, omdat v10.5.1 de automatische publisher nog niet bevat.

## Na installatie
1. Open de Energieproject-console.
2. Klik bij `HA-publicatie` op `Toon publicatiesleutel`.
3. Kopieer de `ssh-ed25519 ...` sleutel.
4. Open GitHub > EnergieProject > Settings > Deploy keys > Add deploy key.
5. Plak de sleutel, geef hem een herkenbare naam en vink `Allow write access` aan.
6. Zet in de add-onconfiguratie `github_publication_enabled` aan.
7. Herstart de add-on.
8. Klik opnieuw `Toon publicatiesleutel`; status moet `Automatisch` / `GitHub bereikbaar` worden.

## Definitieve praktijktest
9. De opvolgende release hoeft daarna alleen nog naar `EnergieProject_Inbox/incoming`.
10. QNAP installeert, Home Assistant publiceert automatisch naar GitHub en HA ziet vervolgens de update.
11. Geen Terminal/SSH meer voor normale releases.
