from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; TOOLS=ROOT/'tools'
if str(TOOLS) not in sys.path: sys.path.insert(0,str(TOOLS))
from release_controller import ReleaseController,Phase,Status
from ha_delivery_adapter import HADelivery
import release_controller_service as rcs

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def state(root):
    c=ReleaseController(); s=c.new_state(from_version='32.4.58',to_version='32.4.59',artifact_sha256='a'*64,artifact_name='EnergieProject_v32.4.59.zip');s.phase=Phase.ACCEPTED.value;s.status=Status.ACTIVE.value;s.step=7;return s

def layout(root,s):
    (root/'Inbox/processing').mkdir(parents=True); (root/'Inbox/ha_runtime').mkdir(parents=True)
    (root/'Inbox/processing'/s.artifact_name).write_bytes(b'x')
    s.artifact_sha256=sha(root/'Inbox/processing'/s.artifact_name)
    (root/'App').mkdir();(root/'App/MANIFEST.sha256').write_text('target')
    rb=root/f'App.__rollback_{s.from_version}';rb.mkdir();(rb/'MANIFEST.sha256').write_text('previous')

def contract(delivery,s): return delivery._contract(s, delivery._active_artifact(s))
def pub(root,s,payload):
    (root/'Inbox/github_publication_state.json').write_text(json.dumps({
      'published':True,'target_exact':True,'version':s.to_version,'release_id':s.release_id,'generation':s.generation,
      'processed_zip':s.artifact_name,'processed_zip_sha256':s.artifact_sha256,
      'target_manifest_sha256':payload['target_manifest_sha256'],'remote_head':'deadbeef','publication_contract_removed':False}))

def test_completed_release_with_matching_ha_but_open_publication_contract_is_not_delivery_green(tmp_path):
    s=state(tmp_path);layout(tmp_path,s);d=HADelivery(tmp_path);p=contract(d,s);(tmp_path/'Inbox/ha_publication_required.json').write_text(json.dumps(p));(tmp_path/'Inbox/ha_runtime/current.json').write_text(json.dumps({'version':s.to_version}))
    out=d.align(s);assert out.status!='GREEN';assert (tmp_path/'Inbox/processing'/s.artifact_name).is_file();assert not (tmp_path/'Inbox/processed'/s.artifact_name).exists()

def test_publication_result_must_match_release_id_generation_artifact_and_manifest(tmp_path):
    s=state(tmp_path);layout(tmp_path,s);d=HADelivery(tmp_path);p=contract(d,s);(tmp_path/'Inbox/ha_publication_required.json').write_text(json.dumps(p));(tmp_path/'Inbox/ha_runtime/current.json').write_text(json.dumps({'version':s.to_version}));pub(tmp_path,s,p)
    q=json.loads((tmp_path/'Inbox/github_publication_state.json').read_text());q['generation']='foreign';(tmp_path/'Inbox/github_publication_state.json').write_text(json.dumps(q))
    assert d.align(s).status!='GREEN';assert (tmp_path/'Inbox/ha_publication_required.json').exists()

def test_completed_release_settles_exact_owned_publication_contract_before_processed(tmp_path):
    s=state(tmp_path);layout(tmp_path,s);d=HADelivery(tmp_path);p=contract(d,s);(tmp_path/'Inbox/ha_publication_required.json').write_text(json.dumps(p));(tmp_path/'Inbox/ha_runtime/current.json').write_text(json.dumps({'version':s.to_version}));pub(tmp_path,s,p)
    out=d.align(s);assert out.status=='GREEN';assert not (tmp_path/'Inbox/ha_publication_required.json').exists();assert not (tmp_path/'Inbox/processing'/s.artifact_name).exists();assert (tmp_path/'Inbox/processed'/s.artifact_name).is_file()

def test_completed_release_does_not_remove_foreign_or_unproven_contract(tmp_path):
    s=state(tmp_path);layout(tmp_path,s);d=HADelivery(tmp_path);p=contract(d,s);p['generation']='foreign';(tmp_path/'Inbox/ha_publication_required.json').write_text(json.dumps(p));(tmp_path/'Inbox/ha_runtime/current.json').write_text(json.dumps({'version':s.to_version}));out=d.align(s);assert out.status=='BLOCKED';assert (tmp_path/'Inbox/ha_publication_required.json').exists()

