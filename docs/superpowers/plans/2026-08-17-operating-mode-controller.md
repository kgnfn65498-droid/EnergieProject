# Operating Mode Controller Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and prove an enforced USER / DEVELOPMENT / MAINTENANCE operating-mode controller for EnergieProject v32.3.12, with automatic temporary switching, persistent Projectmanager state, runtime reconciliation, mode-gated Incoming processing, vacation-safe month automation, GUI controls, and chat-visible status.

**Architecture:** A small pure Python mode core owns the canonical Projectmanager state under `Data/03_Systeem/Projectmanager/State`. The Home Assistant add-on runs the reconciliation loop and applies effective month-workflow overrides; the QNAP release watcher remains a dormant supervisor but asks the same mode core whether release ingress or maintenance-request processing is allowed before touching `Inbox/incoming`. Both GUI actions and ChatGPT/Projectmanager automation use one idempotent file-command contract, so no new NLP subsystem or MCP rebuild is required for the first release.

**Tech Stack:** Python 3.12, frozen dataclasses, pathlib/json, Home Assistant add-on HTTP server in `main.py`, POSIX `sh` watcher, pytest, existing QNAP shared project layout.

## Global Constraints

- Baseline release is exactly `32.3.11`; target release for this implementation is `32.3.12`.
- There are exactly three real modes: `USER`, `DEVELOPMENT`, `MAINTENANCE`; `AUTO` is not a fourth mode.
- `automatic_switching_enabled` defaults to `true`.
- USER is the normal safe/base mode.
- USER must not scan or process `Inbox/incoming`; the watcher process may remain alive only as a dormant supervisor.
- DEVELOPMENT may process release ZIPs from `Inbox/incoming` and must check the release chain on entry.
- MAINTENANCE may process approved maintenance requests but must not process release ZIPs from `Inbox/incoming`.
- Normal energy import, scheduled month workflow and reporting remain enabled in every mode unless an explicit temporary maintenance pause records and restores a named feature.
- USER must effectively enable automatic processing/closing of the previous fully closed calendar month; the current calendar month must never be automatically finalized.
- Destructive restore/delete gates remain unchanged and cannot be bypassed by entering MAINTENANCE.
- Mode transitions are successful only after desired state is applied, observed state is read back, and reconciliation reports `OK`.
- Missing, malformed or legacy mode state must fail closed for release ingress and migrate safely to base/effective `USER`, automatic switching enabled.
- Persistent state writes must use temp-file + `os.replace()` atomic replacement.
- No further Nomad work, no new crash-recovery architecture, no full GUI redesign, no separate runtime/container per mode, and no new month-workflow engine in this release.
- Every task follows TDD: failing test, verify failure, minimal implementation, verify pass, commit.

---

## File map locked for this plan

- Create `slimmemeterportal_import/rootfs/app/operating_modes.py` — canonical modes, state schema, migration, command processing, transition lifecycle, desired profiles, chat-status formatter, atomic persistence.
- Create `tools/operating_mode_gate.py` — tiny CLI adapter used by the shell watcher; imports the canonical mode core from the installed project source and returns capability allow/deny via exit code.
- Modify `tools/release_watcher.sh` — keep supervisor alive but gate release ingress and maintenance-request processing on canonical effective mode.
- Modify `slimmemeterportal_import/rootfs/app/main.py` — instantiate runtime controller, process commands/reconcile in background, apply effective month-workflow profile, expose status/API and render GUI controls.
- Modify `slimmemeterportal_import/config.yaml` — bump version only; do not add a duplicate fourth-mode option or duplicate persisted mode state to HA options.
- Create `tests/test_v32312_operating_modes.py` — pure mode-state/transition/command/profile tests.
- Create `tests/test_v32312_mode_watcher_gate.py` — watcher and gate CLI tests.
- Create `tests/test_v32312_mode_runtime.py` — effective month-profile, previous-month-only guard, startup/reconciliation and file-command tests against `main.py`.
- Modify `tests/test_gui_runtime.py` — mode card and controls render even with missing normal output data.
- Modify `VERSIE.txt`, `CHANGELOG.md`, `slimmemeterportal_import/CHANGELOG.md` — release identity and user-visible behavior.

---

### Task 1: Canonical mode state, profiles and safe migration

**Files:**
- Create: `slimmemeterportal_import/rootfs/app/operating_modes.py`
- Create: `tests/test_v32312_operating_modes.py`

**Interfaces:**
- Produces: `Mode(str, Enum)`, `ModeProfile`, `ModeState`, `state_path(project_root) -> Path`, `command_path(project_root) -> Path`, `load_mode_state(project_root) -> ModeState`, `save_mode_state(project_root, state) -> None`, `profile_for(mode, suspended_features=frozenset()) -> ModeProfile`, `format_chat_status(state) -> str`.
- State location: `<project_root>/Data/03_Systeem/Projectmanager/State/operating_mode_state.json`.
- Command location: `<project_root>/Data/03_Systeem/Projectmanager/State/operating_mode_command.json`.

- [ ] **Step 1: Write failing state/profile/migration tests**

