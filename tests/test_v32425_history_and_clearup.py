from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import historical_energy_excel as hx  # noqa: E402

CLEARUP_MODULE = APP / "project_clearup.py"


def _load_clearup():
    assert CLEARUP_MODULE.is_file(), "32.4.25 project_clearup module ontbreekt"
    spec = importlib.util.spec_from_file_location("project_clearup", CLEARUP_MODULE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_full_actuals(root: Path, month_key: str, *, import_kwh: float = 210.0) -> None:
    year, month = (int(part) for part in month_key.split("_"))
    days = 31 if month in {1, 3, 5, 7, 8, 10, 12} else 30
    month_dir = root / "Data" / "01_Input" / month_key / "HomeAssistant" / "SlimmeMeterPortal"
    month_dir.mkdir(parents=True, exist_ok=True)
    month_dir.joinpath("historical_energy_month_actuals.json").write_text(
        json.dumps({
            "month": month_key,
            "status": "VOLLEDIG",
            "period_start": f"{year:04d}-{month:02d}-01",
            "period_end": f"{year:04d}-{month:02d}-{days:02d}",
            "import_kwh": import_kwh,
            "export_kwh": 510.0,
            "net_kwh": import_kwh - 510.0,
            "gas_m3": 25.0,
            "source": f"fixture {month_key}",
        }),
        encoding="utf-8",
    )


def _build_month(root: Path, month_key: str, output: Path) -> None:
    periods, status = hx.periods_for_publish(root, month_key, include_partial_current=False)
    assert status == "VOLLEDIG"
    output.parent.mkdir(parents=True, exist_ok=True)
    hx.build_historical_energy_workbook(root, month_key, periods=periods, output_path=output)


def test_32425_workbook_semantics_detect_latest_month(tmp_path: Path):
    _write_full_actuals(tmp_path, "2026_08")
    workbook = tmp_path / "aug.xlsx"
    _build_month(tmp_path, "2026_08", workbook)
    assert hx.latest_month_key_in_workbook(workbook) == "2026_08"


def test_32425_bootstrap_repairs_valid_but_stale_master_from_valid_august_archive(tmp_path: Path):
    _write_full_actuals(tmp_path, "2026_08")
    history = tmp_path / "Data/02_Output/Rapportages/Verbruikshistorie"
    archive = history / "Archief/Energie_verbruik_historie_2026_08.xlsx"
    _build_month(tmp_path, "2026_08", archive)
    master = history / "Energie_verbruik_historie.xlsx"
    _build_month(tmp_path, "2026_07", master)
    before = hashlib.sha256(master.read_bytes()).hexdigest()

    result = hx.bootstrap_historical_energy_workbook(tmp_path)

    assert result["status"] == "repaired_stale_master"
    assert result["month"] == "2026_08"
    assert result["previous_master_month"] == "2026_07"
    assert hx.latest_month_key_in_workbook(master) == "2026_08"
    assert master.read_bytes() == archive.read_bytes()
    assert hashlib.sha256(master.read_bytes()).hexdigest() != before


def test_32425_bootstrap_repair_is_idempotent_after_stale_master_fix(tmp_path: Path):
    _write_full_actuals(tmp_path, "2026_08")
    history = tmp_path / "Data/02_Output/Rapportages/Verbruikshistorie"
    archive = history / "Archief/Energie_verbruik_historie_2026_08.xlsx"
    _build_month(tmp_path, "2026_08", archive)
    master = history / "Energie_verbruik_historie.xlsx"
    _build_month(tmp_path, "2026_07", master)

    first = hx.bootstrap_historical_energy_workbook(tmp_path)
    repaired_hash = hashlib.sha256(master.read_bytes()).hexdigest()
    second = hx.bootstrap_historical_energy_workbook(tmp_path)

    assert first["status"] == "repaired_stale_master"
    assert second["status"] == "skipped_existing"
    assert second["master_latest_month"] == "2026_08"
    assert hashlib.sha256(master.read_bytes()).hexdigest() == repaired_hash


def test_32425_bootstrap_never_promotes_archive_with_wrong_semantic_month(tmp_path: Path):
    _write_full_actuals(tmp_path, "2026_08")
    history = tmp_path / "Data/02_Output/Rapportages/Verbruikshistorie"
    master = history / "Energie_verbruik_historie.xlsx"
    archive = history / "Archief/Energie_verbruik_historie_2026_08.xlsx"
    _build_month(tmp_path, "2026_07", master)
    _build_month(tmp_path, "2026_07", archive)

    with pytest.raises(RuntimeError, match="archief.*2026_08|2026_08.*archief"):
        hx.bootstrap_historical_energy_workbook(tmp_path)
    assert hx.latest_month_key_in_workbook(master) == "2026_07"


def test_32425_clearup_module_exists():
    assert CLEARUP_MODULE.is_file()


def _minimal_project(root: Path) -> None:
    (root / "App").mkdir(parents=True)
    (root / "App/VERSIE.txt").write_text("32.4.25\n", encoding="utf-8")
    (root / "Infra").mkdir(parents=True)
    (root / "Inbox").mkdir(parents=True)
    (root / "CLEARUP").mkdir(parents=True)
    (root / "Data/03_Systeem/Projectmanager/Roadmap").mkdir(parents=True)
    (root / "Data/03_Systeem/Projectmanager/Policies").mkdir(parents=True)
    (root / "Data/03_Systeem/Projectmanager/State").mkdir(parents=True)


def _rollback(root: Path, version: str, payload: str = "x") -> Path:
    path = root / f"App.__rollback_{version}"
    path.mkdir(parents=True)
    (path / "VERSIE.txt").write_text(version + "\n", encoding="utf-8")
    (path / "payload.txt").write_text(payload, encoding="utf-8")
    return path


def test_32425_clearup_keeps_latest_three_rollbacks_and_quarantines_older_unreferenced(tmp_path: Path):
    mod = _load_clearup()
    _minimal_project(tmp_path)
    for version in ("32.4.20", "32.4.21", "32.4.22", "32.4.23"):
        _rollback(tmp_path, version)

    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.25", keep_rollbacks=3)
    by_path = {item["source_path"]: item for item in plan["items"]}

    assert by_path["App.__rollback_32.4.20"]["disposition"] == "CLEARUP"
    assert all(f"App.__rollback_{v}" not in by_path for v in ("32.4.21", "32.4.22", "32.4.23"))


def test_32425_dependency_reference_blocks_move_and_is_reported(tmp_path: Path):
    mod = _load_clearup()
    _minimal_project(tmp_path)
    _rollback(tmp_path, "32.4.20")
    _rollback(tmp_path, "32.4.21")
    _rollback(tmp_path, "32.4.22")
    _rollback(tmp_path, "32.4.23")
    (tmp_path / "Infra/active.conf").write_text("fallback=App.__rollback_32.4.20\n", encoding="utf-8")

    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.25", keep_rollbacks=3)
    item = next(item for item in plan["items"] if item["source_path"] == "App.__rollback_32.4.20")

    assert item["disposition"] == "REVIEW"
    assert any(ref["path"] == "Infra/active.conf" for ref in item["active_references"])


def test_32425_clearup_hard_move_removes_old_path_and_preserves_origin_manifest(tmp_path: Path):
    mod = _load_clearup()
    _minimal_project(tmp_path)
    old = _rollback(tmp_path, "32.4.20", payload="important rollback")
    for version in ("32.4.21", "32.4.22", "32.4.23"):
        _rollback(tmp_path, version)

    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.25", keep_rollbacks=3)
    result = mod.apply_clearup_plan(
        tmp_path,
        plan,
        confirmation=plan["confirmation_required"],
        run_id="test-run",
    )

    assert result["status"] == "completed"
    assert not old.exists()
    assert not os.path.lexists(old)
    moved = tmp_path / "CLEARUP/test-run/original/App.__rollback_32.4.20"
    assert moved.is_dir()
    assert moved.joinpath("payload.txt").read_text(encoding="utf-8") == "important rollback"
    manifest = json.loads((tmp_path / "CLEARUP/test-run/manifest.json").read_text(encoding="utf-8"))
    entry = next(item for item in manifest["items"] if item["source_path"] == "App.__rollback_32.4.20")
    assert entry["quarantine_path"] == "CLEARUP/test-run/original/App.__rollback_32.4.20"
    assert entry["old_path_absent"] is True
    assert entry["restore_status"] == "AVAILABLE"
    assert entry["tree_sha256"]


def test_32425_clearup_restore_is_fail_closed_on_conflict_then_roundtrips(tmp_path: Path):
    mod = _load_clearup()
    _minimal_project(tmp_path)
    old = _rollback(tmp_path, "32.4.20", payload="rollback")
    for version in ("32.4.21", "32.4.22", "32.4.23"):
        _rollback(tmp_path, version)
    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.25", keep_rollbacks=3)
    mod.apply_clearup_plan(tmp_path, plan, confirmation=plan["confirmation_required"], run_id="test-run")

    old.mkdir()
    (old / "conflict.txt").write_text("do not overwrite", encoding="utf-8")
    with pytest.raises(FileExistsError):
        mod.restore_clearup_run(tmp_path, "test-run", confirmation="RESTORE CLEARUP test-run")
    assert (old / "conflict.txt").is_file()
    # remove only our test conflict and retry
    (old / "conflict.txt").unlink()
    old.rmdir()

    restored = mod.restore_clearup_run(tmp_path, "test-run", confirmation="RESTORE CLEARUP test-run")
    assert restored["status"] == "completed"
    assert old.joinpath("payload.txt").read_text(encoding="utf-8") == "rollback"
    assert not (tmp_path / "CLEARUP/test-run/original/App.__rollback_32.4.20").exists()


def test_32425_clearup_never_moves_protected_paths_or_current_atomic_rollback(tmp_path: Path):
    mod = _load_clearup()
    _minimal_project(tmp_path)
    for version in ("32.4.20", "32.4.21", "32.4.22", "32.4.23"):
        _rollback(tmp_path, version)
    (tmp_path / "Backups/CrashRecovery").mkdir(parents=True)
    (tmp_path / "Backups/CrashRecovery/keep.zip").write_bytes(b"keep")
    (tmp_path / "Inbox/atomic_app_swap_state.json").write_text(
        json.dumps({"state": "ACCEPTED", "rollback_path": "App.__rollback_32.4.20", "to_version": "32.4.25"}),
        encoding="utf-8",
    )

    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.25", keep_rollbacks=3)
    by_path = {item["source_path"]: item for item in plan["items"]}
    assert by_path["App.__rollback_32.4.20"]["disposition"] == "REVIEW"
    assert "Backups/CrashRecovery" not in by_path


def test_32425_clearup_area_is_never_scanned_as_active_dependency(tmp_path: Path):
    mod = _load_clearup()
    _minimal_project(tmp_path)
    for version in ("32.4.20", "32.4.21", "32.4.22", "32.4.23"):
        _rollback(tmp_path, version)
    clearup = tmp_path / "CLEARUP/old-run"
    clearup.mkdir(parents=True)
    (clearup / "notes.txt").write_text("App.__rollback_32.4.20\n", encoding="utf-8")

    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.25", keep_rollbacks=3)
    item = next(item for item in plan["items"] if item["source_path"] == "App.__rollback_32.4.20")
    assert item["disposition"] == "CLEARUP"
    assert not item["active_references"]


def test_32425_known_old_staging_directories_are_candidates_but_canonical_parents_remain(tmp_path: Path):
    mod = _load_clearup()
    _minimal_project(tmp_path)
    (tmp_path / "Backups/RestoreStaging/drill-1").mkdir(parents=True)
    (tmp_path / "Backups/RestoreStaging/drill-1/a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "Backups/_release_prepare/build-old").mkdir(parents=True)
    (tmp_path / "Backups/_release_prepare/build-old/a.txt").write_text("x", encoding="utf-8")
    (tmp_path / "Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2").mkdir(parents=True)
    (tmp_path / "Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2/old.txt").write_text("x", encoding="utf-8")

    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.25", keep_rollbacks=3)
    paths = {item["source_path"] for item in plan["items"] if item["disposition"] == "CLEARUP"}
    assert "Backups/RestoreStaging/drill-1" in paths
    assert "Backups/_release_prepare/build-old" in paths
    assert "Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2/old.txt" in paths
    assert "Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2" not in paths
    assert "Backups/RestoreStaging" not in paths
    assert "Backups/_release_prepare" not in paths


def test_32425_restore_staging_exact_state_reference_blocks_specific_drill(tmp_path: Path):
    mod = _load_clearup()
    _minimal_project(tmp_path)
    drill = tmp_path / "Backups/RestoreStaging/drill-active"
    drill.mkdir(parents=True)
    (drill / "payload.txt").write_text("x", encoding="utf-8")
    old = tmp_path / "Backups/RestoreStaging/drill-old"
    old.mkdir(parents=True)
    (old / "payload.txt").write_text("y", encoding="utf-8")
    state = tmp_path / "Data/03_Systeem/Projectmanager/State/complete_recovery.json"
    state.write_text(json.dumps({"restore_staging_path": "/recovery/RestoreStaging/drill-active"}), encoding="utf-8")

    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.25", keep_rollbacks=3)
    by_path = {item["source_path"]: item for item in plan["items"]}
    assert by_path["Backups/RestoreStaging/drill-active"]["disposition"] == "REVIEW"
    assert any(ref["path"].endswith("complete_recovery.json") for ref in by_path["Backups/RestoreStaging/drill-active"]["active_references"])
    assert by_path["Backups/RestoreStaging/drill-old"]["disposition"] == "CLEARUP"


def test_32425_dependency_scan_blocks_symlink_from_active_runtime_surface(tmp_path: Path):
    mod = _load_clearup()
    _minimal_project(tmp_path)
    for version in ("32.4.20", "32.4.21", "32.4.22", "32.4.23"):
        _rollback(tmp_path, version)
    target = tmp_path / "App.__rollback_32.4.20"
    os.symlink(target, tmp_path / "Infra/runtime-fallback")

    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.25", keep_rollbacks=3)
    item = next(item for item in plan["items"] if item["source_path"] == "App.__rollback_32.4.20")
    assert item["disposition"] == "REVIEW"
    assert any("symlink_dependency" in ref["matches"] for ref in item["active_references"])



def test_32425_pm_staging_dependency_isolated_per_child(tmp_path: Path):
    mod = _load_clearup()
    _minimal_project(tmp_path)
    staging = tmp_path / "Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2"
    referenced = staging / "Repair32_4_9"
    disposable = staging / "Repair32_4_10"
    referenced.mkdir(parents=True)
    disposable.mkdir(parents=True)
    (referenced / "artifact.zip").write_bytes(b"old-4.9")
    (disposable / "artifact.zip").write_bytes(b"old-4.10")
    runtime = tmp_path / "Inbox/projectmanager_v2/RuntimeV2/commands"
    runtime.mkdir(parents=True, exist_ok=True)
    (runtime / "queue.json").write_text(json.dumps({
        "artifact_path": "Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2/Repair32_4_9/artifact.zip"
    }), encoding="utf-8")

    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.25", keep_rollbacks=3)
    by_path = {item["source_path"]: item for item in plan["items"]}
    assert by_path["Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2/Repair32_4_9"]["disposition"] == "REVIEW"
    assert by_path["Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2/Repair32_4_10"]["disposition"] == "CLEARUP"
    assert "Data/03_Systeem/Projectmanager/Staging/ProjectManagerV2" not in by_path

def _load_hygiene():
    path = APP / "project_hygiene.py"
    assert path.is_file(), "32.4.25 project_hygiene module ontbreekt"
    spec = importlib.util.spec_from_file_location("project_hygiene", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_32425_project_hygiene_surfaces_cleanup_debt_without_mutating(tmp_path: Path):
    mod = _load_hygiene()
    _minimal_project(tmp_path)
    for version in ("32.4.20", "32.4.21", "32.4.22", "32.4.23"):
        _rollback(tmp_path, version)
    (tmp_path / "App.__failed_32.4.10_001").mkdir()
    (tmp_path / "Backups/RestoreStaging/old-drill").mkdir(parents=True)

    before = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))
    check = mod.project_hygiene_check(tmp_path, keep_rollbacks=3)
    after = sorted(p.relative_to(tmp_path).as_posix() for p in tmp_path.rglob("*"))

    assert check["name"] == "project_structure_hygiene"
    assert check["status"] == "ORANGE"
    assert check["details"]["rollback_excess_count"] == 1
    assert check["details"]["failed_release_count"] == 1
    assert check["details"]["restore_staging_child_count"] == 1
    assert before == after, "PM hygiene check mag niets muteren"


def test_32425_ngrok_security_never_calls_full_native_mcp_secure(tmp_path: Path):
    mod = _load_hygiene()
    _minimal_project(tmp_path)
    compose = tmp_path / "Infra/docker-compose.yml"
    compose.write_text(
        "services:\n  ngrok:\n    command:\n      - http\n      - 127.0.0.1:8000\n      - --url\n      - https://example.ngrok-free.dev\n",
        encoding="utf-8",
    )
    check = mod.ngrok_security_check(tmp_path)
    assert check["name"] == "ngrok_security"
    assert check["status"] == "ORANGE"
    assert check["reason"] == "full_native_mcp_tunnel_not_secured"
    assert check["details"]["target"] == "127.0.0.1:8000"


def test_32425_ngrok_8099_without_verified_edge_policy_is_still_not_green(tmp_path: Path):
    mod = _load_hygiene()
    _minimal_project(tmp_path)
    compose = tmp_path / "Infra/docker-compose.yml"
    compose.write_text(
        "services:\n  ngrok:\n    command:\n      - http\n      - 127.0.0.1:8099\n",
        encoding="utf-8",
    )
    check = mod.ngrok_security_check(tmp_path)
    assert check["status"] == "ORANGE"
    assert check["reason"] == "edge_security_not_proven"


def test_32425_projectmanager_health_includes_hygiene_and_ngrok_checks(tmp_path: Path):
    pm_root = APP / "projectmanager_v2"
    if str(pm_root) not in sys.path:
        sys.path.insert(0, str(pm_root))
    from projectmanager_v2.energy_health_collector import EnergyHealthCollector

    _minimal_project(tmp_path)
    input_root = tmp_path / "Data/01_Input"
    recovery_root = tmp_path / "Backups"
    input_root.mkdir(parents=True, exist_ok=True)
    recovery_root.mkdir(parents=True, exist_ok=True)
    (tmp_path / "Infra/docker-compose.yml").write_text(
        "services:\n  ngrok:\n    command:\n      - http\n      - 127.0.0.1:8000\n",
        encoding="utf-8",
    )
    checks = EnergyHealthCollector(tmp_path, input_root, recovery_root).collect()
    by_name = {item["name"]: item for item in checks}
    assert "project_structure_hygiene" in by_name
    assert "ngrok_security" in by_name
    assert by_name["ngrok_security"]["status"] == "ORANGE"


def test_32425_housekeeping_registry_and_docs_do_not_self_block_clearup(tmp_path: Path):
    mod = _load_clearup()
    _minimal_project(tmp_path)
    candidate = tmp_path / "Data/03_Systeem/Debug"
    candidate.mkdir(parents=True)
    (candidate / "old.tmp").write_text("x", encoding="utf-8")
    app_code = tmp_path / "App/slimmemeterportal_import/rootfs/app"
    app_code.mkdir(parents=True)
    (app_code / "project_clearup.py").write_text('candidate = "Data/03_Systeem/Debug"\n', encoding="utf-8")
    scope = tmp_path / "Data/03_Systeem/Projectmanager/State/scope.md"
    scope.write_text("quarantine Data/03_Systeem/Debug after audit\n", encoding="utf-8")

    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.25", keep_rollbacks=3)
    item = next(item for item in plan["items"] if item["source_path"] == "Data/03_Systeem/Debug")
    assert item["disposition"] == "CLEARUP"
    assert not item["active_references"]
    assert any(ref["path"].endswith("project_clearup.py") for ref in item["informational_references"])
    assert any(ref["path"].endswith("scope.md") for ref in item["informational_references"])


def test_32425_machine_state_json_reference_remains_a_hard_dependency(tmp_path: Path):
    mod = _load_clearup()
    _minimal_project(tmp_path)
    candidate = tmp_path / "Data/03_Systeem/Debug"
    candidate.mkdir(parents=True)
    (candidate / "old.tmp").write_text("x", encoding="utf-8")
    state = tmp_path / "Data/03_Systeem/Projectmanager/State/runtime.json"
    state.write_text(json.dumps({"active_path": "Data/03_Systeem/Debug"}), encoding="utf-8")

    plan = mod.build_clearup_plan(tmp_path, current_version="32.4.25", keep_rollbacks=3)
    item = next(item for item in plan["items"] if item["source_path"] == "Data/03_Systeem/Debug")
    assert item["disposition"] == "REVIEW"
    assert any(ref["path"].endswith("runtime.json") for ref in item["active_references"])


def _load_clearup_auto():
    path = APP / "project_clearup_auto.py"
    assert path.is_file(), "32.4.25 project_clearup_auto module ontbreekt"
    spec = importlib.util.spec_from_file_location("project_clearup_auto", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _approve_clearup_scope(root: Path) -> None:
    state = root / "Data/03_Systeem/Projectmanager/State"
    state.mkdir(parents=True, exist_ok=True)
    (state / "32_4_25_scope_cleanup_and_history_repair_20260909.md").write_text(
        "Status: DEVELOPMENT SCOPE APPROVED BY USER\nCLEARUP hard move approved\n",
        encoding="utf-8",
    )


def _accepted_release(root: Path, version: str = "32.4.25") -> None:
    (root / "Inbox").mkdir(parents=True, exist_ok=True)
    (root / "Inbox/atomic_app_swap_state.json").write_text(
        json.dumps({"state": "ACCEPTED", "to_version": version, "rollback_path": "App.__rollback_32.4.23"}),
        encoding="utf-8",
    )
    op = root / "Inbox/operating_mode"
    op.mkdir(parents=True, exist_ok=True)
    (op / "release_validation_hold.json").write_text(
        json.dumps({"active": False, "validation_status": "ok"}), encoding="utf-8"
    )


def _valid_cr_set(root: Path) -> None:
    cr = root / "Backups/CrashRecovery"
    cr.mkdir(parents=True, exist_ok=True)
    zip_path = cr / "2026-09-05 12.15 CrashRecovery EnergieProject.zip"
    zip_path.write_bytes(b"verified-backup-fixture")
    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    stem = zip_path.with_suffix("")
    Path(str(stem) + ".sha256").write_text(f"{sha}  {zip_path.name}\n", encoding="utf-8")
    Path(str(stem) + ".manifest.json").write_text(json.dumps({"file_count": 1}), encoding="utf-8")
    Path(str(stem) + ".restore.txt").write_text("VALID\n", encoding="utf-8")


def test_32425_auto_clearup_gate_requires_persisted_approval_acceptance_hold_and_cr(tmp_path: Path):
    mod = _load_clearup_auto()
    _minimal_project(tmp_path)
    gate = mod.clearup_auto_gate(tmp_path, app_version="32.4.25")
    assert gate["ready"] is False
    assert "user_approval" in gate["blockers"]
    assert "release_phase_not_safe" in gate["blockers"]
    assert "crash_recovery_not_verified" in gate["blockers"]

    _approve_clearup_scope(tmp_path)
    _accepted_release(tmp_path)
    _valid_cr_set(tmp_path)
    gate = mod.clearup_auto_gate(tmp_path, app_version="32.4.25")
    assert gate["ready"] is True
    assert not gate["blockers"]


def test_32425_auto_clearup_run_uses_hard_move_only_after_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    mod = _load_clearup_auto()
    _minimal_project(tmp_path)
    _approve_clearup_scope(tmp_path)
    _accepted_release(tmp_path)
    _valid_cr_set(tmp_path)
    for version in ("32.4.20", "32.4.21", "32.4.22", "32.4.23"):
        _rollback(tmp_path, version)

    def local_executor(root, plan, *, run_id, deadline_monotonic, progress_callback, started_monotonic, pre_acceptance=False):
        return mod.apply_clearup_plan(
            root, plan, confirmation=plan['confirmation_required'], run_id=run_id,
            deadline_monotonic=deadline_monotonic, progress_callback=progress_callback,
            started_monotonic=started_monotonic,
        )

    monkeypatch.setattr(mod, '_apply_clearup_via_watcher', local_executor)
    result = mod.run_approved_clearup_once(tmp_path, app_version="32.4.25", run_id="auto-test")
    assert result["status"] == "completed"
    assert not os.path.lexists(tmp_path / "App.__rollback_32.4.20")
    assert (tmp_path / "CLEARUP/auto-test/original/App.__rollback_32.4.20").is_dir()
    assert result["delete_performed"] is False


def test_32425_auto_gate_does_not_hash_cr_before_release_is_accepted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    mod = _load_clearup_auto()
    _minimal_project(tmp_path)
    _approve_clearup_scope(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("CR hash mag niet draaien vóór release-acceptance")

    monkeypatch.setattr(mod, "_crash_recovery_gate", forbidden)
    gate = mod.clearup_auto_gate(tmp_path, app_version="32.4.25")
    assert gate["ready"] is False
    assert "release_phase_not_safe" in gate["blockers"]



def test_32425_cr_gate_accepts_real_restore_instructions_with_separate_practical_acceptance(tmp_path: Path):
    mod = _load_clearup_auto()
    _minimal_project(tmp_path)
    _approve_clearup_scope(tmp_path)
    _accepted_release(tmp_path)

    cr = tmp_path / "Backups/CrashRecovery"
    cr.mkdir(parents=True, exist_ok=True)
    zip_path = cr / "2026-09-05 12.15 CrashRecovery EnergieProject.zip"
    zip_path.write_bytes(b"verified-backup-fixture")
    sha = hashlib.sha256(zip_path.read_bytes()).hexdigest()
    stem = zip_path.with_suffix("")
    Path(str(stem) + ".sha256").write_text(f"{sha}  {zip_path.name}\n", encoding="utf-8")
    Path(str(stem) + ".manifest.json").write_text(json.dumps({"file_count": 5476}), encoding="utf-8")
    Path(str(stem) + ".restore.txt").write_text(
        "ENERGIEPROJECT CRASH RECOVERY\nNoodherstel: stop containers, pak ZIP uit en controleer de services.\n",
        encoding="utf-8",
    )
    state = tmp_path / "Data/03_Systeem/Projectmanager/State"
    state.mkdir(parents=True, exist_ok=True)
    (state / "crash_recovery_closure_20260904.json").write_text(json.dumps({
        "status": "GREEN_PRACTICAL_ACCEPTANCE_COMPLETE",
        "scope": ["EnergieProject", "NAS/Containers", "Home Assistant"],
        "evidence": {
            "EnergieProject": {"zip_integrity": "ok", "hash_failures": 0},
            "NAS_Containers": {"restore_extract": "ok", "production_containers_changed": False},
            "Home_Assistant": {"backup_manager_state_after_run": "idle"},
        },
    }), encoding="utf-8")

    gate = mod.clearup_auto_gate(tmp_path, app_version="32.4.25")
    assert gate["ready"] is True
    assert gate["crash_recovery"]["practical_acceptance"] is True


def test_32425_cr_gate_blocks_without_practical_acceptance_even_when_latest_zip_hash_is_valid(tmp_path: Path):
    mod = _load_clearup_auto()
    _minimal_project(tmp_path)
    _approve_clearup_scope(tmp_path)
    _accepted_release(tmp_path)
    _valid_cr_set(tmp_path)
    # Make the restore sidecar realistic: instructions, not a synthetic VALID marker.
    restore = next((tmp_path / "Backups/CrashRecovery").glob("*.restore.txt"))
    restore.write_text("Noodherstel: pak de ZIP uit en herstel de projectmap.\n", encoding="utf-8")

    gate = mod.clearup_auto_gate(tmp_path, app_version="32.4.25")
    assert gate["ready"] is False
    assert "crash_recovery_not_verified" in gate["blockers"]

def test_32425_main_wires_post_acceptance_clearup_worker():
    source = (APP / "main.py").read_text(encoding="utf-8")
    assert "from project_clearup_auto import run_approved_clearup_once" in source
    assert "def startup_project_clearup()" in source
    assert 'name="project-clearup-post-acceptance"' in source
    assert "run_approved_clearup_once(" in source
    assert "PROJECT_CLEARUP_STATE_PATH" in source



def test_32425_projectmanager_hygiene_import_works_with_only_pm_runtime_path(monkeypatch):
    """PM modules must be self-contained when HA puts only projectmanager_v2 on sys.path."""
    import subprocess
    pm = APP / "projectmanager_v2"
    code = f"""
import sys
from pathlib import Path
pm = Path({str(pm)!r})
app = Path({str(APP)!r})
sys.path[:] = [str(pm)] + [p for p in sys.path if p not in (str(app), str(pm))]
import energy_health_collector
print(energy_health_collector.project_hygiene_check.__name__)
"""
    completed = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    assert "project_hygiene_check" in completed.stdout
