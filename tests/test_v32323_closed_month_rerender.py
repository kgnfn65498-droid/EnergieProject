import hashlib
import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import/rootfs/app/main.py"


def load_main(name="v32323_main"):
    spec = importlib.util.spec_from_file_location(name, MAIN)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.exists():
        return digest.hexdigest()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def test_closed_month_rerender_uses_isolated_handoff_and_preserves_sources(monkeypatch, tmp_path):
    m = load_main("v32323_isolated_handoff")
    month = "2026_08"
    runtime_input = tmp_path / "config_output" / "01_Input" / month
    canonical_input = tmp_path / "Data" / "01_Input" / month
    runtime_input.mkdir(parents=True)
    canonical_input.mkdir(parents=True)
    (runtime_input / "P1e.csv").write_text("captured_at,total_power_import_kwh\n2026-08-06T00:00:00+02:00,10\n", encoding="utf-8")
    (canonical_input / "source.json").write_text('{"closed":true,"source_data_modified":false}', encoding="utf-8")

    service_root = tmp_path / "report_service"
    service_paths = {
        "root": service_root,
        "generators": service_root / "generators",
        "work": service_root / "work",
        "output": service_root / "output",
        "logs": service_root / "logs",
    }
    for path in service_paths.values():
        path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(m, "MONTH_INPUT_ROOT", runtime_input.parent)
    monkeypatch.setattr(m, "NAS_DATA_ROOT", tmp_path / "Data")
    monkeypatch.setattr(m, "report_service_paths", lambda options: service_paths)
    monkeypatch.setattr(m, "Options", SimpleNamespace(load=lambda: SimpleNamespace()))
    monkeypatch.setattr(m, "report_input_readiness", lambda month_key, options, historical=False: {
        "status": "ready",
        "historical": historical,
        "core_metrics": {"grid_import_kwh": 180.0, "grid_export_kwh": 300.0, "gas_m3": 9.0},
        "missing_core_metrics": [],
    })
    monkeypatch.setattr(m, "_smp_source_candidates", lambda month_key: [])
    monkeypatch.setattr(m, "update_state", lambda **kwargs: None)

    observed = {}
    def fake_generation(options, request_path):
        observed["request_path"] = Path(request_path)
        return {"status": "completed", "month": month}
    monkeypatch.setattr(m, "run_report_generation_from_handoff", fake_generation)

    runtime_before = tree_digest(runtime_input)
    canonical_before = tree_digest(canonical_input)
    result = m.rebuild_historical_report(month)
    runtime_after = tree_digest(runtime_input)
    canonical_after = tree_digest(canonical_input)

    expected_handoff = service_paths["work"] / month / "rerender_handoff"
    assert observed["request_path"].parent == expected_handoff
    assert (expected_handoff / "report_request.json").is_file()
    assert (expected_handoff / "report_request_manifest.json").is_file()
    assert runtime_after == runtime_before
    assert canonical_after == canonical_before
    assert result["source_data_modified"] is False
    assert result["closed_month_preserved"] is True
    assert result["analysis_file_required"] is False


def test_release_identity_32323():
    source = MAIN.read_text(encoding="utf-8")
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == "32.3.31"
    assert 'APP_VERSION = "32.3.31"' in source
    assert 'version: "32.3.31"' in (ROOT / "slimmemeterportal_import/config.yaml").read_text(encoding="utf-8")
