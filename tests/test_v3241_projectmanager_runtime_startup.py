from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / "slimmemeterportal_import"
APP = ADDON / "rootfs/app"


def test_addon_launcher_enters_mode_entrypoint():
    launcher = (ADDON / "run.sh").read_text(encoding="utf-8")
    assert "exec python3 -u /app/mode_entrypoint.py" in launcher
    rootfs_launcher = (APP / "run.sh").read_text(encoding="utf-8")
    assert "exec python3 -u /app/mode_entrypoint.py" in rootfs_launcher


def test_embedded_projectmanager_runtime_uses_writable_inbox_state_root():
    source = (APP / "projectmanager_v2/embedded_config.py").read_text(encoding="utf-8")
    assert "Inbox/projectmanager_v2/RuntimeV2" in source
    assert "Data/03_Systeem/Projectmanager/RuntimeV2" not in source
