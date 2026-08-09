# Testinstructies v10.5.39

1. Zet `EnergieProject_v10.5.39.zip` in `EnergieProject_Inbox/incoming`.
2. Wacht tot de release naar `processed` is verplaatst en Home Assistant de update ziet.
3. Installeer v10.5.39 en open daarna direct de Web UI.
4. Controleer dat de hoofd-GUI opent zonder melding “app lijkt nog niet klaar te zijn”.
5. Open **Rapportpagina** en controleer dat deze als HTML opent.
6. Stuur één screenshot van de geopende GUI.

Verwacht: versie 10.5.39; GUI en rapportpagina openen; geen `NameError: item is not defined`; achtergrondfuncties blijven draaien.

Gebruik GEEN Home Assistant Terminal.
Gebruik GEEN handmatige Git-commit of Git-push.

Juli-EPEX blijft `gedeeltelijk` t/m 2026-07-29.
