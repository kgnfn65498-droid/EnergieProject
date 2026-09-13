# Changelog

## 32.4.52 — Project-CR snapshot/reconciliation closure

- TDD-fix voor de bewezen live Project-CR TOCTOU-race: alleen eigen atomische tijdelijke bestanden onder `Inbox/` en `Data/03_Systeem/` worden veilig uitgesloten of als `transient_skipped` vastgelegd; normale bronbestanden blijven fail-closed.
- Project-CR bridge reconcilieert stale requests van een vorige release alleen wanneer geen worker-marker actief is en bewaart request/result als evidence; actuele same-release command-conflicten blijven fail-closed.
- Project-CR resultaten worden op volledige identiteit gevalideerd: schema, operation, request-id, command-id en runtimeversie.
- Geen algemene retry, geen sequencerwijziging en geen nieuwe release-route.
- Regressiecontract bewijst canonieke Project/NAS CR-health en de bestaande Project CR → NAS CR → CLEARUP closurevolgorde.
- Target identity: EnergieProject 32.4.52 / Projectmanager 2.0.0-rc39.
