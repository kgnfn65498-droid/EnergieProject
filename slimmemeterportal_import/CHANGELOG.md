# Changelog

## 32.5.9 — ClearUp execution + stale control-plane isolation

- ClearUp Type1 remains recovery-first and exact-allowlisted.
- ClearUp Type2 batches 002–012 execute prepare, migrate, path activation, validate, finalize and restore through the bounded privileged route.
- Historical Native-MCP requests are archived outside the live request slot and can no longer block a current release.
- COMPLETE-phase Native-MCP reconciliation is release/generation/artifact/fingerprint fenced and cannot become a generic restart capability.
- Manual Native-MCP restart remains protected and requires explicit Peter approval.
- Retired legacy pending state is evidence-only and is never executed automatically.
