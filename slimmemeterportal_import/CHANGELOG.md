## 32.3.12

- Enforced USER / DEVELOPMENT / MAINTENANCE operating-mode controller.
- Automatic temporary mode escalation with safe return to the configured base mode.
- Release Incoming is enabled only in DEVELOPMENT; maintenance requests only in MAINTENANCE.
- USER effectively enables scheduled workflow and automatic previous-month close while blocking current-month finalization.
- Projectmanager reconciliation, append-only mode audit history, GUI controls and chat-visible mode status.
- Existing destructive restore/delete safety gates are unchanged.
