from pathlib import Path
import sys

import pytest


@pytest.fixture(autouse=True)
def _isolate_v32316_report_retention_state(request, monkeypatch, tmp_path):
    if request.node.name != "test_report_service_history_keeps_latest_13_months":
        return
    root = Path(__file__).resolve().parents[1]
    app_root = root / "slimmemeterportal_import/rootfs/app"
    sys.path.insert(0, str(app_root))
    import main as app_main
    monkeypatch.setattr(app_main, "STATE_PATH", tmp_path / "config/state.json")
