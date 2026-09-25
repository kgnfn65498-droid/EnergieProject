# Changelog

## 32.5.11 — Type2 privileged quiescence authority

- Privileged watcher performs the final two-snapshot old-source quiescence proof and commits its stable source hash.
- PM-observed source hash is retained as audit metadata rather than used as cross-process identity fencing.
- Finalize still refuses any post-validation source change.
- Existing ClearUp_002 migrated state and ClearUp_002..012 recovery exports remain resumable without re-prepare or re-migrate.
