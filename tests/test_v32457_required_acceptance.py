from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'tools'
APP=ROOT/'slimmemeterportal_import/rootfs/app'
PM=APP/'projectmanager_v2'
for value in (str(TOOLS),str(APP),str(PM)):
    if value not in sys.path:sys.path.insert(0,value)

import atomic_app_swap
from atomic_release_adapter import AtomicReleaseAdapter
from ha_delivery_adapter import HADelivery
from ingress_policy import IncomingItem,decide_incoming
from legacy_install_adoption import adopt_exact_pre57_install
from minimal_release_preflight import verify_candidate
from release_controller import Outcome,ReleaseController,Status
from release_controller_service import ReleaseControllerService
import control_plane_bootstrap
from release_ownership import LegacyOwnershipIndex
from release_runtime_adapter import NativeRuntimeCoordinator
from state_store import StateStore


class GreenAdapter:
    def __init__(self,root:Path|None=None):
        self.root=Path(root) if root is not None else None
        self.calls=[]
    def _green(self,name):
        self.calls.append(name);return Outcome.green(name+':green')
    def pre_target_publication(self,s):return self._green('publish')
    def install(self,s):return self._green('install')
    def runtime_align(self,s):return self._green('runtime')
    def verify_live(self,s):return self._green('verify')
    def atomic_accept(self,s):return self._green('accept')
    def delivery(self,s):
        self.calls.append('delivery')
        if self.root is not None:
            src=self.root/'Inbox/processing'/s.artifact_name
            dst=self.root/'Inbox/processed'/s.artifact_name
            dst.parent.mkdir(parents=True,exist_ok=True)
            if src.is_file():os.replace(src,dst)
        return Outcome.green('delivery:green')
    def rollback(self,s,reason):self.calls.append('rollback');return Outcome.rolled_back('rollback:green')


def _prepared():
    c=ReleaseController()
    s=c.new_state(from_version='32.4.56',to_version='32.4.57',artifact_sha256='a'*64,
                  artifact_name='EnergieProject_v32.4.57.zip')
    c.mark_verified(s,['artifact:green'])
    return c,s


def _complete(c,s,adapter):
    for _ in range(8):
        c.cycle(s,adapter)
        if s.status==Status.COMPLETE.value:return s
    raise AssertionError(f'release did not complete: {s.phase}/{s.status}')


def _release_zip(path:Path,version='32.4.57'):
    payload={'VERSIE.txt':(version+'\n').encode(),'README.md':b'ok\n'}
    manifest={name:hashlib.sha256(data).hexdigest() for name,data in payload.items()}
    path.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(path,'w') as z:
        for name,data in payload.items():z.writestr(name,data)
        z.writestr('MANIFEST.sha256',''.join(f'{digest}  {name}\n' for name,digest in manifest.items()))
        z.writestr('SHA256SUMS.json',json.dumps({'files':[{'path':name,'sha256':digest} for name,digest in manifest.items()]}))


# 1. ZIP -> complete release without terminal.
def test_required_01_single_controller_completes_without_terminal():
    c,s=_prepared();a=GreenAdapter()
    _complete(c,s,a)
    assert s.status=='COMPLETE'
    assert a.calls==['publish','install','runtime','verify','accept','delivery']


# 2. Native MCP mismatch -> automatic allowlisted request/readback -> GREEN.
def test_required_02_native_mcp_mismatch_auto_reload_then_green(tmp_path):
    expected='c'*64
    class Guard:
        def __init__(self):self.calls=0
        def probe(self,root):
            self.calls+=1
            return {'ready':self.calls>=3,'expected_fingerprint':expected,
                    'runtime_fingerprint':expected if self.calls>=3 else 'd'*64}
    c,s=_prepared();guard=Guard();coord=NativeRuntimeCoordinator(tmp_path,guard,lambda:True)
    first=coord.align(s)
    assert first.status=='WAITING' and first.reason=='native_mcp_reload_pending'
    request=json.loads((tmp_path/'Inbox/control_plane/requests/native_mcp_reload.json').read_text())
    result={**{k:request[k] for k in ('request_id','release_id','generation','artifact_sha256','release_version')},
            'status':'GREEN','ok':True,'runtime_fingerprint':expected}
    result_path=tmp_path/'Inbox/control_plane/results/native_mcp_reload.json'
    result_path.parent.mkdir(parents=True,exist_ok=True);result_path.write_text(json.dumps(result))
    second=coord.align(s)
    assert second.status=='GREEN'
    assert not (tmp_path/'Inbox/control_plane/requests/native_mcp_reload.json').exists()