```python
from dataclasses import replace
import json

from operating_modes import (
    Mode,
    ModeState,
    format_chat_status,
    load_mode_state,
    profile_for,
    save_mode_state,
)


def test_missing_state_migrates_to_safe_user(tmp_path):
    state = load_mode_state(tmp_path)
    assert state.base_mode is Mode.USER
    assert state.effective_mode is Mode.USER
    assert state.automatic_switching_enabled is True
    assert state.reconciliation_status == "required"


def test_invalid_state_fails_closed_to_user(tmp_path):
    path = tmp_path / "Data/03_Systeem/Projectmanager/State/operating_mode_state.json"
    path.parent.mkdir(parents=True)
    path.write_text('{"base_mode":"BROKEN"}', encoding="utf-8")
    state = load_mode_state(tmp_path)
    assert state.effective_mode is Mode.USER
    assert state.reconciliation_status == "required"
    assert state.drift


def test_profiles_match_approved_contract():
    user = profile_for(Mode.USER)
    dev = profile_for(Mode.DEVELOPMENT)
    maint = profile_for(Mode.MAINTENANCE)
    assert user.release_ingress_enabled is False
    assert user.maintenance_request_processing_enabled is False
    assert user.schedule_enabled is True
    assert user.full_workflow_enabled is True
    assert user.automatic_month_close_enabled is True
    assert dev.release_ingress_enabled is True
    assert dev.maintenance_request_processing_enabled is False
    assert maint.release_ingress_enabled is False
    assert maint.maintenance_request_processing_enabled is True


def test_atomic_roundtrip_preserves_state(tmp_path):
    original = ModeState.initial()
    changed = replace(original, base_mode=Mode.DEVELOPMENT, effective_mode=Mode.DEVELOPMENT)
    save_mode_state(tmp_path, changed)
    assert load_mode_state(tmp_path) == changed


def test_chat_status_shows_base_effective_auto_and_reason():
    state = replace(
        ModeState.initial(),
        effective_mode=Mode.MAINTENANCE,
        temporary_reason="backup uitvoeren",
    )
    assert format_chat_status(state) == "[MODE] MAINTENANCE · AUTO AAN · basis USER · backup uitvoeren"
```

- [ ] **Step 2: Run tests and verify they fail before the module exists**

Run: `pytest tests/test_v32312_operating_modes.py -v`

Expected: collection/import failure for `operating_modes`.

- [ ] **Step 3: Implement the minimal canonical types and persistence**

Use this exact public shape in `operating_modes.py`:

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
import json
import os
from pathlib import Path
from typing import Any


class Mode(str, Enum):
    USER = "USER"
    DEVELOPMENT = "DEVELOPMENT"
    MAINTENANCE = "MAINTENANCE"


@dataclass(frozen=True)
class ModeProfile:
    release_ingress_enabled: bool
    maintenance_request_processing_enabled: bool
    schedule_enabled: bool
    full_workflow_enabled: bool
    automatic_month_close_enabled: bool


@dataclass(frozen=True)
class ModeState:
    schema_version: int = 1
    base_mode: Mode = Mode.USER
    effective_mode: Mode = Mode.USER
    automatic_switching_enabled: bool = True
    temporary_reason: str = ""
    active_transition_id: str = ""
    suspended_features: tuple[str, ...] = ()
    reconciliation_status: str = "required"
    last_reconciled_at: str = ""
    last_processed_request_id: str = ""
    drift: tuple[str, ...] = ()
    observed_profile: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def initial(cls) -> "ModeState":
        return cls()
```

Implement `profile_for()` with compiled safety profiles matching the approved table. Accept only these temporary suspension names: `schedule`, `full_workflow`, `automatic_month_close`; a suspension forces the corresponding profile boolean false and is legal only while effective mode is MAINTENANCE.

Implement state serialization with enum values as strings. `load_mode_state()` must migrate the previous design-only/legacy JSON by treating any missing/unknown runtime mode as USER and adding a drift entry such as `legacy_or_invalid_state_migrated`. Never trust legacy `LEGACY_OPERATIONAL_NOT_MODE_CONTROLLED` as an effective mode.

Implement `save_mode_state()` as:

```python
tmp = path.with_name(path.name + f".tmp.{os.getpid()}")
tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
os.replace(tmp, path)
```

- [ ] **Step 4: Run Task 1 tests**

Run: `pytest tests/test_v32312_operating_modes.py -v`

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add slimmemeterportal_import/rootfs/app/operating_modes.py tests/test_v32312_operating_modes.py
git commit -m "feat: add canonical operating mode state"
```

---

### Task 2: Idempotent Projectmanager command contract and temporary transitions

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/operating_modes.py`
- Modify: `tests/test_v32312_operating_modes.py`

**Interfaces:**
- Consumes: Task 1 `Mode`, `ModeState`, state/command paths and persistence.
- Produces: `ModeCommand`, `process_mode_command(project_root, now=None) -> ModeState`, `begin_temporary_mode(state, requested_mode, reason, transition_id) -> ModeState`, `end_temporary_mode(state, transition_id) -> ModeState`, `set_base_mode(state, mode) -> ModeState`, `set_automatic_switching(state, enabled) -> ModeState`.
- File command actions: `set_base`, `set_auto`, `begin_temporary`, `end_temporary`, `reconcile`.

- [ ] **Step 1: Add failing command/transition tests**

```python
import json
from operating_modes import Mode, command_path, load_mode_state, process_mode_command


