from __future__ import annotations

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"
APP = ROOT / "slimmemeterportal_import/rootfs/app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import historical_energy_excel as hx  # noqa: E402


def load_main(name: str):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _write_connections(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "connections.json").write_text(
        json.dumps([
            {"connection_type": "elektriciteit", "meter_identifier": "E1"},
            {"connection_type": "gas", "meter_identifier": "G1"},
        ]),
        encoding="utf-8",
    )


def _write_false_green_raw_month(root: Path, *, with_summary: bool = True) -> None:
    _write_connections(root)
    raw = root / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    summary_connections = []
    for ctype, meter in (("elektriciteit", "E1"), ("gas", "G1")):
        days = []
        for day in range(1, 32):
            d = f"2026-08-{day:02d}"
            if day == 1 and ctype == "elektriciteit":
                usages = [{
                    "delivery_low": "0.10",
                    "returned_delivery_low": "0.00",
                    "delivery_reading_combined": "100.00",
                    "returned_delivery_reading_combined": "200.00",
                }]
            elif day == 1:
                usages = [{"delivery": "0.20", "delivery_reading": "500.00"}]
            else:
                usages = []
            (raw / f"{ctype}_{meter}_{d}.json").write_text(
                json.dumps({"meter_identifier": meter, "usages": usages}),
                encoding="utf-8",
            )
            days.append({"date": d, "status": "ok", "records": 1})
        summary_connections.append({
            "connection_type": ctype,
            "connection_id": meter,
            "days": days,
        })
    if with_summary:
        (root / "month_summary.json").write_text(
            json.dumps({"connections": summary_connections}), encoding="utf-8"
        )


def _write_stale_green(root: Path) -> None:
    (root / "content_coverage_report.json").write_text(
        json.dumps({
            "status": "ok",
            "month": "2026_08",
            "calendar_expected_through": "2026-08-31",
            "available_through": "2026-08-31",
            "days_expected": 62,
            "days_with_measurements": 62,
            "empty_days": [],
            "missing_days": [],
            "errors": [],
            "warnings": [],
        }),
        encoding="utf-8",
    )


def _write_partial_p1(folder: Path) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "P1e.csv").write_text(
        "captured_at,total_power_import_kwh,total_power_export_kwh\n"
        "2026-08-06T15:55:00+02:00,105.000,210.000\n"
        "2026-08-31T23:48:00+02:00,130.000,260.000\n",
        encoding="utf-8",
    )
    (folder / "P1g.csv").write_text(
        "captured_at,total_gas_m3\n"
        "2026-08-06T15:55:00+02:00,502.000\n"
        "2026-08-31T23:48:00+02:00,509.000\n",
        encoding="utf-8",
    )
    (folder / "month_input_validation.json").write_text(
        json.dumps({"status": "ok", "missing_required": [], "empty_required": []}),
        encoding="utf-8",
    )


def _write_smp_csv_wrappers(month_dir: Path) -> None:
    month_dir.mkdir(parents=True, exist_ok=True)
    fields = ["meter_identifier", "usages", "_date", "_connection_type", "_connection_id"]
    for ctype, meter in (("elektriciteit", "E1"), ("gas", "G1")):
        path = month_dir / f"{ctype}_{meter}_2026_08.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for day in range(1, 32):
                if day == 1 and ctype == "elektriciteit":
                    usages = [{
                        "delivery_low": "0,10",
                        "returned_delivery_low": "0,00",
                        "delivery_reading_combined": "100,00",
                        "returned_delivery_reading_combined": "200,00",
                    }]
                elif day == 1:
                    usages = [{"delivery": "0,20", "delivery_reading": "500,00"}]
                else:
                    usages = []
                writer.writerow({
                    "meter_identifier": meter,
                    "usages": json.dumps(usages),
                    "_date": f"2026-08-{day:02d}",
                    "_connection_type": ctype,
                    "_connection_id": meter,
                })


