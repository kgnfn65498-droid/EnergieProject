## 32.0.3 - Home Assistant GitHub publisher worktree fix
- Herstelt automatische HA→GitHub-publicatie na de NAS-layoutmigratie.
- Publicatie gebruikt een dedicated persistente Git-worktree onder `/config/github_publisher/worktree`; `EnergieProject/App` blijft bewust zonder `.git`.
- Synchroniseert uitsluitend App-inhoud en verifieert na push dat lokale en remote HEAD gelijk zijn.
- Voorkomt CIFS executable-bit vervuiling bij nieuwe bestanden.

# Changelog

## 32.0.3
- NAS-releaseketen gebruikt uitsluitend `EnergieProject/App`, `Data`, `Backups`, `Inbox` en `Infra`.
- Installer vervangt alleen `App`; data, backups, inbox en infrastructuur blijven buiten de worktree.
- Watcher en Container Station bootstrap gebruiken dezelfde projectroot.
- Oude losse inbox/backuplocaties zijn uit runtime en tests verwijderd.
- EPEX lokale bronresolutie gebruikt voortaan `Data`.
