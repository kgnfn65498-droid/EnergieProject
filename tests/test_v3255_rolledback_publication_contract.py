from __future__ import annotations
import hashlib,json,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];TOOLS=ROOT/'tools'
if str(TOOLS) not in sys.path:sys.path.insert(0,str(TOOLS))
from release_controller import ReleaseController
from ha_delivery_adapter import HADelivery

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def jwrite(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x),encoding='utf-8')
def setup(tmp_path):
    (tmp_path/'App').mkdir();(tmp_path/'App/VERSIE.txt').write_text('32.5.2');(tmp_path/'App/MANIFEST.sha256').write_text('base')
    (tmp_path/'Inbox/processing').mkdir(parents=True);(tmp_path/'Inbox/failed/rolled_back').mkdir(parents=True)
    art=tmp_path/'Inbox/processing/EnergieProject_v32.5.5.zip'
    with zipfile.ZipFile(art,'w') as z:z.writestr('MANIFEST.sha256','new')
    s=ReleaseController().new_state(from_version='32.5.2',to_version='32.5.5',artifact_sha256=sha(art),artifact_name=art.name)
    oldzip=tmp_path/'Inbox/failed/rolled_back/EnergieProject_v32.5.3.rolled_back.zip';oldzip.write_bytes(b'old53');oldsha=sha(oldzip)
    old={'schema':'energie_ha_publication_contract_v2','status':'publication_required','source_stage':'processing_pre_target','version':'32.5.3','repository':'https://github.com/kgnfn65498-droid/EnergieProject','branch':'main','expected_previous_version':'32.5.2','expected_previous_manifest_sha256':sha(tmp_path/'App/MANIFEST.sha256'),'predecessor_version':'32.5.2','predecessor_manifest_sha256':sha(tmp_path/'App/MANIFEST.sha256'),'target_manifest_sha256':'f'*64,'processed_zip':'EnergieProject_v32.5.3.zip','processed_zip_sha256':oldsha,'release_id':'32.5.3:old','generation':'oldgen'}
    jwrite(tmp_path/'Inbox/ha_publication_required.json',old)
    jwrite(tmp_path/'Inbox/atomic_app_swap_state.json',{'state':'ACCEPTED','to_version':'32.5.2'})
    pub=dict(old);pub.update({'published':True,'target_exact':True,'remote_head':'abc'});jwrite(tmp_path/'Inbox/github_publication_state.json',pub)
    return s,old

def test_proven_rolledback_contract_is_preserved_then_replaced(tmp_path):
    s,old=setup(tmp_path);d=HADelivery(tmp_path);payload=d._pre_target_contract(s,d._active_artifact(s));marker=tmp_path/'Inbox/ha_publication_required.json'
    got=d._ensure_contract(s,payload,marker);assert got['version']=='32.5.5';assert json.loads(marker.read_text())['release_id']==s.release_id
    archived=tmp_path/'Inbox/failed/rolled_back/EnergieProject_v32.5.3.publication_contract.json';a=json.loads(archived.read_text());assert a['version']=='32.5.3';assert a['status']=='retired_after_proven_rollback'

def test_foreign_contract_stays_fail_closed_without_exact_rolledback_artifact(tmp_path):
    s,old=setup(tmp_path);(tmp_path/'Inbox/failed/rolled_back/EnergieProject_v32.5.3.rolled_back.zip').write_bytes(b'tampered')
    d=HADelivery(tmp_path);payload=d._pre_target_contract(s,d._active_artifact(s));marker=tmp_path/'Inbox/ha_publication_required.json'
    try:d._ensure_contract(s,payload,marker)
    except RuntimeError as e:assert str(e)=='publication_contract_conflict'
    else:raise AssertionError('foreign contract was not blocked')
    assert json.loads(marker.read_text())['version']=='32.5.3'
