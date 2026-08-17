import importlib.util
import json
import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"
REPORT_GENERATORS = ROOT / "slimmemeterportal_import/rootfs/app/report_generators"


def load_main(name: str):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_smp_month(root: pathlib.Path, *, month_key="2026_07", complete=True):
    year = int(month_key[:4])
    month = int(month_key[5:7])
    import calendar

    days = calendar.monthrange(year, month)[1]
    smp = root / "Data" / "01_Input" / month_key / "SlimmeMeterPortal"
    raw = smp / "raw"
    raw.mkdir(parents=True)
    coverage = {
        "status": "ok" if complete else "partial_current_month",
        "month": month_key,
        "calendar_expected_through": f"{year:04d}-{month:02d}-{days:02d}",
        "available_through": f"{year:04d}-{month:02d}-{days if complete else days - 1:02d}",
        "days_expected": days * 2,
        "days_with_measurements": days * 2 if complete else (days * 2 - 2),
        "empty_days": [],
        "missing_days": [] if complete else [f"elektriciteit/meter/{year:04d}-{month:02d}-{days:02d}"],
        "errors": [],
        "warnings": [],
    }
    (smp / "content_coverage_report.json").write_text(json.dumps(coverage), encoding="utf-8")
    (smp / "connections.json").write_text(
        json.dumps([
            {"connection_type": "elektriciteit", "meter_identifier": "meter_e"},
            {"connection_type": "gas", "meter_identifier": "meter_g"},
        ]),
        encoding="utf-8",
    )
    for day in range(1, days + 1):
        date = f"{year:04d}-{month:02d}-{day:02d}"
        electricity = {
            "usages": [{
                "delivery": 1.0,
                "delivery_high": 0.6,
                "delivery_low": 0.4,
                "returned_delivery": 0.5,
                "returned_delivery_high": 0.3,
                "returned_delivery_low": 0.2,
            }]
        }
        gas = {"usages": [{"delivery": 0.2}]}
        (raw / f"elektriciteit_meter_e_{date}.json").write_text(json.dumps(electricity), encoding="utf-8")
        (raw / f"gas_meter_g_{date}.json").write_text(json.dumps(gas), encoding="utf-8")
    return smp


def write_p1_month(folder: pathlib.Path):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "P1e.csv").write_text(
        "total_power_import_kwh,total_power_export_kwh\n100,20\n110,22\n",
        encoding="utf-8",
    )
    (folder / "P1g.csv").write_text(
        "total_gas_m3\n50\n53\n",
        encoding="utf-8",
    )
    (folder / "month_input_validation.json").write_text(
        json.dumps({"status": "ok", "missing_required": [], "empty_required": []}),
        encoding="utf-8",
    )


def minimal_options():
    return SimpleNamespace(
        epex_electricity_enabled=False,
        epex_gas_enabled=False,
        month_input_require_homewizard=True,
        month_input_require_enphase=True,
        month_input_require_nordpool=True,
        report_service_root="Energie_Rapportservice",
        transfer_share_folder="Energie_Overdracht",
    )


def test_complete_smp_only_july_resolves_month_metrics_without_double_counting(monkeypatch, tmp_path):
    m = load_main("smp_fallback_complete")
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")
    monkeypatch.setattr(m, "OUTPUT_ROOT", tmp_path / "config_output")
    write_smp_month(tmp_path)

    result = m.load_smp_month_metrics("2026_07")

    assert result["status"] == "ready"
    assert result["source"] == "SlimmeMeterPortal"
    assert result["grid_import_kwh"] == 31.0
    assert result["grid_export_kwh"] == 15.5
    assert result["gas_m3"] == 6.2
    assert result["days_expected"] == 62
    assert result["days_covered"] == 62


def test_partial_smp_closed_month_is_rejected(monkeypatch, tmp_path):
    m = load_main("smp_fallback_partial")
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")
    monkeypatch.setattr(m, "OUTPUT_ROOT", tmp_path / "config_output")
    write_smp_month(tmp_path, complete=False)

    result = m.load_smp_month_metrics("2026_07")

    assert result["status"] == "incomplete"
    assert result["grid_import_kwh"] is None
    assert result["grid_export_kwh"] is None
    assert result["gas_m3"] is None


