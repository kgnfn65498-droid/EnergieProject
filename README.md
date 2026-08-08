# EnergieProject v10.3.0 – Release Inbox Installer

v10.3.0 bouwt voort op de goedgekeurde v10.2.0-basis en sluit aan op de inmiddels werkende QNAP-share `AI Projecten`, de actieve NAS-repository `EnergieProject` en GitHub-SSH via een repository deploy key. De iMac is niet meer nodig voor de 24/7 projectketen.

## Nieuw
- Werkelijke NAS-layout: `/share/Energie_NAS/EnergieProject`.
- Release-inbox: `EnergieProject_Inbox/incoming`, met `processing`, `processed` en `failed`.
- `tools/release_installer.sh` valideert ZIP-integriteit, verplichte bestanden en `MANIFEST.sha256`.
- Installer weigert te werken bij een dirty Git-worktree of meerdere ZIPs tegelijk.
- Voor iedere live vervanging wordt een tar.gz-herstelkopie gemaakt in `EnergieProject_Backups`.
- `.git` blijft behouden; de release-worktree wordt gecontroleerd vervangen.
- Bij test/commit/push-fouten wordt de Git-worktree teruggezet naar de vooraf vastgelegde commit.
- Geslaagde release-ZIPs gaan naar `processed`; fouten naar `failed`.
- Productiekern blijft `9.4-core1`.

De installer is bewust een host-side tool voor de Home Assistant Terminal/SSH-omgeving. Daarmee gebruikt hij de reeds werkende GitHub deploy key zonder die private sleutel in de Energie-app of op de SMB-share te hoeven opslaan.
