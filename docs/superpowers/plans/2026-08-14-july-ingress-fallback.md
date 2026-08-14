# v32.0.33 July Ingress Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Laat SMP-publicatie voor een afgesloten maand doorgaan wanneer de vaste `HomeAssistant`-ingress nog niet bestaat, zodat juli 2026 met volledige SMP-data kan worden afgerond ondanks ontbrekende lokale historie.

**Architecture:** Behoud de bestaande `Data/01_Input/YYYY_MM/HomeAssistant/SlimmeMeterPortal`-structuur. Maak alleen de vaste ingress-map idempotent aan vóór de bestaande staging/copy/verify/swap-logica. De scheduler, completion-marker en finalisatiecontracten blijven ongewijzigd.

**Tech Stack:** Python 3.12, pathlib, pytest, bestaande QNAP release-watcher/installer.

## Global Constraints
- Versie wordt 32.0.33.
- Augustus 2026 blijft open.
- Geen nieuwe of handmatige `finalize_month`-aanroep.
- Geen wijziging aan Crash Recovery, watcher-cleanup, GitHub-publicatie of iCloud.
- Geen GitHub Actions voor ontwikkeling/testen.
- Bestaande `HomeAssistant/SlimmeMeterPortal`-layout blijft exact behouden.

---

### Task 1: Regressietest voor ontbrekende HA-ingress
**Files:**
- Create: `tests/test_july_ingress_fallback.py`
- Modify: `tests/test_static.py`

**Interfaces:**
- Consumes: `publish_smp_import_to_nas_input(source: Path, month_key: str) -> dict[str, Any]`
- Produces: bewijs dat ontbrekende ingress automatisch wordt aangemaakt en SMP-data wordt gepubliceerd.

- [ ] **Step 1: Write the failing runtime test**
Laad `main.py` via `importlib.util`, vervang `NAS_DATA_ROOT` door `tmp_path / "Data"`, maak een geldige SMP-bronmap met één bestand en roep `publish_smp_import_to_nas_input(..., "2026_07")` aan zonder vooraf `HomeAssistant` aan te maken. Verwacht `status == "ok"`, bestaande ingress en gepubliceerd bestand.

- [ ] **Step 2: Run test to verify it fails**
Run: `python3 -m pytest -q tests/test_july_ingress_fallback.py`
Expected: FAIL met `RuntimeError: HA-ingress ontbreekt voor 2026_07`.

- [ ] **Step 3: Update static contract test**
Vervang de oude eis `if not ingress_root.is_dir()` door de nieuwe eis `ingress_root.mkdir(parents=True, exist_ok=True)` en behoud de asserts die verbieden dat `destination_month` wordt vervangen/verwijderd.

### Task 2: Minimale ingress-fix
**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/main.py`

**Interfaces:**
- Produces: idempotente vaste HA-ingress zonder bredere workflowwijziging.

- [ ] **Step 1: Implement minimal code**
Vervang uitsluitend de ontbrekende-ingress `RuntimeError` door:
```python
ingress_root = destination_month / "HomeAssistant"
try:
    ingress_root.mkdir(parents=True, exist_ok=True)
except OSError as exc:
    raise RuntimeError(
        f"HA-ingress kan niet worden voorbereid voor {month_key}: {ingress_root}: {exc}"
    ) from exc
```
Laat de bestaande `destination_root`, staging, backup, checksum en swap-logica ongemoeid.

- [ ] **Step 2: Run focused tests**
Run: `python3 -m pytest -q tests/test_july_ingress_fallback.py tests/test_static.py`
Expected: PASS.

- [ ] **Step 3: Verify no finalization scope creep**
Tekstcontrole op `finalize_month`; de fix mag geen nieuwe aanroep toevoegen.

### Task 3: Release-identiteit en changelog
**Files:**
- Modify: `VERSIE.txt`
- Modify: `slimmemeterportal_import/config.yaml`
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Modify: `slimmemeterportal_import/CHANGELOG.md`
- Modify: `CHANGELOG.md`
- Modify: release identity test(s)

**Interfaces:**
- Produces: consistente release 32.0.33 met actuele add-on-changelog.

- [ ] **Step 1: Change all current release identities to 32.0.33**
- [ ] **Step 2: Document only the July ingress/fallback fix in the add-on changelog**
- [ ] **Step 3: Update release identity tests to 32.0.33**
- [ ] **Step 4: Run identity/static tests**

### Task 4: Full regression and frozen ZIP
**Files:**
- Regenerate: `MANIFEST.sha256`
- Regenerate: `SHA256SUMS.json`
- Build: `EnergieProject_v32.0.33.zip`

**Interfaces:**
- Produces: één definitieve releasekandidaat.

- [ ] **Step 1: Run full suite** — `python3 -m pytest -q`, 0 failures.
- [ ] **Step 2: Regenerate manifests from exact release tree**
- [ ] **Step 3: Build one ZIP and freeze its SHA-256**
- [ ] **Step 4: Extract exact ZIP elsewhere and rerun full pytest**
- [ ] **Step 5: Run installer simulation from 32.0.32 to 32.0.33**
- [ ] **Step 6: Confirm no GitHub Actions were used**

### Task 5: Real NAS install and July-only recovery
**Files:** none in source.

**Interfaces:**
- Consumes: exact frozen 32.0.33 ZIP.
- Produces: NAS/HA 32.0.33 and then a controlled 2026_07 rerun only.

- [ ] **Step 1: SHA-check and install through the Docker watcher with retention 999**
- [ ] **Step 2: Verify NAS + GitHub + HA on 32.0.33**
- [ ] **Step 3: Read-only inspect July input/output/completion state before rerun**
- [ ] **Step 4: Resume only 2026_07 via the normal workflow path**
- [ ] **Step 5: Verify completion marker and July outputs**
- [ ] **Step 6: Confirm August remains open**
