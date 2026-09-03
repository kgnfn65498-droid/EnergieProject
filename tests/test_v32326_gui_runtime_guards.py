import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"


def load_main(name: str):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def runtime_options(**overrides):
    values = {
        "homewizard_enabled": True,
        "enphase_enabled": False,
        "epex_electricity_enabled": False,
        "epex_gas_enabled": False,
        "automatic_month_close_enabled": True,
        "epex_electricity_enabled": False,
        "epex_gas_enabled": False,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def patch_runtime_health(m, monkeypatch, tmp_path):
    state = {
        "api_test": {"status": "ok"},
        "full_workflow_last_status": "completed",
        "workflow_sources": {
            "slimmemeterportal": "ready",
            "homewizard": "ready",
            "enphase": "not_configured",
            "epex_electricity": "not_configured",
            "epex_gas": "not_configured",
        },
    }
    monkeypatch.setattr(m, "load_state", lambda: state)
    monkeypatch.setattr(m, "validate_production_certificate", lambda: {
        "valid": True,
        "status": "valid",
        "production_core_revision": m.PRODUCTION_CORE_REVISION,
        "integrity": "ok",
        "version": "9.9.0",
        "certificate": {"version": "9.9.0", "production_core_revision": m.PRODUCTION_CORE_REVISION},
    })
    monkeypatch.setattr(m, "validate_audit_trail", lambda: {"valid": True, "status": "ok", "records": 3})
    monkeypatch.setattr(m, "read_recovery_status", lambda: {"status": "ok"})
    monkeypatch.setattr(m, "MONITORING_STATE_PATH", tmp_path / "monitoring_state.json")
    monkeypatch.setattr(m, "MONITORING_HISTORY_PATH", tmp_path / "monitoring_history.jsonl")
    generators = tmp_path / "generators"
    generators.mkdir(exist_ok=True)
    monkeypatch.setattr(m, "BUNDLED_REPORT_GENERATORS", generators)
    output = tmp_path / "output"
    output.mkdir(exist_ok=True)
    monkeypatch.setattr(m, "OUTPUT_ROOT", output)
    return state


def test_gui_refresh_uses_backend_scheduler_state_and_production_core_revision():
    source = MAIN.read_text(encoding="utf-8")

    assert "autoEnabled.checked=Boolean(auto.enabled)" in source
    assert "op.production_core_revision" in source
    assert "String(test.production_core_revision||'')===String(op.production_core_revision||'')" in source
    assert "String(acceptance.production_core_revision||'')===String(op.production_core_revision||'')" in source


def test_monitoring_ignores_disabled_optional_sources(monkeypatch, tmp_path):
    m = load_main("v32326_monitoring_optional_sources")
    patch_runtime_health(m, monkeypatch, tmp_path)

    result = m.monitoring_snapshot(runtime_options(), force=True, trigger="test")
    source_check = next(item for item in result["checks"] if item["name"] == "Bronnen")

    assert source_check["status"] == "ok"
    assert result["active_errors"] == 0
    assert "not_configured" not in source_check["detail"]


def test_health_dashboard_does_not_penalize_disabled_optional_sources(monkeypatch, tmp_path):
    m = load_main("v32326_health_optional_sources")
    patch_runtime_health(m, monkeypatch, tmp_path)

    result = m.health_dashboard(runtime_options())
    source_check = next(item for item in result["checks"] if item["name"] == "Bronstatus")

    assert source_check["status"] == "ok"
    assert "not_configured" not in source_check["detail"]
    assert result["score"] == 100


def write_partial_p1(folder: Path):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "P1e.csv").write_text(
        "captured_at,total_power_import_kwh,total_power_export_kwh\n"
        "2026-08-06T00:15:00+02:00,100,200\n"
        "2026-08-31T23:45:00+02:00,265.33,600.47\n",
        encoding="utf-8",
    )
    (folder / "P1g.csv").write_text(
        "captured_at,total_gas_m3\n"
        "2026-08-06T00:15:00+02:00,500\n"
        "2026-08-31T23:45:00+02:00,507.63\n",
        encoding="utf-8",
    )


def low_smp_month():
    return {
        "status": "ready",
        "coverage_status": "ok",
        "grid_import_kwh": 25.73,
        "grid_export_kwh": 94.09,
        "gas_m3": 1.37,
        "days_expected": 62,
        "days_covered": 62,
        "errors": [],
    }


def test_full_month_smp_is_rejected_when_lower_than_overlapping_partial_p1(monkeypatch, tmp_path):
    m = load_main("v32326_smp_plausibility")
    month = "2026_08"
    folder = tmp_path / month
    write_partial_p1(folder)
    monkeypatch.setattr(m, "load_smp_month_metrics", lambda key: low_smp_month())
    monkeypatch.setattr(m, "_epex_month_context", lambda key: {"source": "test"})

    result = m._month_energy_metrics(month, input_folder=folder)

    assert result["quality"]["smp_plausibility"]["status"] == "error"
    assert result["quality"]["grid_import_source"] == "p1"
    assert result["quality"]["grid_export_source"] == "p1"
    assert result["quality"]["gas_source"] == "p1g"
    assert result["quality"]["measurement_period"]["complete"] is False
    assert result["quality"]["smp"]["status"] == "implausible"


def test_historical_report_readiness_blocks_implausible_smp_instead_of_accepting_partial_p1(monkeypatch, tmp_path):
    m = load_main("v32326_historical_plausibility_gate")
    month = "2026_08"
    month_root = tmp_path / month
    write_partial_p1(month_root)
    monkeypatch.setattr(m, "MONTH_INPUT_ROOT", tmp_path)
    monkeypatch.setattr(m, "load_smp_month_metrics", lambda key: low_smp_month())
    monkeypatch.setattr(m, "_epex_month_context", lambda key: {"source": "test"})
    options = runtime_options()

    result = m.report_input_readiness(month, options, historical=True)

    assert result["status"] == "incomplete"
    assert result["plausibility_status"] == "error"
    assert result["measurement_period_complete"] is False
