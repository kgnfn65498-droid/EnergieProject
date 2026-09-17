from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
GUARD = ROOT / 'tools/embedded_pm_runtime_guard.py'
for path in (str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _project_source(root: Path) -> Path:
    target = root / 'App/slimmemeterportal_import/rootfs/app/projectmanager_v2'
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PM, target, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    (root / 'App/VERSIE.txt').write_text('32.4.55\n', encoding='utf-8')
    return target


class _StopAfterOne:
    def is_set(self):
        return False

    def wait(self, _seconds):
        return True


def test_embedded_runtime_cycle_persists_loaded_fingerprint_release_and_final_generation(tmp_path: Path):
    source = _project_source(tmp_path)
    embedded = _load(PM / 'embedded_runtime.py', 'pm55_embedded_marker')
    config = SimpleNamespace(
        project_root=str(tmp_path),
        system_root=str(tmp_path / 'Inbox/projectmanager_v2/RuntimeV2'),
        running_release_version='32.4.55',
        manager_app_root=str(source),
    )
    runtime = SimpleNamespace(
        config=config,
        run_once=lambda: {
            'cycle_generation': 'cycle-final-55',
            'provenance': {'generation': 'cycle-final-55', 'phase': 'FINAL'},
        },
    )

    result = embedded.run_embedded(_StopAfterOne(), runtime=runtime, interval_seconds=60)

    assert result == {'state': 'stopped', 'failures': 0}
    marker = json.loads((tmp_path/'Inbox/projectmanager_v2/RuntimeV2/embedded_runtime/current.json').read_text(encoding='utf-8'))
    assert marker['schema'] == 'energie_embedded_pm_runtime_v1'
    assert marker['status'] == 'GREEN'
    assert marker['loaded_runtime_fingerprint'] == embedded.LOADED_RUNTIME_FINGERPRINT
    assert marker['runtime_release_version'] == '32.4.55'
    assert marker['cycle_generation'] == 'cycle-final-55'
    assert marker['provenance'] == {'generation': 'cycle-final-55', 'phase': 'FINAL'}
    assert marker['observed_at_epoch'] > 0


def test_embedded_pm_guard_accepts_exact_loaded_source_release_and_final_generation(tmp_path: Path):
    _project_source(tmp_path)
    guard = _load(GUARD, 'pm55_embedded_guard_green')
    expected = guard.expected_fingerprint(tmp_path)
    marker = tmp_path/'Inbox/projectmanager_v2/RuntimeV2/embedded_runtime/current.json'
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        'schema': 'energie_embedded_pm_runtime_v1',
        'status': 'GREEN',
        'loaded_runtime_fingerprint': expected,
        'runtime_release_version': '32.4.55',
        'cycle_generation': 'g55',
        'provenance': {'generation': 'g55', 'phase': 'FINAL'},
        'observed_at_epoch': 1000.0,
    }), encoding='utf-8')

    result = guard.probe(tmp_path, now=1010.0, stale_seconds=180)

    assert result['status'] == 'GREEN'
    assert result['ready'] is True
    assert result['expected_fingerprint'] == result['loaded_runtime_fingerprint'] == expected
    assert result['release_version'] == '32.4.55'
    assert result['cycle_generation'] == 'g55'


def test_embedded_pm_guard_rejects_stale_loaded_code_even_when_marker_heartbeat_is_fresh(tmp_path: Path):
    source = _project_source(tmp_path)
    guard = _load(GUARD, 'pm55_embedded_guard_stale_code')
    loaded = guard.expected_fingerprint(tmp_path)
    (source/'orchestrator.py').write_text((source/'orchestrator.py').read_text(encoding='utf-8') + '\n# changed source\n', encoding='utf-8')
    marker = tmp_path/'Inbox/projectmanager_v2/RuntimeV2/embedded_runtime/current.json'
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({
        'schema': 'energie_embedded_pm_runtime_v1', 'status': 'GREEN',
        'loaded_runtime_fingerprint': loaded, 'runtime_release_version': '32.4.55',
        'cycle_generation': 'g55', 'provenance': {'generation': 'g55', 'phase': 'FINAL'},
        'observed_at_epoch': 1000.0,
    }), encoding='utf-8')

    result = guard.probe(tmp_path, now=1010.0, stale_seconds=180)

    assert result['ready'] is False
    assert result['status'] == 'RESTART_REQUIRED'
    assert result['reason'] == 'loaded_runtime_fingerprint_mismatch'


def test_embedded_pm_guard_fails_closed_for_missing_stale_wrong_release_or_generation(tmp_path: Path):
    _project_source(tmp_path)
    guard = _load(GUARD, 'pm55_embedded_guard_failures')
    expected = guard.expected_fingerprint(tmp_path)
    marker = tmp_path/'Inbox/projectmanager_v2/RuntimeV2/embedded_runtime/current.json'
    marker.parent.mkdir(parents=True, exist_ok=True)

    missing = guard.probe(tmp_path, now=1000.0, stale_seconds=180)
    assert missing['ready'] is False and missing['reason'] == 'runtime_marker_missing'

    base = {
        'schema': 'energie_embedded_pm_runtime_v1', 'status': 'GREEN',
        'loaded_runtime_fingerprint': expected, 'runtime_release_version': '32.4.55',
        'cycle_generation': 'g55', 'provenance': {'generation': 'g55', 'phase': 'FINAL'},
        'observed_at_epoch': 1000.0,
    }
    marker.write_text(json.dumps({**base, 'observed_at_epoch': 700.0}), encoding='utf-8')
    stale = guard.probe(tmp_path, now=1000.0, stale_seconds=180)
    assert stale['ready'] is False and stale['reason'] == 'runtime_marker_stale'

    marker.write_text(json.dumps({**base, 'runtime_release_version': '32.4.54'}), encoding='utf-8')
    wrong_release = guard.probe(tmp_path, now=1010.0, stale_seconds=180)
    assert wrong_release['ready'] is False and wrong_release['reason'] == 'runtime_release_mismatch'

    marker.write_text(json.dumps({**base, 'provenance': {'generation': 'other', 'phase': 'FINAL'}}), encoding='utf-8')
    wrong_generation = guard.probe(tmp_path, now=1010.0, stale_seconds=180)
    assert wrong_generation['ready'] is False and wrong_generation['reason'] == 'runtime_generation_mismatch'
