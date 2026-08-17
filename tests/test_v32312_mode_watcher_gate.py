import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
GATE = ROOT / "tools/operating_mode_gate.py"
WATCHER = ROOT / "tools/release_watcher.sh"


def seed_state(project, mode):
    path = project / "Data/03_Systeem/Projectmanager/State/operating_mode_state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "schema_version": 1,
        "base_mode": "USER",
        "effective_mode": mode,
        "automatic_switching_enabled": True,
        "reconciliation_status": "ok",
    }), encoding="utf-8")


def run_gate(project, capability):
    return subprocess.run([sys.executable, str(GATE), "--root", str(project), "--capability", capability], text=True, capture_output=True)


def test_user_denies_release_and_maintenance(tmp_path):
    seed_state(tmp_path, "USER")
    assert run_gate(tmp_path, "release_ingress").returncode == 3
    assert run_gate(tmp_path, "maintenance_requests").returncode == 3


def test_development_allows_only_release_ingress(tmp_path):
    seed_state(tmp_path, "DEVELOPMENT")
    assert run_gate(tmp_path, "release_ingress").returncode == 0
    assert run_gate(tmp_path, "maintenance_requests").returncode == 3


def test_maintenance_allows_only_maintenance_requests(tmp_path):
    seed_state(tmp_path, "MAINTENANCE")
    assert run_gate(tmp_path, "release_ingress").returncode == 3
    assert run_gate(tmp_path, "maintenance_requests").returncode == 0


def test_missing_state_fails_closed_for_release(tmp_path):
    assert run_gate(tmp_path, "release_ingress").returncode != 0


def test_watcher_checks_mode_before_touching_incoming():
    source = WATCHER.read_text(encoding="utf-8")
    loop = source.split("while :; do", 1)[1]
    assert loop.index("mode_allows maintenance_requests") < loop.index("process_crash_recovery_cleanup")
    assert loop.index("mode_allows release_ingress") < loop.index('set -- "$INCOMING"/*.zip')
