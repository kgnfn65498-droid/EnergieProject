import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for p in (str(APP), str(PM)):
    if p not in sys.path:
        sys.path.insert(0, p)

from release_transition import ReleaseTransitionCoordinator, TransitionBlocked


def _root(tmp_path: Path) -> Path:
    root = tmp_path / 'project'
    (root / 'App').mkdir(parents=True)
    (root / 'App/VERSIE.txt').write_text('32.4.54\n', encoding='utf-8')
    return root


def _evil_state(path: Path):
    path.write_text(json.dumps({
        'schema_version': 1,
        'generation_id': 'evil',
        'revision': 7,
        'from_release': '32.4.53',
        'to_release': '32.4.54',
        'lifecycle_state': 'ACTIVE',
        'phase': 'LIVE_PROVEN',
        'phase_status': 'GREEN',
    }), encoding='utf-8')


def test_transition_load_rejects_current_json_symlink(tmp_path):
    root = _root(tmp_path)
    coord = ReleaseTransitionCoordinator(root)
    external = tmp_path / 'external.json'
    _evil_state(external)
    coord.path.parent.mkdir(parents=True, exist_ok=True)
    coord.path.symlink_to(external)
    with pytest.raises(TransitionBlocked, match='transition state .*symlink'):
        coord.load()


def test_legacy_bootstrap_rejects_current_json_symlink_before_using_external_state(tmp_path):
    root = _root(tmp_path)
    coord = ReleaseTransitionCoordinator(root)
    external = tmp_path / 'external.json'
    _evil_state(external)
    coord.path.parent.mkdir(parents=True, exist_ok=True)
    coord.path.symlink_to(external)
    with pytest.raises(TransitionBlocked):
        coord.bootstrap_legacy_if_needed()


def test_worker_rejects_symlink_transition_state(tmp_path):
    root = _root(tmp_path)
    coord = ReleaseTransitionCoordinator(root)
    external = tmp_path / 'external.json'
    _evil_state(external)
    coord.path.parent.mkdir(parents=True, exist_ok=True)
    coord.path.symlink_to(external)
    from release_transition_worker import ReleaseTransitionWorker
    worker = ReleaseTransitionWorker(root, object())
    with pytest.raises(TransitionBlocked):
        worker.run_once()


def test_mode_web_fails_closed_on_symlink_transition_state(tmp_path):
    root = _root(tmp_path)
    external = tmp_path / 'external.json'
    _evil_state(external)
    state = root / 'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json'
    state.parent.mkdir(parents=True, exist_ok=True)
    state.symlink_to(external)
    import operating_mode_web
    with pytest.raises(RuntimeError, match='transition state'):
        operating_mode_web._active_release_transition(root)


def test_auto_hold_fails_closed_on_symlink_transition_state(tmp_path):
    root = _root(tmp_path)
    external = tmp_path / 'external.json'
    _evil_state(external)
    state = root / 'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json'
    state.parent.mkdir(parents=True, exist_ok=True)
    state.symlink_to(external)
    import operating_mode_auto_release
    result = operating_mode_auto_release.automatic_release_hold_once(object(), root, '32.4.54')
    assert result['status'] == 'transition_invalid'
    assert result['fail_closed'] is True


def test_mode_processor_does_not_follow_symlink_transition_state(tmp_path):
    root = _root(tmp_path)
    external = tmp_path / 'external.json'
    _evil_state(external)
    state = root / 'Inbox/projectmanager_v2/RuntimeV2/release_transition/current.json'
    state.parent.mkdir(parents=True, exist_ok=True)
    state.symlink_to(external)
    import operating_modes
    with pytest.raises(RuntimeError, match='transition state'):
        operating_modes._active_release_transition(root)


def test_handover_optional_transition_read_does_not_follow_symlink(tmp_path):
    root = _root(tmp_path)
    runtime = root / 'Inbox/projectmanager_v2/RuntimeV2'
    external = tmp_path / 'external.json'
    _evil_state(external)
    state = runtime / 'release_transition/current.json'
    state.parent.mkdir(parents=True, exist_ok=True)
    state.symlink_to(external)
    from handover_snapshot import HandoverSnapshotService
    svc = HandoverSnapshotService(runtime, project_root=root)
    with pytest.raises(RuntimeError, match='transition state'):
        svc._load_optional_dict('release_transition/current.json')
