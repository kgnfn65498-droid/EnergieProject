# DEV CHECKPOINT — 32.5.29

Status: PACKAGE_CANDIDATE_GREEN
Basis: exact audited 32.5.28 artifact.

Repair scope:
- privileged ReleaseController normalizes exact shared PM writer directories: Handover, ClearUp/Recovery, ClearUp/Exports, ClearUp/State to 0777;
- symlink/non-directory paths fail closed;
- Type-2 002–012 remains CLOSED;
- final Inbox recovery-first flow and confirmation gates remain unchanged.

Live after install:
1. verify 32.5.29 COMPLETE and HA exact;
2. submit fresh `inbox_cleanup_prepare_recovery`;
3. export and verify `FinalInboxCleanup_v32.5.29_recovery.zip`;
4. deliver recovery ZIP externally;
5. only after exact external confirmation apply final Inbox cleanup and 20 s resurrection soak.
