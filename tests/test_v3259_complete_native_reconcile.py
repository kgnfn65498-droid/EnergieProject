from pathlib import Path
import importlib.util

ROOT = Path(__file__).resolve().parents[1]
AUTH = ROOT / 'tools/control_plane/release_scoped_auth.py'

spec = importlib.util.spec_from_file_location('release_scoped_auth_3259', AUTH)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
validate = mod.validate_release_scoped_request


def request():
    return {
        'schema': 'energie_control_plane_release_request_v1',
        'authorization': 'release_controller',
        'action': 'native_mcp_reload',
        'container': 'energie-filesystem-mcp',
        'request_id': 'a' * 32,
        'release_id': '32.5.9:' + 'b' * 12,
        'generation': 'g3259',
        'release_version': '32.5.9',
        'artifact_sha256': 'c' * 64,
        'expected_fingerprint': 'd' * 64,
    }


def state(*, phase='RUNTIME_ALIGNING', status='ACTIVE'):
    return {
        'phase': phase,
        'status': status,
        'release_id': '32.5.9:' + 'b' * 12,
        'generation': 'g3259',
        'to_version': '32.5.9',
        'artifact_sha256': 'c' * 64,
    }


def test_exact_runtime_align_request_is_allowed():
    assert validate(request(), state(), live_version='32.5.9', expected_fingerprint='d' * 64)


def test_exact_complete_same_release_reconcile_is_allowed():
    assert validate(
        request(), state(phase='COMPLETE', status='COMPLETE'),
        live_version='32.5.9', expected_fingerprint='d' * 64,
    )


def test_complete_waiting_state_is_not_a_restart_capability():
    assert not validate(
        request(), state(phase='COMPLETE', status='WAITING'),
        live_version='32.5.9', expected_fingerprint='d' * 64,
    )


def test_complete_wrong_generation_is_rejected():
    bad = request(); bad['generation'] = 'stale-generation'
    assert not validate(
        bad, state(phase='COMPLETE', status='COMPLETE'),
        live_version='32.5.9', expected_fingerprint='d' * 64,
    )


def test_complete_wrong_release_is_rejected():
    bad = request(); bad['release_version'] = '32.5.8'
    assert not validate(
        bad, state(phase='COMPLETE', status='COMPLETE'),
        live_version='32.5.9', expected_fingerprint='d' * 64,
    )


def test_complete_wrong_fingerprint_is_rejected():
    assert not validate(
        request(), state(phase='COMPLETE', status='COMPLETE'),
        live_version='32.5.9', expected_fingerprint='e' * 64,
    )


def test_complete_runtime_mismatch_blocks_next_incoming_candidate(tmp_path):
    import sys, json
    TOOLS = ROOT / 'tools'
    sys.path.insert(0, str(TOOLS))
    from release_controller_service import ReleaseControllerService
    from release_controller import ReleaseState, Outcome

    (tmp_path / 'App').mkdir(parents=True)
    (tmp_path / 'App/VERSIE.txt').write_text('32.5.9\n', encoding='utf-8')
    for rel in ('Inbox/incoming','Inbox/processing','Inbox/processed','Inbox/failed','Inbox/release_controller'):
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)
    candidate = tmp_path / 'Inbox/incoming/EnergieProject_v32.5.10.zip'
    candidate.write_bytes(b'candidate-must-stay-unclaimed')

    state = ReleaseState(
        release_id='32.5.9:' + 'b' * 12,
        generation='g3259',
        from_version='32.5.8',
        to_version='32.5.9',
        artifact_sha256='c' * 64,
        artifact_name='EnergieProject_v32.5.9.zip',
        phase='COMPLETE', status='COMPLETE', step=9, total=9,
        started_at_epoch=1.0, phase_started_at_epoch=1.0, updated_at_epoch=1.0,
        evidence=[],
    )

    class Adapter:
        def reconcile_completed_native_runtime(self, _state):
            return Outcome.waiting('native_mcp_reload_pending', 'native_mcp_reload_requested')

    service = ReleaseControllerService(tmp_path, Adapter(), stable_polls=2)
    service.store.save(state.to_dict())
    returned = service.cycle()
    assert returned.status == 'COMPLETE'
    assert candidate.is_file()
    assert not (tmp_path / 'Inbox/processing/EnergieProject_v32.5.10.zip').exists()
    runtime = json.loads((tmp_path / 'Inbox/release_controller/runtime.json').read_text())
    assert runtime['status'] == 'WAITING'
    assert runtime['phase'] == 'COMPLETE'
    assert runtime['reason'] == 'native_mcp_reload_pending'


