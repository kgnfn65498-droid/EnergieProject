# v32.0.30 Crash Recovery Heartbeat Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Maak Crash Recovery bestand tegen normale `quarter_hour_heartbeat.json`-updates, behoud strenge integriteitscontrole voor alle andere projectbestanden en geef de browser-ZIP de naam `YYYY-MM-DD HH.MM CrashRecovery EnergieProject.zip`.

**Architecture:** `crash_recovery_export.py` krijgt één expliciet runtime-snapshotpad. Dat bestand wordt als bytes geïnventariseerd en uit die snapshot naar de ZIP geschreven; alle andere bestanden blijven rechtstreeks uit de projectboom geschreven en na afloop op size/mtime gecontroleerd. `main.py` krijgt een kleine filename-helper voor de download/exportnaam. Geen wijziging aan maandafsluiting of restoregedrag.

**Tech Stack:** Python 3.12, `pathlib`, `zipfile`, pytest, GitHub Actions, Docker smoke test.

## Global Constraints

- Releaseversie: `32.0.30`.
- `PRODUCTION_CORE_REVISION` blijft `9.4-core1`.
- Geen `finalize_month` in Crash Recovery-flow.
- Juli/maandafsluiting wordt niet gewijzigd in deze release.
- Heartbeat blijft in de ZIP aanwezig.
- Alleen `Data/01_Input/_scheduler/quarter_hour_heartbeat.json` krijgt snapshotsemantiek.
- Andere muterende projectbestanden blijven een harde exportfout.
- Bestaande uitsluitingen blijven exact `Energie_Complete_Backup_*.zip`, `FULL_RECOVERY*.tar.gz`, `.DS_Store`.
- Downloadnaam bevat geen `:` en volgt exact `YYYY-MM-DD HH.MM CrashRecovery EnergieProject.zip`.
- Tijdelijke CI/spec/planbestanden worden niet in de release-ZIP opgenomen.

---

### Task 1: Reproduceer heartbeat-race en bewijs dat gewone mutatie fout blijft

**Files:**
- Modify: `tests/test_crash_recovery_export.py`

**Interfaces:**
- Consumes: `build_recovery_export(project_root: Path, output_zip: Path) -> ExportBuildResult`
- Produces: regressietests voor heartbeat-snapshot en gewone mutatiecontrole.

- [ ] **Step 1: Voeg RED-test toe voor muterende heartbeat**

Gebruik een monkeypatch op `zipfile.ZipFile.write` die na het schrijven van `quarter_hour_heartbeat.json` het live heartbeatbestand vervangt door andere bytes. De test verwacht dat export slaagt en dat de ZIP de oorspronkelijke bytes bevat.

- [ ] **Step 2: Voeg controletest toe voor muterend gewoon bestand**

Patch dezelfde schrijfstap voor `Data/live.json`; verander dat bestand na het schrijven en verwacht `RuntimeError` met `Projectinhoud wijzigde`.

- [ ] **Step 3: Run alleen deze tests**

Run: `pytest -q tests/test_crash_recovery_export.py`
Expected op v32.0.29-bron: heartbeattest FAIL; gewone-mutatie-test PASS.

- [ ] **Step 4: Commit RED-tests**

Commit message: `test: reproduce crash recovery heartbeat race`

---