def test_raw_empty_usages_cannot_be_promoted_by_month_summary(tmp_path: Path):
    m = load_main("v32328_empty_usages")
    _write_false_green_raw_month(tmp_path)

    result = m.validate_smp_content_coverage(tmp_path, "2026_08")

    assert result["status"] == "error"
    assert result["available_through"] == "2026-08-01"
    assert len(result["empty_days"]) == 60
    assert result["days_with_measurements"] == 2


def test_stale_green_coverage_is_revalidated_from_raw_content(tmp_path: Path, monkeypatch):
    m = load_main("v32328_stale_green")
    _write_false_green_raw_month(tmp_path)
    _write_stale_green(tmp_path)
    monkeypatch.setattr(m, "_smp_source_candidates", lambda key: [tmp_path])

    result = m.load_smp_month_metrics("2026_08")

    assert result["status"] == "incomplete"
    assert result["coverage_status"] == "error"
    assert result["days_covered"] == 2


def test_historical_csv_wrapper_dates_without_usages_remain_partial(tmp_path: Path):
    _write_smp_csv_wrappers(tmp_path)

    result = hx._smp_csv_month_actuals(tmp_path, "2026_08")

    assert result is not None
    assert result["status"] == "PARTIEEL"
    assert result["period_end"] == "2026-08-01"


def test_month_metrics_bridge_smp_start_boundary_to_p1_month_end(tmp_path: Path, monkeypatch):
    m = load_main("v32328_hybrid_main")
    smp = tmp_path / "smp"
    _write_false_green_raw_month(smp, with_summary=False)
    input_folder = tmp_path / "month_input"
    _write_partial_p1(input_folder)
    monkeypatch.setattr(m, "_smp_source_candidates", lambda key: [smp])
    monkeypatch.setattr(m, "_epex_month_context", lambda key: {"source": "test"})

    result = m._month_energy_metrics("2026_08", input_folder=input_folder)

    assert result["metrics"]["grid_import_kwh"] == pytest.approx(30.1)
    assert result["metrics"]["grid_export_kwh"] == pytest.approx(60.0)
    assert result["metrics"]["gas_m3"] == pytest.approx(9.2)
    assert result["quality"]["grid_import_source"] == "smp_start_p1_end_boundary"
    assert result["quality"]["grid_export_source"] == "smp_start_p1_end_boundary"
    assert result["quality"]["gas_source"] == "smp_start_p1_end_boundary"
    assert result["quality"]["measurement_period"]["complete"] is True
    assert result["quality"]["smp"]["status"] == "incomplete"


def test_historical_actuals_use_same_smp_start_p1_end_bridge(tmp_path: Path):
    month_root = tmp_path / "Data/01_Input/2026_08"
    smp = month_root / "HomeAssistant/SlimmeMeterPortal"
    _write_smp_csv_wrappers(smp)
    _write_stale_green(smp)
    _write_partial_p1(month_root)

    result = hx.read_project_month_actuals(tmp_path, "2026_08")

    assert result is not None
    assert result["status"] == "VOLLEDIG"
    assert result["import_kwh"] == pytest.approx(30.1)
    assert result["export_kwh"] == pytest.approx(60.0)
    assert result["gas_m3"] == pytest.approx(9.2)
    assert result["source_method"] == "smp_start_p1_end_boundary"


def test_v32328_release_identity_is_consistent():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.4.3"
    assert 'version: "32.4.3"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert 'APP_VERSION = "32.4.3"' in MAIN.read_text(encoding="utf-8")
    assert 'TARGET_RELEASE_VERSION = "32.4.3"' in (APP / "mode_entrypoint.py").read_text(encoding="utf-8")
    assert (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").startswith("## 32.4.3")
    assert (ROOT / "slimmemeterportal_import/CHANGELOG.md").read_text(encoding="utf-8").startswith("# Changelog\n\n## 32.4.3")