def _write_valid_release_zip(path: Path, version: str) -> None:
    import hashlib, json, zipfile
    payload = {
        'VERSIE.txt': (version + '\n').encode(),
        'README.md': b'regression candidate\n',
        'INSTALL.md': b'regression candidate\n',
        'CHANGELOG.md': b'regression candidate\n',
        'repository.yaml': b'name: EnergieProject\n',
        'slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt': b'2.0.0-rc45\n',
    }
    hashes = {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()}
    manifest = ''.join(f'{sha}  {name}\n' for name, sha in hashes.items()).encode()
    sums = json.dumps({'files':[{'path':name,'sha256':sha} for name,sha in hashes.items()]}, indent=2).encode()+b'\n'
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in payload.items(): z.writestr(name, data)
        z.writestr('MANIFEST.sha256', manifest)
        z.writestr('SHA256SUMS.json', sums)


def test_predecessor_3258_complete_mismatch_reconciles_then_3259_is_claimed(tmp_path, monkeypatch):
    import json, sys
    TOOLS = ROOT / 'tools'
    sys.path.insert(0, str(TOOLS))
    import release_controller_service as rcs
    from release_controller_service import ReleaseControllerService
    from release_controller import ReleaseState, Outcome

    (tmp_path / 'App').mkdir(parents=True)
    (tmp_path / 'App/VERSIE.txt').write_text('32.5.8\n', encoding='utf-8')
    for rel in ('Inbox/incoming','Inbox/processing','Inbox/processed','Inbox/failed','Inbox/release_controller'):
        (tmp_path / rel).mkdir(parents=True, exist_ok=True)
    candidate = tmp_path / 'Inbox/incoming/EnergieProject_v32.5.9.zip'
    _write_valid_release_zip(candidate, '32.5.9')

    predecessor = ReleaseState(
        release_id='32.5.8:' + '8' * 12,
        generation='g3258',
        from_version='32.5.7',
        to_version='32.5.8',
        artifact_sha256='8' * 64,
        artifact_name='EnergieProject_v32.5.8.zip',
        phase='COMPLETE', status='COMPLETE', step=9, total=9,
        started_at_epoch=1.0, phase_started_at_epoch=1.0, updated_at_epoch=1.0,
        evidence=[],
    )

    class Adapter:
        def __init__(self): self.native_calls = 0
        def reconcile_completed_native_runtime(self, state):
            assert state.to_version == '32.5.8'
            self.native_calls += 1
            if self.native_calls == 1:
                return Outcome.waiting('native_mcp_reload_pending', 'exact_3258_complete_reconcile_requested')
            return Outcome.green('native_mcp_runtime_exact_3258')
        def reconcile_completed_delivery(self, state):
            return Outcome.green('delivery_settled')

    adapter=Adapter()
    monkeypatch.setattr(rcs, 'write_post_live_audit', lambda root, state: {'status':'GREEN'})
    service = ReleaseControllerService(tmp_path, adapter, stable_polls=2)
    service.store.save(predecessor.to_dict())

    # First cycle: predecessor mismatch keeps the next artifact safely unclaimed.
    returned = service.cycle()
    assert returned.to_version == '32.5.8' and returned.status == 'COMPLETE'
    assert candidate.is_file()
    assert not (tmp_path/'Inbox/processing/EnergieProject_v32.5.9.zip').exists()
    runtime=json.loads((tmp_path/'Inbox/release_controller/runtime.json').read_text())
    assert runtime['status']=='WAITING' and runtime['reason']=='native_mcp_reload_pending'

    # Second cycle: exact COMPLETE reconciliation turns GREEN; first ingress poll
    # only establishes copy stability and still does not claim prematurely.
    service.cycle()
    assert candidate.is_file()
    runtime=json.loads((tmp_path/'Inbox/release_controller/runtime.json').read_text())
    assert runtime['status']=='WAITING' and runtime['reason']=='copy_not_stable'

    # Third cycle: same integral ZIP is stable, verified and atomically claimed.
    current=service.cycle()
    claimed=tmp_path/'Inbox/processing/EnergieProject_v32.5.9.zip'
    assert not candidate.exists()
    assert claimed.is_file()
    assert current.to_version=='32.5.9'
    assert current.from_version=='32.5.8'
    assert current.phase=='PUBLISHING'
    assert current.status=='ACTIVE'
    assert current.artifact_name=='EnergieProject_v32.5.9.zip'
