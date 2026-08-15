from __future__ import annotations

import hashlib
import json
import sys
import zipfile
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import historical_energy_excel as hx  # noqa: E402

EXPECTED_SHEETS = [
    "Dashboard",
    "Dashboard 2026",
    "2026 vs 3 jaar",
    "Jaaroverzicht",
    "Kalenderjaren",
    "Maanddetail",
    "Contractjaren",
    "Zonnepanelen",
    "Apparaatmetingen",
    "Bronnen",
    "Onderhoud",
]


def test_seed_contains_audited_history_and_july_2026():
    seed = hx.load_seed()
    periods = seed["periods"]
    assert periods[0]["from"] == "2009-11-01"
    assert not any(str(item["from"]).startswith("2008-") for item in periods)
    july = next(
        item for item in periods
        if item["from"] == "2026-07-01" and item["to"] == "2026-07-31"
    )
    assert july["status"] == "VOLLEDIG"
    assert july["import_kwh"] == pytest.approx(156.32)
    assert july["export_kwh"] == pytest.approx(603.97)
    assert july["net_kwh"] == pytest.approx(-447.65)
    assert july["gas_m3"] == pytest.approx(33.89)


def test_calendar_year_rows_are_explicit_about_coverage():
    rows = {row["year"]: row for row in hx.build_calendar_year_rows(hx.load_seed()["periods"])}
    assert rows[2023]["status"] == "VOLLEDIG"
    assert rows[2023]["import_kwh"] == pytest.approx(3578)
    assert rows[2025]["status"] == "VOLLEDIG"
    assert rows[2025]["import_kwh"] == pytest.approx(4983)
    assert rows[2022]["status"] == "PARTIEEL"
    assert rows[2022]["coverage"] == "15 jul–31 dec"
    assert rows[2026]["status"] == "PARTIEEL"
    assert "jan–jul" in rows[2026]["coverage"].lower()


def test_equal_month_comparison_includes_july_and_excludes_august():
    comparison = hx.build_equal_month_comparison(hx.load_seed()["periods"], 2026, years_back=3)
    assert comparison["through_month"] == 7
    row_2026 = next(row for row in comparison["years"] if row["year"] == 2026)
    assert row_2026["period"] == "01-01 t/m 31-07"
    assert row_2026["import_kwh"] == pytest.approx(2604.32)
    assert row_2026["export_kwh"] == pytest.approx(2807.97)
    july = next(row for row in comparison["monthly_net"] if row["month"] == 7)
    assert july[2026] == pytest.approx(-447.65)


def test_build_clean_workbook_is_value_only_and_valid(tmp_path: Path):
    output = tmp_path / "Energie_verbruik_historie.xlsx"
    result = hx.build_historical_energy_workbook(
        project_root=tmp_path,
        month_key="2026_07",
        periods=hx.load_seed()["periods"],
        output_path=output,
    )
    assert result["status"] == "ok"
    validation = hx.validate_xlsx(output)
    assert validation["status"] == "ok"
    assert validation["sheet_names"] == EXPECTED_SHEETS
    assert validation["formula_count"] == 0
    assert validation["external_link_count"] == 0
    assert validation["vba_present"] is False
    assert validation["has_2008_date"] is False
    with zipfile.ZipFile(output) as zf:
        assert zf.testzip() is None


def test_month_publish_is_atomic_and_archive_matches_master(tmp_path: Path):
    reports = tmp_path / "Data" / "02_Output" / "Rapportages" / "Verbruikshistorie"
    reports.mkdir(parents=True)
    prior = reports / "Energie_verbruik_historie.xlsx"
    prior.write_bytes(b"previous-valid-master")

    result = hx.publish_historical_energy_workbook(
        project_root=tmp_path,
        month_key="2026_07",
        include_partial_current=False,
    )
    assert result["status"] == "completed"
    master = reports / "Energie_verbruik_historie.xlsx"
    archive = reports / "Archief" / "Energie_verbruik_historie_2026_07.xlsx"
    assert master.is_file() and archive.is_file()
    assert master.read_bytes() == archive.read_bytes()
    assert hashlib.sha256(master.read_bytes()).hexdigest() == result["master_sha256"]
    assert result["archive_sha256"] == result["master_sha256"]


