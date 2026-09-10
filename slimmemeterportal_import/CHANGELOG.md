# Changelog

## 32.4.28 — CLEARUP PM-observation dependency closure

- Projectmanager `RuntimeV2/status/**` en `snapshots/**` zijn afgeleide observatiebestanden en blokkeren CLEARUP niet langer als vermeende runtimeconsument.
- Een PM-snapshotrefresh tussen plan en apply mag alleen observationele evidence wijzigen; echte actieve dependencywijzigingen blijven fail-closed.
- Protected/REVIEW/no-delete/restore en pre-move SHA-256 blijven ongewijzigd; core blijft `9.4-core3`, PM blijft `2.0.0-rc22`.
