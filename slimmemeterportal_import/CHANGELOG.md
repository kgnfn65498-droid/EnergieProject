# Changelog

## 32.3.13

- USER / DEVELOPMENT / MAINTENANCE operating-mode controller with automatic temporary escalation and safe return.
- Release Incoming is enabled only in DEVELOPMENT; maintenance requests only in MAINTENANCE.
- USER enforces scheduled workflow and automatic previous-month close while blocking current-month finalization.
- Hotfix: operating-mode runtime state and commands use the shared writable Inbox area instead of protected Projectmanager/State.
- Prevents Home Assistant startup failure while preserving Projectmanager least-privilege protection.
