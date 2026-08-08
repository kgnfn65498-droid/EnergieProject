# Testinstructies v10.4.2

Deze release is de end-to-end test van de automatische release-watcher.

## Test
1. Zorg dat de v10.4.1 watcher nog draait.
2. Zet alleen `EnergieProject_v10.4.2.zip` in `EnergieProject_Inbox/incoming`.
3. Typ daarna **geen commando**.
4. Binnen circa 30–60 seconden moet de watcher de release verwerken.

## Geslaagd wanneer
- `incoming` weer leeg is;
- `processed/EnergieProject_v10.4.2.zip` bestaat;
- `VERSIE.txt` op de NAS `10.4.2` bevat;
- GitHub `main` dezelfde nieuwe commit bevat;
- repository daarna clean is;
- geen handmatige installerstart nodig was.

## Daarna
Controleer of Home Assistant een app-update naar 10.4.2 aanbiedt. Die HA-update zelf blijft voorlopig handmatig.
