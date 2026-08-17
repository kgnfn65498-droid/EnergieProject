import json
import pathlib
import sys

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "slimmemeterportal_import/rootfs/app"
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from release_validation_hold import (
    activate_release_hold,
    ensure_release_hold_state,
    hold_state_path,
    load_release_hold,
    release_hold,
)


def test_missing_hold_from_v32313_is_materialized_fail_closed(tmp_path):
    path = hold_state_path(tmp_path)
    assert not path.exists()
    state = ensure_release_hold_state(tmp_path, "32.3.14")
    assert state.active is True
    assert state.release_version == "32.3.14"
    assert path.is_file()
    loaded = load_release_hold(tmp_path, "32.3.14")
    assert loaded.active is True
    assert loaded.release_version == "32.3.14"
    assert "missing_hold_state" in loaded.reasons


def test_existing_active_hold_is_not_replaced(tmp_path):
    before = activate_release_hold(tmp_path, "32.3.14", "release_install")
    after = ensure_release_hold_state(tmp_path, "32.3.14")
    assert after == before


def test_released_hold_stays_released_across_startup(tmp_path):
    activate_release_hold(tmp_path, "32.3.14", "release_install")
    released = release_hold(tmp_path, "32.3.14", issued_by="projectmanager", emergency=True)
    assert released.active is False
    after = ensure_release_hold_state(tmp_path, "32.3.14")
    assert after.active is False
    assert after.released_by == "projectmanager"


def test_corrupt_hold_is_repaired_as_active_fail_closed(tmp_path):
    path = hold_state_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")
    state = ensure_release_hold_state(tmp_path, "32.3.14")
    assert state.active is True
    assert state.release_version == "32.3.14"
    assert "invalid_hold_state" in state.reasons
    json.loads(path.read_text(encoding="utf-8"))


def test_mismatched_release_hold_is_repaired_for_installed_release(tmp_path):
    activate_release_hold(tmp_path, "32.3.13", "old_release")
    state = ensure_release_hold_state(tmp_path, "32.3.14")
    assert state.active is True
    assert state.release_version == "32.3.14"
    assert "release_version_mismatch" in state.reasons


def test_entrypoint_materializes_hold_before_runtime_and_app_main():
    text = (APP_ROOT / "mode_entrypoint.py").read_text(encoding="utf-8")
    call = "ensure_release_hold_state(root, TARGET_RELEASE_VERSION)"
    assert call in text
    assert text.index(call) < text.index("install_release_hold_guards(app, root)")
    assert text.index(call) < text.index("app.main()")
