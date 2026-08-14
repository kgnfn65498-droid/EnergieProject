# Changelog

## 32.0.32 - Crash Recovery watcher-cleanup
- Na een volledig geslaagde browserdownload verwijdert Home Assistant alleen de lokale export-ZIP.
- Exacte NAS-runartefacten worden daarna automatisch opgeruimd door de bestaande QNAP/Docker-watcher.
- Cleanup accepteert uitsluitend `Energie_Complete_Backup_*.zip`, het exact afgeleide manifest en één concrete `/recovery/RestoreStaging/`-run.
- Maandbackups, `FULL_RECOVERY*.tar.gz`, release-ZIP's en willekeurige paden zijn expliciet uitgesloten.
- Een bestaande v32.0.31 cleanup-warning wordt zonder nieuwe backup veilig opnieuw aan de watcher aangeboden.
- Backendketen blijft GUI-onafhankelijk en is daarmee geschikt voor latere start via spraakopdracht.
- Geen wijziging aan maandafsluiting, juli-status, `finalize_month` of automatische iCloud-upload.
