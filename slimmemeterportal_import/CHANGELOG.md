# Changelog

## 32.0.2
- NAS-releaseketen gebruikt uitsluitend `EnergieProject/App`, `Data`, `Backups`, `Inbox` en `Infra`.
- Installer vervangt alleen `App`; data, backups, inbox en infrastructuur blijven buiten de worktree.
- Watcher en Container Station bootstrap gebruiken dezelfde projectroot.
- Oude losse inbox/backuplocaties zijn uit runtime en tests verwijderd.
- EPEX lokale bronresolutie gebruikt voortaan `Data`.
