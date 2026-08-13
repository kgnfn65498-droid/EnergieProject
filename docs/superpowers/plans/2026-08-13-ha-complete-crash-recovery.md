# Home Assistant Complete Crash Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lever één normale v32.0.28-release op die vanuit Home Assistant de bestaande volledige Crash Recovery kan maken, deep-verifiëren en uitsluitend naar RestoreStaging kan test-herstellen, zonder maandfinalisatie of wijziging van de bestaande productieflow.

**Architecture:** De bestaande `slimmemeterportal_import/rootfs/app/main.py` blijft de enige HA-runtime. De nieuwe functionaliteit wordt als kleine, afgebakende recovery-controller in dezelfde runtime toegevoegd en roept uitsluitend de bestaande NAS MCP-recoverytools aan via een niet-cachende action-call. De release wordt eerst in een geïsoleerde QNAP release-stagingkopie gebouwd en volledig getest; GitHub `main` en de draaiende HA v32.0.27 blijven tot de vrijgavepoort onaangeraakt.

**Tech Stack:** Python 3.12, `ThreadingHTTPServer`, Home Assistant Ingress, JSON-RPC/MCP streamable HTTP, QNAP release watcher/installer, pytest, ZIP/SHA-256/manifestvalidatie.

## Global Constraints

- Releaseversie is exact `32.0.28`.
- `finalize_month` wordt door de nieuwe Crash Recovery-route nooit aangeroepen.
- Geen tweede backupformaat: alleen bestaande `create_complete_backup` en `verify_complete_backup`.
- Restore-test gebruikt uitsluitend `preview_backup_restore` en `stage_backup_restore` naar `/recovery/RestoreStaging`.
- Een actieve maandworkflow/import blokkeert een nieuwe Crash Recovery-start met conflictstatus; er wordt niets onderbroken.
- Deep verify is alleen GO bij `status=valid`, `deep_verified=true`, `verified_files == manifest_file_count > 0` en nul `hash_failures`.
- GitHub `main` en de draaiende HA worden niet gewijzigd vóór volledige releasevalidatie.
- De QNAP `Backups`-map wordt eerst read-only geïnventariseerd; tijdens deze release worden geen bestaande backups verwijderd op basis van naam/leeftijd alleen.
- De huidige bekende goede recovery `Energie_Complete_Backup_2026_08_20260813T174549Z.zip` blijft behouden.
- Geen credentials, secrets of `/data/options.json` in GitHub, tests, logs of release-documentatie.

---

### Task 1: Read-only Backups-inventaris en bewaarbeleid

**Files:**
- Inspect only: `/share/CACHEDEV1_DATA/AI Projecten/EnergieProject/Backups/**`
- Inspect only: `/share/CACHEDEV1_DATA/AI Projecten/EnergieProject/Infra/Docker/native-mcp/recovery_core.py`
- Inspect only: `/share/CACHEDEV1_DATA/AI Projecten/EnergieProject/Infra/Docker/native-mcp/tools_recovery.py`
- Inspect only: `/share/CACHEDEV1_DATA/AI Projecten/EnergieProject/Infra/Docker/native-mcp/tools_recovery_extensions.py`

**Interfaces:**
- Consumes: actuele QNAP-directorymetadata, bestaande recovery-retentie/backup-prefixen.
- Produces: classificatie `complete_crash_recovery`, `month_sidecar`, `release_prebackup`, `fix_prebackup`, `other`; advies `KEEP`, `REVIEW`, nooit automatisch `DELETE`.

- [ ] **Step 1: Maak een read-only inventaris zonder hashes van grote bestanden opnieuw te berekenen**

Run op QNAP:
```sh
ROOT="/share/CACHEDEV1_DATA/AI Projecten/EnergieProject"
find "$ROOT/Backups" -maxdepth 3 -type f -printf '%TY-%Tm-%TdT%TH:%TM:%TS\t%s\t%p\n' 2>/dev/null | sort
```
Expected: uitsluitend lijstoutput; geen `rm`, `mv`, `touch`, `zip` of schrijfactie.

- [ ] **Step 2: Inventariseer directorygroottes en aantallen read-only**

Run:
```sh
ROOT="/share/CACHEDEV1_DATA/AI Projecten/EnergieProject"
printf 'FILES='; find "$ROOT/Backups" -type f 2>/dev/null | wc -l
printf 'DIRS='; find "$ROOT/Backups" -type d 2>/dev/null | wc -l
du -h -d 2 "$ROOT/Backups" 2>/dev/null | sort -h
```
Expected: totalen en groottes; geen wijziging.

- [ ] **Step 3: Leg bewaarbeleid vast**

