# Changelog

## 32.4.30

- CLEARUP runtime-checkpoint verplaatst naar de bewezen schrijfbare runtime-oppervlakte `Inbox/logs/project_clearup_runtime.json`.
- Direct na NAS-rootresolutie wordt `root_resolved` vastgelegd vóór gate/CR/dependencywerk; de 25 minuten harde timeout en fail-closed gedrag blijven intact.
- Checkpoint blijft observationeel; echte dependencies en symlinks blijven fail-closed.
- Geen delete of veiligheidsversoepeling; hard rename, hash, rollback en manifest blijven verplicht.
- Core blijft `9.4-core3`, PM blijft `2.0.0-rc22`.
- Repair: PM-hygiëne telt settled releases in `Inbox/failed` mee, zodat oude failed-builds niet meer buiten de hygiëne-status vallen.
- Releasepackaging gebruikt voortaan de canonieke builder die cache/junk uitsluit en de uiteindelijke ZIP met de atomic membervalidator controleert.
