import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'; CP_DIR = TOOLS / 'control_plane'
for path in (str(TOOLS), str(CP_DIR)):
    if path not in sys.path: sys.path.insert(0, path)
def _write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + '\n', encoding='utf-8')
def _plane(tmp_path, release, request):
    import control_plane as cp
    inbox=tmp_path/'Inbox'; approved=tmp_path/'approved.json'; version=tmp_path/'VERSIE.txt'; evidence=tmp_path/'RuntimeEvidence'
    approved.write_text('{"items": []}\n'); version.write_text(release+'\n'); evidence.mkdir()
    _write_json(inbox/'control_plane/requests/native_mcp_reload.json', request)
    return cp.ControlPlane(inbox=inbox, approved_queue=approved, version_path=version, runtime_evidence=evidence, host_project_root='/share/Energie_NAS/EnergieProject', docker=object()), inbox
def test_32447_stale_request_is_ignored_before_approval_lookup(tmp_path):
    plane,inbox=_plane(tmp_path,'32.4.47',{'schema':'energie_control_plane_request_v1','request_id':'1'*32,'action':'native_mcp_reload','approved_by':'Peter','decision_id':'old-dec','command_id':'old-cmd','release_version':'32.4.43','expected_fingerprint':'a'*64})
    assert plane.process_once()==[]
    assert not (inbox/'control_plane/results/native_mcp_reload.json').exists()
    assert (inbox/'control_plane/requests/native_mcp_reload.json').exists()
def test_32447_current_request_without_exact_approval_stays_fail_closed(tmp_path):
    plane,inbox=_plane(tmp_path,'32.4.47',{'schema':'energie_control_plane_request_v1','request_id':'2'*32,'action':'native_mcp_reload','approved_by':'Peter','decision_id':'cur-dec','command_id':'cur-cmd','release_version':'32.4.47','expected_fingerprint':'b'*64})
    plane.process_once(); result=json.loads((inbox/'control_plane/results/native_mcp_reload.json').read_text())
    assert result['status']=='RED' and result['ok'] is False and 'geen live Peter-goedkeuring' in result['error']
def test_32447_stale_request_removes_only_non_green_noise(tmp_path):
    plane,inbox=_plane(tmp_path,'32.4.47',{'schema':'energie_control_plane_request_v1','request_id':'3'*32,'action':'native_mcp_reload','approved_by':'Peter','decision_id':'old-dec','command_id':'old-cmd','release_version':'32.4.46','expected_fingerprint':'c'*64})
    rp=inbox/'control_plane/results/native_mcp_reload.json'; _write_json(rp,{'schema':'energie_control_plane_result_v1','action':'native_mcp_reload','status':'RED','ok':False,'error':'stale'})
    plane.process_once(); assert not rp.exists()
