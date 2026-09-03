import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"
PROBE = ROOT / "slimmemeterportal_import/rootfs/app/assistant_runtime_probe.py"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def reconciled_august_context():
    return {
        "months": [{
            "month": "2026_08",
            "quality": {
                "smp": {
                    "status": "incomplete",
                    "coverage_status": "error",
                    "days_expected": 62,
                    "days_covered": 10,
                    "errors": ["elektriciteit/2026-08-06: geen meetrecords"],
                },
                "boundary_bridge": {
                    "status": "ready",
                    "source": "smp_start_p1_end_boundary",
                    "grid_import_kwh": 193.83,
                    "grid_export_kwh": 507.498,
                    "gas_m3": 9.074,
                },
                "grid_import_source": "smp_start_p1_end_boundary",
                "grid_export_source": "smp_start_p1_end_boundary",
                "gas_source": "smp_start_p1_end_boundary",
                "smp_plausibility": {"status": "not_applicable", "errors": []},
                "measurement_period": {
                    "complete": True,
                    "source": "smp_start_p1_end_boundary",
                    "coverage_status": "full_calendar_month",
                },
            },
        }],
    }


def test_assistant_acceptance_accepts_reconciled_complete_august():
    m = load(PROBE, "v32329_probe")
    calls = {
        "health": {"http_status": 200, "json": {"status": "ready", "version": "32.3.38", "read_only": True}},
        "august_gas": {"http_status": 200, "json": {
            "resolved": {"month": "2026_08", "domains": ["gas"]},
            "quality": {"status": "COMPLETE", "source_quality": {
                "gas_source": "smp_start_p1_end_boundary",
                "grid_import_source": "smp_start_p1_end_boundary",
                "grid_export_source": "smp_start_p1_end_boundary",
                "boundary_bridge": {"status": "ready", "source": "smp_start_p1_end_boundary"},
                "measurement_period": {"complete": True, "source": "smp_start_p1_end_boundary"},
                "quarter_hour": {"available": False, "coverage_status": "not_applicable_closed_month"},
            }},
            "evidence": {"metrics": {"gas_m3": 9.074}, "sources": {"gas": "smp_start_p1_end_boundary"}},
        }},
        "previous_month": {"http_status": 200, "json": {"resolved": {"month": "2026_07", "domains": ["gas"]}, "evidence": {"metrics": {"gas_m3": 33.95}}}},
        "finance": {"http_status": 200, "json": {"quality": {"financial_claim": "MODELED_OR_PARTIAL_NOT_INVOICE_ACTUAL"}, "evidence": {"finance": {"contract_components_ready": True, "invoice_actuals_present": False, "invoice_actual_eur": None}}}},
        "apparatus": {"http_status": 200, "json": {"resolved": {"domains": ["apparatus"]}, "evidence": {"knowledge": {"matches": [{"source": "Knowledge_Base.md"}]}}}},
        "negative_path": {"http_status": 404, "json": None},
        "negative_payload": {"http_status": 400, "json": {"status": "error"}},
    }

    result = m.evaluate_assistant_runtime_acceptance(calls, expected_version="32.3.38")

    assert result["status"] == "PASS"
    assert result["voice_gate"] == "OPEN_FOR_NEXT_ACCEPTANCE_STEP"
    assert result["checks"]["august_reconciled_full_month"]["passed"] is True


def test_empty_usages_are_not_reported_as_ok_day():
    m = load(MAIN, "v32329_day_semantics")
    result = m.smp_day_summary_from_payload({"meter_identifier": "E1", "usages": []}, "elektriciteit", "2026-08-06")

    assert result["records"] == 0
    assert result["stored_records"] == 1
    assert result["status"] == "warning"
    assert result["reason"] == "empty_usages"


def test_nonempty_usages_keep_semantic_measurement_count():
    m = load(MAIN, "v32329_day_semantics_nonempty")
    result = m.smp_day_summary_from_payload({"usages": [{"delivery": 0.1}, {"delivery": 0.2}]}, "gas", "2026-08-01")

    assert result["records"] == 2
    assert result["stored_records"] == 1
    assert result["status"] == "ok"


