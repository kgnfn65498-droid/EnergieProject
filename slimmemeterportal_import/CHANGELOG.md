# Changelog

## 32.3.14

- Adds a persistent RELEASE VALIDATION HOLD above USER / DEVELOPMENT / MAINTENANCE before automatic mutating energy workflows may resume after an update.
- Keeps an active DEVELOPMENT session persistent across release and reboot; only explicit user confirmation may end development and return to USER.
- Blocks run-on-start, scheduling, automatic full workflow and automatic month close during HOLD, with an independent execute-time guard for automatic month close.
- Reconciliation now uses measured runtime signals; forbidden activity during HOLD becomes DRIFT and requests controlled cancellation instead of reporting a false OK state.
- HOLD release uses five compact health checks plus measured reconciliation; a confirmed emergency release remains available only after a safe read-only check and is audited.
- The installer arms the HOLD atomically in the writable Inbox/operating_mode area before Home Assistant publication, preserving Projectmanager least-privilege protection.