Rules:
```text
KEEP  : iedere deep-verified Energie_Complete_Backup die tot de actuele retentieset/known-good herstelpunten behoort.
KEEP  : de actuele v32.0.27 known-good backup met SHA-256 ec360d0d730fc8163ec84f7f6364377ae160b4754bae2d981f8088927156edbf.
KEEP  : maand-sidecarbackups zolang niet bewezen is dat dezelfde maand volledig in een nieuwere complete recovery zit én het noodherstelcontract ze niet meer nodig heeft.
KEEP  : pre-release/pre-fix backups zolang de release waarop ze betrekking hebben nog rollbackwaarde heeft.
REVIEW: duplicaten of oude technische fixbackups pas na vergelijking op inhoud/herstelwaarde.
DELETE: geen enkel bestand tijdens deze taak; verwijderen vereist een aparte expliciete beslissing na inventarisatie.
```

- [ ] **Step 4: Controleer dat de bekende goede recovery nog deep-valid is**

Run:
```sh
docker exec -i energie-filesystem-mcp python - <<'PY'
import json
import tools_recovery as r
result = r.verify_complete_backup(
    year=2026,
    month=8,
    backup_name="Energie_Complete_Backup_2026_08_20260813T174549Z.zip",
    deep_verify_files=True,
)
print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
PY
```
Expected: `status=valid`, `deep_verified=true`, `verified_files=1216`, nul hash failures.

---

### Task 2: Failing tests voor de HA Crash Recovery-route

**Files:**
- Create: `tests/test_complete_crash_recovery_runtime.py`
- Modify later: `slimmemeterportal_import/rootfs/app/main.py:4550-4800, 15000-15100, 16200-16520`

**Interfaces:**
- Consumes: toekomstige `_mcp_call_project_action(name, arguments, timeout)`, `run_complete_crash_recovery()`, `run_complete_restore_staging()`.
- Produces: regressiecontract voor MCP-volgorde, lockgedrag, deep-verifycriteria en `finalize_month`-afwezigheid.

- [ ] **Step 1: Schrijf de testloader en action-sequence test**

```python
import importlib.util
import pathlib
import sys


def load_main():
    source = pathlib.Path(__file__).parents[1] / "slimmemeterportal_import/rootfs/app/main.py"
    spec = importlib.util.spec_from_file_location("energy_complete_recovery_runtime", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_complete_recovery_uses_preview_create_deep_verify_only(monkeypatch, tmp_path):
    m = load_main()
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "complete_crash_recovery_state.json"
    calls = []

    def fake_action(name, arguments, timeout=8.0):
        calls.append((name, dict(arguments)))
        if name == "preview_month_closure":
            return {"confirmation": "BEVESTIG COMPLETE BACKUP"}
        if name == "create_complete_backup":
            return {"status": "ok", "backup": "/recovery/Energie_Complete_Backup_2026_08_test.zip"}
        if name == "verify_complete_backup":
            return {
                "status": "valid", "deep_verified": True,
                "manifest_file_count": 1216, "verified_files": 1216,
                "hash_failures": [], "sha256": "abc123",
            }
        raise AssertionError(name)

    monkeypatch.setattr(m, "_mcp_call_project_action", fake_action)
    result = m.run_complete_crash_recovery(year=2026, month=8)
    assert result["status"] == "verified"
    assert [name for name, _ in calls] == [
        "preview_month_closure", "create_complete_backup", "verify_complete_backup"
    ]
    assert calls[-1][1]["deep_verify_files"] is True
    assert "finalize_month" not in [name for name, _ in calls]
```

- [ ] **Step 2: Schrijf de busy/lock test**

```python
def test_complete_recovery_refuses_active_workflow(monkeypatch, tmp_path):
    m = load_main()
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"
    monkeypatch.setattr(m.WORKFLOW_LOCK, "locked", lambda: True)
    result = m.run_complete_crash_recovery(year=2026, month=8)
    assert result["status"] == "busy"
```

- [ ] **Step 3: Schrijf de deep-verify fail-closed test**

```python
def test_complete_recovery_does_not_mark_bad_verify_as_good(monkeypatch, tmp_path):
    m = load_main()
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"

    def fake_action(name, arguments, timeout=8.0):
        if name == "preview_month_closure":
            return {"confirmation": "BEVESTIG"}
        if name == "create_complete_backup":
            return {"backup": "/recovery/Energie_Complete_Backup_2026_08_bad.zip"}
        return {
            "status": "valid", "deep_verified": True,
            "manifest_file_count": 1216, "verified_files": 1215,
            "hash_failures": [],
        }

    monkeypatch.setattr(m, "_mcp_call_project_action", fake_action)
    result = m.run_complete_crash_recovery(year=2026, month=8)
    assert result["status"] == "error"
    assert result["deep_verified"] is False
```