### Task 2: Implementeer expliciete heartbeat-snapshot

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/crash_recovery_export.py`
- Test: `tests/test_crash_recovery_export.py`

**Interfaces:**
- Produces: `SNAPSHOT_RUNTIME_PATHS: frozenset[PurePosixPath]` met exact `Data/01_Input/_scheduler/quarter_hour_heartbeat.json`.
- `ProjectFile` krijgt optionele `snapshot_bytes: bytes | None`.

- [ ] **Step 1: Voeg snapshotconstant en dataveld toe**

Definieer exact één runtimepad en leg bij `collect_project_files()` voor dat pad de bytes vast nadat `stat()` is gelezen. Controleer direct na `read_bytes()` opnieuw size/mtime; als het bestand tijdens die ene snapshotread wijzigde, probeer maximaal één keer opnieuw en faal daarna expliciet.

- [ ] **Step 2: Schrijf snapshotbytes naar ZIP**

Gebruik `archive.writestr()` voor items met `snapshot_bytes`; gebruik bestaande `archive.write()` voor alle andere bestanden.

- [ ] **Step 3: Behoud post-build controle voor alle niet-snapshotitems**

Sla alleen de expliciete heartbeat over in de post-build size/mtime-check. Verander geen andere controles.

- [ ] **Step 4: Run gerichte tests**

Run: `pytest -q tests/test_crash_recovery_export.py`
Expected: alle tests PASS.

- [ ] **Step 5: Commit GREEN**

Commit message: `fix: snapshot changing scheduler heartbeat in crash recovery`

---

### Task 3: Menselijk leesbare downloadnaam

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Modify: `tests/test_crash_recovery_download.py`

**Interfaces:**
- Produces: `_crash_recovery_export_filename(now: datetime) -> str`.
- Exact formaat: `%Y-%m-%d %H.%M CrashRecovery EnergieProject.zip`.

- [ ] **Step 1: Schrijf RED-test voor exact formaat**

Voor `datetime(2026, 8, 14, 10, 30, tzinfo=TZ)` verwacht exact `2026-08-14 10.30 CrashRecovery EnergieProject.zip` en assert dat `:` niet voorkomt.

- [ ] **Step 2: Run test en bevestig RED**

Run: `pytest -q tests/test_crash_recovery_download.py`
Expected: FAIL omdat helper/naam nog ontbreekt.

- [ ] **Step 3: Implementeer helper en gebruik hem in `run_complete_crash_recovery_export()`**

Vervang alleen de exportfilename-opbouw; downloadendpoint blijft dezelfde gevalideerde exportpath streamen.

- [ ] **Step 4: Run downloadtests**

Run: `pytest -q tests/test_crash_recovery_download.py`
Expected: PASS.

- [ ] **Step 5: Commit**

Commit message: `feat: use readable crash recovery download name`

---

### Task 4: Release-identiteit 32.0.30

**Files:**
- Modify: `VERSIE.txt`
- Modify: `slimmemeterportal_import/config.yaml`
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Modify: `CHANGELOG.md`
- Modify: `tests/test_v32029_release_identity.py` or replace with `tests/test_v32030_release_identity.py`
- Modify: `tests/test_static.py`

**Interfaces:**
- `APP_VERSION = "32.0.30"`
- add-on `version: "32.0.30"`
- root `VERSIE.txt` = `32.0.30`.

- [ ] **Step 1: Maak release-identiteitstest RED voor 32.0.30**
- [ ] **Step 2: Run identiteitstest; verwacht FAIL op 32.0.29**
- [ ] **Step 3: Pas alleen versie-identiteit en changelog aan**
- [ ] **Step 4: Run identiteit + static tests; verwacht PASS**
- [ ] **Step 5: Commit**

Commit message: `release: set v32.0.30 identity`

---

### Task 5: Volledige bron-gate en definitieve kandidaat

**Files:**
- Create branch-only: `.github/workflows/v32030-final-candidate.yml`

**Interfaces:**
- Produces exact één artifact `EnergieProject_v32.0.30-final` met `EnergieProject_v32.0.30.zip` en `.sha256`.

- [ ] **Step 1: Maak tijdelijke workflow die op exact source-commit checkt**

Workflow moet: Python 3.12 + pytest dependencies installeren; volledige `pytest -q`; `py_compile`; AST-check dat Crash Recovery-functies geen `finalize_month` bevatten; canonical release stage maken; `.github/` en `docs/superpowers/` uitsluiten; manifests genereren; exact één ZIP bouwen met create-mode `x`.

- [ ] **Step 2: Test exact uitgepakte kandidaat opnieuw**

Run in Actions: manifest SHA-check, volledige pytest, py_compile, identity 32.0.30.

- [ ] **Step 3: Docker smoke test exact kandidaat**

Build add-on met `BUILD_VERSION=32.0.30`, start container, controleer `/health`, GUI, ingress en `/api/crash-recovery/state`, en geen startup traceback.

- [ ] **Step 4: QNAP-installer simulatie**

Simuleer 32.0.29 -> 32.0.30 in tijdelijke projectboom met retenties 999; eis fase 1–8 en canonieke `processed/EnergieProject_v32.0.30.zip`.

- [ ] **Step 5: Upload artifact en fingerprint**

Print SHA256, bytes en ZIP-entrycount. Bouw kandidaat niet opnieuw na deze gate.

---

### Task 6: Eindverificatie vóór echte NAS-installatie

**Files:** none

- [ ] **Step 1: Controleer branch-diff tegen main**

Alleen heartbeat-snapshot, naamgeving, versie/tests/changelog, specs/plans en tijdelijke CI mogen verschillen.

- [ ] **Step 2: Verifieer artifact lokaal na download**

`sha256sum`, ZIP-integriteit en exact dezelfde SHA als Actions.

- [ ] **Step 3: Lever één definitieve ZIP aan gebruiker**

Geen tweede build. Installatie op NAS pas daarna via Docker-watcher met retenties 999.
