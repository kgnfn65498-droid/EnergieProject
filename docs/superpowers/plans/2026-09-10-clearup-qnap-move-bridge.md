# CLEARUP QNAP Move Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Route CLEARUP hard-renames and restore through the existing `energie-release-watcher` Python container so root-level candidates can be moved without changing project-root permissions.

**Architecture:** HA keeps approval, release, Crash-Recovery, candidate hashing and dependency audit. It sends an expiring release-bound plan request through `Inbox`; the watcher container executes the existing `apply_clearup_plan`/`restore_clearup_run` code and returns a request-id-matched result. No direct HA fallback is allowed.

**Tech Stack:** Python 3.12, POSIX shell, pytest, shared NAS filesystem.

**Spec:** Live 32.4.32 failed after 172/172 planning with `PermissionError` renaming root-level `App.__failed_32.4.10_001`; project root remains 0755 and must not be made broadly writable.

## Global Constraints
- No project-root chmod/chown shortcut.
- No host Python dependency; watcher Python runs inside `python:3.12-slim`.
- Exact quarantine remains `EnergieProject/CLEARUP` on the same filesystem.
- Preserve dependency audit, unreadable-candidate REVIEW, hard timeout, no-delete, atomic rollback and manifest identity checks.
- Request must be bound to current ACCEPTED release and released validation hold, with expiry.
- Restore must use the same privileged boundary.

### Task 1 — RED regressions
- Create `tests/test_v32433_clearup_watcher_move_bridge.py`.
- Prove HA auto-run must delegate instead of direct `apply_clearup_plan`.
- Prove watcher executor can apply+restore and rejects release mismatch.
- Prove watcher wiring uses container Python and no project-root chmod.
- Run new tests and require RED.

### Task 2 — Watcher executor
- Create `tools/project_clearup_move_executor.py`.
- Validate request schema/id/action/version/atomic/hold/expiry/plan version before mutation.
- Call existing `apply_clearup_plan` or `restore_clearup_run` under remaining deadline.
- Atomically persist completed/rejected/error result with `delete_performed=false`.
- Wire request processing into `tools/release_watcher.sh` under `maintenance_requests`.

### Task 3 — HA bridge
- Modify `slimmemeterportal_import/rootfs/app/project_clearup_auto.py`.
- Atomically publish one expiring request and wait only for matching result until existing deadline.
- Never overwrite an unmatched active request and never fall back to direct rename.
- Emit wait progress to existing runtime checkpoint.
- Replace only auto-flow direct apply call with watcher delegation.

### Task 4 — 32.4.33 identity/docs
- Bump current release identity to 32.4.33.
- Update changelogs and `PROJECT_AFSPRAKEN.md` with source-parent permission lesson.
- Adjust only tests intentionally tracking current release.

### Task 5 — release verification
- Relevant CLEARUP/release regressions, static suite, full source suite.
- Clean fresh staging; exclude generated junk and this temporary plan only.
- Canonical builder with `filtered_count=0`.
- Exact ZIP manifest/hash verification.
- Production-equivalent atomic 32.4.32→32.4.33→ACCEPTED, rollback intact.
- Full fresh-extract suite, then KB/PM evidence.
