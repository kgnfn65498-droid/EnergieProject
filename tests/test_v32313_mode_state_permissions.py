from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
if str(APP) not in sys.path:
    sys.path.insert(0, str(APP))

from operating_modes import ModeState, command_path, save_mode_state, state_path
from operating_mode_runtime import mode_history_path


def test_mode_coordination_files_use_shared_inbox_not_protected_projectmanager(tmp_path):
    protected = tmp_path / "Data/03_Systeem/Projectmanager/State"
    protected.mkdir(parents=True)

    assert state_path(tmp_path) == tmp_path / "Inbox/operating_mode/operating_mode_state.json"
    assert command_path(tmp_path) == tmp_path / "Inbox/operating_mode/operating_mode_command.json"
    assert mode_history_path(tmp_path) == tmp_path / "Inbox/logs/operating_mode_history.jsonl"

    save_mode_state(tmp_path, ModeState.initial())
    assert state_path(tmp_path).is_file()
    assert not (protected / "operating_mode_state.json").exists()
