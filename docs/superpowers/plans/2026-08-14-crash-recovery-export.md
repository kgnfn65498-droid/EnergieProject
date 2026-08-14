# Crash Recovery Export v32.0.29 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bouw een veilige browser/iCloud Crash-Recovery-export die de volledige actuele `EnergieProject/`-map downloadbaar maakt, behalve `Energie_Complete_Backup_*.zip`, `FULL_RECOVERY*.tar.gz` en niet-inhoudelijke `.DS_Store`, terwijl de bestaande RecoveryManager create/verify/RestoreStaging-controles als verplichte veiligheidsvoorwaarde blijven bestaan.

**Architecture:** De bestaande RecoveryManager blijft de bewezen create/deep-verify/RestoreStaging-laag. Een nieuwe, kleine exportmodule maakt daarna rechtstreeks vanuit `NAS_LAYOUT_ROOT` één herstelvriendelijke ZIP met top-level `EnergieProject/`, bewaakt de expliciete inclusie-/exclusieregels en verifieert de ZIP opnieuw. `main.py` orkestreert de locks, status, HTTP-download, GUI en run-specifieke cleanup. Productie `32.0.28` blijft onaangeroerd tot alle branchtests en de latere echte HA-releasegate groen zijn.

**Tech Stack:** Python 3.12 stdlib (`pathlib`, `zipfile`, `hashlib`, `fnmatch`, `dataclasses`, `http.server`), bestaande SlimmeMeterPortal HA add-on, native MCP RecoveryManager, pytest.

## Global Constraints

- Basisproductie blijft `32.0.28`; werk uitsluitend op `feature/v32.0.29-crash-recovery-export` tot de releasegate volledig groen is.
- Neem de hele actuele `EnergieProject/`-map mee uit alle hoofdmappen en submappen.
- Sluit inhoudelijk alleen bestanden uit die als basename voldoen aan `Energie_Complete_Backup_*.zip`, bestanden die voldoen aan `FULL_RECOVERY*.tar.gz`, en `.DS_Store`.
- Maandbackups zoals `EnergieProject_maandbackup*`, manifests, logs, herstelhandleidingen, disaster-recoverydocumentatie, release-/repair-/storagehistorie, retentie- en workflowhistorie moeten behouden blijven.
- Geen algemene opschoon- of minimalisatielijst voor `Backups`.
- Geen automatische iCloud-upload; de gebruiker krijgt één browserdownload en zet die zelf in iCloud.
- Geen live restore over `/project` of `NAS_LAYOUT_ROOT`.
- Nooit `finalize_month` aanroepen.
- Crash-Recovery-export is nooit een release-ZIP en gaat nooit naar `Inbox/incoming`.
- Bestaande normale NAS-backupretentie blijft ongewijzigd.
- Browserdownload wordt pas aangeboden na geldige RecoveryManager deep verify, veilige RestoreStaging en geldige export-ZIP-verificatie.
- Bij afgebroken download wordt niets opgeruimd; retry moet mogelijk blijven.
- Na volledige succesvolle browserstream wordt uitsluitend run-specifieke tijdelijke Crash-Recovery-inhoud opgeruimd; geen glob-delete.
- Augustus/lopende maand blijft open.

---

## File structure

- Create `slimmemeterportal_import/rootfs/app/crash_recovery_export.py` — pure exportselectie, ZIP-opbouw, ZIP-verificatie en SHA-256; geen HTTP en geen RecoveryManager.
- Create `tests/test_crash_recovery_export.py` — unit/integratietests voor volledige projectinhoud, de drie toegestane uitsluitingen, ZIP-structuur, SHA en wijzigingsdetectie.
- Modify `slimmemeterportal_import/rootfs/app/main.py` — orkestratie RecoveryManager → RestoreStaging → export, runstate, veilige padconversie, HTTP-download en cleanup, GUI.
- Modify `tests/test_complete_crash_recovery_runtime.py` — bestaande contracttests behouden en uitbreiden voor exportflow/cleanup/no-finalize.
- Modify `tests/test_static.py` — release-identiteit en vereiste routes/teksten voor `32.0.29`.
- Modify `slimmemeterportal_import/config.yaml` — versie `32.0.29`; geen nieuwe gebruikersopties nodig.
- Modify `VERSIE.txt` — `32.0.29` pas in de release-identiteitstaak.
- Modify `CHANGELOG.md` — korte releasebeschrijving zonder claims vóór verificatie.

