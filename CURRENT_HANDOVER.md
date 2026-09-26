# CURRENT HANDOVER — EnergieProject 32.5.16

## Actuele ontwikkelpositie
- Runtime-statusautoriteit: canonieke `Data/03_Systeem/Projectmanager/RuntimeV2`; retired Inbox-routes zijn na hun Type-2 activatie geen actieve waarheid.
- Live predecessor bij build: 32.5.15, exacte SHA256 `d95be5bb054c0e4b2fdd2d666a85f464fb934e2b4d20e29b3b365c03665810f3`.
- Deze 32.5.16 vervangt alle eerdere 32.5.16-kandidaten en hashes. Alleen de fysieke ZIP die bij deze acceptance hoort mag worden gebruikt.
- Hoofddoel: ClearUp Type-2 002–012 betrouwbaar afmaken zonder dat Peter technische tussenstappen hoeft te managen.
- ClearUp_002 is live al gemigreerd en blijft MIGRATED_PENDING_VALIDATION; 32.5.15 recovery-refresh faalde fail-closed door post-cutover RuntimeV2-drift.
- 32.5.16 herstelt die recovery, sluit de vluchtige PREPARED-recovery foutklasse (o.a. 012) en borgt path-rebinding van actieve readers/writers.
- Geen destructive Type-2 finalize/delete vóór externe recoveryontvangst.

## Autonome vervolgroute na installatie
1. Controleer 32.5.16 COMPLETE, PM/runtime readback en Native-MCP.
2. Refresh ClearUp_002 non-destructief en deep-verify de nieuwe recovery-ZIP.
3. Refresh/deep-verify zo nodig 003–012; alle elf exports moeten individueel GREEN zijn.
4. Download de echte 002–012 ZIP's naar de ChatGPT-workspace en verifieer lokaal size + SHA256.
5. Lever de ZIP's aan Peter. Stop destructive acties totdat Peter expliciet ontvangst bevestigt.
6. Daarna validate/finalize ieder Type-2 onderdeel gecontroleerd; controleer na ieder onderdeel dat de oude route niet terugkomt.
7. Werk autonoom door zonder normale tussencommentaren; stop alleen bij een echte harde gate.

## Handoverregel
Een chatwissel is pas volledig wanneer de actuele taak/PM-KB-state én de laatste exact geaccepteerde fysieke release-ZIP met bestandsnaam, grootte en SHA256 beschikbaar zijn. Een hash/checkpoint zonder fysiek artifact is geen GREEN overdracht.
