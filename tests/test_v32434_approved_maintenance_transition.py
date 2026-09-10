import json
from pathlib import Path

from operating_modes import Mode, process_mode_command
from projectmanager_v2.mode_bridge import ModeBridge


def _write(root, payload):
    p = Path(root) / 'Inbox/operating_mode/operating_mode_command.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload), encoding='utf-8')


def _open_dev(root):
    _write(root, {
        'schema_version': 1, 'request_id': 'dev-open', 'action': 'set_base',
        'requested_mode': 'DEVELOPMENT', 'issued_by': 'projectmanager',
    })
    return process_mode_command(root)


def test_unconfirmed_set_base_maintenance_still_cannot_close_development(tmp_path):
    _open_dev(tmp_path)
    _write(tmp_path, {
        'schema_version': 1, 'request_id': 'maint-denied', 'action': 'set_base',
        'requested_mode': 'MAINTENANCE', 'issued_by': 'projectmanager',
        'confirmed_by_user': False,
    })
    state = process_mode_command(tmp_path)
    assert state.base_mode is Mode.DEVELOPMENT
    assert state.effective_mode is Mode.DEVELOPMENT
    assert state.development_session_active is True
    assert 'development_session_requires_explicit_close' in state.drift


def test_confirmed_set_base_maintenance_atomically_closes_development(tmp_path):
    _open_dev(tmp_path)
    _write(tmp_path, {
        'schema_version': 1, 'request_id': 'maint-approved', 'action': 'set_base',
        'requested_mode': 'MAINTENANCE', 'issued_by': 'projectmanager',
        'confirmed_by_user': True,
    })
    state = process_mode_command(tmp_path)
    assert state.base_mode is Mode.MAINTENANCE
    assert state.effective_mode is Mode.MAINTENANCE
    assert state.development_session_active is False
    assert state.last_processed_request_id == 'maint-approved'


def test_mode_bridge_can_carry_explicit_user_confirmation(tmp_path):
    bridge = ModeBridge(tmp_path / 'mode.json')
    result = bridge.request_base_mode('MAINTENANCE', reason='approved', confirmed_by_user=True)
    payload = json.loads((tmp_path / 'mode.json').read_text(encoding='utf-8'))
    assert result['confirmed_by_user'] is True
    assert payload['confirmed_by_user'] is True


def test_command_processor_approved_remote_mode_marks_confirmation_true():
    text = Path('slimmemeterportal_import/rootfs/app/projectmanager_v2/command_processor.py').read_text(encoding='utf-8')
    assert "confirmed_by_user=True" in text