- [ ] **Step 4: Schrijf de RestoreStaging-safety test**

```python
def test_restore_test_accepts_only_isolated_staging(monkeypatch, tmp_path):
    m = load_main()
    m.COMPLETE_CRASH_RECOVERY_STATE_PATH = tmp_path / "state.json"
    m.write_atomic_json(m.COMPLETE_CRASH_RECOVERY_STATE_PATH, {
        "status": "verified",
        "backup_name": "Energie_Complete_Backup_2026_08_test.zip",
        "year": 2026, "month": 8,
    })
    calls = []

    def fake_action(name, arguments, timeout=8.0):
        calls.append(name)
        if name == "preview_backup_restore":
            return {"confirmation": "BEVESTIG HERSTELTEST"}
        return {
            "status": "staged",
            "staging_path": "/recovery/RestoreStaging/Energie_Complete_Backup_2026_08_test",
            "source_project_modified": False,
        }

    monkeypatch.setattr(m, "_mcp_call_project_action", fake_action)
    result = m.run_complete_restore_staging()
    assert result["status"] == "staged"
    assert result["source_project_modified"] is False
    assert calls == ["preview_backup_restore", "stage_backup_restore"]
```

- [ ] **Step 5: Run alleen nieuwe tests en bevestig dat ze vóór implementatie falen**

Run:
```sh
python -m pytest -q tests/test_complete_crash_recovery_runtime.py
```
Expected: FAIL omdat `_mcp_call_project_action`, `run_complete_crash_recovery` en `run_complete_restore_staging` nog niet bestaan.

---

### Task 3: Niet-cachende MCP action-helper en recovery-controller

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/main.py:70-95` — statepad/lock naast bestaande globale statepaden.
- Modify: `slimmemeterportal_import/rootfs/app/main.py:4615-4695` — action-helper naast `_mcp_call_project_tool`.
- Modify: `slimmemeterportal_import/rootfs/app/main.py:ca. 13100-14000` — recovery-controllerfuncties buiten maandworkflow.
- Test: `tests/test_complete_crash_recovery_runtime.py`

**Interfaces:**
- Produces: `_mcp_call_project_action(name: str, arguments: dict[str, Any], timeout: float = 8.0) -> Any`.
- Produces: `run_complete_crash_recovery(*, year: int | None = None, month: int | None = None) -> dict[str, Any]`.
- Produces: `run_complete_restore_staging() -> dict[str, Any]`.

- [ ] **Step 1: Voeg statepad en lock toe**

```python
COMPLETE_CRASH_RECOVERY_STATE_PATH = Path("/config/output/complete_crash_recovery_state.json")
COMPLETE_CRASH_RECOVERY_LOCK = threading.Lock()
```

- [ ] **Step 2: Implementeer niet-cachende MCP action-call met dezelfde JSON-RPC-normalisatie als de bestaande helper**

De helper mag `_MCP_TOOL_CACHE` niet lezen of schrijven. Structured content wordt eerst gebruikt; text content wordt indien mogelijk als JSON gedecodeerd; HTTP-/decodefouten worden als `RuntimeError` doorgegeven zodat create/stage nooit stilzwijgend `None` opleveren.

```python
def _mcp_call_project_action(name: str, arguments: dict[str, Any], timeout: float = 8.0) -> Any:
    request_id = int(time.time() * 1000) % 2147483647
    payload = {
        "jsonrpc": "2.0", "id": request_id, "method": "tools/call",
        "params": {"name": name, "arguments": arguments, "_meta": {
            "io.modelcontextprotocol/protocolVersion": "2026-07-28",
            "io.modelcontextprotocol/clientCapabilities": {},
            "io.modelcontextprotocol/clientInfo": {
                "name": "energieproject-homeassistant", "version": APP_VERSION,
            },
        }},
    }
    req = urllib.request.Request(
        ENERGIE_MCP_URL,
        data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json, text/event-stream",
                 "MCP-Protocol-Version": "2026-07-28", "Mcp-Method": "tools/call", "Mcp-Name": name},
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        envelope = json.loads(response.read().decode("utf-8"))
    result = envelope.get("result") or {}
    if result.get("structuredContent") is not None:
        return result["structuredContent"]
    for block in result.get("content") or []:
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
            try:
                return json.loads(block["text"])
            except json.JSONDecodeError:
                return block["text"]
    raise RuntimeError(f"MCP-tool {name} gaf geen bruikbaar resultaat.")
