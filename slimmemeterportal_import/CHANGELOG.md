# Changelog

## 32.5.10 — Type2 ClearUp validation hardening

- Type2 validation proof is committed through the bounded privileged watcher instead of direct embedded-Projectmanager writes to the system Validation directory.
- Exact request-id grace readback closes the watcher completion/timeout boundary race.
- Existing 32.5.9 Type2 recovery exports and the already migrated ClearUp_002 state remain resumable without re-prepare or re-migrate.
- Release mailbox protections, dangerous-action isolation and the 32.5.9 stale-control-plane fixes remain unchanged.

