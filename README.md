# EnergieProject v10.3.1 – Hardened Release Inbox Installer

v10.3.1 hardent de werkende NAS-releaseketen: volledige tar-backup/rollback, controle op tracked én untracked wijzigingen, expliciete teststatus en een harde eindcontrole dat lokale `main` en GitHub `main` exact gelijk zijn. De gecertificeerde productiekern blijft 9.4-core1.

## Nieuw
- Volledige tar-backup vóór iedere live vervanging en validatie dat de backup daadwerkelijk leesbaar is.
- Volledige tar-rollback van de vorige worktree bij fouten vóór een bevestigde GitHub-push; `.git` blijft behouden.
- Installer blokkeert op tracked én untracked lokale wijzigingen en wanneer lokale `main` niet exact gelijk is aan GitHub `main`.
- ZIP-integriteit, verplichte bestanden, `MANIFEST.sha256`, post-installatiehashes en shellsyntax zijn verplichte controles.
- Python/pytest wordt alleen uitgevoerd wanneer het op de host beschikbaar is; ontbrekende runtime wordt expliciet als `NIET UITGEVOERD` gelogd in plaats van stil overgeslagen.
- Een geslaagde release wordt pas naar `processed` verplaatst nadat lokale HEAD en GitHub `main` dezelfde commit hebben en de repository clean is.
- Productiekern blijft `9.4-core1`.

De installer is bewust een host-side tool voor de Home Assistant Terminal/SSH-omgeving. Daarmee gebruikt hij de reeds werkende GitHub deploy key zonder die private sleutel in de Energie-app of op de SMB-share te hoeven opslaan.