def test_analysis_uses_smp_when_p1_missing(monkeypatch, tmp_path):
    m = load_main("smp_analysis_fallback")
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")
    monkeypatch.setattr(m, "OUTPUT_ROOT", tmp_path / "config_output")
    monkeypatch.setattr(m, "MONTH_INPUT_ROOT", tmp_path / "month_input")
    monkeypatch.setattr(m, "EPEX_HISTORY_ROOT", None)
    monkeypatch.setattr(m, "_epex_mcp_month_context", lambda month_key: None)
    write_smp_month(tmp_path)

    result = m._month_energy_metrics("2026_07")

    assert result["metrics"]["grid_import_kwh"] == 31.0
    assert result["metrics"]["grid_export_kwh"] == 15.5
    assert result["metrics"]["gas_m3"] == 6.2
    assert "SlimmeMeterPortal" in result["quality"]["available_sources"]
    assert result["quality"]["grid_import_source"] == "slimmemeterportal_fallback"
    assert result["quality"]["grid_export_source"] == "slimmemeterportal_fallback"
    assert result["quality"]["gas_source"] == "slimmemeterportal_fallback"


def test_valid_p1_wins_over_complete_smp_without_summing(monkeypatch, tmp_path):
    m = load_main("smp_analysis_p1_wins")
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")
    monkeypatch.setattr(m, "OUTPUT_ROOT", tmp_path / "config_output")
    monkeypatch.setattr(m, "MONTH_INPUT_ROOT", tmp_path / "month_input")
    monkeypatch.setattr(m, "EPEX_HISTORY_ROOT", None)
    monkeypatch.setattr(m, "_epex_mcp_month_context", lambda month_key: None)
    write_smp_month(tmp_path)
    write_p1_month(tmp_path / "month_input" / "2026_07")

    result = m._month_energy_metrics("2026_07")

    assert result["metrics"]["grid_import_kwh"] == 10.0
    assert result["metrics"]["grid_export_kwh"] == 2.0
    assert result["metrics"]["gas_m3"] == 3.0
    assert result["quality"]["grid_import_source"] == "p1"
    assert result["quality"]["grid_export_source"] == "p1"
    assert result["quality"]["gas_source"] == "p1g"


def test_historical_report_readiness_accepts_complete_smp_core(monkeypatch, tmp_path):
    m = load_main("smp_historical_readiness")
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")
    monkeypatch.setattr(m, "OUTPUT_ROOT", tmp_path / "config_output")
    monkeypatch.setattr(m, "MONTH_INPUT_ROOT", tmp_path / "month_input")
    monkeypatch.setattr(m, "EPEX_HISTORY_ROOT", None)
    monkeypatch.setattr(m, "_epex_mcp_month_context", lambda month_key: None)
    write_smp_month(tmp_path)

    result = m.report_input_readiness("2026_07", minimal_options(), historical=True)

    assert result["status"] == "ready"
    assert result["core_metrics"]["grid_import_kwh"] == 31.0
    assert result["core_metrics"]["grid_export_kwh"] == 15.5
    assert result["core_metrics"]["gas_m3"] == 6.2


