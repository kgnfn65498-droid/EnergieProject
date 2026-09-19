# Changelog

## 32.4.57 — single-owner release controller

- Incoming heeft één centrale releasecontroller met acht lineaire fasen en één persisted state.
- Oude release-transition, release-hold, mode, CR, CLEARUP en PM FINAL zijn geen releasegates meer.
- Atomic App swap blijft de enige install/rollback primitive; restart-resume gebruikt hetzelfde journal en dezelfde generation.
- Native MCP kan uitsluitend release-scoped self-healen met exacte release/generation/artifact/fingerprint-fencing.
- GitHub/HA delivery start pas na lokale atomic ACCEPTED en kan daarna nooit een App rollback veroorzaken.
- De HA runtime publiceert een directe version marker voor deterministische end-to-end readback.
- Target identity: EnergieProject 32.4.57 / Projectmanager 2.0.0-rc45.
