import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
TOOLS = ROOT / 'tools'
for path in (str(APP), str(PM), str(TOOLS)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def test_32446_stale_native_reload_archives_under_writable_system_runtime_evidence(tmp_path):
    from protected_action_executor import ProtectedActionExecutor

    project = tmp_path / 'project'
    (project / 'App').mkdir(parents=True)
    (project / 'App/VERSIE.txt').write_text('32.4.46\n', encoding='utf-8')
    _write_json(project / 'Inbox/native_mcp_runtime/runtime_guard.json', {
        'status': 'RELOAD_REQUIRED', 'ready': False, 'reload_required': True,
        'expected_fingerprint': 'a' * 64, 'runtime_fingerprint': 'b' * 64,
    })
    stale = project / 'Inbox/control_plane/requests/native_mcp_reload.json'
    _write_json(stale, {
        'schema': 'energie_control_plane_request_v1', 'request_id': '1' * 32,
        'action': 'native_mcp_reload', 'approved_by': 'Peter',
        'decision_id': 'old-decision', 'command_id': 'old-command',
        'release_version': '32.4.45', 'expected_fingerprint': 'c' * 64,
    })

    executor = ProtectedActionExecutor(project, None, None, None)
    action = {'id': 'action-46', 'command_id': 'cmd46', 'decision_id': 'dec46'}
    command = {'id': 'cmd46', 'approval_decision_id': 'dec46', 'release_version': '32.4.46'}
    decision = {
        'id': 'dec46', 'status': 'APPROVED', 'approved_by': 'Peter', 'kind': 'PRODUCTION_RESTART',
        'context': {'command_id': 'cmd46', 'intent': 'native_mcp_reload', 'release_version': '32.4.46'},
    }
    result = executor._queue_native_mcp_reload(action, command, decision)

    current = json.loads(stale.read_text(encoding='utf-8'))
    assert result['restart_queued'] is True
    assert current['release_version'] == '32.4.46'
    archive_root = project / 'Inbox/projectmanager_v2/RuntimeV2/control_plane_archive'
    archives = list(archive_root.glob('native_mcp_reload.32.4.45.*.json'))
    assert len(archives) == 1
    assert json.loads(archives[0].read_text(encoding='utf-8'))['request_id'] == '1' * 32
    assert not (project / 'Inbox/control_plane/archive').exists()


def test_32446_native_approval_tool_is_exact_pending_ingress_and_security_gated():
    import native_mcp_runtime_contract_hotfix as hotfix

    source = (
        'from pathlib import Path\nimport os\nimport json\nfrom uuid import uuid4\n'
        'from registry import mcp\nREAD_ONLY_ANNOTATIONS = {}\nWRITE_ANNOTATIONS = {}\n'
        'RUNTIME_ROOT = Path("/project/Inbox/projectmanager_v2/RuntimeV2")\n'
        'def _write_immutable(root, envelope, *, max_bytes): return envelope["id"]\n'
        '# Remote decision resolution, direct deploy/purchase/payment and arbitrary\n'
        '# RuntimeV2 writes are deliberately absent. Protected approval stays local HA.\n'
    )
    transformed, changed, reason = hotfix._ensure_approval_tool(source)
    assert changed is True
    assert reason == 'approval_tool_added'
    assert 'PM_APPROVAL_TOOL_VERSION=2026-09-12.v3' in transformed
    assert 'def projectmanager_submit_approval(' in transformed
    assert "item.get('status') == 'PENDING'" in transformed
    assert "decision_id == decision_id" not in transformed  # no tautological match
    assert "item.get('id') == decision_id" in transformed
    assert "token not in allowed" in transformed
    assert "approved_by': 'Peter'" in transformed
    assert '_write_immutable(APPROVAL_INGRESS_ROOT' in transformed
    assert 'PM_REMOTE_APPROVAL_ENABLED' in transformed
    assert 'Remote approval is fail-closed until secured edge is enabled.' in transformed
    assert '.resolve(' not in transformed[transformed.index('def projectmanager_submit_approval('):]
