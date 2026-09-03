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


def test_historical_report_audit_uses_current_handoff_validation_not_stale_workflow_state(monkeypatch, tmp_path):
    m = load_main("v32324_audit_current_validation")
    month = "2026_08"
    input_folder = tmp_path / "input" / month
    input_folder.mkdir(parents=True)

    output_folder = tmp_path / "output" / month
    output_folder.mkdir(parents=True)
    pdf = output_folder / f"Energierapport_{month}.pdf"
    recovery = output_folder / f"Recovery_Update_{month}.zip"
    pdf.write_bytes(b"%PDF-current-rerender")
    recovery.write_bytes(b"PK-current-rerender")

    stale_state = {
        "last_central_validation": {
            "status": "error",
            "source": "legacy_full_workflow",
            "errors": ["oude centrale validatiefout"],
        },
        "report_runtime_last_status": "ok",
        "report_runtime_modules": ["reportlab"],
        "report_generators_install_status": "completed",
        "report_service_generators": ["page_1", "page_2", "pages_3_13"],
        "report_adapter_last_status": "completed",
        "report_adapter_last_files": ["adapter.json"],
        "report_merge_last_status": "completed",
        "report_merge_last_output": str(pdf),
        "report_output_last_status": "completed",
        "report_output_last_files": [str(pdf), str(recovery)],
    }
    monkeypatch.setattr(m, "load_state", lambda: stale_state)
    monkeypatch.setattr(m, "update_state", lambda **kwargs: None)
    monkeypatch.setattr(m, "validate_report_input_files", lambda *args, **kwargs: {"status": "ok"})
    monkeypatch.setattr(m, "validate_report_handoff_files", lambda handoff: {"status": "ok", "errors": []})
    monkeypatch.setattr(m, "execute_local_report_service", lambda *args, **kwargs: {"status": "completed", "error": None})
    monkeypatch.setattr(m, "cleanup_report_service_history", lambda options: {"status": "completed"})
    monkeypatch.setattr(m, "build_compact_workflow_summary", lambda month_key: {"status": "completed", "month": month_key})

    current_validation = {
        "status": "ok",
        "source": "historical_rerender_readiness",
        "month": month,
    }
    handoff = {
        "month": month,
        "input_folder": str(input_folder),
        "central_validation": current_validation,
    }
    monkeypatch.setattr(m, "load_report_handoff", lambda path: dict(handoff))

    options = SimpleNamespace(report_service_enabled=True, report_trigger_enabled=False)
    result = m.run_report_generation_from_handoff(options, tmp_path / "report_request.json")

    assert result["status"] == "completed"
    assert result["audit"]["status"] == "completed"
    central = next(check for check in result["audit"]["checks"] if check["name"] == "central_validation")
    assert central["status"] == "ok"
    assert central["detail"] == current_validation


def test_rebuild_historical_report_builds_fresh_validation_instead_of_reusing_legacy_file(monkeypatch, tmp_path):
    m = load_main("v32324_fresh_historical_validation")
    month = "2026_08"
    runtime_input = tmp_path / "runtime" / month
    canonical_input = tmp_path / "Data" / "01_Input" / month
    runtime_input.mkdir(parents=True)
    canonical_input.mkdir(parents=True)
    (runtime_input / "P1e.csv").write_text("partial-control-source\n", encoding="utf-8")
    (canonical_input / "canonical.json").write_text('{"closed": true}', encoding="utf-8")

    legacy_smp = canonical_input / "HomeAssistant" / "SlimmeMeterPortal"
    legacy_smp.mkdir(parents=True)
    (legacy_smp / "central_validation.json").write_text(
        json.dumps({"status": "error", "source": "legacy_full_workflow", "errors": ["oude fout"]}),
        encoding="utf-8",
    )

    service_root = tmp_path / "report_service"
    service_paths = {
        "root": service_root,
        "generators": service_root / "generators",
        "work": service_root / "work",
        "output": service_root / "output",
        "logs": service_root / "logs",
    }
    for path in service_paths.values():
        path.mkdir(parents=True, exist_ok=True)

    readiness = {
        "status": "ready",
        "historical": True,
        "core_metrics": {"grid_import_kwh": 180.0, "grid_export_kwh": 300.0, "gas_m3": 9.0},
        "missing_core_metrics": [],
        "energy_sources": {
            "grid_import": "SlimmeMeterPortal",
            "grid_export": "SlimmeMeterPortal",
            "gas": "SlimmeMeterPortal",
        },
    }

    monkeypatch.setattr(m, "MONTH_INPUT_ROOT", runtime_input.parent)
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")
    monkeypatch.setattr(m, "report_service_paths", lambda options: service_paths)
    monkeypatch.setattr(m, "Options", SimpleNamespace(load=lambda: SimpleNamespace()))
    monkeypatch.setattr(m, "report_input_readiness", lambda month_key, options, historical=False: dict(readiness))
    monkeypatch.setattr(m, "_smp_source_candidates", lambda month_key: [legacy_smp])
    monkeypatch.setattr(m, "update_state", lambda **kwargs: None)

    observed = {}

    def fake_generation(options, request_path):
        request = json.loads(Path(request_path).read_text(encoding="utf-8"))
        observed["central_validation"] = request["central_validation"]
        return {"status": "completed", "month": month}

    monkeypatch.setattr(m, "run_report_generation_from_handoff", fake_generation)

    result = m.rebuild_historical_report(month)

    validation = observed["central_validation"]
    assert validation["status"] == "ok"
    assert validation["source"] == "historical_rerender_readiness"
    assert validation["month"] == month
    assert validation["readiness"]["core_metrics"] == readiness["core_metrics"]
    assert result["status"] == "completed"
