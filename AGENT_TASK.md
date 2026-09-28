# AGENT_TASK — EnergieProject 32.5.27 processing-mailbox correctie

- mode: DEVELOPMENT
- reasoning: HIGH
- buildbasis: exact verified EnergieProject_v32.5.26.zip SHA256 e0ffa48b93e42b8ef09319775b1a54b8e25a9e7719a30d347762c1dcdeed71f5
- PM target: 2.0.0-rc62
- productieautoriteit: NEE

## Doel
Corrigeer de live bewezen 32.5.26-fout zonder Type-2 te heropenen: Inbox/processing is een permanente mailbox en blijft leeg bestaan na closure. Behoud ClearUp_011 canonieke publication-state locatie en maak het cross-identity writercontract structureel bruikbaar.

## Acceptance
- incoming -> processing -> processed; processing blijft aanwezig en leeg.
- finale Type3/Inbox cleanup verwijdert processing nooit.
- post-live audit accepteert alleen present+empty processing.
- canonical Publication blijft Data/03_Systeem; geen Inbox fallback.
- cross-identity Publication directory/file modes worden na COMPLETE 0777/0666.
- targeted + full regression, compile, shell, fresh-extract, CRC/manifest exact GREEN.

## Platformgrens
Release acceptance en host-capability Platform Qualification zijn afzonderlijke contracten. Host-capability Platform Qualification is geen releasegate en geen bestaande test mag worden verwijderd of verzwakt om GREEN te fabriceren.
