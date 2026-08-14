# v32.0.30 Crash Recovery heartbeat fix — Design

## Doel
De browser-Crash-Recovery moet succesvol kunnen exporteren terwijl de kwartiercollector/scheduler zijn normale heartbeat blijft bijwerken, zonder de bestaande integriteitscontrole voor gewone projectbestanden te versoepelen.

## Oorzaak
`build_recovery_export()` inventariseert vóór het ZIP-bouwen voor ieder bestand grootte en `mtime_ns` en controleert die waarden na afloop opnieuw. `Data/01_Input/_scheduler/quarter_hour_heartbeat.json` is een verwacht veranderend runtimebestand. Een normale heartbeat tijdens het ZIP-bouwen veroorzaakt daardoor een `RuntimeError: Projectinhoud wijzigde tijdens Crash Recovery export`.

## Ontwerp
1. Het heartbeatbestand blijft onderdeel van de Crash Recovery; het wordt niet uitgesloten.
2. Voor precies `Data/01_Input/_scheduler/quarter_hour_heartbeat.json` wordt tijdens de inventarisatie een stabiele byte-snapshot gemaakt. De ZIP schrijft die snapshot in plaats van het live bestand opnieuw te lezen.
3. De post-build size/mtime-consistentiecontrole blijft ongewijzigd streng voor alle andere projectbestanden. Alleen het expliciet benoemde heartbeatbestand wordt niet afgekeurd wanneer het live bestand tijdens de export verder verandert.
4. Symlinks blijven verboden. De bestaande uitsluitingen blijven exact: `Energie_Complete_Backup_*.zip`, `FULL_RECOVERY*.tar.gz` en `.DS_Store`.
5. De downloadnaam wordt menselijk leesbaar en filesystem-veilig: `YYYY-MM-DD HH.MM CrashRecovery EnergieProject.zip`. Geen dubbele punt in de tijd.
6. Geen wijziging aan maandafsluiting, juli-status, `finalize_month`, normale NAS-backupretentie of RestoreStaging-veiligheid.

## Foutafhandeling
- Als een gewoon projectbestand tijdens export verandert of verdwijnt, blijft de export falen en wordt de tijdelijke ZIP verwijderd.
- Als de heartbeat na snapshot verandert, blijft de export geldig: de ZIP bevat de complete heartbeat-versie die tijdens de snapshot is gelezen.
- Als het heartbeatbestand bij inventarisatie niet bestaat, is er niets speciaals te doen; de normale bestandsinventarisatie bepaalt de inhoud.

## Tests
- Reproduceer RED: wijzig `quarter_hour_heartbeat.json` nadat de inventaris is gemaakt maar vóór de post-buildcontrole; v32.0.29 faalt.
- GREEN: dezelfde test moet slagen en de ZIP moet de oorspronkelijke snapshotbytes bevatten.
- Bewijs dat een ander veranderend bestand nog steeds faalt.
- Test de exacte bestandsnaamvorm zonder `:`.
- Volledige regressiesuite en Python-compile moeten groen zijn.