def write_command(root, payload):
    path = command_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_begin_temporary_development_preserves_user_base(tmp_path):
    write_command(tmp_path, {
        "schema_version": 1,
        "request_id": "req-1",
        "action": "begin_temporary",
        "requested_mode": "DEVELOPMENT",
        "reason": "mode controller bouwen",
        "issued_by": "chatgpt_projectmanager",
    })
    state = process_mode_command(tmp_path)
    assert state.base_mode is Mode.USER
    assert state.effective_mode is Mode.DEVELOPMENT
    assert state.active_transition_id == "req-1"


def test_end_temporary_returns_to_base(tmp_path):
    write_command(tmp_path, {"schema_version": 1, "request_id": "req-1", "action": "begin_temporary", "requested_mode": "MAINTENANCE", "reason": "backup"})
    process_mode_command(tmp_path)
    write_command(tmp_path, {"schema_version": 1, "request_id": "req-2", "action": "end_temporary", "transition_id": "req-1"})
    state = process_mode_command(tmp_path)
    assert state.effective_mode is Mode.USER
    assert state.active_transition_id == ""


def test_replayed_request_is_idempotent(tmp_path):
    payload = {"schema_version": 1, "request_id": "req-1", "action": "set_base", "requested_mode": "DEVELOPMENT"}
    write_command(tmp_path, payload)
    first = process_mode_command(tmp_path)
    second = process_mode_command(tmp_path)
    assert second == first


def test_auto_off_blocks_temporary_escalation(tmp_path):
    write_command(tmp_path, {"schema_version": 1, "request_id": "req-1", "action": "set_auto", "enabled": False})
    process_mode_command(tmp_path)
    write_command(tmp_path, {"schema_version": 1, "request_id": "req-2", "action": "begin_temporary", "requested_mode": "MAINTENANCE", "reason": "backup"})
    state = process_mode_command(tmp_path)
    assert state.effective_mode is Mode.USER
    assert any("automatic_switching_disabled" in item for item in state.drift)


def test_wrong_transition_token_cannot_end_another_task(tmp_path):
    write_command(tmp_path, {"schema_version": 1, "request_id": "req-1", "action": "begin_temporary", "requested_mode": "DEVELOPMENT", "reason": "build"})
    process_mode_command(tmp_path)
    write_command(tmp_path, {"schema_version": 1, "request_id": "req-2", "action": "end_temporary", "transition_id": "wrong"})
    state = process_mode_command(tmp_path)
    assert state.effective_mode is Mode.DEVELOPMENT
    assert state.active_transition_id == "req-1"
```

- [ ] **Step 2: Run the new tests and verify failure**

Run: `pytest tests/test_v32312_operating_modes.py -v`

Expected: FAIL because command/transition functions are absent.

- [ ] **Step 3: Implement command parsing and transition rules**

`ModeCommand` validates the exact action set and rejects missing/empty `request_id`. `process_mode_command()` must:

1. load state;
2. return unchanged if the request ID equals `last_processed_request_id`;
3. validate the command;
4. apply one transition function;
5. record `last_processed_request_id`;
6. set `reconciliation_status="required"` after any desired-state change;
7. atomically save state.

`begin_temporary` is legal only when automatic switching is enabled, requested mode is DEVELOPMENT or MAINTENANCE, and no different active transition exists. `end_temporary` requires the matching transition ID and returns effective mode to base mode. `set_base` is a manual override and sets both base/effective mode only when there is no active temporary transition. `set_auto(False)` does not destroy the base mode; it merely blocks future automatic temporary escalation.

Support optional `suspended_features` only for MAINTENANCE, validating against the Task 1 allowlist.

- [ ] **Step 4: Run Task 1–2 tests**

Run: `pytest tests/test_v32312_operating_modes.py -v`

Expected: PASS.

- [ ] **Step 5: Commit Task 2**

```bash
git add slimmemeterportal_import/rootfs/app/operating_modes.py tests/test_v32312_operating_modes.py
git commit -m "feat: add idempotent mode transitions"
```

---

### Task 3: Mode-gate the QNAP watcher without killing the supervisor

**Files:**
- Create: `tools/operating_mode_gate.py`
- Modify: `tools/release_watcher.sh`
- Create: `tests/test_v32312_mode_watcher_gate.py`
- Modify: `tests/test_crash_recovery_watcher_cleanup.py`

**Interfaces:**
- Consumes: canonical state/profile from Task 1.
- Produces CLI: `python3 tools/operating_mode_gate.py --root <project-root> --capability release_ingress|maintenance_requests|status`.
- Exit `0` means allowed/healthy; exit `3` means capability denied by mode; exit `4` means malformed/unreadable state and therefore fail-closed.
- `status` prints one compact JSON object with base/effective/auto/reconcile values.

- [ ] **Step 1: Write failing gate and watcher tests**

```python
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = ROOT / "tools/operating_mode_gate.py"
WATCHER = ROOT / "tools/release_watcher.sh"


def seed_state(project, mode):
    path = project / "Data/03_Systeem/Projectmanager/State/operating_mode_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": 1,
        "base_mode": "USER",
        "effective_mode": mode,
        "automatic_switching_enabled": True,
        "reconciliation_status": "ok",
    }), encoding="utf-8")