```

- [ ] **Step 3: Implementeer helpers voor confirmation, ZIP-naam en state**

Use recursively nested dict/list traversal; accept a confirmation string only from a key containing `confirm` or `bevest`; accept a backup name only when basename matches `Energie_Complete_Backup_*.zip`.

- [ ] **Step 4: Implementeer complete backup-controller fail-closed**

Required flow:
```text
workflow/import idle -> acquire COMPLETE_CRASH_RECOVERY_LOCK
-> state running
-> preview_month_closure
-> extract backend confirmation
-> create_complete_backup
-> extract exact backup_name
-> verify_complete_backup(deep_verify_files=True)
-> require valid + deep + count equality + 0 hash_failures
-> persist status verified/error
-> release lock
```
`create_complete_backup` timeout: 900s. `verify_complete_backup`: 900s. Preview: 30s.

- [ ] **Step 5: Implementeer restore-staging controller**

Required flow:
```text
last state must be verified
-> preview_backup_restore
-> exact backend confirmation
-> stage_backup_restore
-> require source_project_modified is False
-> require returned result contains /recovery/RestoreStaging
-> persist restore_test status staged/error
```
Stage timeout: 900s. No restore-to-production tool may be referenced.

- [ ] **Step 6: Run nieuwe tests**

Run:
```sh
python -m pytest -q tests/test_complete_crash_recovery_runtime.py
```
Expected: PASS.

---

### Task 4: Home Assistant GUI en POST-routes

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/main.py:15000-15070` — nieuwe card direct vóór bestaande `Recovery v...` card.
- Modify: `slimmemeterportal_import/rootfs/app/main.py:16200-16520` — twee POST-routes naast `run-recovery-controller`.
- Modify: `tests/test_gui_runtime.py`
- Test: `tests/test_complete_crash_recovery_runtime.py`

**Interfaces:**
- Produces POST `/crash-recovery-complete` en `/crash-recovery-stage`.
- Produces GUI-card `Complete Crash Recovery`.

- [ ] **Step 1: Voeg GUI-regressietest toe**

```python
def test_gui_contains_complete_crash_recovery_controls():
    m = load_main()
    body = m.html_page("/api/hassio_ingress/test").decode("utf-8")
    assert "Complete Crash Recovery" in body
    assert "Maak complete Crash Recovery" in body
    assert "Test herstel naar RestoreStaging" in body
```

- [ ] **Step 2: Voeg card toe met fail-safe state-read**

Card toont ten minste `status`, `backup_name`, `sha256`, `manifest_file_count`, `verified_files`, `hash_failures`, `updated_at`, plus expliciet: `Maand wordt niet afgesloten` en `Restore-test wijzigt productie niet`.

Buttons:
```html
<form method="post" action="crash-recovery-complete"><button type="submit">Maak complete Crash Recovery</button></form>
<form method="post" action="crash-recovery-stage"><button type="submit" class="secondary">Test herstel naar RestoreStaging</button></form>
```
De tweede button wordt disabled wanneer laatste status niet `verified` is.

- [ ] **Step 3: Start create/verify in background thread**

`POST /crash-recovery-complete`:
- 409 als workflow/import/recovery lock bezet is.
- Anders thread starten en direct redirect naar `./` zodat HA Ingress niet minutenlang op een HTTP-response wacht.
- Worker exceptions altijd in statebestand vastleggen; nooit serverthread laten crashen.

- [ ] **Step 4: Start stagingtest in background thread**

Zelfde patroon; alleen bij laatst `verified` resultaat.

- [ ] **Step 5: Run GUI + recoverytests**

Run:
```sh
python -m pytest -q tests/test_gui_runtime.py tests/test_complete_crash_recovery_runtime.py
```
Expected: PASS.

---

### Task 5: Release-identiteit v32.0.28 en regressiecontracten

**Files:**
- Modify: `slimmemeterportal_import/config.yaml` — version `32.0.28`.
- Modify: `slimmemeterportal_import/rootfs/app/main.py:ca. 45` — `APP_VERSION = "32.0.28"`.
- Modify: `VERSIE.txt` — `32.0.28`.
- Modify: `CHANGELOG.md` — alleen v32.0.28 release-entry.
- Modify: `tests/test_static.py` — release-identiteit `32.0.28` en nieuwe safety assertions.
- Regenerate: `MANIFEST.sha256`, `SHA256SUMS.json` via bestaande releasebuilder.

**Interfaces:**
- Produces eenduidige version identity `32.0.28` in HA config, runtime en projectmanifest.

- [ ] **Step 1: Update exacte release-identiteiten**

