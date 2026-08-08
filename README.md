# EnergieProject v10.4.1 – Self-safe Release Watcher

v10.4.1 herstelt het uitvoeringsprobleem uit v10.4.0: installer en watcher draaien voortaan vanuit `/tmp` en nooit vanuit de worktree die tijdens een release wordt vervangen. De gecertificeerde productiekern blijft `9.4-core1`.

## Nieuw
- Installer kopieert zichzelf automatisch naar `/tmp` wanneer hij vanuit `EnergieProject/tools` wordt gestart.
- Rollbackstatus wordt vóór het leegmaken van de worktree geactiveerd; ook een fout tijdens verwijderen triggert daardoor volledige tar-rollback.
- Watcher kopieert zichzelf naar `/tmp` en gebruikt per release een tijdelijke installer-kopie.
- Hierdoor kunnen `tools/` en de rest van de worktree veilig worden vervangen zonder dat het actieve installatieproces zijn eigen script blokkeert.
- ZIP-integriteit, SHA256, verplichte bestanden, GitHub-sync, backupvalidatie en eindcontrole blijven verplicht.
- Productiekern blijft `9.4-core1`.

De installer is bewust een host-side tool voor de Home Assistant Terminal/SSH-omgeving. Daarmee gebruikt hij de reeds werkende GitHub deploy key zonder die private sleutel in de Energie-app of op de SMB-share te hoeven opslaan.