# 3. Stale Control Plane heartbeat is observability only when Docker health and loaded fingerprint are exact.
def test_required_03_stale_control_plane_marker_uses_direct_probe_without_restart(monkeypatch,tmp_path):
    calls=[]
    monkeypatch.setattr(control_plane_bootstrap,'sync_control_plane_source',lambda root:{'changed':[]})
    monkeypatch.setattr(
        control_plane_bootstrap.control_plane_runtime_guard,'probe',
        lambda root,stale_seconds=30:{
            'ready':False,'reason':'runtime_heartbeat_stale',
            'expected_fingerprint':'e'*64,'loaded_fingerprint':'e'*64,
        },
    )
    def fake_request(method,path,ok):
        calls.append((method,path))
        if method=='GET':
            return {'State':{'Running':True,'Health':{'Status':'healthy'}}}
        raise AssertionError('stale exact control-plane runtime must not restart')
    monkeypatch.setattr(control_plane_bootstrap,'_request',fake_request)
    result=control_plane_bootstrap.ensure_control_plane_current(tmp_path)
    assert result['status']=='GREEN'
    assert result['restart_performed'] is False
    assert result['direct_runtime_probe'] is True
    assert [method for method,_path in calls]==['GET']


# 4. Control Plane down -> exactly one bounded blocker; never a recreate/rescue chain.
def test_required_04_control_plane_down_one_blocker(tmp_path):
    class Guard:
        def probe(self,root):return {'ready':False,'expected_fingerprint':'e'*64,'runtime_fingerprint':'f'*64}
    def prepare():
        raise RuntimeError('existing control-plane container is not running')
    _c,s=_prepared()
    result=NativeRuntimeCoordinator(
        tmp_path,Guard(),lambda:False,control_plane_prepare=prepare
    ).align(s)
    assert result.status=='BLOCKED'
    assert result.reason=='control_plane_prepare_failed:RuntimeError'
    assert 'restore existing control-plane capability' in result.required_action


# 5. HA update/start -> direct runtime marker makes delivery current.
def test_required_05_ha_delivery_waits_then_reads_runtime_current(tmp_path):
    artifact=tmp_path/'Inbox/processing/EnergieProject_v32.4.57.zip'
    artifact.parent.mkdir(parents=True);artifact.write_bytes(b'exact')
    sha=hashlib.sha256(artifact.read_bytes()).hexdigest()
    app=tmp_path/'App';app.mkdir();(app/'MANIFEST.sha256').write_text('target')
    rollback=tmp_path/'App.__rollback_32.4.56';rollback.mkdir();(rollback/'MANIFEST.sha256').write_text('source')
    c=ReleaseController();s=c.new_state(from_version='32.4.56',to_version='32.4.57',artifact_sha256=sha,artifact_name=artifact.name)
    s.phase='ACCEPTED';s.status='ACTIVE';s.step=7;s.phase_started_at_epoch=time.time()
    delivery=HADelivery(tmp_path,timeout_seconds=60)
    first=delivery.align(s)
    assert first.status=='WAITING'
    marker=tmp_path/'Inbox/ha_runtime/current.json';marker.parent.mkdir(parents=True,exist_ok=True)
    marker.write_text(json.dumps({'schema':'energie_ha_runtime_v1','version':'32.4.57'}))
    second=delivery.align(s)
    # Runtime version alone is no longer sufficient from 32.4.59 onward.
    # Exact publisher identity evidence + controller-owned contract settlement
    # are required before delivery can become GREEN/Processed.
    assert second.status=='WAITING'
    assert (tmp_path/'Inbox/processing'/artifact.name).is_file()
    assert not (tmp_path/'Inbox/processed'/artifact.name).exists()


# 6. PM may become current later; base acceptance has no PM dependency.
def test_required_06_pm_runtime_not_needed_for_base_controller_acceptance():
    c,s=_prepared();_complete(c,s,GreenAdapter())
    assert s.status=='COMPLETE'


# 7. 50+ MB legacy index is streamed once per migration/index instance.
def test_required_07_legacy_index_50mb_single_load(tmp_path):
    idx_path=tmp_path/'Inbox/projectmanager_v2/RuntimeV2/release_ownership/legacy_index.jsonl'
    idx_path.parent.mkdir(parents=True)
    size=51*1024*1024
    with idx_path.open('wb') as h:
        h.seek(size-2);h.write(b'x\n')
    idx=LegacyOwnershipIndex(tmp_path)
    for n in range(82):
        task={'id':f't{n}','title':f'build release 32.4.{n%56}','goal':'legacy build','next_action':'continue'}
        idx.classify('tasks',task,current_release='32.4.57')
    assert idx_path.stat().st_size>=size
    assert idx.load_passes==1


