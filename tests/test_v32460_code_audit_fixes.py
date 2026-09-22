from __future__ import annotations

import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / "slimmemeterportal_import/rootfs/app/projectmanager_v2/release_controller_state.py"
BOOTSTRAP = ROOT / "tools/bootstrap_release_watcher_container.sh"


def _load_state_module():
    spec = importlib.util.spec_from_file_location("release_controller_state_v32460", STATE)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_projectmanager_accepts_publishing_release_controller_phase(tmp_path: Path):
    module = _load_state_module()
    state_path = tmp_path / "Inbox/release_controller/current.json"
    state_path.parent.mkdir(parents=True)
    payload = {
        "release_id": "32.4.60:test",
        "generation": "g-test",
        "from_version": "32.4.59",
        "to_version": "32.4.60",
        "artifact_sha256": "a" * 64,
        "phase": "PUBLISHING",
        "status": "ACTIVE",
    }
    state_path.write_text(json.dumps(payload), encoding="utf-8")
    assert module.load_release_controller_state(tmp_path)["phase"] == "PUBLISHING"


def test_watcher_bootstrap_does_not_gate_release_startup_on_nas_cr_capability():
    source = BOOTSTRAP.read_text(encoding="utf-8")
    forbidden = (
        "NAS_CR_LOCAL_DIR=",
        "NAS_CR_OPERATION_LOCK=",
        "ensure_nas_cr_mailbox_contract",
        "ensure_nas_cr_operation_lock_contract",
        "CAPABILITY_MARKER=",
        "CAPABILITY_READY=",
        "NAS Container CR lokale capability werd niet GREEN",
        'chmod 0777 "$NAS_CR_LOCAL_DIR"',
        'chmod 0666 "$NAS_CR_OPERATION_LOCK"',
    )
    for token in forbidden:
        assert token not in source
    # The watcher container contract remains mandatory.
    assert 'CONTRACT_MARKER="$INBOX/watcher_container_contract.json"' in source
    assert 'watcher container-contract v3 is GREEN' in source


def test_60_withdrawn_same_transition_rolled_back_journal_does_not_block_replacement(tmp_path):
    import json
    import sys
    from pathlib import Path

    tools = Path(__file__).resolve().parents[1] / 'tools'
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))

    import atomic_app_swap
    from atomic_release_adapter import AtomicReleaseAdapter
    from release_controller import ReleaseController

    root = tmp_path / 'energy'
    app = root / 'App'
    app.mkdir(parents=True)
    (app / 'VERSIE.txt').write_text('32.4.59\n', encoding='utf-8')

    paths = atomic_app_swap.SwapPaths.for_release(root, '32.4.59', '32.4.60')
    atomic_app_swap.write_journal_atomic(paths, state='ROLLED_BACK', artifact_sha256='a' * 64,
                                         error='withdrawn previous candidate')

    state = ReleaseController().new_state(
        from_version='32.4.59', to_version='32.4.60', artifact_sha256='b' * 64,
        artifact_name='EnergieProject_v32.4.60.zip',
    )
    adapter = AtomicReleaseAdapter(root, atomic_app_swap, None, None)

    # A fully settled ROLLED_BACK journal for a different, withdrawn artifact of
    # the same transition is historical evidence, not an active ownership claim.
    assert adapter._journal(state) is None
    raw = json.loads((root / 'Inbox/atomic_app_swap_state.json').read_text(encoding='utf-8'))
    assert raw['state'] == 'ROLLED_BACK'
    assert raw['artifact_sha256'] == 'a' * 64
    assert (root / 'App/VERSIE.txt').read_text(encoding='utf-8').strip() == '32.4.59'


def test_60_withdrawn_same_transition_stays_fail_closed_if_filesystem_not_settled(tmp_path):
    import sys
    from pathlib import Path

    tools = Path(__file__).resolve().parents[1] / 'tools'
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))

    import atomic_app_swap
    from atomic_release_adapter import AtomicReleaseAdapter
    from release_controller import ReleaseController

    root = tmp_path / 'energy'
    app = root / 'App'
    app.mkdir(parents=True)
    (app / 'VERSIE.txt').write_text('32.4.59\n', encoding='utf-8')

    paths = atomic_app_swap.SwapPaths.for_release(root, '32.4.59', '32.4.60')
    atomic_app_swap.write_journal_atomic(paths, state='ROLLED_BACK', artifact_sha256='a' * 64,
                                         error='withdrawn previous candidate')
    paths.candidate.mkdir()

    state = ReleaseController().new_state(
        from_version='32.4.59', to_version='32.4.60', artifact_sha256='b' * 64,
        artifact_name='EnergieProject_v32.4.60.zip',
    )
    adapter = AtomicReleaseAdapter(root, atomic_app_swap, None, None)

    try:
        adapter._journal(state)
    except RuntimeError as exc:
        assert 'atomic_artifact_mismatch' in str(exc)
    else:
        raise AssertionError('same-transition replacement must stay fail-closed while candidate residue exists')


