import importlib.util
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"


def load_main(name: str):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_smp_publish_creates_missing_homeassistant_ingress_for_july(monkeypatch, tmp_path):
    m = load_main("july_ingress_fallback_runtime")
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")

    source = tmp_path / "smp_source"
    source.mkdir()
    (source / "month_summary.json").write_text('{"month":"2026_07"}', encoding="utf-8")

    result = m.publish_smp_import_to_nas_input(source, "2026_07")

    ingress = tmp_path / "Data" / "01_Input" / "2026_07" / "HomeAssistant"
    published = ingress / "SlimmeMeterPortal"
    assert result["status"] == "ok"
    assert ingress.is_dir()
    assert (published / "month_summary.json").read_text(encoding="utf-8") == '{"month":"2026_07"}'
    assert (published / "ha_smp_transfer_manifest.json").is_file()


def test_smp_publish_reports_unusable_homeassistant_ingress(monkeypatch, tmp_path):
    m = load_main("july_ingress_fallback_unusable")
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")

    source = tmp_path / "smp_source"
    source.mkdir()
    (source / "month_summary.json").write_text('{"month":"2026_07"}', encoding="utf-8")

    ingress = tmp_path / "Data" / "01_Input" / "2026_07" / "HomeAssistant"
    ingress.parent.mkdir(parents=True)
    ingress.write_text("not-a-directory", encoding="utf-8")

    try:
        m.publish_smp_import_to_nas_input(source, "2026_07")
    except RuntimeError as exc:
        assert "HA-ingress kan niet worden voorbereid voor 2026_07" in str(exc)
    else:
        raise AssertionError("onbruikbare HA-ingress had hard moeten falen")