---

### Task 1: Pure exportselectie en herstelvriendelijke ZIP

**Files:**
- Create: `slimmemeterportal_import/rootfs/app/crash_recovery_export.py`
- Create: `tests/test_crash_recovery_export.py`

**Interfaces:**
- Consumes: `project_root: pathlib.Path`, `output_zip: pathlib.Path`.
- Produces:
  - `should_include_project_file(relative_path: Path) -> bool`
  - `collect_project_files(project_root: Path) -> list[ProjectFile]`
  - `build_recovery_export(project_root: Path, output_zip: Path) -> ExportBuildResult`
  - `verify_recovery_export(zip_path: Path) -> ExportVerifyResult`
  - `sha256_file(path: Path) -> str`
- `ProjectFile` bevat minimaal `relative_path`, `size`, `mtime_ns`.
- `ExportBuildResult` bevat minimaal `zip_path`, `file_count`, `total_bytes`, `sha256`.
- `ExportVerifyResult` bevat minimaal `valid`, `file_count`, `sha256`, `top_level_ok`, `required_roots_ok`, `excluded_hits`, `error`.

- [ ] **Step 1: Schrijf falende tests voor de inclusieregel**

```python
from pathlib import Path


def test_include_rule_only_excludes_explicit_backup_archives_and_ds_store():
    from crash_recovery_export import should_include_project_file

    included = [
        Path("Backups/EnergieProject_maandbackup_2026_07.zip"),
        Path("Backups/Manifests/Energie_Complete_Backup_old_manifest.json"),
        Path("Backups/NAS_DISASTER_RECOVERY_v32.md"),
        Path("Backups/release_repair/history.json"),
        Path("Data/02_Output/2026_07/rapport.pdf"),
        Path("Inbox/processed/EnergieProject_v32.0.28.zip"),
    ]
    excluded = [
        Path("Backups/Energie_Complete_Backup_2026_08_x.zip"),
        Path("Backups/FULL_RECOVERY_v32.tar.gz"),
        Path("Backups/old/FULL_RECOVERY_2026.tar.gz"),
        Path("App/.DS_Store"),
    ]

    assert all(should_include_project_file(path) for path in included)
    assert all(not should_include_project_file(path) for path in excluded)
```

- [ ] **Step 2: Run de nieuwe test en bevestig RED**

Run:
```bash
pytest -q tests/test_crash_recovery_export.py::test_include_rule_only_excludes_explicit_backup_archives_and_ds_store
```
Expected: FAIL omdat `crash_recovery_export` of de functie nog niet bestaat.

- [ ] **Step 3: Implementeer de minimale expliciete selectie**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import fnmatch
import hashlib
import zipfile

EXCLUDED_BASENAME_PATTERNS = (
    "Energie_Complete_Backup_*.zip",
    "FULL_RECOVERY*.tar.gz",
)


def should_include_project_file(relative_path: Path) -> bool:
    name = relative_path.name
    if name == ".DS_Store":
        return False
    return not any(fnmatch.fnmatchcase(name, pattern) for pattern in EXCLUDED_BASENAME_PATTERNS)
```

Geen andere inhoudsfilter toevoegen.

- [ ] **Step 4: Schrijf falende test voor volledige ZIP-structuur**

Maak in `tmp_path/EnergieProject` de vijf hoofdmappen `App`, `Data`, `Backups`, `Inbox`, `Infra` en test dat:
- alle normale bestanden uit alle vijf mappen in de ZIP staan onder `EnergieProject/...`;
- maandbackup, manifest, log en herstelhandleiding aanwezig blijven;
- de twee complete-backup-patronen en `.DS_Store` ontbreken;
- niets buiten `EnergieProject/` in de ZIP staat.

Testkern:
```python
with zipfile.ZipFile(result.zip_path) as archive:
    names = set(archive.namelist())

