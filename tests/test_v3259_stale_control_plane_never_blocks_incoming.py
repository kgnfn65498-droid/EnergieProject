from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
sys.path.insert(0, str(TOOLS))

from release_controller import ReleaseState
from release_runtime_adapter import NativeRuntimeCoordinator


def _state():
    return ReleaseState(
        release_id='32.5.9:newrelease0001', generation='gen-new',
        from_version='32.5.8', to_version='32.5.9', artifact_sha256='a'*64,
        artifact_name='EnergieProject_v32.5.9.zip', phase='RUNTIME_ALIGNING',
        status='ACTIVE', step=7, total=9, started_at_epoch=1.0,
        phase_started_at_epoch=1.0, updated_at_epoch=1.0, evidence=[])


class GuardMismatch:
    @staticmethod
    def probe(root):
        return {'ready': False, 'expected_fingerprint': 'b'*64}


def test_stale_previous_release_request_is_archived_and_replaced(tmp_path, monkeypatch):
    (tmp_path/'App').mkdir(parents=True)
    (tmp_path/'App/VERSIE.txt').write_text('32.5.9\n')
    request_path=tmp_path/'Inbox/control_plane/requests/native_mcp_reload.json'
    request_path.parent.mkdir(parents=True)
    stale={
        'schema':'energie_control_plane_release_request_v1','authorization':'release_controller',
        'action':'native_mcp_reload','container':'energie-filesystem-mcp',
        'request_id':'1'*32,'release_id':'32.5.8:old','generation':'old-gen',
        'release_version':'32.5.8','artifact_sha256':'2'*64,'expected_fingerprint':'3'*64,
    }
    request_path.write_text(json.dumps(stale))
    monkeypatch.setattr('release_runtime_adapter.native_mcp_runtime_contract_hotfix.apply',
                        lambda root:{'status':'GREEN','command_forwarding_current':True})
    c=NativeRuntimeCoordinator(tmp_path,GuardMismatch,lambda:True)
    out=c.align(_state())
    assert out.status == 'WAITING'
    now=json.loads(request_path.read_text())
    assert now['release_version']=='32.5.9'
    assert now['release_id']=='32.5.9:newrelease0001'
    archive=tmp_path/'Inbox/projectmanager_v2/RuntimeV2/control_plane_archive'
    rows=list(archive.glob('native_mcp_reload.stale.32.5.8.*.json'))
    assert len(rows)==1 and json.loads(rows[0].read_text())==stale


def test_same_current_fence_different_request_remains_fail_closed(tmp_path, monkeypatch):
    (tmp_path/'App').mkdir(parents=True)
    (tmp_path/'App/VERSIE.txt').write_text('32.5.9\n')
    request_path=tmp_path/'Inbox/control_plane/requests/native_mcp_reload.json'
    request_path.parent.mkdir(parents=True)
    current={
        'schema':'energie_control_plane_release_request_v1','authorization':'release_controller',
        'action':'native_mcp_reload','container':'energie-filesystem-mcp',
        'request_id':'f'*32,'release_id':'32.5.9:newrelease0001','generation':'gen-new',
        'release_version':'32.5.9','artifact_sha256':'a'*64,'expected_fingerprint':'c'*64,
    }
    request_path.write_text(json.dumps(current))
    monkeypatch.setattr('release_runtime_adapter.native_mcp_runtime_contract_hotfix.apply',
                        lambda root:{'status':'GREEN','command_forwarding_current':True})
    c=NativeRuntimeCoordinator(tmp_path,GuardMismatch,lambda:True)
    out=c.align(_state())
    assert out.status == 'BLOCKED'
    assert out.reason == 'native_mcp_request_conflict'
    assert json.loads(request_path.read_text())==current
