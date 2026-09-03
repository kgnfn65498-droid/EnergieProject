import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"


def load_main(name: str):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def write_raw_interval_month(root: Path, month_key: str = "2026_08") -> Path:
    year = int(month_key[:4])
    month = int(month_key[5:7])
    import calendar

    days = calendar.monthrange(year, month)[1]
    raw = root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (root / "connections.json").write_text(
        json.dumps([
            {"connection_type": "elektriciteit", "meter_identifier": "E1"},
            {"connection_type": "gas", "meter_identifier": "G1"},
        ]),
        encoding="utf-8",
    )
    for day in range(1, days + 1):
        d = f"{year:04d}-{month:02d}-{day:02d}"
        electricity = {
            "usages": [
                {"delivery": 0.01, "returned_delivery": 0.02}
                for _ in range(96)
            ]
        }
        gas = {"usages": [{"delivery": 0.01} for _ in range(24)]}
        (raw / f"elektriciteit_E1_{d}.json").write_text(json.dumps(electricity), encoding="utf-8")
        (raw / f"gas_G1_{d}.json").write_text(json.dumps(gas), encoding="utf-8")
    return root


def test_live_smp_raw_interval_files_count_as_complete_closed_month(tmp_path):
    m = load_main("v32325_raw_coverage")
    write_raw_interval_month(tmp_path)

    result = m.validate_smp_content_coverage(tmp_path, "2026_08")

    assert result["status"] == "ok"
    assert result["days_expected"] == 62
    assert result["days_with_measurements"] == 62
    assert result["errors"] == []


def test_smp_reader_revalidates_stale_coverage_report_without_mutating_source(tmp_path, monkeypatch):
    m = load_main("v32325_stale_coverage")
    write_raw_interval_month(tmp_path)
    stale = {
        "status": "error",
        "month": "2026_08",
        "calendar_expected_through": "2026-08-31",
        "available_through": "2026-08-31",
        "days_expected": 62,
        "days_with_measurements": 62,
        "missing_days": [],
        "empty_days": [],
        "errors": ["elektriciteit/E1/2026-08-01: 96 record(s), verwacht [1] voor SlimmeMeterPortal."],
    }
    coverage_path = tmp_path / "content_coverage_report.json"
    coverage_path.write_text(json.dumps(stale, sort_keys=True), encoding="utf-8")
    before = coverage_path.read_bytes()
    monkeypatch.setattr(m, "_smp_source_candidates", lambda key: [tmp_path])

    result = m.load_smp_month_metrics("2026_08")

    assert result["status"] == "ready"
    assert result["coverage_status"] == "ok"
    assert result["data_shape"] == "raw_daily"
    assert result["grid_import_kwh"] == 29.76
    assert result["grid_export_kwh"] == 59.52
    assert result["gas_m3"] == 7.44
    assert coverage_path.read_bytes() == before
