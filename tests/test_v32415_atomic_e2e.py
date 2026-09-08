import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(APP))
sys.path.insert(0, str(PM))

from tools.atomic_app_swap import SwapPaths, perform_swap
from atomic_release_acceptance import finalize_validated_atomic_release
from operating_mode_runtime import _projectmanager_self_audit_check


def _tree(path: Path, version: str, pm_version: str):
    files = {
        'README.md': b'readme\n', 'INSTALL.md': b'install\n', 'CHANGELOG.md': b'changelog\n',
        'repository.yaml': b'name: energie\n', 'VERSIE.txt': f'{version}\n'.encode(), 'SHA256SUMS.json': b'{}\n',
        'slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt': f'{pm_version}\n'.encode(),
        'tools/atomic_app_swap.py': (ROOT / 'tools/atomic_app_swap.py').read_bytes(),
    }
    path.mkdir(parents=True, exist_ok=True)
    for rel, data in files.items():
        target = path / rel; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(data)
    manifest = ''.join(f"{hashlib.sha256(data).hexdigest()}  {rel}\n" for rel, data in sorted(files.items()))
    (path / 'MANIFEST.sha256').write_text(manifest, encoding='utf-8')


def test_32414_to_32415_stale_live_acceptance_can_close_to_accepted(tmp_path):
    root = tmp_path / 'energy'; (root / 'Inbox').mkdir(parents=True)
    paths = SwapPaths.for_release(root, '32.4.14', '32.4.15')
    _tree(paths.app, '32.4.14', '2.0.0-rc11')
    _tree(paths.candidate, '32.4.15', '2.0.0-rc12')
    result = perform_swap(paths, artifact_sha256='synthetic', expected_target_pm_version='2.0.0-rc12')
    assert result['state'] == 'LIVE_ACCEPTANCE'

    runtime = root / 'Inbox/projectmanager_v2/RuntimeV2'
    (runtime / 'self_audit').mkdir(parents=True)
    (runtime / 'status').mkdir(parents=True)
    (runtime / 'self_audit/current.json').write_text(json.dumps({'status': 'GREEN', 'invalid': [], 'warnings': []}), encoding='utf-8')
    (runtime / 'status/current.json').write_text(json.dumps({
        'schema': 'energie_projectmanager_status_v2', 'release': {'version': '32.4.15'},
        'health': {'status': 'RED', 'checks': [{
            'name': 'release_atomic_state', 'status': 'RED', 'reason': 'live_acceptance_blocks_release_ingress',
            'details': {'atomic_swap': {'state': 'LIVE_ACCEPTANCE', 'age_seconds': 2784}},
        }]},
    }), encoding='utf-8')
    stat = (runtime / 'status/current.json').stat()
    os.utime(runtime / 'self_audit/current.json', (stat.st_atime + 1, stat.st_mtime + 1))

    assert _projectmanager_self_audit_check(root)['ok'] is True
    accepted = finalize_validated_atomic_release(root, '32.4.15')
    assert accepted['status'] == 'accepted'
    journal = json.loads((root / 'Inbox/atomic_app_swap_state.json').read_text())
    assert journal['state'] == 'ACCEPTED'
    assert (root / 'App/VERSIE.txt').read_text().strip() == '32.4.15'
    assert (root / 'App.__rollback_32.4.14/VERSIE.txt').read_text().strip() == '32.4.14'
