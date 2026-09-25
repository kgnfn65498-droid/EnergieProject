# Changelog

## 32.5.13 — Type2 recovery download bridge

- Uses the existing Projectmanager status surface and existing ClearUp export path to expose short-lived signed recovery ZIP download links.
- No new MCP tool name, no new storage path and no destructive ClearUp action.

## 32.5.12 — Type2 privileged quiescence authority

- Privileged watcher performs the final two-snapshot old-source quiescence proof and commits its stable source hash.
- PM-observed source hash is retained as audit metadata rather than used as cross-process identity fencing.
- Finalize still refuses any post-validation source change.
- Existing ClearUp_002 migrated state and ClearUp_002..012 recovery exports remain resumable without re-prepare or re-migrate.
