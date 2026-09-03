import importlib.util
import json
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
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def patch_common_health(m, monkeypatch, tmp_path, state):
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
    return output


def test_old_release_workflow_failure_is_not_current_health_error(monkeypatch, tmp_path):
    m = load_main("v32327_stale_workflow_health")
    state = {
        "api_test": {"status": "ok"},
        "full_workflow_last_month": "2026_08",
        "full_workflow_last_status": "error",
        "workflow_sources": {"slimmemeterportal": "ready", "homewizard": "ready"},
    }
    output = patch_common_health(m, monkeypatch, tmp_path, state)
    result_dir = output / "workflow_results" / "2026_08"
    result_dir.mkdir(parents=True)
    (result_dir / "workflow_result.json").write_text(json.dumps({
        "version": "32.3.23", "month": "2026_08", "status": "error",
        "failed_step": "Rapportgenerator koppelen",
    }), encoding="utf-8")

    monitoring = m.monitoring_snapshot(runtime_options(), force=True, trigger="test")
    health = m.health_dashboard(runtime_options())

    workflow_monitor = next(item for item in monitoring["checks"] if item["name"] == "Workflow")
    workflow_health = next(item for item in health["checks"] if item["name"] == "Laatste workflow")
    assert workflow_monitor["status"] == "ok"
    assert monitoring["active_errors"] == 0
    assert "histor" in workflow_monitor["detail"].lower()
    assert workflow_health["status"] == "ok"
    assert "32.3.23" in workflow_health["detail"]


def test_top_last_run_marks_old_release_failure_as_historical(monkeypatch, tmp_path):
    m = load_main("v32327_last_run_semantics")
    output = tmp_path / "output"
    result_dir = output / "workflow_results" / "2026_08"
    result_dir.mkdir(parents=True)
    (result_dir / "workflow_result.json").write_text(json.dumps({
        "version": "32.3.23", "month": "2026_08", "status": "error",
    }), encoding="utf-8")
    monkeypatch.setattr(m, "OUTPUT_ROOT", output)

    snapshot_fn = getattr(m, "workflow_ui_snapshot", None)
    if snapshot_fn is None:
        snapshot = {"display_status": "error", "display_label": "error", "historical": False}
    else:
        snapshot = snapshot_fn({
            "full_workflow_last_month": "2026_08",
            "full_workflow_last_status": "error",
        })

    assert snapshot["historical"] is True
    assert snapshot["display_status"] == "stale"
    assert "historische fout" in snapshot["display_label"].lower()


def blocked_analysis_context():
    return {
        "months": [{
            "month": "2026_08",
            "quality": {
                "smp_plausibility": {"status": "error", "errors": ["SMP lager dan P1-deelperiode"]},
                "measurement_period": {"complete": False, "coverage_status": "partial_source_coverage"},
            },
        }],
    }


def test_central_validation_ui_distinguishes_technical_ok_from_blocked_month_data():
    m = load_main("v32327_central_validation_semantics")
    fn = getattr(m, "central_validation_ui_snapshot", None)
    if fn is None:
        snapshot = {"status": "ok", "label": "ok", "detail": ""}
    else:
        snapshot = fn({"last_central_validation": {"status": "ok"}}, blocked_analysis_context())

    assert snapshot["status"] == "warning"
    assert "technisch ok" in snapshot["label"].lower()
    assert "plausibil" in snapshot["detail"].lower()


def test_existing_output_is_not_called_definitive_when_quality_or_audit_is_blocked(tmp_path):
    m = load_main("v32327_output_semantics_blocked")
    pdf = tmp_path / "Energierapport_2026_08.pdf"
    rec = tmp_path / "Recovery_Update_2026_08.zip"
    pdf.write_bytes(b"%PDF-test")
    rec.write_bytes(b"PKtest")
    state = {
        "report_output_last_status": "completed",
        "report_output_last_month": "2026_08",
        "report_output_last_files": [str(pdf), str(rec)],
        "workflow_audit_last_status": "failed",
        "workflow_audit_last_month": "2026_08",
    }
    fn = getattr(m, "report_output_ui_snapshot", None)
    if fn is None:
        snapshot = {"is_definitive": True, "label": "Definitieve output", "text": "2026_08: 2 bestand(en)"}
    else:
        snapshot = fn(state, blocked_analysis_context())

    assert snapshot["is_definitive"] is False
    assert "bestaande output" in snapshot["label"].lower()
    assert "niet definitief" in snapshot["text"].lower()


def test_output_can_be_called_definitive_only_after_audit_and_full_quality(tmp_path):
    m = load_main("v32327_output_semantics_valid")
    pdf = tmp_path / "Energierapport_2026_08.pdf"
    rec = tmp_path / "Recovery_Update_2026_08.zip"
    pdf.write_bytes(b"%PDF-test")
    rec.write_bytes(b"PKtest")
    (tmp_path / "report_manifest.json").write_text(
        json.dumps({"version": m.APP_VERSION, "month": "2026_08", "status": "completed"}),
        encoding="utf-8",
    )
    state = {
        "report_output_last_status": "completed",
        "report_output_last_month": "2026_08",
        "report_output_last_files": [str(pdf), str(rec)],
        "workflow_audit_last_status": "completed",
        "workflow_audit_last_month": "2026_08",
    }
    context = {"months": [{"month": "2026_08", "quality": {
        "smp_plausibility": {"status": "ok", "errors": []},
        "measurement_period": {"complete": True, "coverage_status": "full_calendar_month"},
    }}]}
    fn = getattr(m, "report_output_ui_snapshot", None)
    if fn is None:
        snapshot = {"is_definitive": False, "label": "Bestaande output", "text": "niet definitief"}
    else:
        snapshot = fn(state, context)

    assert snapshot["is_definitive"] is True
    assert "definitieve output" in snapshot["label"].lower()


def test_current_release_workflow_failure_still_counts_as_active_error(monkeypatch, tmp_path):
    m = load_main("v32327_current_workflow_error")
    state = {
        "api_test": {"status": "ok"},
        "full_workflow_last_month": "2026_08",
        "full_workflow_last_status": "error",
        "workflow_sources": {"slimmemeterportal": "ready", "homewizard": "ready"},
    }
    output = patch_common_health(m, monkeypatch, tmp_path, state)
    result_dir = output / "workflow_results" / "2026_08"
    result_dir.mkdir(parents=True)
    (result_dir / "workflow_result.json").write_text(json.dumps({
        "version": m.APP_VERSION, "month": "2026_08", "status": "error",
    }), encoding="utf-8")

    monitoring = m.monitoring_snapshot(runtime_options(), force=True, trigger="test")
    workflow_monitor = next(item for item in monitoring["checks"] if item["name"] == "Workflow")

    assert workflow_monitor["status"] == "warning"
    assert monitoring["active_errors"] >= 1


def test_report_output_without_explicit_full_measurement_quality_is_not_definitive(tmp_path):
    m = load_main("v32327_output_requires_quality_evidence")
    pdf = tmp_path / "Energierapport_2026_08.pdf"
    rec = tmp_path / "Recovery_Update_2026_08.zip"
    pdf.write_bytes(b"%PDF-test")
    rec.write_bytes(b"PKtest")
    state = {
        "report_output_last_status": "completed",
        "report_output_last_month": "2026_08",
        "report_output_last_files": [str(pdf), str(rec)],
        "workflow_audit_last_status": "completed",
        "workflow_audit_last_month": "2026_08",
    }

    snapshot = m.report_output_ui_snapshot(state, {"months": []})

    assert snapshot["is_definitive"] is False