def run_gate(project, capability):
    return subprocess.run([sys.executable, str(GATE), "--root", str(project), "--capability", capability], text=True, capture_output=True)


def test_user_denies_release_and_maintenance(tmp_path):
    seed_state(tmp_path, "USER")
    assert run_gate(tmp_path, "release_ingress").returncode == 3
    assert run_gate(tmp_path, "maintenance_requests").returncode == 3


def test_development_allows_only_release_ingress(tmp_path):
    seed_state(tmp_path, "DEVELOPMENT")
    assert run_gate(tmp_path, "release_ingress").returncode == 0
    assert run_gate(tmp_path, "maintenance_requests").returncode == 3


def test_maintenance_allows_only_maintenance_requests(tmp_path):
    seed_state(tmp_path, "MAINTENANCE")
    assert run_gate(tmp_path, "release_ingress").returncode == 3
    assert run_gate(tmp_path, "maintenance_requests").returncode == 0


def test_missing_state_fails_closed_for_release(tmp_path):
    assert run_gate(tmp_path, "release_ingress").returncode != 0


def test_watcher_checks_mode_before_touching_incoming():
    source = WATCHER.read_text(encoding="utf-8")
    loop = source.split("while :; do", 1)[1]
    assert loop.index("mode_allows maintenance_requests") < loop.index("process_crash_recovery_cleanup")
    assert loop.index("mode_allows release_ingress") < loop.index('set -- "$INCOMING"/*.zip')
```

Change the old cleanup watcher test so it no longer requires unconditional cleanup processing; it must require cleanup to be nested behind the MAINTENANCE gate.

- [ ] **Step 2: Run watcher tests and verify failure**

Run: `pytest tests/test_v32312_mode_watcher_gate.py tests/test_crash_recovery_watcher_cleanup.py -v`

Expected: FAIL because gate does not exist and watcher has no mode checks.

- [ ] **Step 3: Implement the CLI adapter**

`tools/operating_mode_gate.py` must locate the canonical module from:

```python
app_module = root / "App/slimmemeterportal_import/rootfs/app"
if not app_module.is_dir():
    app_module = root / "slimmemeterportal_import/rootfs/app"  # repository test layout
