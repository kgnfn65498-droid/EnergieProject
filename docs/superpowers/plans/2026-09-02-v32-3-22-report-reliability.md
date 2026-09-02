# v32.3.22 Report Reliability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce a source-grounded, internally consistent August report and workflow suitable for Crash Recovery.

**Architecture:** Keep the existing three-generator pipeline, but make the adapter the single source of truth for report semantics. Correct the SMP coverage validator at the representation boundary, remove stale fixture semantics from generators, and centralize offer/battery/source status values in adapter output.

**Tech Stack:** Python 3.12, pytest, ReportLab, pypdf, Home Assistant ingress HTTP handler.

**Spec:** `docs/superpowers/specs/2026-09-02-v32-3-22-report-reliability-design.md`

## Global Constraints
- Version is 32.3.22.
- No fabricated observed monthly all-in cost.
- Canonical report output is `Data/02_Output/Rapportages/YYYY_MM` only.
- EPEX is reference-only and must not be presented as configured when disabled.
- Existing release/install/mode safety behavior remains unchanged.

---

### Task 1: Add report reliability regression tests
**Files:**
- Create: `tests/test_v32322_report_reliability.py`
- Test: `tests/test_v32322_report_reliability.py`
**Interfaces:**
- Consumes existing `main.py` and generator source files.
- Produces executable regression assertions for release semantics.
- [ ] Write tests asserting no stale July/demo text, canonical output only, offer finance values, dynamic source labels, page count, and corrected coverage logic.
- [ ] Run the test and verify RED failures against v32.3.21.

### Task 2: Correct SMP content coverage semantics
**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Test: `tests/test_v32322_report_reliability.py`
**Interfaces:**
- Consumes raw SMP daily payloads and month summary state.
- Produces a coverage result that accepts valid daily-summary payloads without requiring 92/23 interval items when the payload shape is daily aggregated.
- [ ] Implement representation-aware record validation.
- [ ] Run coverage tests to GREEN.

### Task 3: Unify report adapter financial/source/battery context
**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Test: `tests/test_v32322_report_reliability.py`
**Interfaces:**
- Produces page JSON with current term 150, offer monthly 153, annual 1836, annual payments 1800, balance -36, source statuses, and one battery scenario block.
- [ ] Extend adapter output with explicit known-vs-unknown finance fields.
- [ ] Ensure EPEX claims depend on actual configured status.
- [ ] Ensure page 3-13 JSON has no fixture finance/appliance/battery values.
- [ ] Run adapter tests to GREEN.

### Task 4: Repair page 1 and page 2 semantics
**Files:**
- Modify: page 1 and page 2 generator sources under `slimmemeterportal_import/rootfs/app/report_generators/`.
- Test: `tests/test_v32322_report_reliability.py`
**Interfaces:**
- Consumes adapter page JSON only.
- Produces consistent August management and finance pages.
- [ ] Remove stale 8-day/July footer and `1 van 7` text.
- [ ] Populate known offer-backed finance fields; leave only truly unknown observed all-in monthly costs unavailable.
- [ ] Remove unsupported graaddagen/weather explanations.
- [ ] Run page 1/2 source tests to GREEN.

### Task 5: Replace pages 3-13 demo semantics
**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/report_generators/Energierapport_Pagina3_tm_13_Generator_v1_0/src/generate_pages_3_13.py`
- Test: `tests/test_v32322_report_reliability.py`
**Interfaces:**
- Consumes dynamic adapter JSON.
- Produces source-grounded pages without stale July/demo language or fabricated appliances/finance.
- [ ] Replace hard-coded score/demo text with adapter values/status.
- [ ] Replace stale July actions and EPEX claims.
- [ ] Use one battery scenario block.
- [ ] Render unavailable source-dependent metrics as explicit source limitations, not zero/fabricated values.
- [ ] Run pages 3-13 tests to GREEN.

### Task 6: Fix immediate report navigation and workflow final status
**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Test: `tests/test_v32322_report_reliability.py`
**Interfaces:**
- Produces direct ingress back navigation and correct final status after successful canonical publication.
- [ ] Remove any artificial navigation delay/retry wait on report back route.
- [ ] Ensure successful publication is not overwritten by the corrected SMP coverage representation issue.
- [ ] Run UI/workflow tests to GREEN.

### Task 7: Version, changelog, manifest, package verification
**Files:**
- Modify: `VERSIE.txt`, add-on config/version metadata, `CHANGELOG.md`, release manifests.
- Test: targeted v32.3.22 tests plus compile/package checks.
**Interfaces:**
- Produces `EnergieProject_v32.3.22.zip`.
- [ ] Update all release identity strings.
- [ ] Run targeted regression suite and Python compile.
- [ ] Build SHA manifests from final file set.
- [ ] ZIP and extract into a second clean directory.
- [ ] Verify every manifest hash and ZIP integrity.
