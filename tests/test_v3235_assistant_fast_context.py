import importlib.util
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
FAST = ROOT / "slimmemeterportal_import/rootfs/app/assistant_fast_context.py"
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"


def load_fast(name="assistant_fast_context_test"):
    spec = importlib.util.spec_from_file_location(name, FAST)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_quarter_hour_fast_reader_extracts_multiple_entities_in_one_snapshot_pass(tmp_path):
    module = load_fast()
    folder = tmp_path / "01_Input/2026_08/HomeAssistant/QuarterHour"
    folder.mkdir(parents=True)
    for idx, stamp in enumerate(("20260816T180000Z", "20260816T181500Z", "20260816T183000Z")):
        payload = {
            "entities": [
                {"entity_id": "sensor.import", "state": str(100 + idx), "last_updated": stamp},
                {"entity_id": "sensor.export", "state": str(200 + idx * 2), "last_updated": stamp},
                {"entity_id": "sensor.gas", "state": str(300 + idx * 0.5), "last_updated": stamp},
            ]
        }
        (folder / f"home_assistant_quarter_{stamp}.json").write_text(json.dumps(payload), encoding="utf-8")

    series = module.load_quarter_hour_series_once(
        tmp_path,
        "2026_08",
        ("sensor.import", "sensor.export", "sensor.gas"),
    )

    assert [x["value"] for x in series["sensor.import"]] == [100.0, 101.0, 102.0]
    assert [x["value"] for x in series["sensor.export"]] == [200.0, 202.0, 204.0]
    assert [x["value"] for x in series["sensor.gas"]] == [300.0, 300.5, 301.0]
    assert all(x["transport"] == "nas_data_filesystem_read_only_single_pass" for x in series["sensor.import"])


def test_assistant_wiring_uses_fast_month_context_and_runtime_roots():
    source = MAIN.read_text(encoding="utf-8")
    assert "from project_paths import find_existing_nas_roots" in source
    assert "def _assistant_runtime_data_root()" in source
    assert "def build_assistant_analysis_context(" in source
    assert "analysis_provider=build_assistant_analysis_context" in source
    assert "analysis_provider=build_analysis_context" not in source[source.index("ASSISTANT_ENGINE = EnergyConversationEngine"):source.index("def analysis_overview")]
    assert "load_quarter_hour_series_once" in source
    assert "root = _assistant_runtime_data_root() / \"02_Output\" / \"Rapportages\" / \"KnowledgeBase\"" in source
