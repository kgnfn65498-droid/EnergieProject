# Changelog EnergieProject

## 10.5.2
- Automatische GitHub-publicatie toegevoegd aan de Home Assistant add-on.
- De add-on bevat voortaan Git en OpenSSH.
- Home Assistant maakt bij eerste start een persistente ED25519-publicatiesleutel.
- De operationele console kan de publieke sleutel tonen om hem eenmalig als write-enabled GitHub Deploy Key te registreren.
- Nieuwe opties: `github_publication_enabled`, `github_repository_ssh`, `github_branch`, `github_publication_poll_seconds`.
- Na activering bewaakt Home Assistant de QNAP-release. Zodra de nieuwe ZIP in `processed` staat, voert Home Assistant automatisch Git add/commit/push uit.
- De QNAP hoeft zelf geen GitHub-internettoegang of credentials te hebben.
- Productiekern `9.4-core1`, maandworkflow en rapportgeneratoren blijven ongewijzigd.
