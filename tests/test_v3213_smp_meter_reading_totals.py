from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

import historical_energy_excel as hx  # noqa: E402


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["meter_identifier", "usages", "_date", "_connection_type", "_connection_id"])
        writer.writeheader()
        writer.writerows(rows)


def test_smp_actuals_use_meter_reading_boundaries_not_rounded_interval_sums(tmp_path: Path):
    # Reproduceert juli 2026: de detailwaarden zijn op 0,01 afgerond en kunnen
    # daardoor niet veilig worden opgeteld. De cumulatieve meterstanden zijn leidend.
    _write_csv(
        tmp_path / "elektriciteit_1_2026_07.csv",
        [
            {
                "meter_identifier": "1",
                "_date": "2026-07-01",
                "_connection_type": "elektriciteit",
                "_connection_id": "1",
                "usages": json.dumps([
                    {
                        "delivery_high": None,
                        "delivery_low": "0,06",
                        "delivery_reading_combined": "17.056,81",
                        "returned_delivery_high": None,
                        "returned_delivery_low": "0,00",
                        "returned_delivery_reading_combined": "12.298,13",
                    },
                    {
                        # De maandgrens: intervalwaarden alleen optellen zou 0,16/0,00 geven,
                        # terwijl de meterstanden exact de gevalideerde julitotalen geven.
                        "delivery_high": None,
                        "delivery_low": "0,10",
                        "delivery_reading_combined": "17.213,07",
                        "returned_delivery_high": None,
                        "returned_delivery_low": "0,00",
                        "returned_delivery_reading_combined": "12.902,10",
                    },
                ]),
            }
        ],
    )
    _write_csv(
        tmp_path / "gas_1_2026_07.csv",
        [
            {
                "meter_identifier": "1",
                "_date": "2026-07-01",
                "_connection_type": "gas",
                "_connection_id": "1",
                "usages": json.dumps([
                    {"delivery": "0,00", "delivery_reading": "3.743,04"},
                    # Dit bootst de echte bron na waar een meterstand met 0,01 kan
                    # stijgen terwijl de afgeronde intervalwaarde 0,00 is.
                    {"delivery": "0,00", "delivery_reading": "3.776,93"},
                ]),
            }
        ],
    )

    actuals = hx._smp_csv_month_actuals(tmp_path, "2026_07")
    assert actuals is not None
    assert actuals["import_kwh"] == pytest.approx(156.32)
    assert actuals["export_kwh"] == pytest.approx(603.97)
    assert actuals["net_kwh"] == pytest.approx(-447.65)
    assert actuals["gas_m3"] == pytest.approx(33.89)