def test_next_release_can_create_publication_contract_after_predecessor_complete(tmp_path):
    s=state(tmp_path);layout(tmp_path,s);d=HADelivery(tmp_path);p=contract(d,s);(tmp_path/'Inbox/ha_publication_required.json').write_text(json.dumps(p));(tmp_path/'Inbox/ha_runtime/current.json').write_text(json.dumps({'version':s.to_version}));pub(tmp_path,s,p);assert d.align(s).status=='GREEN';assert not (tmp_path/'Inbox/ha_publication_required.json').exists()

def test_processed_means_complete_not_merely_atomic_accepted(tmp_path):
    s=state(tmp_path);layout(tmp_path,s);d=HADelivery(tmp_path);out=d.align(s);assert out.status!='GREEN';assert (tmp_path/'Inbox/processing'/s.artifact_name).exists();assert not (tmp_path/'Inbox/processed'/s.artifact_name).exists()

def test_repository_contains_exactly_one_home_assistant_config_yaml():
    assert [p for p in ROOT.rglob('config.yaml') if '.pytest_cache' not in p.parts]==[ROOT/'slimmemeterportal_import/config.yaml']
def test_legacy57_fixture_uses_config_legacy57_yaml():
    assert (ROOT/'tests/fixtures/legacy57/config_legacy57.yaml').is_file();assert not (ROOT/'tests/fixtures/legacy57/config.yaml').exists()
def test_builder_uses_corrected_58_baseline_identity():
    marker=ROOT/'BASELINE_32.4.59.json';d=json.loads(marker.read_text());assert d['predecessor_sha256']=='c9d67b5aec5e800a5dbca2ea0a1b8a5199ea0db6e1a656d488cc0e26789755e4'
def test_publisher_does_not_remove_contract_before_controller_settlement():
    text=(ROOT/'slimmemeterportal_import/rootfs/app/main.py').read_text();section=text[text.index('def publish_github_release'):text.index('def _write_github_publish_state')];assert 'HA_PUBLICATION_REQUIRED.unlink()' not in section

def test_controller_does_not_claim_next_incoming_until_completed_delivery_settled(tmp_path):
    class A:
        def reconcile_completed_delivery(self,s):
            from release_controller import Outcome
            return Outcome.blocked('predecessor_publication_unsettled')
    service=rcs.ReleaseControllerService(tmp_path,A(),stable_polls=2)
    s=ReleaseController().new_state(from_version='32.4.58',to_version='32.4.59',artifact_sha256='a'*64,artifact_name='59.zip');s.phase='COMPLETE';s.status='COMPLETE';s.step=8;service.store.save(s.to_dict())
    (tmp_path/'Inbox').mkdir(exist_ok=True);(tmp_path/'Inbox/ha_publication_required.json').write_text('{}');inc=tmp_path/'Inbox/incoming';inc.mkdir();(inc/'EnergieProject_v32.4.60.zip').write_bytes(b'next')
    service.cycle();assert (inc/'EnergieProject_v32.4.60.zip').exists();runtime=json.loads((tmp_path/'Inbox/release_controller/runtime.json').read_text());assert runtime['status']=='BLOCKED'

def test_59_to_60_simulated_release_requires_no_manual_contract_cleanup(tmp_path):
    s=state(tmp_path);layout(tmp_path,s);d=HADelivery(tmp_path);p=contract(d,s);(tmp_path/'Inbox/ha_publication_required.json').write_text(json.dumps(p));(tmp_path/'Inbox/ha_runtime/current.json').write_text(json.dumps({'version':s.to_version}));pub(tmp_path,s,p);assert d.align(s).status=='GREEN';assert not (tmp_path/'Inbox/ha_publication_required.json').exists()
    # A successor can now create its own independent contract without conflict.
    n=ReleaseController().new_state(from_version='32.4.59',to_version='32.4.60',artifact_sha256='b'*64,artifact_name='EnergieProject_v32.4.60.zip')
    (tmp_path/'Inbox/processing'/n.artifact_name).write_bytes(b'next');n.artifact_sha256=sha(tmp_path/'Inbox/processing'/n.artifact_name)
    rb=tmp_path/'App.__rollback_32.4.59';rb.mkdir();(rb/'MANIFEST.sha256').write_text('59')
    p60=d._contract(n,d._active_artifact(n));d._ensure_contract(n,p60,tmp_path/'Inbox/ha_publication_required.json');assert json.loads((tmp_path/'Inbox/ha_publication_required.json').read_text())['release_id']==n.release_id