# 8. CR absent -> release can complete.
def test_required_08_cr_absent_does_not_gate_release(tmp_path):
    assert not (tmp_path/'Backups').exists()
    c,s=_prepared();_complete(c,s,GreenAdapter())
    assert s.status=='COMPLETE'


# 9. CLEARUP debt -> release can complete unless physical install collision exists.
def test_required_09_clearup_debt_does_not_gate_release(tmp_path):
    p=tmp_path/'Inbox/logs/project_clearup_runtime.json';p.parent.mkdir(parents=True)
    p.write_text(json.dumps({'status':'blocked','blockers':['historical_debt']}))
    c,s=_prepared();_complete(c,s,GreenAdapter())
    assert s.status=='COMPLETE'


# 10. Corrupt/missing operating mode is irrelevant to candidate preflight.
def test_required_10_corrupt_mode_file_does_not_gate_preflight(tmp_path):
    (tmp_path/'App').mkdir();(tmp_path/'App/VERSIE.txt').write_text('32.4.56')
    mode=tmp_path/'Inbox/operating_mode/operating_mode_state.json';mode.parent.mkdir(parents=True);mode.write_text('{broken')
    candidate=tmp_path/'Inbox/incoming/EnergieProject_v32.4.57.zip';_release_zip(candidate)
    result=verify_candidate(tmp_path,candidate)
    assert result['ready'] is True


# 11. Old generation/request/result can never satisfy the current release.
def test_required_11_old_release_result_is_not_accepted(tmp_path):
    expected='1'*64
    class Guard:
        def probe(self,root):return {'ready':False,'expected_fingerprint':expected,'runtime_fingerprint':'2'*64}
    _c,s=_prepared()
    stale={'status':'GREEN','ok':True,'request_id':'0'*32,'release_id':s.release_id,
           'generation':'old','artifact_sha256':s.artifact_sha256,'release_version':s.to_version,
           'runtime_fingerprint':expected}
    rp=tmp_path/'Inbox/control_plane/results/native_mcp_reload.json';rp.parent.mkdir(parents=True);rp.write_text(json.dumps(stale))
    result=NativeRuntimeCoordinator(tmp_path,Guard(),lambda:True).align(s)
    assert result.status=='WAITING'
    current=json.loads((tmp_path/'Inbox/control_plane/requests/native_mcp_reload.json').read_text())
    assert current['generation']==s.generation


# 12. Interrupted pre-activation install settles same atomic rollback and removes only candidate.
def test_required_12_interrupted_install_reconciles_same_atomic_rollback(tmp_path):
    app=tmp_path/'App';app.mkdir();(app/'VERSIE.txt').write_text('32.4.56')
    c,s=_prepared();paths=atomic_app_swap.SwapPaths.for_release(tmp_path,'32.4.56','32.4.57')
    paths.candidate.mkdir();(paths.candidate/'VERSIE.txt').write_text('32.4.57')
    atomic_app_swap.write_journal_atomic(paths,state='PREPARED',artifact_sha256=s.artifact_sha256)
    result=AtomicReleaseAdapter(tmp_path,atomic_app_swap,None,None).rollback(s,'interrupted')
    assert result.status=='ROLLED_BACK'
    assert atomic_app_swap.load_journal(paths)['state']=='ROLLED_BACK'
    assert not paths.candidate.exists()
    assert (app/'VERSIE.txt').read_text().strip()=='32.4.56'


# 13. Distinct duplicate Incoming candidates fail closed.
def test_required_13_duplicate_incoming_is_clear_fail_closed():
    a=IncomingItem('a.zip',10,1,'a'*64,True);b=IncomingItem('b.zip',10,1,'b'*64,True)
    decision=decide_incoming([a,b],{})
    assert decision.status=='BLOCKED' and decision.reason=='multiple_distinct_incoming'


# 14. Incomplete copy waits until stable.
def test_required_14_incomplete_copy_waits():
    item=IncomingItem('v57.zip',100,2,'a'*64,True)
    decision=decide_incoming([item],{'v57.zip':(99,1)})
    assert decision.status=='WAITING' and decision.reason=='copy_not_stable'


