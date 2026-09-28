# DEV CHECKPOINT 32.5.27 — PREINSTALL GREEN

Exact predecessor: EnergieProject_v32.5.26.zip
SHA256: e0ffa48b93e42b8ef09319775b1a54b8e25a9e7719a30d347762c1dcdeed71f5

## Correcties
- Inbox/processing permanent mailbox; idle aanwezig en leeg.
- ReleaseController/HA delivery/recovery verwijderen Processing niet.
- Post-live audit gebruikt processing_directory_present_and_empty.
- Finale Type-3/Inbox cleanup sluit Processing uit van remove/quarantine/soak-forbidden.
- ClearUp_011 publication-state blijft canoniek onder Data/03_Systeem.
- Canonieke Publication directory/file modes worden na COMPLETE 0777/0666 voor cross-identity HA atomic writes.

## Acceptance vóór artifact build
- Static: 600 passed, 2 skipped.
- 32.5.x geselecteerde regressies: 208 passed.
- late 32.4.59–32.4.67 regressies: 68 passed.
- totaal geselecteerd: 876 passed.
- compileall GREEN.
- shell syntax 13/13 GREEN.

Type-2 002–012 blijft CLOSED; geen live rerun.