def test_report_adapter_uses_same_smp_totals_as_analysis(monkeypatch, tmp_path):
    m = load_main("smp_report_adapter")
    monkeypatch.setattr(m, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")
    monkeypatch.setattr(m, "OUTPUT_ROOT", tmp_path / "config_output")
    monkeypatch.setattr(m, "MONTH_INPUT_ROOT", tmp_path / "month_input")
    monkeypatch.setattr(m, "EPEX_HISTORY_ROOT", None)
    monkeypatch.setattr(m, "_epex_mcp_month_context", lambda month_key: None)
    monkeypatch.setattr(m, "BUNDLED_REPORT_GENERATORS", REPORT_GENERATORS)
    service_root = tmp_path / "report_service"
    monkeypatch.setattr(m, "report_service_paths", lambda options: {
        "root": service_root,
        "generators": service_root / "generators",
        "work": service_root / "work",
        "output": service_root / "output",
        "logs": service_root / "logs",
    })
    write_smp_month(tmp_path)
    input_folder = tmp_path / "month_input" / "2026_07"
    input_folder.mkdir(parents=True)

    analysis = m._month_energy_metrics("2026_07")
    adapter = m.build_report_adapter_data(minimal_options(), {
        "month": "2026_07",
        "input_folder": str(input_folder),
    })

    assert adapter["measurements"]["import_kwh"] == analysis["metrics"]["grid_import_kwh"]
    assert adapter["measurements"]["export_kwh"] == analysis["metrics"]["grid_export_kwh"]
    assert adapter["measurements"]["gas_m3"] == analysis["metrics"]["gas_m3"]
    assert adapter["energy_sources"]["grid_import"] == "slimmemeterportal_fallback"


def test_durable_publication_replaces_only_exact_month_after_validation(monkeypatch, tmp_path):
    m = load_main("smp_durable_publish")
    monkeypatch.setattr(m, "STATE_PATH", tmp_path / "state.json")
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")
    output = tmp_path / "service_output"
    output.mkdir()
    (output / "Energierapport_2026_07.pdf").write_bytes(b"pdf-july")
    (output / "Recovery_Update_2026_07.zip").write_bytes(b"zip-july")
    august = tmp_path / "Data" / "02_Output" / "Rapportages" / "2026_08"
    august.mkdir(parents=True)
    (august / "keep.txt").write_text("keep", encoding="utf-8")

    result = m.publish_durable_report_package({
        "month": "2026_07",
        "output_contract": {
            "report_pdf": "Energierapport_2026_07.pdf",
            "recovery_update_zip": "Recovery_Update_2026_07.zip",
        },
    }, output)

    july = tmp_path / "Data" / "02_Output" / "Rapportages" / "2026_07"
    assert result["status"] == "completed"
    assert (july / "Energierapport_2026_07.pdf").read_bytes() == b"pdf-july"
    assert (july / "Recovery_Update_2026_07.zip").read_bytes() == b"zip-july"
    assert (july / "report_manifest.json").is_file()
    assert (august / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_failed_durable_publication_keeps_existing_month_untouched(monkeypatch, tmp_path):
    m = load_main("smp_durable_publish_failure")
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")
    output = tmp_path / "service_output"
    output.mkdir()
    (output / "Energierapport_2026_07.pdf").write_bytes(b"new-pdf")
    july = tmp_path / "Data" / "02_Output" / "Rapportages" / "2026_07"
    july.mkdir(parents=True)
    (july / "keep.txt").write_text("old-package", encoding="utf-8")

    result = m.publish_durable_report_package({
        "month": "2026_07",
        "output_contract": {
            "report_pdf": "Energierapport_2026_07.pdf",
            "recovery_update_zip": "Recovery_Update_2026_07.zip",
        },
    }, output)

    assert result["status"] == "failed"
    assert (july / "keep.txt").read_text(encoding="utf-8") == "old-package"
    assert not (july / "Energierapport_2026_07.pdf").exists()


def test_validate_report_input_files_accepts_historical_smp_core(monkeypatch, tmp_path):
    m = load_main("smp_validate_historical_input")
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")
    monkeypatch.setattr(m, "OUTPUT_ROOT", tmp_path / "config_output")
    monkeypatch.setattr(m, "MONTH_INPUT_ROOT", tmp_path / "month_input")
    monkeypatch.setattr(m, "EPEX_HISTORY_ROOT", None)
    monkeypatch.setattr(m, "_epex_mcp_month_context", lambda month_key: None)
    write_smp_month(tmp_path)
    input_folder = tmp_path / "month_input" / "2026_07"
    input_folder.mkdir(parents=True)

    result = m.validate_report_input_files(
        input_folder,
        month_key="2026_07",
        historical=True,
    )

    assert result["status"] == "ok"
    assert result["missing"] == []
    assert result["core_metrics"]["grid_import_kwh"] == 31.0


def test_targeted_historical_report_rebuild_does_not_run_month_workflow(monkeypatch, tmp_path):
    m = load_main("smp_targeted_rebuild")
    monkeypatch.setattr(m, "MONTH_INPUT_ROOT", tmp_path / "month_input")
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")
    input_folder = tmp_path / "month_input" / "2026_07"
    input_folder.mkdir(parents=True)
    transfer = tmp_path / "Data" / "01_Input" / "2026_07"
    transfer.mkdir(parents=True)
    central = transfer / "SlimmeMeterPortal" / "central_validation.json"
    central.parent.mkdir(parents=True)
    central.write_text('{"status":"ok"}', encoding="utf-8")

    monkeypatch.setattr(m, "historical_month_allowed", lambda value: "2026_07")
    monkeypatch.setattr(m, "Options", SimpleNamespace(load=lambda: minimal_options()))
    monkeypatch.setattr(m, "report_input_readiness", lambda month, options, historical=False: {
        "status": "ready",
        "historical": historical,
        "core_metrics": {"grid_import_kwh": 1.0, "grid_export_kwh": 2.0, "gas_m3": 3.0},
    })
    monkeypatch.setattr(m, "create_report_handoff", lambda *args, **kwargs: {"request": str(transfer / "report_request.json")})
    monkeypatch.setattr(m, "run_report_generation_from_handoff", lambda options, request: {
        "status": "completed", "month": "2026_07", "request": str(request)
    })
    monkeypatch.setattr(m, "run_full_month_workflow", lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("month workflow must not run")))
    monkeypatch.setattr(m, "update_state", lambda **kwargs: None)

    result = m.rebuild_historical_report("2026_07")

    assert result["status"] == "completed"
    assert result["month"] == "2026_07"
    assert result["targeted_rebuild"] is True


def test_local_report_service_requires_durable_rapportages_publication(monkeypatch, tmp_path):
    m = load_main("smp_local_report_durable")
    service_root = tmp_path / "service"
    paths = {
        "root": service_root,
        "generators": service_root / "generators",
        "work": service_root / "work",
        "output": service_root / "output",
        "logs": service_root / "logs",
    }
    monkeypatch.setattr(m, "report_service_paths", lambda options: paths)
    monkeypatch.setattr(m, "discover_report_generators", lambda options: {
        "status": "ready",
        "generators": {
            "page_1": {"path": "p1.py", "name": "p1"},
            "page_2": {"path": "p2.py", "name": "p2"},
            "pages_3_13": {"path": "p3.py", "name": "p3"},
        },
    })
    monkeypatch.setattr(m, "build_report_adapter_data", lambda options, handoff: {"status": "completed"})
    monkeypatch.setattr(m, "update_state", lambda **kwargs: None)
    monkeypatch.setattr(m, "write_atomic_json", lambda path, value: None)
    handoff = {
        "month": "2026_07",
        "input_folder": str(tmp_path / "input"),
        "output_contract": {
            "report_pdf": "Energierapport_2026_07.pdf",
            "recovery_update_zip": "Recovery_Update_2026_07.zip",
        },
    }
    pathlib.Path(handoff["input_folder"]).mkdir()

    class Completed:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, **kwargs):
        work = paths["work"] / "2026_07"
        work.mkdir(parents=True, exist_ok=True)
        (work / "Energierapport_Pagina1_2026_07.pdf").write_bytes(b"page1")
        return Completed()

    monkeypatch.setattr(m.subprocess, "run", fake_run)

    def fake_merge(handoff_value, work_folder):
        (work_folder / "Energierapport_2026_07.pdf").write_bytes(b"final")
        return {"status": "completed"}

    def fake_recovery(options, handoff_value, work_folder):
        (work_folder / "Recovery_Update_2026_07.zip").write_bytes(b"recovery")
        return {"status": "completed"}

    monkeypatch.setattr(m, "merge_report_pdfs", fake_merge)
    monkeypatch.setattr(m, "create_recovery_update", fake_recovery)
    monkeypatch.setattr(m, "validate_report_outputs", lambda handoff_value, output: {"status": "ok", "errors": []})
    monkeypatch.setattr(m, "publish_month_output", lambda handoff_value, work: {"status": "completed", "errors": []})
    calls = []
    monkeypatch.setattr(m, "publish_durable_report_package", lambda handoff_value, output: calls.append((handoff_value, output)) or {"status": "completed", "errors": []})
    options = SimpleNamespace(report_service_timeout_seconds=60)

    result = m.execute_local_report_service(options, "request.json", handoff)

    assert result["status"] == "completed"
    assert len(calls) == 1
    assert calls[0][1] == paths["output"] / "2026_07"
    assert result["durable_publication"]["status"] == "completed"


def test_gui_exposes_targeted_historical_report_rebuild_action():
    source = MAIN.read_text(encoding="utf-8")
    assert 'action="rebuild-historical-report"' in source
    assert 'path.endswith("/rebuild-historical-report")' in source


def test_gas_falls_back_to_documented_delivery_reading_delta(monkeypatch, tmp_path):
    m = load_main("smp_gas_documented_reading_fallback")
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")
    monkeypatch.setattr(m, "OUTPUT_ROOT", tmp_path / "config_output")
    smp = write_smp_month(tmp_path)
    raw = smp / "raw"
    gas_files = sorted(raw.glob("gas_*.json"))
    for index, path in enumerate(gas_files):
        reading = 100.0 + (6.2 * index / (len(gas_files) - 1))
        path.write_text(
            json.dumps({"usages": [{"delivery_reading_combined": reading}]}),
            encoding="utf-8",
        )

    result = m.load_smp_month_metrics("2026_07")

    assert result["status"] == "ready"
    assert round(result["gas_m3"], 6) == 6.2
