from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import/rootfs/app"
EXECUTOR = ROOT / "tools/project_clearup_move_executor.py"
WATCHER = ROOT / "tools/release_watcher.sh"
BOOTSTRAP = ROOT / "tools/bootstrap_release_watcher_container.sh"


def load_module(name: str, filename: str):
    if str(APP) not in sys.path:
        sys.path.insert(0, str(APP))
    spec = importlib.util.spec_from_file_location(name, APP / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def rollback(root: Path, version: str) -> Path:
    path = root / f"App.__rollback_{version}"
    path.mkdir(parents=True)
    (path / "VERSIE.txt").write_text(version, encoding="utf-8")
    (path / "payload.txt").write_text(f"payload-{version}", encoding="utf-8")
    return path


def ready_root(root: Path, version: str = "32.4.32") -> None:
    (root / "CLEARUP").mkdir(parents=True, exist_ok=True)
    approval = root / "Data/03_Systeem/Projectmanager/State/32_4_25_scope_cleanup_and_history_repair_20260909.md"
    approval.parent.mkdir(parents=True, exist_ok=True)
    approval.write_text("Status: DEVELOPMENT SCOPE APPROVED BY USER\nCLEARUP\n", encoding="utf-8")

    inbox = root / "Inbox"
    (inbox / "operating_mode").mkdir(parents=True, exist_ok=True)
    (inbox / "logs").mkdir(parents=True, exist_ok=True)
    (inbox / "atomic_app_swap_state.json").write_text(
        json.dumps({"state": "ACCEPTED", "to_version": version, "rollback_path": f"App.__rollback_{version}"}),
        encoding="utf-8",
    )
    (inbox / "operating_mode/release_validation_hold.json").write_text(
        json.dumps({"active": False, "validation_status": "ok"}), encoding="utf-8"
    )

    cr = root / "Backups/CrashRecovery"
    cr.mkdir(parents=True, exist_ok=True)
    backup = cr / "2026-09-10 10.00 CrashRecovery EnergieProject.zip"
    backup.write_bytes(b"tiny-test-backup")
    digest = hashlib.sha256(backup.read_bytes()).hexdigest()
    stem = backup.with_suffix("")
    Path(str(stem) + ".sha256").write_text(f"{digest}  {backup.name}\n", encoding="utf-8")
    Path(str(stem) + ".manifest.json").write_text(json.dumps({"file_count": 1}), encoding="utf-8")
    Path(str(stem) + ".restore.txt").write_text("RESTORE VERIFIED\n", encoding="utf-8")


def seed_executor_app(root: Path, version: str = "32.4.32") -> None:
    app = root / "App/slimmemeterportal_import/rootfs/app"
    app.mkdir(parents=True, exist_ok=True)
    shutil.copy2(APP / "project_clearup.py", app / "project_clearup.py")
    (root / "App/VERSIE.txt").write_text(version + "\n", encoding="utf-8")


def test_auto_clearup_delegates_apply_to_watcher_bridge(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    auto = load_module("project_clearup_auto_32433_delegate", "project_clearup_auto.py")
    ready_root(tmp_path)
    for version in ("32.4.20", "32.4.21", "32.4.22", "32.4.23"):
        rollback(tmp_path, version)

    called: dict[str, object] = {}

    def forbidden_direct_apply(*args, **kwargs):
        raise AssertionError("HA runtime mag CLEARUP hard-renames niet meer direct uitvoeren")

    def fake_bridge(root, plan, *, run_id, deadline_monotonic, progress_callback, started_monotonic, pre_acceptance=False):
        called["root"] = root
        called["plan_id"] = plan["plan_id"]
        called["run_id"] = run_id
        return {
            "status": "completed",
            "run_id": run_id,
            "manifest": f"CLEARUP/{run_id}/manifest.json",
            "moved_count": 1,
            "review_count": 0,
            "delete_performed": False,
        }

    monkeypatch.setattr(auto, "apply_clearup_plan", forbidden_direct_apply)
    monkeypatch.setattr(auto, "_apply_clearup_via_watcher", fake_bridge, raising=False)

    result = auto.run_approved_clearup_once(
        tmp_path,
        app_version="32.4.32",
        run_id="delegated-run",
        timeout_seconds=30,
    )

    assert result["status"] == "completed"
    assert called["root"] == tmp_path.resolve()
    assert called["run_id"] == "delegated-run"
    assert result["delete_performed"] is False


def test_watcher_executor_applies_and_restores_root_level_candidate(tmp_path: Path):
    clearup = load_module("project_clearup_32433_executor", "project_clearup.py")
    ready_root(tmp_path)
    seed_executor_app(tmp_path)
    for version in ("32.4.20", "32.4.21", "32.4.22", "32.4.23"):
        rollback(tmp_path, version)
    plan = clearup.build_clearup_plan(tmp_path, current_version="32.4.32", keep_rollbacks=3)
    target = tmp_path / "App.__rollback_32.4.20"
    assert target.is_dir()

    request = tmp_path / "Inbox/project_clearup_move_request.json"
    result_path = tmp_path / "Inbox/logs/project_clearup_move_result.json"
    request_id = "a" * 32
    request.write_text(json.dumps({
        "schema": "energie_project_clearup_move_request_v1",
        "request_id": request_id,
        "operation": "apply",
        "release_version": "32.4.32",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat(),
        "plan": plan,
        "confirmation": plan["confirmation_required"],
        "run_id": "watcher-apply-test",
    }), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(EXECUTOR), "--root", str(tmp_path), "--request", str(request), "--result", str(result_path)],
        text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0, completed.stderr
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["request_id"] == request_id
    assert payload["status"] == "completed"
    assert payload["delete_performed"] is False
    assert not os.path.lexists(target)
    manifest = tmp_path / "CLEARUP/watcher-apply-test/manifest.json"
    assert manifest.is_file()
    manifest_data = json.loads(manifest.read_text(encoding="utf-8"))
    moved = next(item for item in manifest_data["items"] if item["source_path"] == "App.__rollback_32.4.20")
    assert moved["old_path_absent"] is True
    assert moved["rename_identity_verified"] is True
    assert moved["restore_status"] == "AVAILABLE"

    restore_request_id = "b" * 32
    request.write_text(json.dumps({
        "schema": "energie_project_clearup_move_request_v1",
        "request_id": restore_request_id,
        "operation": "restore",
        "release_version": "32.4.32",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat(),
        "restore_run_id": "watcher-apply-test",
        "confirmation": "RESTORE CLEARUP watcher-apply-test",
    }), encoding="utf-8")
    restored = subprocess.run(
        [sys.executable, str(EXECUTOR), "--root", str(tmp_path), "--request", str(request), "--result", str(result_path)],
        text=True, capture_output=True, check=False,
    )
    assert restored.returncode == 0, restored.stderr
    restore_payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert restore_payload["request_id"] == restore_request_id
    assert restore_payload["status"] == "completed"
    assert target.is_dir()
    assert not (tmp_path / "CLEARUP/watcher-apply-test/original/App.__rollback_32.4.20").exists()


def test_watcher_executor_rejects_release_mismatch_without_move(tmp_path: Path):
    clearup = load_module("project_clearup_32433_mismatch", "project_clearup.py")
    ready_root(tmp_path, version="32.4.32")
    seed_executor_app(tmp_path, version="32.4.32")
    for version in ("32.4.20", "32.4.21", "32.4.22", "32.4.23"):
        rollback(tmp_path, version)
    plan = clearup.build_clearup_plan(tmp_path, current_version="32.4.32", keep_rollbacks=3)
    target = tmp_path / "App.__rollback_32.4.20"
    request = tmp_path / "Inbox/project_clearup_move_request.json"
    result_path = tmp_path / "Inbox/logs/project_clearup_move_result.json"
    request.write_text(json.dumps({
        "schema": "energie_project_clearup_move_request_v1",
        "request_id": "c" * 32,
        "operation": "apply",
        "release_version": "32.4.99",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(seconds=60)).isoformat(),
        "plan": plan,
        "confirmation": plan["confirmation_required"],
        "run_id": "must-not-run",
    }), encoding="utf-8")

    completed = subprocess.run(
        [sys.executable, str(EXECUTOR), "--root", str(tmp_path), "--request", str(request), "--result", str(result_path)],
        text=True, capture_output=True, check=False,
    )
    assert completed.returncode != 0
    payload = json.loads(result_path.read_text(encoding="utf-8"))
    assert payload["status"] == "rejected"
    assert "release" in payload["error"].lower()
    assert target.is_dir()
    assert not (tmp_path / "CLEARUP/must-not-run").exists()


def test_watcher_wires_clearup_move_request_in_python_container_without_root_chmod():
    watcher = WATCHER.read_text(encoding="utf-8")
    bootstrap = BOOTSTRAP.read_text(encoding="utf-8")
    assert 'PROJECT_CLEARUP_REQUEST="$INBOX/project_clearup_move_request.json"' in watcher
    assert 'PROJECT_CLEARUP_EXECUTOR="$PROJECT/tools/project_clearup_move_executor.py"' in watcher
    assert "process_project_clearup_move" in watcher
    assert 'python3 "$PROJECT_CLEARUP_EXECUTOR"' in watcher
    assert "python:3.12-slim" in bootstrap
    assert 'chmod 777 "$ROOT"' not in watcher
    assert 'chmod 1777 "$ROOT"' not in watcher


def test_32433_release_identity_is_consistent():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.4.46"
    main = (APP / "main.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.4.46"' in main
