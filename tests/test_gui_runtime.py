import importlib.util
import pathlib
import sys
import tempfile


def load_main():
    source = pathlib.Path(__file__).parents[1] / "slimmemeterportal_import/rootfs/app/main.py"
    spec = importlib.util.spec_from_file_location("energy_gui_runtime", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_gui_renders_when_output_directory_does_not_exist():
    m = load_main()
    root = pathlib.Path(tempfile.mkdtemp())
    m.OPTIONS_PATH = root / "missing-options.json"
    m.STATE_PATH = root / "state.json"
    m.OUTPUT_ROOT = root / "missing-output"
    m.PRODUCTION_CERTIFICATE_PATH = m.OUTPUT_ROOT / "production_certificate.json"
    m.PRODUCTION_CERTIFICATE_HISTORY_PATH = m.OUTPUT_ROOT / "production_certificate_history.jsonl"
    m.PRODUCTION_CERTIFICATE_MANAGEMENT_PATH = m.OUTPUT_ROOT / "production_certificate_management.json"
    m.AUDIT_TRAIL_PATH = m.OUTPUT_ROOT / "audit_trail.jsonl"
    m.RECOVERY_STATE_PATH = m.OUTPUT_ROOT / "recovery_state.json"
    m.RECOVERY_HISTORY_PATH = m.OUTPUT_ROOT / "recovery_history.jsonl"
    m.MONITORING_STATE_PATH = m.OUTPUT_ROOT / "monitoring_state.json"
    m.MONITORING_HISTORY_PATH = m.OUTPUT_ROOT / "monitoring_history.jsonl"

    body = m.html_page("/api/hassio_ingress/test")

    assert b"SlimmeMeterPortal" in body
