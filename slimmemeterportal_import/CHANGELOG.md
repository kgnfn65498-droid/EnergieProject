# Changelog

## 32.5.25 — Type-2 writer closure + Projectmanager continuity hardening
- Rebinds the autonomous GitHub publisher to canonical Type-2 paths and keeps rollback on recreate failure.
- Removes direct legacy log writes from Native-MCP/CR hotfixes.
- Adds post-delete source-reappearance detection to Type-2 finalize.
- Keeps external recovery-gate persistence behind the privileged watcher boundary.
- Expands FULL_KB and new-chat preflight/self-audit to Decision Log, Development Changelog, Spock Context, Full-KB audit, Ticket/Issue Index and KB Inventory.
- PM `2.0.0-rc60`.
