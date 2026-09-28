# Changelog

## 32.5.26 — autonomous release closure + Type-3/final Inbox cleanup
- Reuses the proven 32.5.x request-scoped privileged sideband/executor for the original Type-3/final Inbox cleanup; no parallel executor and no 32.4 auto-ClearUp reactivation.
- Keeps Type-2 ClearUp_002–012 closed and untouched.
- Makes `Inbox/failed` structurally flat for 32.5.26+ and updates corrupt/rejected/duplicate/rolled-back writers accordingly.
- Makes `Inbox/processing` ephemeral: created only when a release is claimed and removed after successful or rolled-back settlement.
- Rebinds Crash Recovery cleanup request/result state and GitHub publisher lock to canonical Projectmanager paths.
- Removes the legacy ApprovalIngress fallback and moves `Inbox/projectmanager_v2` only as the final guarded cleanup step after receipt proof.
- Adds capability-provenance continuity so new chats must discover valid 32.5.x executors before concluding a capability is unavailable; 32.4 auto-ClearUp is explicitly historical/forbidden for this path.
- PM `2.0.0-rc61`.
