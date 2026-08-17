import pathlib
import sys
from types import SimpleNamespace

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP_ROOT = ROOT / "slimmemeterportal_import/rootfs/app"
sys.path.insert(0, str(APP_ROOT))

import main as m


def test_report_service_history_keeps_latest_13_months(monkeypatch, tmp_path):
    paths = {
        "root": tmp_path / "service",
        "generators": tmp_path / "service/generators",
        "work": tmp_path / "service/work",
        "output": tmp_path / "service/output",
        "logs": tmp_path / "service/logs",
    }
    monkeypatch.setattr(m, "report_service_paths", lambda options: paths)
    monkeypatch.setattr(m, "STATE_PATH", tmp_path / "config/state.json")
    months = [
        "2025_06", "2025_07", "2025_08", "2025_09", "2025_10",
        "2025_11", "2025_12", "2026_01", "2026_02", "2026_03",
        "2026_04", "2026_05", "2026_06", "2026_07", "2026_08",
    ]
    for key in ("work", "output", "logs"):
        paths[key].mkdir(parents=True)
        for month in months:
            (paths[key] / month).mkdir()

    result = m.cleanup_report_service_history(
        SimpleNamespace(report_service_retention_months=13)
    )

    assert result["status"] == "completed"
    assert result["retention_months"] == 13
    expected = set(months[-13:])
    for key in ("work", "output", "logs"):
        remaining = {path.name for path in paths[key].iterdir() if path.is_dir()}
        assert remaining == expected
    assert len(result["removed"]) == 6


def test_report_retention_default_and_addon_option_are_exactly_13_months():
    main_source = (APP_ROOT / "main.py").read_text(encoding="utf-8")
    config = (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
    assert 'raw.get("report_service_retention_months", 13)' in main_source
    assert "report_service_retention_months: 13" in config