def test_60_replacement_install_overwrites_settled_withdrawn_journal_with_new_identity(tmp_path):
    import hashlib
    import json
    import sys
    import zipfile
    from pathlib import Path

    tools = Path(__file__).resolve().parents[1] / 'tools'
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))

    import atomic_app_swap
    from atomic_release_adapter import AtomicReleaseAdapter
    from release_controller import ReleaseController

    def sha(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    root = tmp_path / 'energy'
    app = root / 'App'
    (app / 'slimmemeterportal_import/rootfs/app/projectmanager_v2').mkdir(parents=True)
    (app / 'VERSIE.txt').write_text('32.4.59\n', encoding='utf-8')
    (app / 'slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt').write_text('2.0.0-rc59\n', encoding='utf-8')
    (root / 'Inbox/processing').mkdir(parents=True)

    paths = atomic_app_swap.SwapPaths.for_release(root, '32.4.59', '32.4.60')
    atomic_app_swap.write_journal_atomic(paths, state='ROLLED_BACK', artifact_sha256='a' * 64,
                                         error='withdrawn previous candidate')

    payload = {
        'README.md': b'readme\n',
        'INSTALL.md': b'install\n',
        'CHANGELOG.md': b'changelog\n',
        'repository.yaml': b'name: energie\n',
        'VERSIE.txt': b'32.4.60\n',
        'SHA256SUMS.json': b'{}\n',
        'slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt': b'2.0.0-rc60\n',
    }
    payload['MANIFEST.sha256'] = ''.join(
        f"{sha(data)}  {name}\n" for name, data in sorted(payload.items())
    ).encode()
    artifact = root / 'Inbox/processing/EnergieProject_v32.4.60.zip'
    with zipfile.ZipFile(artifact, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        for name, data in payload.items():
            z.writestr(name, data)
    artifact_sha = hashlib.sha256(artifact.read_bytes()).hexdigest()

    state = ReleaseController().new_state(
        from_version='32.4.59', to_version='32.4.60', artifact_sha256=artifact_sha,
        artifact_name=artifact.name,
    )
    adapter = AtomicReleaseAdapter(root, atomic_app_swap, None, None)

    outcome = adapter.install(state)
    assert outcome.status == 'GREEN'
    assert (root / 'App/VERSIE.txt').read_text(encoding='utf-8').strip() == '32.4.60'
    journal = json.loads((root / 'Inbox/atomic_app_swap_state.json').read_text(encoding='utf-8'))
    assert journal['artifact_sha256'] == artifact_sha
    assert journal['state'] == 'LIVE_ACCEPTANCE'
    assert (root / 'App.__rollback_32.4.59/VERSIE.txt').read_text(encoding='utf-8').strip() == '32.4.59'


def test_60_withdrawn_same_transition_exception_is_strictly_fenced(tmp_path):
    import json
    import sys
    from pathlib import Path

    tools = Path(__file__).resolve().parents[1] / 'tools'
    if str(tools) not in sys.path:
        sys.path.insert(0, str(tools))

    import atomic_app_swap
    from atomic_release_adapter import AtomicReleaseAdapter
    from release_controller import ReleaseController

    def make_root(name: str):
        root = tmp_path / name
        app = root / 'App'
        app.mkdir(parents=True)
        (app / 'VERSIE.txt').write_text('32.4.59\n', encoding='utf-8')
        paths = atomic_app_swap.SwapPaths.for_release(root, '32.4.59', '32.4.60')
        atomic_app_swap.write_journal_atomic(paths, state='ROLLED_BACK', artifact_sha256='a' * 64,
                                             error='withdrawn previous candidate')
        state = ReleaseController().new_state(
            from_version='32.4.59', to_version='32.4.60', artifact_sha256='b' * 64,
            artifact_name='EnergieProject_v32.4.60.zip',
        )
        return root, paths, state

    cases = []

    root, paths, state = make_root('rollback-residue')
    paths.rollback.mkdir()
    cases.append((root, state))

    root, paths, state = make_root('wrong-active')
    (paths.app / 'VERSIE.txt').write_text('32.4.58\n', encoding='utf-8')
    cases.append((root, state))

    root, paths, state = make_root('wrong-journal-path')
    raw = json.loads(paths.journal.read_text(encoding='utf-8'))
    raw['candidate_path'] = 'App.__candidate_WRONG'
    paths.journal.write_text(json.dumps(raw), encoding='utf-8')
    cases.append((root, state))

    root, paths, state = make_root('malformed-old-sha')
    raw = json.loads(paths.journal.read_text(encoding='utf-8'))
    raw['artifact_sha256'] = 'not-a-sha'
    paths.journal.write_text(json.dumps(raw), encoding='utf-8')
    cases.append((root, state))

    for root, state in cases:
        adapter = AtomicReleaseAdapter(root, atomic_app_swap, None, None)
        try:
            adapter._journal(state)
        except RuntimeError as exc:
            assert 'atomic_artifact_mismatch' in str(exc)
        else:
            raise AssertionError(f'unsafe withdrawn-journal state was accepted: {root.name}')
