# Crash Recovery Watcher Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Maak Crash-Recovery-cleanup na succesvolle download automatisch en betrouwbaar via de QNAP/Docker-watcher, met behoud van spraakgeschikte headless backendlogica.

**Architecture:** Home Assistant streamt de ZIP en verwijdert alleen zijn lokale export. Daarna schrijft HA een strikt requestbestand naar `Inbox`; de watcher roept een kleine Python-helper aan die uitsluitend exact geregistreerde complete-backup-, manifest- en RestoreStaging-artifacten mag verwijderen. De watcher schrijft een resultaatbestand dat HA naar de lokale Crash-Recovery-status reconcileert.

**Tech Stack:** Python 3.12, POSIX shell, Home Assistant add-on HTTP backend, QNAP bind-mount, pytest.

## Global Constraints

- Versie: 32.0.32.
- Geen `finalize_month` of automatische maandafsluiting uitvoeren.
- Augustus 2026 blijft open.
- Geen brede deletes; alleen exacte run-artifacten.
- Maandbackups, `FULL_RECOVERY*.tar.gz` en release-ZIP's mogen nooit door Crash-Recovery-cleanup worden verwijderd.
- GUI is geen vereiste voor backend/cleanup; toekomstige spraakopdracht gebruikt dezelfde backendactie.
- Geen automatische iCloud-upload.
- Geen GitHub Actions voor ontwikkeltests.

---

### Task 1: Veilige watcher-cleanup helper

**Files:**
- Create: `tools/crash_recovery_cleanup.py`
- Create: `tests/test_crash_recovery_watcher_cleanup.py`

**Interfaces:**
- Consumes: JSON request met `request_id`, `backup_name`, `manifest_name`, `restore_staging_path`.
- Produces: JSON result met `request_id`, `status`, `removed`, `already_absent`, `warnings`, `error`.

- [ ] **Step 1: Write failing tests**
  Test geldige cleanup, idempotentie, path traversal, verkeerde manifestnaam, maandbackup, FULL_RECOVERY en RestoreStaging-root.
- [ ] **Step 2: Run tests and verify RED**
  Run: `pytest tests/test_crash_recovery_watcher_cleanup.py -q`
- [ ] **Step 3: Implement minimal helper**
  Resolve paden uitsluitend vanuit `ENERGIE_ROOT`; valideer regex/afleiding; verwijder alleen exacte targets; schrijf atomisch resultaat.
- [ ] **Step 4: Run tests and verify GREEN**
  Run: `pytest tests/test_crash_recovery_watcher_cleanup.py -q`

### Task 2: Watcher verwerkt cleanup-verzoeken

**Files:**
- Modify: `tools/release_watcher.sh`
- Test: `tests/test_crash_recovery_watcher_cleanup.py`

**Interfaces:**
- Consumes: `Inbox/crash_recovery_cleanup_request.json`.
- Produces: `Inbox/crash_recovery_cleanup_result.json` en watcherlogregels.

- [ ] **Step 1: Write failing static/integration test**
  Eis helperpad, request/result-constanten en aanroep vóór release-ZIP-detectie in iedere watcherloop.
- [ ] **Step 2: Run focused test and verify RED**
- [ ] **Step 3: Add watcher function**
  Roep `python3 tools/crash_recovery_cleanup.py` aan; laat release-watcher bij cleanupfout actief blijven; verwijder request alleen na geschreven resultaat.
- [ ] **Step 4: Run focused tests and shell syntax check**
  Run: `sh -n tools/release_watcher.sh` plus pytest.

### Task 3: HA download schakelt naar watcher-cleanup

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Modify: `tests/test_crash_recovery_download.py`

**Interfaces:**
- Produces helperfuncties voor requestopbouw, atomische request-write en result-reconciliation.
- `_stream_complete_recovery_download()` retourneert na volledige stream `downloaded` + `cleanup_pending` totdat watcherresultaat `ok` is.

- [ ] **Step 1: Rewrite tests to require watcher request**
  Succesvolle stream moet lokale export verwijderen, NAS-backup/staging behouden tot watcherresultaat en exact requestbestand schrijven. Broken stream schrijft geen cleanuprequest.
- [ ] **Step 2: Run focused tests and verify RED**
- [ ] **Step 3: Implement request/reconciliation**
  Geen directe NAS `unlink/rmtree` meer vanuit HA. Reconcile resultaat bij state-read en voor statusweergave.
- [ ] **Step 4: Add migration test for v32.0.31 warning**
  Een reeds `downloaded` state met `cleanup_status=warning` mag exact één veilig request opnieuw aanbieden zonder nieuwe backup/export.
- [ ] **Step 5: Run focused tests GREEN**

### Task 4: Release-identiteit, changelog en regressie

**Files:**
- Modify: `VERSIE.txt`
- Modify: `slimmemeterportal_import/config.yaml`
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Modify: `slimmemeterportal_import/CHANGELOG.md`
- Modify: `CHANGELOG.md`
- Replace: `tests/test_v32031_release_identity.py` with `tests/test_v32032_release_identity.py`
- Regenerate: `MANIFEST.sha256`, `SHA256SUMS.json`

- [ ] **Step 1: Set all release identities to 32.0.32 and document cleanup design**
- [ ] **Step 2: Run complete pytest suite**
  Expected: all tests pass, only established skips remain.
- [ ] **Step 3: Run compile and shell gates**
  `python -m py_compile` on changed Python files; `sh -n` watcher/installer.
- [ ] **Step 4: Build exactly one release ZIP and hash it**
- [ ] **Step 5: Re-extract exact ZIP and rerun full tests plus installer simulation**
- [ ] **Step 6: Verify no `finalize_month` entered Crash-Recovery flow and no workflow files were added**
