# Changelog

## 32.5.24 — Type-2 closure + Project Manager live-truth replacement
- Replaces the earlier 32.5.24 N+1-only candidate; release version stays 32.5.24 and PM becomes rc58.
- Retains the predecessor-controller activation carrier needed to execute the 32.5.23 control-plane binding repair during the 32.5.24 transition.
- Reconciles Type-2 external recovery truth: confirmed historical receipt is never presented as missing again; current-set integrity remains an independent fail-closed gate.
- Full ClearUp_002..012 E2E acceptance now includes non-empty release mailboxes, a mutating runtime source, canonical writer handoff, finalize/delete readback and practical restore.
- ClearUp_007 explicitly proves the writer moves from legacy Inbox/control_plane to canonical ControlPlane/Runtime.
- Project Manager blocks functional completion of LIVE_REQUIRED work until LIVE_PROVEN, including the task-completion route.
- Project Manager enforces development Step X/Y + elapsed/ETA truth and complete terminal fallback metadata when a terminal is exceptionally unavoidable.
- Project Manager detects multi-release carry-forward/version stacking and reports a concrete blocker/evidence/next action instead of silently carrying work forward.
- No new watcher/controller/status chain; all repairs use existing PM, roadmap, status, handoff and ClearUp logic.
