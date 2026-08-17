import json
import pathlib
import sys
from dataclasses import dataclass, replace

APP_ROOT = pathlib.Path(__file__).resolve().parents[1] / "slimmemeterportal_import/rootfs/app"
sys.path.insert(0, str(APP_ROOT))

from release_validation_hold import (
    activate_release_hold,
    hold_state_path,
    load_release_hold,
)


def test_release_hold_persists_across_reload(tmp_path):
    state = activate_release_hold(tmp_path, "32.3.14", "release_install")
    loaded = load_release_hold(tmp_path, "32.3.14")
    assert state.active is True
    assert loaded.active is True
    assert loaded.release_version == "32.3.14"
    assert loaded.activated_reason == "release_install"


def test_missing_hold_state_for_new_release_is_fail_closed(tmp_path):
    loaded = load_release_hold(tmp_path, "32.3.14")
    assert loaded.active is True
    assert loaded.validation_status == "required"
    assert "missing_hold_state" in loaded.reasons


def test_corrupt_hold_state_is_fail_closed(tmp_path):
    path = hold_state_path(tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text("{broken", encoding="utf-8")
    loaded = load_release_hold(tmp_path, "32.3.14")
    assert loaded.active is True
    assert loaded.validation_status == "required"
    assert "invalid_hold_state" in loaded.reasons