```

Import `load_mode_state` and `profile_for`; for missing/malformed state, do not create a state file from the watcher. Print a JSON error and return `4`. This keeps release ingress fail-closed until the always-on add-on/controller performs migration/reconciliation.

- [ ] **Step 4: Gate both watcher paths**

Add near watcher variables:

```sh
MODE_GATE="$PROJECT/tools/operating_mode_gate.py"
mode_allows(){
  capability=$1
  [ -f "$MODE_GATE" ] || return 1
  python3 "$MODE_GATE" --root "$ROOT" --capability "$capability" >/dev/null 2>&1
}
```

Replace the unconditional loop body with the exact structure:

```sh
while :; do
  touch_heartbeat

  if mode_allows maintenance_requests; then
    process_crash_recovery_cleanup || true
  fi

  if mode_allows release_ingress; then
    set -- "$INCOMING"/*.zip
    # existing stable-copy/integrity/install block remains unchanged here
  fi

  sleep "$INTERVAL"
done
```

Do not stop the watcher process in USER. Do not scan `Inbox/incoming` merely to report that USER is inactive. The supervisor heartbeat/lock may stay alive.

- [ ] **Step 5: Run watcher tests**

Run: `pytest tests/test_v32312_mode_watcher_gate.py tests/test_crash_recovery_watcher_cleanup.py -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

```bash
git add tools/operating_mode_gate.py tools/release_watcher.sh tests/test_v32312_mode_watcher_gate.py tests/test_crash_recovery_watcher_cleanup.py
git commit -m "feat: gate watcher by operating mode"
```

---

### Task 4: Runtime reconciliation and Projectmanager file-command worker

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/operating_modes.py`
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Create: `tests/test_v32312_mode_runtime.py`

**Interfaces:**
- Consumes: Tasks 1–2 state/command logic.
- Produces: `reconcile_state(project_root, observed_profile, now=None) -> ModeState` and in `main.py`: `operating_mode_project_root() -> Path`, `operating_mode_snapshot() -> dict[str, Any]`, `operating_mode_worker() -> None`.
- The worker is the 24/7 enforcement loop; the Projectmanager/ChatGPT can submit the same idempotent command file using existing project-system write access.

- [ ] **Step 1: Add failing reconciliation tests**

```python
from dataclasses import replace
from operating_modes import Mode, ModeState, reconcile_state, save_mode_state


def test_reconcile_marks_matching_user_profile_ok(tmp_path):
    save_mode_state(tmp_path, ModeState.initial())
    observed = {
        "release_ingress_enabled": False,
        "maintenance_request_processing_enabled": False,
        "schedule_enabled": True,
        "full_workflow_enabled": True,
        "automatic_month_close_enabled": True,
    }
    state = reconcile_state(tmp_path, observed)
    assert state.reconciliation_status == "ok"
    assert state.drift == ()


def test_reconcile_records_drift(tmp_path):
    save_mode_state(tmp_path, ModeState.initial())
    state = reconcile_state(tmp_path, {"release_ingress_enabled": True})
    assert state.reconciliation_status == "drift"
    assert any("release_ingress_enabled" in item for item in state.drift)
```

Add a `main.py` worker test that redirects `_runtime_nas_roots_now()`/state paths to `tmp_path`, writes one `begin_temporary` command, invokes one single-cycle helper `operating_mode_tick()`, and asserts effective DEVELOPMENT plus `last_processed_request_id`.

- [ ] **Step 2: Run runtime tests and verify failure**

Run: `pytest tests/test_v32312_mode_runtime.py -v`

Expected: FAIL because reconciliation/tick helpers do not exist.

- [ ] **Step 3: Implement pure reconciliation**

`reconcile_state()` compares only keys present in the complete observed profile produced by the runtime adapter against `profile_for(state.effective_mode, state.suspended_features)`. It stores the observed profile, sets `reconciliation_status` to `ok` or `drift`, sets `last_reconciled_at`, and atomically persists.

A drift is not cleared until a later readback matches. Do not silently set `ok` after merely attempting a correction.

- [ ] **Step 4: Implement one-cycle runtime worker in `main.py`**

Add imports:

```python
from dataclasses import dataclass, replace
from operating_modes import (
    Mode,
    command_path as operating_mode_command_path,
    format_chat_status,
    load_mode_state,
    process_mode_command,
    profile_for,
    reconcile_state,
)
```

Implement:

```python
def operating_mode_project_root() -> Path:
    return _runtime_nas_roots_now()[1]


def operating_mode_tick() -> dict[str, Any]:
    root = operating_mode_project_root()
    state = process_mode_command(root)
    desired = profile_for(state.effective_mode, state.suspended_features)
    observed = observe_operating_mode_runtime(desired)
    state = reconcile_state(root, observed)
    return operating_mode_snapshot(state)
```

`observe_operating_mode_runtime()` reports the *effective values the add-on and watcher will use*, not raw stale HA options. For release/maintenance booleans, observed state comes from the canonical effective profile because watcher gate consumes the same state; Task 8 live acceptance will prove the external behavior.

Worker loop:

```python
def operating_mode_worker() -> None:
    while not STOP.wait(5):
        try:
            operating_mode_tick()
        except Exception:
            LOGGER.exception("Operating mode reconciliation failed")
```

Start this daemon alongside existing planner/background threads during application startup. Also call `operating_mode_tick()` once before the normal scheduler begins, so legacy/missing state migrates to safe USER before unattended automation.

- [ ] **Step 5: Run runtime tests**

Run: `pytest tests/test_v32312_mode_runtime.py tests/test_gui_runtime.py -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add slimmemeterportal_import/rootfs/app/operating_modes.py slimmemeterportal_import/rootfs/app/main.py tests/test_v32312_mode_runtime.py
git commit -m "feat: reconcile operating mode runtime"
```

---

### Task 5: Enforce vacation-safe effective month automation by mode

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Modify: `tests/test_v32312_mode_runtime.py`

**Interfaces:**
- Consumes: `Options.load()`, Task 4 current mode state/profile.
- Produces: `effective_options_for_mode(options: Options, state: ModeState) -> Options`, `is_fully_closed_month(month_key: str, now: datetime | None = None) -> bool`.
- Existing scheduler functions must consume effective options; raw `/data/options.json` and `/config/automatic_month_close.json` remain user configuration, not the safety-critical mode truth.

- [ ] **Step 1: Add failing effective-options and closed-month tests**

```python
from dataclasses import replace
from datetime import datetime
from zoneinfo import ZoneInfo
from operating_modes import Mode, ModeState


def test_user_overrides_stale_disabled_month_switches(m):
    options = replace(
        m.Options.load(),
        schedule_enabled=False,
        full_workflow_enabled=False,
        automatic_month_close_enabled=False,
    )
    effective = m.effective_options_for_mode(options, ModeState.initial())
    assert effective.schedule_enabled is True
    assert effective.full_workflow_enabled is True
    assert effective.automatic_month_close_enabled is True


def test_current_month_is_never_fully_closed(m):
    now = datetime(2026, 8, 17, 12, 0, tzinfo=ZoneInfo("Europe/Amsterdam"))
    assert m.is_fully_closed_month("2026_08", now) is False
    assert m.is_fully_closed_month("2026_07", now) is True


def test_maintenance_pause_is_restored_by_profile(m):
    state = replace(ModeState.initial(), effective_mode=Mode.MAINTENANCE, suspended_features=("automatic_month_close",))
    paused = m.effective_options_for_mode(m.Options.load(), state)
    assert paused.automatic_month_close_enabled is False
    restored = m.effective_options_for_mode(m.Options.load(), replace(state, suspended_features=()))
    assert restored.automatic_month_close_enabled is True
```

Use the existing test fixture/helper pattern to redirect `OPTIONS_PATH` to a temp options file with minimum valid values.

- [ ] **Step 2: Run tests and verify failure**

Run: `pytest tests/test_v32312_mode_runtime.py -v`

Expected: FAIL because effective mode overrides and closed-month guard are missing.

- [ ] **Step 3: Implement immutable effective options**

Import `replace` from `dataclasses` and implement:

```python
def effective_options_for_mode(options: Options, state) -> Options:
    profile = profile_for(state.effective_mode, state.suspended_features)
    return replace(
        options,
        schedule_enabled=profile.schedule_enabled,
        full_workflow_enabled=profile.full_workflow_enabled,
        automatic_month_close_enabled=profile.automatic_month_close_enabled,
    )
```

Do not write the overridden values back to `/data/options.json` or the existing auto-close UI file. This avoids fighting Home Assistant Supervisor option persistence and makes the mode controller the single effective-state authority.

- [ ] **Step 4: Route scheduler reads through effective options**

At scheduler entry points, replace direct `Options.load()` usage with:

```python
raw_options = Options.load()
mode_state = load_mode_state(operating_mode_project_root())
options = effective_options_for_mode(raw_options, mode_state)
```

Apply this to:
- the normal import planner loop using `schedule_enabled`;
- automatic month-close due/next-run logic using `automatic_month_close_enabled`;
- full-month workflow scheduler entry using `full_workflow_enabled`.

Manual test/UI functions may continue to show raw user settings but must also expose `effective_enabled` in status so the GUI can explain when USER enforces ON.

- [ ] **Step 5: Add and apply the hard closed-calendar-month guard**

```python
def is_fully_closed_month(month_key: str, now: datetime | None = None) -> bool:
    now = now or datetime.now(TZ)
    year, month = (int(part) for part in month_key.split("_", 1))
    return (year, month) < (now.year, now.month)
```

Immediately before any automatic scheduler finalization, assert the selected `month_key` passes this guard. If it does not, append an audit event with status `blocked_current_month` and return without running finalization. Keep existing `previous_month(now.date())` behavior as the normal source; the guard is defense in depth.

- [ ] **Step 6: Run month/runtime regression tests**

Run: `pytest tests/test_v32312_mode_runtime.py tests/test_static.py -q`

Expected: PASS.

- [ ] **Step 7: Commit Task 5**

```bash
git add slimmemeterportal_import/rootfs/app/main.py tests/test_v32312_mode_runtime.py
git commit -m "feat: enforce mode-safe month automation"
```

---

### Task 6: GUI status card, manual controls and shared command path

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Modify: `tests/test_gui_runtime.py`
- Modify: `tests/test_v32312_mode_runtime.py`

**Interfaces:**
- Consumes: Task 2 command schema, Task 4 `operating_mode_snapshot()`.
- Produces HTTP POST endpoints `/set-operating-mode`, `/set-operating-mode-auto`, `/reconcile-operating-mode`; dashboard payload key `operating_mode`; one permanent GUI card.
- Manual GUI mode buttons issue `set_base`; they do not create a fourth AUTO mode.

- [ ] **Step 1: Add failing GUI rendering test**

Extend `test_gui_runtime.py`:

```python
body = m.html_page("/api/hassio_ingress/test")
text = body.decode("utf-8")
assert "Bedrijfsmodus" in text
assert "USER" in text
assert "DEVELOPMENT" in text
assert "MAINTENANCE" in text
assert "Automatisch schakelen" in text
assert "Reconciliation" in text
```

- [ ] **Step 2: Add failing command-endpoint tests**

Test the command-writing helper directly rather than starting a real HTTP server:

```python
def test_gui_set_base_uses_same_command_contract(m, tmp_path):
    m.operating_mode_project_root = lambda: tmp_path
    result = m.submit_operating_mode_command(action="set_base", requested_mode="DEVELOPMENT", issued_by="gui")
    assert result["status"] == "ok"
    state = load_mode_state(tmp_path)
    assert state.base_mode is Mode.DEVELOPMENT
```

Add equivalent test for `set_auto(False)` and `reconcile`.

- [ ] **Step 3: Run GUI/runtime tests and verify failure**

Run: `pytest tests/test_gui_runtime.py tests/test_v32312_mode_runtime.py -v`

Expected: FAIL on absent card/helper/endpoints.

- [ ] **Step 4: Implement one command-submission helper**

`submit_operating_mode_command()` generates a unique request ID using timestamp + `secrets.token_hex(4)`, atomically writes the canonical command file, invokes `operating_mode_tick()` synchronously for immediate GUI feedback, and returns the resulting snapshot. Do not implement separate mutation logic in HTTP handlers.

- [ ] **Step 5: Add POST handlers**

Handlers accept only:
- `/set-operating-mode`: `mode=USER|DEVELOPMENT|MAINTENANCE` → `set_base`;
- `/set-operating-mode-auto`: `enabled=0|1` → `set_auto`;
- `/reconcile-operating-mode`: no mode parameter → `reconcile`.

Return JSON including `base_mode`, `effective_mode`, `automatic_switching_enabled`, `reconciliation_status`, `reason`, and `chat_status`.

- [ ] **Step 6: Render the mode card**

Add a compact top-level card before development/maintenance-heavy controls:

```html
<div class="card" id="operating-mode-card">
  <h2>Bedrijfsmodus</h2>
  <p><strong>Basis:</strong> ... <strong>Actueel:</strong> ...</p>
  <p><strong>Automatisch schakelen:</strong> AAN/UIT</p>
  <p><strong>Reden:</strong> ... <strong>Reconciliation:</strong> ...</p>
  <!-- three mode buttons + one auto switch + reconcile button -->
</div>
```

Show drift in the existing warning style when reconciliation is not `ok`. Label the release state as `Incoming verwerking` rather than claiming the supervisor process is killed.

- [ ] **Step 7: Run GUI/runtime tests**

Run: `pytest tests/test_gui_runtime.py tests/test_v32312_mode_runtime.py -v`

Expected: PASS.

- [ ] **Step 8: Commit Task 6**

```bash
git add slimmemeterportal_import/rootfs/app/main.py tests/test_gui_runtime.py tests/test_v32312_mode_runtime.py
git commit -m "feat: add operating mode controls to gui"
```

---

### Task 7: Audit trail, Projectmanager-visible status and transition acceptance tests

**Files:**
- Modify: `slimmemeterportal_import/rootfs/app/operating_modes.py`
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Modify: `tests/test_v32312_operating_modes.py`
- Modify: `tests/test_v32312_mode_runtime.py`

**Interfaces:**
- Consumes: all previous mode APIs.
- Produces: `<project-root>/Data/03_Systeem/Projectmanager/Logs/operating_mode_history.jsonl`; snapshot fields `desired_profile`, `observed_profile`, `drift`, `last_reconciled_at`, `chat_status`.

- [ ] **Step 1: Add failing audit/roundtrip acceptance tests**

```python
def test_user_dev_user_roundtrip_restores_profile(tmp_path):
    # begin DEVELOPMENT
    write_command(tmp_path, {"schema_version": 1, "request_id": "dev-1", "action": "begin_temporary", "requested_mode": "DEVELOPMENT", "reason": "build"})
    dev = process_mode_command(tmp_path)
    assert profile_for(dev.effective_mode).release_ingress_enabled is True
    # finish
    write_command(tmp_path, {"schema_version": 1, "request_id": "dev-2", "action": "end_temporary", "transition_id": "dev-1"})
    user = process_mode_command(tmp_path)
    assert user.effective_mode is Mode.USER
    assert profile_for(user.effective_mode).release_ingress_enabled is False
    assert profile_for(user.effective_mode).automatic_month_close_enabled is True


def test_user_maintenance_user_restores_paused_month_close(tmp_path):
    write_command(tmp_path, {"schema_version": 1, "request_id": "m-1", "action": "begin_temporary", "requested_mode": "MAINTENANCE", "reason": "backup", "suspended_features": ["automatic_month_close"]})
    maint = process_mode_command(tmp_path)
    assert profile_for(maint.effective_mode, maint.suspended_features).automatic_month_close_enabled is False
    write_command(tmp_path, {"schema_version": 1, "request_id": "m-2", "action": "end_temporary", "transition_id": "m-1"})
    user = process_mode_command(tmp_path)
    assert user.suspended_features == ()
    assert profile_for(user.effective_mode).automatic_month_close_enabled is True
```

Add a test that each accepted command appends exactly one JSONL audit entry and replaying the same request appends none.

- [ ] **Step 2: Run tests and verify audit failure**

Run: `pytest tests/test_v32312_operating_modes.py tests/test_v32312_mode_runtime.py -v`

Expected: transition tests may pass; audit assertion FAIL until logging is added.

- [ ] **Step 3: Implement append-only mode audit log**

Each accepted command and reconciliation correction attempt logs:

```json
{
  "timestamp": "2026-08-17T12:00:00+02:00",
  "request_id": "...",
  "issued_by": "...",
  "action": "begin_temporary",
  "base_mode": "USER",
  "from_effective_mode": "USER",
  "to_effective_mode": "MAINTENANCE",
  "reason": "backup",
  "desired_profile": {},
  "observed_profile": {},
  "reconciliation_status": "required"
}
```

Use one append lock in the add-on runtime; the pure file helper may use a best-effort append because commands are serialized by state replacement. Do not log secrets or full user prompts; only the short transition reason.

- [ ] **Step 4: Make snapshot the Projectmanager read contract**

`operating_mode_snapshot()` returns all status fields needed by GUI/chat/manager. The existing canonical `operating_mode_state.json` remains directly readable by the Energie NAS/Projectmanager tools, so automatic ChatGPT orchestration can issue commands through the existing system-text write path without requiring a new MCP binary in v32.3.12.

Document the command example in a module docstring:

```json
{"schema_version":1,"request_id":"chat-...","action":"begin_temporary","requested_mode":"MAINTENANCE","reason":"backup","issued_by":"chatgpt_projectmanager"}
```

and end with a matching transition token.

- [ ] **Step 5: Run the complete mode suite**

Run: `pytest tests/test_v32312_operating_modes.py tests/test_v32312_mode_watcher_gate.py tests/test_v32312_mode_runtime.py tests/test_gui_runtime.py -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 7**

```bash
git add slimmemeterportal_import/rootfs/app/operating_modes.py slimmemeterportal_import/rootfs/app/main.py tests/test_v32312_operating_modes.py tests/test_v32312_mode_runtime.py
git commit -m "test: prove operating mode transitions and audit"
```

---

### Task 8: Release v32.3.12 identity, full regression and live acceptance gate

**Files:**
- Modify: `VERSIE.txt`
- Modify: `slimmemeterportal_import/config.yaml`
- Modify: `slimmemeterportal_import/rootfs/app/main.py`
- Modify: `CHANGELOG.md`
- Modify: `slimmemeterportal_import/CHANGELOG.md`
- Create: `tests/test_v32312_release_identity.py`

**Interfaces:**
- Consumes: completed Tasks 1–7.
- Produces: release identity `32.3.12` and evidence for `MODES_EXIT = PASS` only after live readback.

- [ ] **Step 1: Write failing release-identity test**

```python
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_v32312_identity_is_consistent():
    assert (ROOT / "VERSIE.txt").read_text().strip() == "32.3.12"
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text()
    main = (ROOT / "slimmemeterportal_import/rootfs/app/main.py").read_text()
    assert 'version: "32.3.12"' in config
    assert 'APP_VERSION = "32.3.12"' in main
```

- [ ] **Step 2: Run identity test and verify failure on v32.3.11**

Run: `pytest tests/test_v32312_release_identity.py -v`

Expected: FAIL showing `32.3.11`.

- [ ] **Step 3: Bump release identity and changelogs**

Set exactly:
- `VERSIE.txt` → `32.3.12`
- add-on `config.yaml` version → `32.3.12`
- `main.py` `APP_VERSION` → `32.3.12`

Changelog entry must state:
- operating-mode controller enforced;
- USER/DEV/MAINT profiles;
- dormant watcher supervisor with mode-gated Incoming processing;
- USER vacation-safe previous-month automation;
- Projectmanager file-command/reconciliation contract;
- GUI/chat status;
- no change to destructive safety gates.

- [ ] **Step 4: Run targeted and full automated regression**

Run targeted:

```bash
pytest tests/test_v32312_operating_modes.py \
       tests/test_v32312_mode_watcher_gate.py \
       tests/test_v32312_mode_runtime.py \
       tests/test_gui_runtime.py \
       tests/test_v32312_release_identity.py -v
```

Expected: PASS.

Run full:

```bash
pytest -q
```

Expected: all tests PASS; no existing crash-recovery, release-publication, month-workflow or Nomad regression.

- [ ] **Step 5: Commit v32.3.12**

```bash
git add VERSIE.txt CHANGELOG.md slimmemeterportal_import/config.yaml slimmemeterportal_import/CHANGELOG.md slimmemeterportal_import/rootfs/app/main.py tests/test_v32312_release_identity.py
git commit -m "release: v32.3.12 operating modes"
```

- [ ] **Step 6: Publish through the existing controlled release chain**

Use the established GitHub → automatic Home Assistant publication / Incoming installer path already proven by v32.3.11. Do not manually bypass watcher/installer gates. Because the current pre-release environment is DEVELOPMENT, release ingress must be effective before the ZIP/publication step.

Expected post-deploy identity readback:
- `App/VERSIE.txt = 32.3.12`
- HA add-on config version `32.3.12`
- runtime `APP_VERSION = 32.3.12`

- [ ] **Step 7: Run live USER acceptance**

Issue canonical command:

```json
{"schema_version":1,"request_id":"accept-user","action":"set_base","requested_mode":"USER","issued_by":"acceptance"}
```

Read back state and prove:
- base/effective USER;
- auto true;
- reconciliation `ok`;
- `release_ingress_enabled=false`;
- `schedule_enabled=true`;
- `full_workflow_enabled=true`;
- `automatic_month_close_enabled=true` effective;
- placing/observing no test ZIP processing in USER (do not leave a real release ZIP in Incoming);
- previous-month calculation points to July while current date is August, and current August cannot pass `is_fully_closed_month`.

- [ ] **Step 8: Run live automatic DEVELOPMENT roundtrip**

Issue `begin_temporary` DEVELOPMENT with reason `acceptance build test`; prove release ingress allowed. End with matching transition token; prove effective USER and release ingress denied again.

- [ ] **Step 9: Run live automatic MAINTENANCE roundtrip without destructive action**

Issue `begin_temporary` MAINTENANCE with reason `acceptance maintenance test`; prove release ingress denied and maintenance-request capability allowed. Use only a read-only/non-destructive maintenance preview as behavioral proof. End transition and prove effective USER.

- [ ] **Step 10: Prove reconciliation drift recovery**

Create a safe test-only drift through the runtime test hook/state fixture, not by disabling production month processing. Reconcile and prove the next observed snapshot matches USER. Never fabricate `ok`; require readback.

- [ ] **Step 11: Mark mode exit gate only after all evidence is green**

Update Projectmanager status/Roadmap through the existing report/state update path with:

`MODES_EXIT = PASS — v32.3.12 controller enforced; USER/DEVELOPMENT/MAINTENANCE transitions, watcher gating, month automation, GUI/status and reconciliation live-validated.`

Then and only then return the system to:

`[MODE] USER · AUTO AAN · basis USER · Reconcile OK`

The next project priority becomes the already-planned crash-recovery proof; Nomad remains blocked behind that second gate.

---

## Plan self-review checklist

- Spec coverage: all approved requirements map to Tasks 1–8, including the 15 acceptance behaviors, vacation month processing, GUI/chat status, reboot/startup reconciliation, manual fixed mode, temporary auto escalation, drift and fail-safe behavior.
- No placeholders: no TBD/TODO/fill-later steps remain.
- Type consistency: mode names, command actions, paths and function signatures are consistent across tasks.
- Scope: no Nomad expansion, crash-recovery redesign, container split or new month-workflow engine is introduced.
- Safety: watcher is fail-closed on invalid state; current month cannot auto-finalize; destructive gates are untouched; live acceptance uses no destructive operation.
