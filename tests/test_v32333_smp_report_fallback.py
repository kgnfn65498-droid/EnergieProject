from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
MAIN = APP / "main.py"


def load_main():
    spec = importlib.util.spec_from_file_location("main_v32333_smp_fallback", MAIN)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_page13_uses_resolved_smp_quality_when_coverage_report_is_missing(monkeypatch, tmp_path):
    m = load_main()
    service = tmp_path / "service"
    input_folder = tmp_path / "input" / "2026_08"
    input_folder.mkdir(parents=True)
    (input_folder / "Enphase.csv").write_text(
        "captured_at,entity_id,friendly_name,value,unit,device_class,state_class,last_updated\n"
        "2026-08-06T16:00:56.681534+02:00,sensor.envoy,Envoy,7372.792,kWh,energy,total_increasing,2026-08-06T13:56:58+00:00\n"
        "2026-08-31T23:48:28.852271+02:00,sensor.envoy,Envoy,7594.335,kWh,energy,total_increasing,2026-08-31T21:41:05+00:00\n",
        encoding="utf-8",
    )
    # Intentionally NO HomeAssistant/SlimmeMeterPortal/content_coverage_report.json.
    # This mirrors the live .32 situation: the resolved analysis quality already
    # knows the semantic SMP coverage and must be sufficient for page 13.

    monkeypatch.setattr(m, "BUNDLED_REPORT_GENERATORS", APP / "report_generators")
    monkeypatch.setattr(m, "report_service_paths", lambda _options: {
        "root": service,
        "generators": service / "generators",
        "work": service / "work",
        "output": service / "output",
        "logs": service / "logs",
    })
    monkeypatch.setattr(m, "update_state", lambda **_changes: None)
    monkeypatch.setattr(m, "_month_energy_metrics", lambda *_args, **_kwargs: {
        "metrics": {
            "grid_import_kwh": 193.83,
            "grid_export_kwh": 507.498,
            "gas_m3": 9.074,
            "solar_production_kwh": 221.543,
            "direct_solar_use_kwh": None,
            "house_use_kwh": None,
            "self_use_pct": None,
            "self_supply_pct": None,
        },
        "quality": {
            "measurement_period": {"complete": True, "source": "smp_start_p1_end_boundary"},
            "grid_import_source": "smp_start_p1_end_boundary",
            "grid_export_source": "smp_start_p1_end_boundary",
            "gas_source": "smp_start_p1_end_boundary",
            "production_source": "enphase",
            "solar_balance_status": "inconsistent_period_coverage",
            "boundary_bridge": {"status": "ready", "source": "smp_start_p1_end_boundary"},
            "smp": {
                "status": "incomplete",
                "coverage_status": "error",
                "days_expected": 62,
                "days_covered": 10,
                "errors": ["52 semantic empty-usage connection-days"],
            },
        },
    })

    result = m.build_report_adapter_data(
        SimpleNamespace(report_service_root="unused"),
        {"month": "2026_08", "input_folder": str(input_folder)},
    )
    pages = json.loads(Path(result["files"][2]).read_text(encoding="utf-8"))
    source_text = " ".join(" ".join(map(str, row)) for row in pages["quality"]["sources"])
    check_text = " ".join(" ".join(map(str, row)) for row in pages["quality"]["checks"])

    assert "10/62 meetdagen" in source_text
    assert "52 lege aansluitingsdagen" in source_text + check_text
    assert "smp_start_p1_end_boundary" in source_text + check_text
    assert "SMP-detaildekking aandacht" in check_text
    assert "detaildekking onbekend" not in source_text + check_text
    assert "Geen detaildekkingsrapport beschikbaar" not in source_text + check_text
