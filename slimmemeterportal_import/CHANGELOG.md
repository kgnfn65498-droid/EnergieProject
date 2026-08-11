## 32.0.5 - GitHub publisher status-state cleanup
- Voorkomt recursieve `last_publication`-nesting in `/config/output/github_publication_state.json`.
- Behoudt de dedicated persistente Git-worktree `/config/github_publisher/worktree` en automatische HA→GitHub-publicatie.
- Corrigeert de v32 release-identiteitsmarker naar v32.0.5.
- Geen wijzigingen aan energiegegevens, rapportlogica, financiële gates, NAS-layout of Home Assistant-mounts.

# Changelog

## 32.0.5
- NAS-releaseketen gebruikt uitsluitend `EnergieProject/App`, `Data`, `Backups`, `Inbox` en `Infra`.
- Installer vervangt alleen `App`; data, backups, inbox en infrastructuur blijven buiten de worktree.
- Watcher en Container Station bootstrap gebruiken dezelfde projectroot.
- Oude losse inbox/backuplocaties zijn uit runtime en tests verwijderd.
- EPEX lokale bronresolutie gebruikt voortaan `Data`.
