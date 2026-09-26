from pathlib import Path
from types import SimpleNamespace
import sys

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from release_runtime_adapter import NativeRuntimeCoordinator


class _ReadyGuard:
    def __init__(self):
        self.calls = 0

    def probe(self, root):
        self.calls += 1
        return {
            'ready': True,
            'expected_fingerprint': 'a' * 64,
            'runtime_fingerprint': 'a' * 64,
        }


def _state(version='32.5.23', generation='gen-a'):
    return SimpleNamespace(
        release_id=f'{version}:artifact',
        generation=generation,
        artifact_sha256='b' * 64,
        to_version=version,
    )


def test_v32523_ready_native_runtime_still_prepares_control_plane_once_per_fence(tmp_path, monkeypatch):
    guard = _ReadyGuard()
    calls = []

    def prepare():
        calls.append('prepare')
        return {'status': 'GREEN', 'binding_current': True}

    monkeypatch.setattr('tools.release_runtime_adapter.native_mcp_runtime_contract_hotfix.apply', lambda root: {
        'status': 'GREEN', 'command_forwarding_current': True,
    })
    coordinator = NativeRuntimeCoordinator(tmp_path, guard, lambda: True, control_plane_prepare=prepare)
    state = _state()

    first = coordinator.align(state)
    second = coordinator.align(state)

    assert first.status == 'GREEN'
    assert second.status == 'GREEN'
    assert calls == ['prepare']


def test_v32523_new_release_fence_rechecks_control_plane_binding(tmp_path, monkeypatch):
    guard = _ReadyGuard()
    calls = []

    def prepare():
        calls.append('prepare')
        return {'status': 'GREEN', 'binding_current': True}

    monkeypatch.setattr('tools.release_runtime_adapter.native_mcp_runtime_contract_hotfix.apply', lambda root: {
        'status': 'GREEN', 'command_forwarding_current': True,
    })
    coordinator = NativeRuntimeCoordinator(tmp_path, guard, lambda: True, control_plane_prepare=prepare)

    assert coordinator.align(_state(generation='gen-a')).status == 'GREEN'
    assert coordinator.align(_state(generation='gen-b')).status == 'GREEN'
    assert calls == ['prepare', 'prepare']


def test_v32523_prepare_failure_blocks_even_when_native_runtime_is_ready(tmp_path, monkeypatch):
    guard = _ReadyGuard()

    def prepare():
        raise RuntimeError('binding recreate failed')

    monkeypatch.setattr('tools.release_runtime_adapter.native_mcp_runtime_contract_hotfix.apply', lambda root: {
        'status': 'GREEN', 'command_forwarding_current': True,
    })
    coordinator = NativeRuntimeCoordinator(tmp_path, guard, lambda: True, control_plane_prepare=prepare)

    result = coordinator.align(_state())

    assert result.status == 'BLOCKED'
    assert result.reason.startswith('control_plane_prepare_failed:RuntimeError')


def test_v32522_and_older_keep_legacy_ready_shortcut(tmp_path, monkeypatch):
    guard = _ReadyGuard()
    calls = []

    def prepare():
        calls.append('prepare')
        return {'status': 'GREEN', 'binding_current': True}

    monkeypatch.setattr('tools.release_runtime_adapter.native_mcp_runtime_contract_hotfix.apply', lambda root: {
        'status': 'GREEN', 'command_forwarding_current': True,
    })
    coordinator = NativeRuntimeCoordinator(tmp_path, guard, lambda: True, control_plane_prepare=prepare)

    result = coordinator.align(_state(version='32.5.22'))

    assert result.status == 'GREEN'
    assert calls == []
