# 32.4.45 Native MCP Runtime Closure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate the recurring false Native MCP reload cycle and make PM coordination robust when the NAS wall clock is skewed, while preserving fail-closed protected restarts for actual Native MCP code changes.

**Architecture:** Split Native MCP runtime identity from unrelated Projectmanager source identity: the runtime fingerprint covers only files actually loaded by the Native MCP process. PM coordination uses same-cycle generation/provenance as the authoritative freshness contract during final self-audit; wall-clock timestamps remain observational. The protected restart/control-plane remains unchanged for real native runtime changes.

**Tech Stack:** Python 3.12, pytest, shell release watcher, ZIP manifest packaging.

**Spec:** Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/09_20260912_32444_INCOMING_NATIVE_MCP_STRUCTURAL_CLOSURE.md plus Peter's 2026-09-12 requirement that Native MCP must be structurally solved without relying on NAS NTP correctness.

## Global Constraints

- Exact previous verified ZIP `EnergieProject_v32.4.44.zip` is the build basis.
- `/project` remains read-only in Native MCP.
- Native MCP runtime evidence writes only through `/system/Projectmanager/RuntimeEvidence`.
- No generic Docker or restart surface; actual native code changes remain protected by exact Peter-approved restart route.
- No wall-clock/NTP dependency for correctness where cycle generation or monotonic runtime evidence suffices.
- Incoming remains the only release ingress path.
- TDD RED -> GREEN and fresh-extract verification are mandatory.

---

### Task 1: Native MCP fingerprint ownership

**Files:**
- Modify: `tools/native_mcp_runtime_contract_hotfix.py`
- Modify: `tools/native_mcp_runtime_guard.py`
- Test: `tests/test_v32445_native_mcp_clock_independence.py`

**Interfaces:**
- Consumes: native MCP source directory and runtime marker v3.
- Produces: native-only fingerprint and exact target list.

- [ ] Write failing tests proving PM-only source changes do not alter expected Native MCP fingerprint.
- [ ] Run targeted tests and verify RED.
- [ ] Change runtime contract to v3 and hash only native process-loaded files.
- [ ] Keep marker on `/system` and preserve strict target-list verification.
- [ ] Run targeted tests and verify GREEN.

### Task 2: Clock-independent PM final coordination

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/projectmanager_v2/self_audit.py`
- Test: `tests/test_v32445_native_mcp_clock_independence.py`

**Interfaces:**
- Consumes: status/heartbeat/handover cycle generation and FINAL provenance.
- Produces: self-audit that fails on generation/provenance mismatch but does not fail the same final cycle solely because NAS wall clock is skewed.

- [ ] Write failing test with extreme wall-clock skew but matching FINAL cycle generation.
- [ ] Run targeted test and verify RED.
- [ ] Make wall-clock freshness informational for coordinated FINAL generation on 32.4.45+ while retaining timestamp schema validation and strict stale checks for non-coordinated/older flows.
- [ ] Run targeted tests and verify GREEN.

### Task 3: Release identity and regression

**Files:**
- Modify release identity files to 32.4.45 / PM rc32.
- Create: `docs/32.4.45-build-basis.json`
- Update changelogs.
- Test: release identity and previous regression suites.

- [ ] Update release identity coherently.
- [ ] Record exact 32.4.44 basis SHA256.
- [ ] Run targeted 32.4.44/32.4.45 regressions.
- [ ] Run full non-overlapping pytest suite.

### Task 4: Exact artifact verification

**Files:**
- Rebuild manifest and SHA inventory.
- Produce: `/mnt/data/EnergieProject_v32.4.45.zip`

- [ ] Build one exact ZIP using the canonical release builder.
- [ ] Verify ZIP CRC/integrity and manifest hashes.
- [ ] Fresh-extract the exact ZIP.
- [ ] Run critical Native MCP, Incoming, atomic acceptance, self-audit and release identity tests from fresh extraction.
- [ ] Record final SHA256 and verification evidence.