Expected assertions:
```python
assert cfg_version == app_version == "32.0.28"
assert "finalize_month" not in recovery_route_source
assert "stage_backup_restore" in recovery_route_source
assert "restore" not in recovery_route_source.replace("stage_backup_restore", "")
```
De laatste statische check wordt concreet begrensd tot de nieuwe controllerfuncties, niet tot heel `main.py`.

- [ ] **Step 2: Voeg changelog-entry toe**

Entry beschrijft uitsluitend: HA complete recovery UI, bestaande MCP-backend, deep verify, RestoreStaging test, geen productiekern-/maandworkflowwijziging.

- [ ] **Step 3: Run volledige testsuite in release-staging**

Run:
```sh
python -m pytest -q
```
Expected: alle bestaande tests plus nieuwe tests PASS; alleen reeds bekende expliciete skips toegestaan.

---

### Task 6: Vrijgavepoort en één ZIP

**Files:**
- Build artifact: `/share/CACHEDEV1_DATA/AI Projecten/EnergieProject/Backups/_release_prepare/EnergieProject_v32.0.28.zip` of de door de bestaande releasebuilder gebruikte equivalente `_release_prepare`-locatie.
- Final upload target: `/share/CACHEDEV1_DATA/AI Projecten/EnergieProject/Inbox/incoming/EnergieProject_v32.0.28.zip`.

**Interfaces:**
- Consumes: volledige geteste v32.0.28 release-stagingtree.
- Produces: één `EnergieProject_v32.0.28.zip` + SHA-256 + testbewijs.

- [ ] **Step 1: Bouw uitsluitend vanuit geïsoleerde release-staging**

De live `App` v32.0.27 wordt vóór watcher-installatie niet overschreven. Gebruik de bestaande releasebuilder/watchercontracten; geen handmatig `zip -r` over de live projectroot.

- [ ] **Step 2: Controleer ZIP-integriteit en manifest**

Run op het uiteindelijke bestand:
```sh
unzip -t "EnergieProject_v32.0.28.zip"
sha256sum "EnergieProject_v32.0.28.zip"
```
Expected: `No errors detected` en één vastgelegde SHA-256.

- [ ] **Step 3: Installatiesimulatie oude watcher → v32.0.28**

Gebruik dezelfde bewezen release-installatieketentest als v32.0.27. Vereist: rollbackpad aanwezig, version identity 32.0.28, processed-retentie maximaal 3 release-ZIPs.

- [ ] **Step 4: Runtime smoke buiten productie**

Start de app uit de geteste staging/container en controleer:
```text
GET /health -> 200 + version 32.0.28
GET / -> 200 + Complete Crash Recovery card
missing options/output precondition -> GUI blijft renderen
startup-selftest -> geen exception
```

- [ ] **Step 5: Pas na alle groene checks ZIP naar incoming**

Watcher mag daarna normale backup/install/rollback doen. Als watcher faalt: HA/GitHub niet wijzigen en terug naar v32.0.27.

- [ ] **Step 6: Publiceer HA-code gecontroleerd naar GitHub en update HA**

Voor GitHub-publicatie eerst diff controleren: alleen release-identiteit, recovery-controller/UI/tests/manifests/docs. Geen onverwachte verwijderingen of wijzigingen aan SMP-import, scheduler, rapportage of publisher. Publicatie via aparte branch/PR of de bewezen publisherroute; nooit onreviewed direct op `main`.

- [ ] **Step 7: Bewijs de route vanuit Home Assistant zelf**

In HA:
1. Klik `Maak complete Crash Recovery`.
2. Wacht tot status `verified` toont.
3. Controleer naam, SHA, `verified_files == manifest_file_count`, hash failures 0.
4. Klik `Test herstel naar RestoreStaging`.
5. Vereis `source_project_modified=false` en stagingpad onder `/recovery/RestoreStaging`.
6. Herhaal Master Health; verwacht 100% of uitsluitend verklaarde niet-blokkerende data-info.

## Plan self-review

- Spec coverage: backup create, deep verify, GUI, background execution, fail-closed, restore staging, no finalize, active-workflow conflict, release gate en GitHub/HA-isolatie zijn alle aan taken gekoppeld.
- Extra gebruikerswens: Backups-map inventaris/bewaarbeslissing is Task 1 en bevat expliciet geen delete-stap.
- Placeholder scan: geen TODO/TBD/implement-later-stappen.
- Type/interface consistency: action helper en twee controllerfuncties zijn consequent benoemd in tests en implementatietaken.
- Scope: één releasefeature plus één read-only backupinventaris; geen andere roadmapfunctie wordt meegenomen.
