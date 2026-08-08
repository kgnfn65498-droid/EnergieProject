# Installatie / praktijktest v10.4.2

## Voorwaarde
- v10.4.1 staat actief op de NAS en GitHub.
- `release_watcher.sh` draait en toont `Release watcher gestart; interval=30s`.

## v10.4.2 testen
1. Plaats `EnergieProject_v10.4.2.zip` in:
   `AI Projecten/EnergieProject_Inbox/incoming`
2. **Voer geen Terminal-commando uit.**
3. Wacht ongeveer 30–60 seconden.
4. De watcher hoort automatisch te valideren, back-uppen, installeren, committen/pushen en de ZIP naar `processed` te verplaatsen.
5. Controleer daarna GitHub: `main` moet v10.4.2 tonen.
6. Home Assistant mag daarna de normale app-update naar 10.4.2 aanbieden; die update blijft vooralsnog een bewuste handmatige Home Assistant-handeling.

## Bij fout
- Geen handmatige reparaties uitvoeren.
- Laat de ZIP in `failed` staan en deel de watcher-/installeruitvoer.
- De gevalideerde herstelbackup en GitHub-baseline blijven de herstelbron.

## Productiekern
`9.4-core1` blijft ongewijzigd.
