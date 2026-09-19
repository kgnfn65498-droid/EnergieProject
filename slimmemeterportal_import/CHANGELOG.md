# Changelog

## 32.4.58 — simplified autonomous release steady state

- Eén permanente ReleaseController blijft na COMPLETE actief/IDLE en is de enige release-lifecycle-owner.
- Legacy install adoption, globale operating-mode gates en automatische post-release CLEARUP zijn uit de actieve runtime verwijderd.
- Supervisor delivery gebruikt `/store/reload` gevolgd door `/addons/self/rebuild`, met `hassio_api: true` en `hassio_role: manager`.
- Projectmanager health gebruikt controller-runtime als livenessbron en toont release/runtime, energiedata/live sources, onderhoud/backup/hygiëne en observability als onafhankelijke domeinen.
- Een lege kwartiersnapshot blijft een collectorfout maar veroorzaakt geen fictieve live-source-uitval.
- Target identity: EnergieProject 32.4.58 / Projectmanager 2.0.0-rc45.
