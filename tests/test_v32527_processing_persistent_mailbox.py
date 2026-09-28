from __future__ import annotations

import json
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/'tools'
APP=ROOT/'slimmemeterportal_import/rootfs/app'
PM=APP/'projectmanager_v2'
for p in (str(TOOLS),str(APP),str(PM)):
    if p not in sys.path: sys.path.insert(0,p)


def _w(path:Path,data:bytes=b'x'):
    path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)


def test_32527_release_service_keeps_processing_as_permanent_mailbox(tmp_path):
    import release_controller_service as rcs
    root=tmp_path/'p'
    service=rcs.ReleaseControllerService(root,adapter=None)
    processing=root/'Inbox/processing'
    assert processing.is_dir() and not processing.is_symlink()
    assert service._reconcile_idle_processing() is None
    assert processing.is_dir() and not any(processing.iterdir())


def test_32527_ingress_recovery_recreates_processing_mailbox(tmp_path):
    import release_ingress_recovery as rir
    root=tmp_path/'p'
    result=rir.reconcile(root,stale_seconds=30,now=1000)
    assert result['status'] in {'IDLE','GREEN','RECOVERED','WAITING'}
    assert (root/'Inbox/processing').is_dir()
    assert not any((root/'Inbox/processing').iterdir())


def test_32527_archive_moves_only_zip_and_keeps_processing(tmp_path):
    from ha_delivery_adapter import HADelivery
    import hashlib
    root=tmp_path/'p'
    src=root/'Inbox/processing/EnergieProject_v32.5.27.zip';_w(src,b'candidate')
    sha=hashlib.sha256(src.read_bytes()).hexdigest()
    out=HADelivery(root)._archive_complete(SimpleNamespace(artifact_name=src.name,artifact_sha256=sha))
    assert out==root/'Inbox/processed'/src.name
    assert out.is_file()
    assert (root/'Inbox/processing').is_dir()
    assert not any((root/'Inbox/processing').iterdir())


def test_32527_final_cleanup_plan_never_removes_processing(tmp_path,monkeypatch):
    import inbox_cleanup_32526 as cleanup
    root=tmp_path/'p'
    (root/'App').mkdir(parents=True);(root/'App/VERSIE.txt').write_text('32.5.27\n')
    (root/'Inbox/processing').mkdir(parents=True)
    (root/'Inbox/incoming').mkdir(parents=True)
    (root/'Inbox/processed').mkdir(parents=True)
    (root/'Inbox/failed').mkdir(parents=True)
    for rel in cleanup.CANONICAL_REQUIRED:(root/rel).mkdir(parents=True,exist_ok=True)
    (root/'Data/03_Systeem/Projectmanager/ReleaseController').mkdir(parents=True,exist_ok=True)
    (root/'Data/03_Systeem/Projectmanager/ReleaseController/current.json').write_text(json.dumps({'status':'COMPLETE','phase':'COMPLETE','to_version':'32.5.27'}))
    monkeypatch.setattr(cleanup,'_binding_contract',lambda _root:[])
    plan=cleanup.build_cleanup_plan(root)
    assert not any(a.get('source')=='Inbox/processing' for a in plan['actions'])


def test_32527_executor_forbids_processing_removal_and_requires_it_after_cleanup():
    source=(ROOT/'tools/project_clearup_move_executor.py').read_text(encoding='utf-8')
    assert 'allowed = {*(f"Inbox/failed/{name}" for name in service.FAILED_BUCKETS)}' in source
    assert '"Inbox/processing", *(f"Inbox/failed/{name}"' not in source
    assert 'processing mailbox must remain present and empty after scoped cleanup' in source
    assert '"processing_directory_present_and_empty": True' in source


def test_32527_post_live_audit_contract_is_present_and_empty_not_absent():
    source=(ROOT/'tools/release_controller_service.py').read_text(encoding='utf-8')
    assert "'processing_directory_present_and_empty':" in source
    assert "'processing_directory_absent':" not in source


def test_32527_canonical_publication_writer_contract_is_cross_identity_writable(tmp_path):
    import release_controller_service as rcs
    root=tmp_path/'p'
    pub=root/'Data/03_Systeem/Projectmanager/ReleaseController/Publication'
    pub.mkdir(parents=True)
    state=pub/'github_publication_state.json';state.write_text('{}\n')
    publisher=pub/'github_publisher_state.json';publisher.write_text('{}\n')
    os.chmod(pub,0o755);os.chmod(state,0o644);os.chmod(publisher,0o644)
    result=rcs.ensure_publication_writer_contract(root)
    assert result['status']=='GREEN'
    assert stat.S_IMODE(pub.stat().st_mode)==0o777
    assert stat.S_IMODE(state.stat().st_mode)==0o666
    assert stat.S_IMODE(publisher.stat().st_mode)==0o666


def test_32527_no_publication_fallback_to_inbox():
    source=(ROOT/'tools/release_controller_service.py').read_text(encoding='utf-8')
    assert "Data/03_Systeem/Projectmanager/ReleaseController/Publication" in source
    # Existing legacy paths may be checked only for absence/quiescence; the writer contract itself is canonical-only.
    helper=source[source.index('def ensure_publication_writer_contract'):source.index('def verify_publication_writer_quiescence')]
    assert 'Inbox/github_publication_state.json' not in helper
    assert 'Inbox/github_publisher_state.json' not in helper
