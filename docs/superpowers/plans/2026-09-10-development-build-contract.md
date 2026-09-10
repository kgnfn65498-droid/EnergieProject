# Development Build Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Maak vaste ontwikkelafspraken machine-leesbaar en persistent zodat iedere nieuwe chat/build dezelfde MIDDEL/HOOG-, stappen-, tijd-, safety- en releasecontracten opnieuw ontvangt en een onvolledige build niet compliant kan lijken.

**Architecture:** Voeg één canonieke contractmodule toe; laat TaskStore optionele buildmetadata dragen; projecteer die metadata via progress/status/handover; laat self-audit de verplichte velden van expliciet gemarkeerde builds afdwingen. Behoud backwards compatibility voor bestaande niet-build taken.

**Tech Stack:** Python 3, pytest, bestaande ProjectManagerV2 persistence/status/handover/self-audit modules.

**Spec:** `docs/superpowers/specs/2026-09-10-development-build-contract-design.md`

## Global Constraints
- Geen productie-write tijdens ontwikkeling.
- QNAP host-python3 niet veronderstellen.
- TDD RED→GREEN.
- Geen versoepeling van bestaande release-, approval-, mode- of CLEARUP-safety.
- Exacte release-ZIP moet fresh-extract en atomic 4.33→4.34-validatie halen.

---

### Task 1: Canonieke contractevaluator
**Files:**
- Create: `slimmemeterportal_import/rootfs/app/projectmanager_v2/development_build_contract.py`
- Test: `tests/test_v32434_development_build_contract.py`

**Interfaces:**
- Produces: `CONTRACT_VERSION`, `canonical_contract()`, `normalize_build_metadata()`, `evaluate_build_contract(task, progress=None)`.

- [ ] Schrijf RED-tests voor verplichte setting, stappenraming, totale/testtijd en immutable baseline.
- [ ] Run gerichte tests en bevestig RED.
- [ ] Implementeer minimale evaluator.
- [ ] Run gerichte tests en bevestig GREEN.

### Task 2: Task/progress/handover integratie
**Files:**
- Modify: `.../task_engine.py`
- Modify: `.../progress_truth.py`
- Modify: `.../handover.py`
- Test: `tests/test_v32434_development_build_contract.py`

**Interfaces:**
- `TaskStore.start(..., build_metadata=None)` bewaart genormaliseerde metadata.
- `build_task_progress()` projecteert contractvelden zonder oorspronkelijke schatting te muteren.
- `build_handover()` bevat `development_build_contract`.

- [ ] Voeg RED-integratietests toe.
- [ ] Run en bevestig RED.
- [ ] Implementeer minimale opslag/projectie.
- [ ] Run en bevestig GREEN.

### Task 3: PM-status/web/self-audit afdwingen
**Files:**
- Modify: `.../manager_service.py`
- Modify: `.../projectmanager_web.py`
- Modify: `.../self_audit.py`
- Test: `tests/test_v32434_development_build_contract.py`

**Interfaces:**
- Status bevat `development_build_contract` snapshot.
- Handover/web tonen contractversie + thinking level + timingtruth.
- Self-audit rapporteert invalid voor expliciete development build met ontbrekende contractvelden.

- [ ] Voeg RED-tests toe.
- [ ] Run en bevestig RED.
- [ ] Implementeer minimale integratie.
- [ ] Run en bevestig GREEN.

### Task 4: Releasecontract/documentatie
**Files:**
- Modify: `PROJECT_AFSPRAKEN.md`
- Modify: `CHANGELOG.md`
- Modify: release identity files if needed.
- Test: static/release identity tests.

- [ ] Leg de permanente cross-chat/buildregel vast.
- [ ] Voeg statische regressie toe zodat de contractmodule niet uit toekomstige releases verdwijnt.
- [ ] Run relevante release/static tests.

### Task 5: End-to-end verification
- [ ] Run modefix + buildcontract + PM-regressies.
- [ ] Run volledige suite in deterministische batches indien één proces de tooltimeout raakt.
- [ ] Maak nieuwe schone staging; caches/junk = 0.
- [ ] Bouw met canonical builder; `filtered_count=0`.
- [ ] Fresh-extract exact ZIP en run volledige suite.
- [ ] Atomic 4.33→4.34 prepare/swap/accept; rollback 4.33 intact.
- [ ] Alleen daarna ZIP vrijgeven.