def test_failed_validation_preserves_existing_master(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    reports = tmp_path / "Data" / "02_Output" / "Rapportages" / "Verbruikshistorie"
    reports.mkdir(parents=True)
    master = reports / "Energie_verbruik_historie.xlsx"
    master.write_bytes(b"previous-valid-master")

    monkeypatch.setattr(hx, "validate_xlsx", lambda path: {"status": "error", "errors": ["forced"]})
    with pytest.raises(RuntimeError, match="validatie"):
        hx.publish_historical_energy_workbook(
            project_root=tmp_path,
            month_key="2026_07",
            include_partial_current=False,
        )
    assert master.read_bytes() == b"previous-valid-master"


def test_partial_month_updates_master_but_does_not_create_frozen_archive(tmp_path: Path):
    month_root = tmp_path / "Data" / "01_Input" / "2026_08" / "HomeAssistant" / "SlimmeMeterPortal"
    month_root.mkdir(parents=True)
    (month_root / "historical_energy_month_actuals.json").write_text(
        json.dumps({
            "month": "2026_08",
            "status": "PARTIEEL",
            "period_start": "2026-08-01",
            "period_end": "2026-08-15",
            "import_kwh": 83.075,
            "export_kwh": 288.443,
            "net_kwh": -205.368,
            "gas_m3": 5.4,
            "source": "fixture",
        }),
        encoding="utf-8",
    )
    result = hx.publish_historical_energy_workbook(
        project_root=tmp_path,
        month_key="2026_08",
        include_partial_current=True,
    )
    assert result["status"] == "completed"
    assert result["archive_status"] == "skipped_partial"
    assert not (tmp_path / "Data/02_Output/Rapportages/Verbruikshistorie/Archief/Energie_verbruik_historie_2026_08.xlsx").exists()


def test_month_upsert_never_downgrades_full_month_to_partial():
    seed_periods = hx.load_seed()["periods"]
    partial = {
        "from": "2026-07-01", "to": "2026-07-15", "days": 15,
        "import_kwh": 69.0, "export_kwh": 314.0, "net_kwh": -245.0,
        "gas_m3": 10.0, "airco_kwh": None, "extra_pv_kwh": None,
        "source_type": "Home Assistant/P1", "status": "PARTIEEL", "source": "partial fixture",
    }
    merged = hx.merge_periods(seed_periods, [partial])
    july = [p for p in merged if p["from"].startswith("2026-07")]
    assert len(july) == 1
    assert july[0]["status"] == "VOLLEDIG"
    assert july[0]["import_kwh"] == pytest.approx(156.32)


def test_next_month_rebuild_keeps_previous_validated_month(tmp_path: Path):
    for month_key, import_kwh, export_kwh, gas_m3, days in (
        ("2026_08", 210.0, 510.0, 25.0, 31),
        ("2026_09", 240.0, 430.0, 35.0, 30),
    ):
        month_dir = tmp_path / "Data" / "01_Input" / month_key / "HomeAssistant" / "SlimmeMeterPortal"
        month_dir.mkdir(parents=True)
        year, month = (int(part) for part in month_key.split("_"))
        month_dir.joinpath("historical_energy_month_actuals.json").write_text(
            json.dumps({
                "month": month_key,
                "status": "VOLLEDIG",
                "period_start": f"{year:04d}-{month:02d}-01",
                "period_end": f"{year:04d}-{month:02d}-{days:02d}",
                "import_kwh": import_kwh,
                "export_kwh": export_kwh,
                "net_kwh": import_kwh - export_kwh,
                "gas_m3": gas_m3,
                "source": f"fixture {month_key}",
            }),
            encoding="utf-8",
        )

    periods, target_status = hx.periods_for_publish(
        tmp_path,
        "2026_09",
        include_partial_current=False,
    )
    assert target_status == "VOLLEDIG"
    august = next(p for p in periods if p["from"] == "2026-08-01")
    september = next(p for p in periods if p["from"] == "2026-09-01")
    assert august["status"] == "VOLLEDIG"
    assert august["import_kwh"] == pytest.approx(210.0)
    assert september["status"] == "VOLLEDIG"
    assert september["import_kwh"] == pytest.approx(240.0)