def test_central_validation_ui_marks_smp_detail_incomplete_but_reconciled_month_complete():
    m = load(MAIN, "v32329_central_ui")
    state = {"last_central_validation": {
        "status": "error",
        "errors": ["SMP inhoudsdekking: elektriciteit/2026-08-06: geen meetrecords binnen verplichte dekkingsreeks."],
    }}

    snapshot = m.central_validation_ui_snapshot(state, reconciled_august_context())

    assert snapshot["status"] == "warning"
    assert "maandtotalen volledig" in snapshot["label"].lower()
    assert "smp-detail" in snapshot["detail"].lower()
    assert snapshot["quality_gate"]["measurement_period"]["complete"] is True


def test_stale_report_manifest_can_never_be_called_definitive(tmp_path):
    m = load(MAIN, "v32329_stale_report")
    pdf = tmp_path / "Energierapport_2026_08.pdf"
    recovery = tmp_path / "Recovery_Update_2026_08.zip"
    pdf.write_bytes(b"%PDF-current")
    recovery.write_bytes(b"PK-current")
    (tmp_path / "report_manifest.json").write_text(json.dumps({"version": "32.3.23", "month": "2026_08", "status": "completed"}), encoding="utf-8")
    state = {
        "report_output_last_status": "completed",
        "report_output_last_month": "2026_08",
        "report_output_last_files": [str(pdf), str(recovery)],
        "workflow_audit_last_status": "completed",
        "workflow_audit_last_month": "2026_08",
    }

    snapshot = m.report_output_ui_snapshot(state, reconciled_august_context())

    assert snapshot["is_definitive"] is False
    assert snapshot["status"] == "warning"
    assert snapshot["report_version"] == "32.3.23"
    assert "verouderd" in snapshot["text"].lower()


def test_current_report_manifest_can_be_definitive(tmp_path, monkeypatch):
    m = load(MAIN, "v32329_current_report")
    monkeypatch.setattr(m, "APP_VERSION", "32.3.38")
    pdf = tmp_path / "Energierapport_2026_08.pdf"
    recovery = tmp_path / "Recovery_Update_2026_08.zip"
    pdf.write_bytes(b"%PDF-current")
    recovery.write_bytes(b"PK-current")
    (tmp_path / "report_manifest.json").write_text(json.dumps({"version": "32.3.38", "month": "2026_08", "status": "completed"}), encoding="utf-8")
    state = {
        "report_output_last_status": "completed",
        "report_output_last_month": "2026_08",
        "report_output_last_files": [str(pdf), str(recovery)],
        "workflow_audit_last_status": "completed",
        "workflow_audit_last_month": "2026_08",
    }

    snapshot = m.report_output_ui_snapshot(state, reconciled_august_context())

    assert snapshot["is_definitive"] is True
    assert snapshot["report_version"] == "32.3.38"


def test_historical_report_readiness_accepts_reconciled_boundary_without_analysis(monkeypatch, tmp_path):
    m = load(MAIN, "v32329_rebuild_readiness")
    month = "2026_08"
    month_root = tmp_path / month
    month_root.mkdir()
    monkeypatch.setattr(m, "MONTH_INPUT_ROOT", tmp_path)
    monkeypatch.setattr(m, "expected_month_input_files", lambda options: [])
    monkeypatch.setattr(m, "_month_energy_metrics", lambda *args, **kwargs: {
        "metrics": {"grid_import_kwh": 193.83, "grid_export_kwh": 507.498, "gas_m3": 9.074},
        "quality": {
            "grid_import_source": "smp_start_p1_end_boundary",
            "grid_export_source": "smp_start_p1_end_boundary",
            "gas_source": "smp_start_p1_end_boundary",
            "smp_plausibility": {"status": "not_applicable", "errors": []},
            "measurement_period": {"complete": True, "source": "smp_start_p1_end_boundary"},
        },
    })

    result = m.report_input_readiness(month, object(), historical=True)

    assert result["status"] == "ready"
    assert result["measurement_period_complete"] is True
    assert result["energy_sources"]["gas"] == "smp_start_p1_end_boundary"
    assert not (month_root / "Analysis" / "energieanalyse_2026_08.json").exists()
