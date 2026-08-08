# Testinstructies v10.5.17

## Eenmalige overgang
1. Laat mislukte v10.5.16 in `failed` staan.
2. Plaats `EnergieProject_v10.5.17.ready` volledig in `EnergieProject_Inbox/incoming`.
3. Hernoem pas na volledig kopiëren `.ready` naar `.zip`.
4. Omdat de huidige losse watcher gestopt is, start deze overgang één laatste keer via de bestaande watcher/installer.
5. Na succesvolle installatie van 10.5.17 voer één keer uit:
   `sh "/share/AI Projecten/EnergieProject/tools/bootstrap_release_watcher_container.sh"`
6. Daarna moet in Container Station een vijfde groene container staan: `energie-release-watcher`.

Vanaf daarna:
- alleen een normale `.zip` in `incoming`;
- geen Terminal voor releases;
- geen `.ready`;
- geen watcher-PID/lock handelingen.

Gebruik GEEN Home Assistant Terminal. Gebruik GEEN handmatige Git-commit of Git-push.

Na installatie blijft juli-EPEX `gedeeltelijk` t/m 2026-07-29; dat is de bekende brondekking.