assert "EnergieProject/Backups/EnergieProject_maandbackup_2026_07.zip" in names
assert "EnergieProject/Backups/Manifests/current.json" in names
assert "EnergieProject/Backups/NAS_DISASTER_RECOVERY_v32.md" in names
assert not any("Energie_Complete_Backup_" in name and name.endswith(".zip") for name in names)
assert not any(Path(name).name.startswith("FULL_RECOVERY") and name.endswith(".tar.gz") for name in names)
assert all(name.startswith("EnergieProject/") for name in names)
```

- [ ] **Step 5: Run de ZIP-structuurtest en bevestig RED**

Run:
```bash
pytest -q tests/test_crash_recovery_export.py -k "structure or content"
```
Expected: FAIL omdat build/verify nog ontbreken.

- [ ] **Step 6: Implementeer inventaris, ZIP-opbouw en verificatie**

Belangrijke implementatieregels:
```python
@dataclass(frozen=True)
class ProjectFile:
    relative_path: Path
    size: int
    mtime_ns: int


def collect_project_files(project_root: Path) -> list[ProjectFile]:
    files: list[ProjectFile] = []
    for path in sorted(project_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(project_root)
        if not should_include_project_file(relative):
            continue
        stat = path.stat()
        files.append(ProjectFile(relative, stat.st_size, stat.st_mtime_ns))
    return files
```

`build_recovery_export`:
- eist dat `project_root/{App,Data,Backups,Inbox,Infra}` directories bestaan;
- maakt parent van `output_zip` aan;
- schrijft elk geïnventariseerd bestand als `EnergieProject/<relative_path>` met `ZIP_DEFLATED`;
- controleert na schrijven per bronbestand opnieuw `size` en `mtime_ns`; bij verschil: verwijder alleen de incomplete `output_zip` en raise `RuntimeError("Projectinhoud wijzigde tijdens Crash Recovery export")`;
- berekent daarna SHA-256 over de afgeronde ZIP.

`verify_recovery_export`:
- `ZipFile.testzip()` moet `None` teruggeven;
- alle niet-directory members beginnen met `EnergieProject/`;
- de vijf hoofdroots zijn aantoonbaar vertegenwoordigd;
- geen memberbasename matcht de twee uitgesloten patronen en geen `.DS_Store`;
- `sha256_file` levert de SHA terug.

- [ ] **Step 7: Run alle nieuwe pure-exporttests en bevestig GREEN**

Run:
```bash
pytest -q tests/test_crash_recovery_export.py
```
Expected: PASS.

- [ ] **Step 8: Commit Task 1**

```bash
git add slimmemeterportal_import/rootfs/app/crash_recovery_export.py tests/test_crash_recovery_export.py
git commit -m "feat: build complete crash recovery export zip"
```

---

### Task 2: RecoveryManager-veiligheidsflow en exportstate

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/main.py` rond de bestaande complete-recoveryfuncties
- Modify: `tests/test_complete_crash_recovery_runtime.py`

**Interfaces:**
- Consumes Task 1: `build_recovery_export`, `verify_recovery_export`, `sha256_file`.
- Produces:
  - `run_complete_crash_recovery_export(year: int | None = None, month: int | None = None) -> dict[str, Any]`
  - `_recovery_path_to_project_backup(path: str) -> Path | None`
  - `_safe_export_state_for_persistence(state: dict[str, Any]) -> dict[str, Any]`
- Statevelden minimaal: `status`, `version`, `year`, `month`, `backup_name`, `backup_sha256`, `manifest_file_count`, `verified_files`, `restore_test_status`, `restore_staging_path`, `source_project_modified`, `export_path`, `export_name`, `export_sha256`, `export_file_count`, `download_status`, `cleanup_status`, `checked_at`.

- [ ] **Step 1: Schrijf falende orchestratietest**

Test met gemockte `_mcp_call_project_action` en gemockte `build_recovery_export`/`verify_recovery_export` dat de callvolgorde exact is:
```python
[
    "preview_month_closure",
    "create_complete_backup",
    "verify_complete_backup",
    "preview_backup_restore",
    "stage_backup_restore",
]
```
En dat export pas wordt gebouwd wanneer:
- verify status geldig is;
- `deep_verified is True`;
- `verified_files == manifest_file_count > 0`;
- `hash_failures == []`;
- staging onder `/recovery/RestoreStaging` ligt;
- `source_project_modified is False`.

- [ ] **Step 2: Run orchestratietest en bevestig RED**

Run:
```bash
pytest -q tests/test_complete_crash_recovery_runtime.py -k export_flow
```
Expected: FAIL omdat `run_complete_crash_recovery_export` ontbreekt.

- [ ] **Step 3: Refactor zonder regressie naar interne create/verify/stage helpers**

Behoud de bestaande publieke functies compatibel, maar voorkom dubbele lock-acquisitie door interne helpers te introduceren:
```python
def _create_and_verify_complete_backup(year: int, month: int) -> dict[str, Any]: ...
def _stage_verified_backup(state: dict[str, Any]) -> dict[str, Any]: ...
```

`run_complete_crash_recovery()` blijft dezelfde outputcontracten leveren als v32.0.28 en gebruikt `_create_and_verify_complete_backup`.

`run_complete_restore_staging()` blijft dezelfde outputcontracten leveren en gebruikt `_stage_verified_backup`.

- [ ] **Step 4: Implementeer `run_complete_crash_recovery_export`**

Gedrag:
1. weiger bij actieve `WORKFLOW_LOCK`;
2. acquire `COMPLETE_CRASH_RECOVERY_LOCK` non-blocking;
3. status `running` opslaan;
4. `_create_and_verify_complete_backup` uitvoeren;
5. alleen bij volledig geldig verify-resultaat `_stage_verified_backup` uitvoeren;
6. stagingpad en `source_project_modified` opnieuw valideren;
7. maak run-specifiek tijdelijk exportpad onder `CRASH_RECOVERY_EXPORT_ROOT = Path("/config/output/crash_recovery_exports")`, bijvoorbeeld `EnergieProject_Complete_Crash_Recovery_20260814T092200.zip`;
8. `build_recovery_export(NAS_LAYOUT_ROOT, export_path)`;
9. `verify_recovery_export(export_path)` en SHA matchen met buildresultaat;
10. alleen dan status `ready_for_download` opslaan;
11. bij elke fout status `error`, exportdownload niet aanbieden en alleen een eventueel incomplete exportbestand van deze run verwijderen;
12. release de lock in `finally`.

De exportfunctie mag nergens `finalize_month` bevatten of indirect aanroepen.

- [ ] **Step 5: Schrijf en run falende veiligheidsvarianten**

Minimaal:
```python
def test_export_rejects_incomplete_deep_verify(...): ...
def test_export_rejects_restore_outside_restorestaging(...): ...
def test_export_rejects_source_project_modified_true(...): ...
def test_export_never_calls_finalize_month(...): ...
```
Expected vóór afronding: RED; na implementatie: GREEN.

- [ ] **Step 6: Run bestaande én nieuwe recoverytests**

Run:
```bash
pytest -q tests/test_complete_crash_recovery_runtime.py tests/test_crash_recovery_export.py
```
Expected: alle tests PASS; bestaande v32.0.28 contracttests blijven ongewijzigd groen.

- [ ] **Step 7: Commit Task 2**

```bash
git add slimmemeterportal_import/rootfs/app/main.py tests/test_complete_crash_recovery_runtime.py
git commit -m "feat: orchestrate verified crash recovery export"
```

---

### Task 3: Veilige browserdownload en run-specifieke cleanup

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Modify: `tests/test_complete_crash_recovery_runtime.py`

**Interfaces:**
- Consumes Task 2 state `ready_for_download` en `export_path/export_sha256`.
- Produces:
  - `_validated_export_download_path(state: dict[str, Any]) -> Path`
  - `_stream_file_to_response(path: Path) -> bool`
  - `_cleanup_completed_export(state: dict[str, Any]) -> dict[str, Any]`
  - `GET /api/crash-recovery/download`
  - `POST /api/crash-recovery/cleanup`

- [ ] **Step 1: Schrijf falende pad- en cleanup-tests**

Test dat `_validated_export_download_path` alleen een bestaand `.zip` accepteert dat resolvet onder `CRASH_RECOVERY_EXPORT_ROOT`, met SHA gelijk aan `state["export_sha256"]`.

Test dat cleanup alleen deze run-specifieke objecten mag verwijderen:
- `export_path` onder `CRASH_RECOVERY_EXPORT_ROOT`;
- `PROJECT_BACKUP_ROOT / backup_name` wanneer basename exact matcht `Energie_Complete_Backup_*.zip`;
- bijbehorend run-specifiek manifest `PROJECT_BACKUP_ROOT / "Manifests" / f"{Path(backup_name).stem}_manifest.json"` als het bestaat;
- het exacte RestoreStaging-pad dat via `/recovery/RestoreStaging/...` veilig is omgerekend naar `PROJECT_BACKUP_ROOT/RestoreStaging/...`.

Test expliciet dat `PROJECT_BACKUP_ROOT`, `NAS_LAYOUT_ROOT`, een maandbackup, algemene `Manifests`-directory en willekeurige sibling nooit verwijderd kunnen worden.

- [ ] **Step 2: Run cleanup-tests en bevestig RED**

Run:
```bash
pytest -q tests/test_complete_crash_recovery_runtime.py -k "cleanup or download_path"
```
Expected: FAIL omdat helpers ontbreken.

- [ ] **Step 3: Implementeer veilige padvalidatie en cleanup**

Gebruik geen `glob()` voor delete. Resolve elk exact pad en controleer parenthood vóór `unlink()`/`rmtree()`.

Voor `/recovery/...` mapping:
```python
def _recovery_path_to_project_backup(path: str) -> Path | None:
    value = str(path or "").strip()
    if value == "/recovery":
        return PROJECT_BACKUP_ROOT
    if not value.startswith("/recovery/"):
        return None
    relative = Path(value.removeprefix("/recovery/"))
    candidate = (PROJECT_BACKUP_ROOT / relative).resolve()
    root = PROJECT_BACKUP_ROOT.resolve()
    if candidate == root or root not in candidate.parents:
        return None
    return candidate
```

Voor RestoreStaging-cleanup vereist de caller bovendien dat de oorspronkelijke string begint met `/recovery/RestoreStaging/` en dat de gemapte target onder `PROJECT_BACKUP_ROOT/RestoreStaging` blijft.

- [ ] **Step 4: Schrijf falende HTTP-streamtests**

Gebruik een fake handler/wfile om te bewijzen:
- geldige route zet `Content-Type: application/zip`;
- `Content-Disposition: attachment; filename="...zip"`;
- bytes worden in blokken gestreamd;
- volledige stream zet `download_status=downloaded` en roept cleanup aan;
- `BrokenPipeError` of `ConnectionResetError` zet `download_status=retry_available`, roept cleanup niet aan en laat exportfile bestaan.

- [ ] **Step 5: Implementeer `GET /api/crash-recovery/download`**

Voor streaming:
```python
chunk_size = 1024 * 1024
with path.open("rb") as handle:
    while True:
        chunk = handle.read(chunk_size)
        if not chunk:
            break
        self.wfile.write(chunk)
```

Vóór headers:
- state moet `ready_for_download` zijn;
- exportpath veilig;
- huidige SHA moet gelijk zijn aan state-SHA.

Na laatste succesvolle `write`/flush:
- state eerst `downloaded` markeren;
- `_cleanup_completed_export` uitvoeren;
- cleanupstatus opslaan.

Bij streamfout:
- geen bron-/exportcleanup;
- state `retry_available` met foutmelding zonder geheimen.

- [ ] **Step 6: Implementeer expliciete cleanup-retryroute**

`POST /api/crash-recovery/cleanup` mag alleen werken wanneer `download_status == "downloaded"` en `cleanup_status != "ok"`. Anders `409 Conflict`.

- [ ] **Step 7: Run alle recovery/downloadtests**

Run:
```bash
pytest -q tests/test_complete_crash_recovery_runtime.py tests/test_crash_recovery_export.py
```
Expected: PASS.

- [ ] **Step 8: Commit Task 3**

```bash
git add slimmemeterportal_import/rootfs/app/main.py tests/test_complete_crash_recovery_runtime.py
git commit -m "feat: stream and clean crash recovery export"
```

---

### Task 4: Home Assistant GUI één normale flow

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Modify: `tests/test_complete_crash_recovery_runtime.py`

**Interfaces:**
- Consumes API:
  - `POST /api/crash-recovery/export`
  - `GET /api/crash-recovery/state`
  - `GET /api/crash-recovery/download`
- Produces GUI-acties:
  - primaire knop `Maak complete Crash Recovery` start volledige exportflow;
  - downloadknop `Download Crash Recovery ZIP` verschijnt/wordt enabled bij `ready_for_download` of `retry_available`;
  - diagnoseknop RestoreStaging mag blijven, maar is niet nodig in de normale flow.

- [ ] **Step 1: Schrijf falende statische GUI-test**

```python
def test_gui_has_single_export_flow_and_download_button():
    source = MAIN.read_text(encoding="utf-8")
    for required in (
        "/api/crash-recovery/export",
        "/api/crash-recovery/download",
        "Maak complete Crash Recovery",
        "Download Crash Recovery ZIP",
        "ready_for_download",
    ):
        assert required in source
```

- [ ] **Step 2: Run GUI-test en bevestig RED**

Run:
```bash
pytest -q tests/test_complete_crash_recovery_runtime.py -k gui_has_single_export_flow
```
Expected: FAIL.

- [ ] **Step 3: Wijzig de GUI/JS minimaal**

Primaire knop:
```javascript
await fetch('./api/crash-recovery/export', {method: 'POST'});
```

Bij state `ready_for_download` of `retry_available`:
- toon backupnaam/exportnaam;
- toon export file count en SHA-256;
- enable downloadknop;
- downloadknop navigeert naar `./api/crash-recovery/download` zodat de browser een echte attachmentdownload start.

Tijdens `running`: knoppen disabled.
Bij `error`: downloadknop disabled en fout zichtbaar.
Na `downloaded` + cleanup `ok`: tekst meldt dat de tijdelijke NAS-Crash-Recovery is opgeruimd.

- [ ] **Step 4: Behoud expliciete veiligheidsmelding**

GUI moet zichtbaar blijven melden dat:
- lopende maand niet wordt afgesloten;
- RestoreStaging geen productie overschrijft;
- de browserdownload bedoeld is om zelf in iCloud te bewaren.

- [ ] **Step 5: Run GUI + recovery tests**

Run:
```bash
pytest -q tests/test_complete_crash_recovery_runtime.py tests/test_crash_recovery_export.py
```
Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add slimmemeterportal_import/rootfs/app/main.py tests/test_complete_crash_recovery_runtime.py
git commit -m "feat: expose crash recovery browser download in HA"
```

---

### Task 5: Release-identiteit 32.0.29 en statische regressiegate

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Modify: `slimmemeterportal_import/config.yaml`
- Modify: `VERSIE.txt`
- Modify: `tests/test_static.py`
- Modify: `CHANGELOG.md`

**Interfaces:**
- Produces consistente release-identiteit `32.0.29` in app/config/root version en tests.

- [ ] **Step 1: Schrijf/actualiseer falende statische versiechecks**

Tests moeten eisen:
```python
assert 'APP_VERSION = "32.0.29"' in main_source
assert 'version: "32.0.29"' in config_source
assert versie_txt.strip() == "32.0.29"
```
En vereiste routes/labels:
```python
for required in (
    "/api/crash-recovery/export",
    "/api/crash-recovery/download",
    "Download Crash Recovery ZIP",
):
    assert required in main_source
```

- [ ] **Step 2: Run relevante static tests en bevestig RED vóór version bump**

Run:
```bash
pytest -q tests/test_static.py -k "version or crash or recovery"
```
Expected: versiechecks FAIL op 32.0.28.

- [ ] **Step 3: Bump uitsluitend release-identiteit naar 32.0.29**

Wijzig:
- `APP_VERSION = "32.0.29"`;
- `slimmemeterportal_import/config.yaml` version;
- root `VERSIE.txt`;
- release-identiteitsverwachtingen in `tests/test_static.py`.

Geen functionele workflow/scheduler/retry-core bump; `PRODUCTION_CORE_REVISION` blijft `9.4-core1` tenzij een bestaande statische contracttest aantoonbaar anders vereist.

- [ ] **Step 4: Voeg changelogregel toe**

Beschrijf feitelijk:
- volledige browser/iCloud Crash-Recovery-export;
- volledige projectinhoud met alleen expliciete backup-in-backup-uitsluitingen;
- deep verify + RestoreStaging vereist;
- cleanup pas na succesvolle download;
- geen maandfinalisatie/live restore.

Geen claim `release complete` vóór echte releasegate.

- [ ] **Step 5: Run volledige pytest-suite**

Run:
```bash
pytest -q
```
Expected: alle ondersteunde tests PASS; alleen reeds bekende expliciet gedocumenteerde skips zijn toegestaan. Geen nieuwe skip toevoegen om een v32.0.29-fout te verbergen.

- [ ] **Step 6: Compile check**

Run:
```bash
python -m py_compile slimmemeterportal_import/rootfs/app/main.py slimmemeterportal_import/rootfs/app/crash_recovery_export.py
```
Expected: exit 0.

- [ ] **Step 7: Commit Task 5**

```bash
git add slimmemeterportal_import/rootfs/app/main.py slimmemeterportal_import/config.yaml VERSIE.txt tests/test_static.py CHANGELOG.md
git commit -m "chore: set v32.0.29 crash recovery export identity"
```

---

### Task 6: Branch-verificatie en releasecandidate-gate zonder productie te wijzigen

**Files:**
- Verify only; releasebuilder/manifests alleen volgens de bestaande bewezen releaseprocedure nadat alle tests groen zijn.

**Interfaces:**
- Consumes alle eerdere tasks.
- Produces één kandidaat die later op NAS/HA getest kan worden; geen automatische claim dat productie al groen is.

- [ ] **Step 1: Inspecteer branchdiff tegen `main`**

Run:
```bash
git diff --check main...HEAD
git diff --stat main...HEAD
```
Expected: geen whitespace errors; alleen verwachte spec/plan/tests/app/config/version/changelog-bestanden.

- [ ] **Step 2: Run gerichte veiligheidsaudit**

Run:
```bash
grep -R "finalize_month" -n slimmemeterportal_import/rootfs/app/crash_recovery_export.py tests/test_crash_recovery_export.py || true
grep -n "def run_complete_crash_recovery_export" -A220 slimmemeterportal_import/rootfs/app/main.py | grep "finalize_month" && exit 1 || true
```
Expected: geen `finalize_month` in exportflow.

Controleer tevens dat de exportmodule geen code bevat die naar `Inbox/incoming` schrijft.

- [ ] **Step 3: Run volledige regressiesuite nogmaals**

Run:
```bash
pytest -q
```
Expected: PASS met uitsluitend bestaande gedocumenteerde skips.

- [ ] **Step 4: Run geïsoleerde startup/selftest volgens bestaande v32.0.28 releasegate**

Gebruik dezelfde bewezen geïsoleerde container/startupmethode als v32.0.28 en eis minimaal:
- `/health` HTTP 200;
- GUI HTTP 200;
- ingress HTTP 200;
- geen startup exception;
- productie-32.0.28 hash vóór/na identiek.

- [ ] **Step 5: Bouw maximaal één definitieve v32.0.29 releasecandidate**

Pas nadat Steps 1-4 groen zijn. Verifieer ZIP-integriteit, manifest, vereiste files en SHA-256 vóór plaatsing in een installatiepad. Niet opnieuw bouwen tenzij een aantoonbare inhoudsfout wordt gevonden.

- [ ] **Step 6: Stop bij de echte HA-validatiepoort**

De enige gebruikersactie die daarna nodig is:
1. HA update naar 32.0.29;
2. `Maak complete Crash Recovery`;
3. wacht op `ready_for_download`;
4. klik `Download Crash Recovery ZIP`;
5. bewaar ZIP tijdelijk en pak hem uit in `AI Projecten/Test backup`;
6. controleer dat daar precies `Test backup/EnergieProject/` ontstaat;
7. vergelijk inhoud/tellingen en bevestig dat maandbackups, manifests, logs en handleidingen aanwezig zijn en de twee complete backup-archiefpatronen ontbreken;
8. controleer dat na geslaagde download de tijdelijke NAS-Crash-Recovery-run is opgeruimd;
9. controleer dat normale NAS-backups en augustusstatus onaangeroerd zijn.

Pas na deze echte HA-/uitpaktest mag v32.0.29 end-to-end als volledig bewezen worden verklaard.

---

## Plan self-review

- **Spec coverage:** create/deep verify/RestoreStaging, volledige projectinhoud, expliciete exclusions, browserdownload, interrupted-download retry, run-specifieke cleanup, no-finalize, no-live-restore, behoud normale backups, GUI en echte HA-test zijn allemaal aan een taak gekoppeld.
- **Placeholder scan:** geen `TBD`, `TODO`, `implement later` of vrijblijvende foutafhandeling opgenomen.
- **Type consistency:** de Task-1 interfaces worden met dezelfde namen gebruikt in Tasks 2-3; statevelden voor export/download/cleanup zijn doorlopend gelijk benoemd.
- **Scope:** spraak/ChatGPT-aanroep blijft buiten v32.0.29; deze release levert alleen de veilige backend/API/GUI-downloadlaag zoals goedgekeurd.
