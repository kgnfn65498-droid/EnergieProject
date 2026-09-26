from __future__ import annotations

import json
import shutil
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for path in (str(TOOLS), str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)

import clearup_type2_service as service
import project_clearup_move_executor as executor
import sideband_bridge


def _json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n', encoding='utf-8')


def _watch(root: Path, monkeypatch):
    monkeypatch.setattr(executor, '_load_clearup_type2_service', lambda _root: service)
    monkeypatch.setattr(service, 'WATCHER_TIMEOUT_SECONDS', 5.0)
    request_path = root / service.WATCHER_REQUEST_REL

    def run():
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline and not request_path.is_file():
            time.sleep(0.005)
        assert request_path.is_file()
        payload = sideband_bridge.process_once(root)
        assert isinstance(payload, dict)

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def _call(root: Path, monkeypatch, fn, /, **kwargs):
    t = _watch(root, monkeypatch)
    result = fn(root, source='mcp_remote', **kwargs)
    t.join(timeout=4)
    assert not t.is_alive()
    return result


def _seed_release(root: Path) -> None:
    (root / 'App/tools/clearup_type2_plans').mkdir(parents=True, exist_ok=True)
    for cid in ('ClearUp_005', 'ClearUp_006', 'ClearUp_007'):
        shutil.copy2(ROOT / 'tools/clearup_type2_plans' / f'{cid}.json', root / 'App/tools/clearup_type2_plans' / f'{cid}.json')
    (root / 'App/VERSIE.txt').write_text('32.5.21\n', encoding='utf-8')
    (root / 'App/tools/clearup_type2_path_contract.json').write_text(
        json.dumps({'release':'32.5.21','ClearUp_005':'GREEN','ClearUp_006':'GREEN','ClearUp_007':'GREEN'}, indent=2) + '\n',
        encoding='utf-8',
    )
    for rel in ('Inbox/incoming','Inbox/processing','Inbox/processed','Inbox/failed'):
        (root / rel).mkdir(parents=True, exist_ok=True)


def test_clearup005_can_migrate_into_existing_shared_releasecontroller_parent(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    _seed_release(root)
    # Seed the live pre-migration source and release-idle evidence.
    src = root / 'Inbox/release_controller'
    src.mkdir(parents=True)
    _json(src / 'current.json', {'status':'COMPLETE','phase':'COMPLETE'})
    _json(src / 'runtime.json', {'status':'IDLE','seed':'source'})
    (src / 'migrations').mkdir()
    (src / 'migrations' / 'old.json').write_text('old\n', encoding='utf-8')
    (root / 'Inbox/latest_release_status.txt').write_text('COMPLETE\n', encoding='utf-8')

    prepared = _call(root, monkeypatch, service.prepare_type2, clearup_id='ClearUp_005')
    assert prepared['status'] == 'GREEN'

    # Simulate 32.5.20 live continuation: later mappings have already created
    # canonical sibling subtrees under the same ReleaseController parent.
    dst = root / 'Data/03_Systeem/Projectmanager/ReleaseController'
    _json(dst / 'Publication/github_publication_state.json', {'owned_by':'ClearUp_011'})
    _json(dst / 'State/atomic_app_swap_state.json', {'owned_by':'ClearUp_011'})

    migrated = _call(root, monkeypatch, service.migrate_type2, clearup_id='ClearUp_005', explicit_user_text='akkoord')
    assert migrated['phase'] == 'MIGRATED_PENDING_VALIDATION'
    assert (dst / 'current.json').read_text(encoding='utf-8') == (src / 'current.json').read_text(encoding='utf-8')
    assert (dst / 'migrations/old.json').read_text(encoding='utf-8') == 'old\n'
    assert json.loads((dst / 'Publication/github_publication_state.json').read_text())['owned_by'] == 'ClearUp_011'
    assert json.loads((dst / 'State/atomic_app_swap_state.json').read_text())['owned_by'] == 'ClearUp_011'


def test_validation_filesystem_proof_runs_only_in_privileged_watcher(tmp_path, monkeypatch):
    root = tmp_path / 'project'
    _seed_release(root)
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_QUIESCENCE_SECONDS', '0.05')
    monkeypatch.setenv('ENERGIE_CLEARUP_TYPE2_PROOF_TIMEOUT_SECONDS', '0.2')

    # Use ClearUp_006 because live 32.5.20 failed when the embedded PM tried
    # to read privileged native-mcp runtime content.
    _json(root / 'Inbox/release_controller/current.json', {'status':'COMPLETE','phase':'COMPLETE'})
    ha = root / 'Inbox/ha_runtime'; ha.mkdir(parents=True); _json(ha/'current.json', {'seed':1})
    nm = root / 'Inbox/native_mcp_runtime'; nm.mkdir(parents=True); _json(nm/'runtime_guard.json', {'seed':1})

    _call(root, monkeypatch, service.prepare_type2, clearup_id='ClearUp_006')
    _call(root, monkeypatch, service.migrate_type2, clearup_id='ClearUp_006', explicit_user_text='akkoord')

    # The old PM-side filesystem walker is forbidden in 32.5.21. If validate
    # ever falls back to it, this test fails immediately.
    monkeypatch.setattr(service, '_tree_rows_for_validation', lambda *a, **k: (_ for _ in ()).throw(AssertionError('PM-side filesystem validation forbidden')))

    proof = _call(root, monkeypatch, service.validate_type2, clearup_id='ClearUp_006')
    assert proof['status'] == 'GREEN', proof
    assert proof['validation_authority'] == 'privileged_watcher_full_validation'
    assert proof['source_quiescence_authority'] == 'privileged_watcher_double_snapshot'


def test_current_release_identity():
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == '32.5.21'
    assert (PM / 'VERSION.txt').read_text(encoding='utf-8').strip() == '2.0.0-rc54'
