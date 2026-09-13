# 32.4.50 Stale Task Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the 32.4.49 self-audit stale-task blocker and prevent recurrence of stale Native-MCP runtime truth.

**Architecture:** Extend existing release-bound state reconciliation rather than add a new route. Keep runtime fingerprint observation outside mode-gated maintenance mutation, and normalize the dedicated control-plane source configuration to the canonical NAS project root.

**Tech Stack:** Python 3, pytest, POSIX shell, Docker/Container Station configuration.

**Spec:** Live audit of 32.4.49 on 2026-09-13.

## Global Constraints

- Exact 32.4.49 verified ZIP is the build basis.
- TDD RED→GREEN before implementation.
- No new release route or generic Docker executor.
- Protected actions remain fail-closed.
- Canonical project root is `/share/Energie_NAS/EnergieProject`.

---

### Task 1: Reconcile stale release-bound maintenance tasks

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/projectmanager_v2/state_reconciliation.py`
- Test: `tests/test_v32450_stale_task_and_runtime_closure.py`

- [x] Step 1: Add failing test for stale `32.4.48 Native MCP guard refresh` with live 32.4.49.
- [x] Step 2: Verify RED (`REVIEW_REQUIRED`).
- [x] Step 3: Extend exact release-bound MAINTENANCE classification.
- [x] Step 4: Verify GREEN.

### Task 2: Keep Native-MCP runtime truth fresh

**Files:**
- Modify: `tools/release_watcher.sh`
- Test: `tests/test_v32450_stale_task_and_runtime_closure.py`

- [x] Step 1: Add failing ordering test.
- [x] Step 2: Move observational guard refresh outside MAINTENANCE gate.
- [x] Step 3: Verify GREEN.

### Task 3: Canonicalize control-plane project root

**Files:**
- Modify: `tools/control_plane/docker-compose.containerstation.yml`
- Modify: `tools/control_plane/qnap_control_plane_bootstrap.py`
- Test: `tests/test_v32450_stale_task_and_runtime_closure.py`

- [x] Step 1: Add failing no-CACHEDEV1/canonical-root test.
- [x] Step 2: Replace physical cache path with canonical project root.
- [x] Step 3: Verify GREEN.

### Task 4: Release identity and verification

**Files:**
- Modify: release identity/version/changelog files.
- Create: `docs/32.4.50-build-basis.json`

- [x] Step 1: Set release 32.4.50 and PM 2.0.0-rc37.
- [ ] Step 2: Run targeted and full regression.
- [ ] Step 3: Build exact artifact, fresh-extract and re-run critical tests.