# 15. Simulated service E2E: one ZIP, no decision/approval/rescue layer, processed + COMPLETE.
# Real NAS/HA live E2E remains a separate post-install acceptance gate and is never inferred from this test.
def test_required_15_simulated_service_e2e_one_zip_zero_extra_approval(tmp_path):
    (tmp_path/'App').mkdir();(tmp_path/'App/VERSIE.txt').write_text('32.4.56')
    candidate=tmp_path/'Inbox/incoming/EnergieProject_v32.4.57.zip';_release_zip(candidate)
    service=ReleaseControllerService(tmp_path,GreenAdapter(tmp_path),stable_polls=2,ingress_stale_seconds=30)
    final=None
    for _ in range(8):
        final=service.cycle()
        if final is not None and final.status=='COMPLETE':break
    assert final is not None and final.status=='COMPLETE'
    assert (tmp_path/'Inbox/processed/EnergieProject_v32.4.57.zip').is_file()
    assert not (tmp_path/'Inbox/projectmanager_v2/RuntimeV2/decisions').exists()
    assert not (tmp_path/'Inbox/control_plane/requests/native_mcp_reload.json').exists()


# 32.4.55 retained: orphan Processing recovers inside the same controller, no recovery daemon.
def test_regression_orphan_processing_without_durable_owner_fails_closed(tmp_path):
    p=tmp_path/'Inbox/processing/orphan.zip';p.parent.mkdir(parents=True);p.write_bytes(b'orphan')
    old=time.time()-120;os.utime(p,(old,old))
    service=ReleaseControllerService(tmp_path,GreenAdapter(),stable_polls=2,ingress_stale_seconds=30)
    result=service._reconcile_idle_processing()
    assert result.status=='BLOCKED'
    assert result.reason=='orphan_processing_unowned_fail_closed'
    assert p.is_file()
    assert not (tmp_path/'Inbox/incoming/orphan.zip').exists()


# 32.4.55 retained: stable corrupt Incoming is quarantined after bounded stale grace.
def test_regression_55_stable_corrupt_incoming_is_quarantined(tmp_path):
    p=tmp_path/'Inbox/incoming/bad.zip';p.parent.mkdir(parents=True);p.write_bytes(b'not-a-zip')
    old=time.time()-120;os.utime(p,(old,old))
    service=ReleaseControllerService(tmp_path,GreenAdapter(),stable_polls=2,ingress_stale_seconds=30)
    first,_=service._incoming_decision();second,candidate=service._incoming_decision()
    assert first.status=='WAITING'
    assert second.reason=='corrupt_candidate_quarantined' and candidate is None
    assert not p.exists()
    assert list((tmp_path/'Inbox/failed/corrupt').glob('*.zip'))



# Hard acceptance: after COMPLETE, the next release can use the same Incoming route immediately.
def test_required_next_release_can_start_after_complete_without_state_reset(tmp_path):
    (tmp_path/'App').mkdir();(tmp_path/'App/VERSIE.txt').write_text('32.4.56')
    class AdvancingAdapter(GreenAdapter):
        def install(self,s):
            self.calls.append('install')
            (self.root/'App/VERSIE.txt').write_text(s.to_version)
            return Outcome.green('install:green')
    adapter=AdvancingAdapter(tmp_path)
    service=ReleaseControllerService(tmp_path,adapter,stable_polls=2,ingress_stale_seconds=30)

    first=tmp_path/'Inbox/incoming/EnergieProject_v32.4.57.zip';_release_zip(first,'32.4.57')
    state=None
    for _ in range(8):
        state=service.cycle()
        if state is not None and state.status=='COMPLETE':break
    assert state is not None and state.status=='COMPLETE' and state.to_version=='32.4.57'

    second=tmp_path/'Inbox/incoming/EnergieProject_v32.4.58.zip';_release_zip(second,'32.4.58')
    next_state=None
    for _ in range(8):
        next_state=service.cycle()
        if next_state is not None and next_state.status=='COMPLETE' and next_state.to_version=='32.4.58':break
    assert next_state is not None
    assert next_state.status=='COMPLETE' and next_state.to_version=='32.4.58'
    persisted=json.loads((tmp_path/'Inbox/release_controller/current.json').read_text())
    assert persisted['to_version']=='32.4.58' and persisted['status']=='COMPLETE'
    assert (tmp_path/'Inbox/processed/EnergieProject_v32.4.57.zip').is_file()
    assert (tmp_path/'Inbox/processed/EnergieProject_v32.4.58.zip').is_file()
