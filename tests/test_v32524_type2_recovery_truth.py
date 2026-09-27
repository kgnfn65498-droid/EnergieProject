from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for path in (str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)

import clearup_type2_service as service

IDS = [f'ClearUp_{i:03d}' for i in range(2, 13)]


def _write_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def _seed_exports(root: Path):
    (root / 'App/tools/clearup_type2_plans').mkdir(parents=True, exist_ok=True)
    (root / 'App/VERSIE.txt').write_text('32.5.24\n', encoding='utf-8')
    delivered = []
    for cid in IDS:
        shutil.copy2(ROOT / 'tools/clearup_type2_plans' / f'{cid}.json', root / 'App/tools/clearup_type2_plans' / f'{cid}.json')
        plan = service._load_plan(root, cid)
        stage = root / service.STAGING_ROOT_REL / cid
        stage.mkdir(parents=True, exist_ok=True)
        manifest = {
            'schema':'energie_clearup_type2_recovery_v1', 'classification':'TYPE2',
            'clearup_id':cid, 'plan_sha256':plan['plan_sha256'], 'items':[], 'deletion_performed':False,
        }
        (stage / 'TYPE2_MANIFEST.json').write_text(json.dumps(manifest), encoding='utf-8')
        export = root / service.EXPORT_ROOT_REL / f'{cid}_Type2_recovery.zip'
        export.parent.mkdir(parents=True, exist_ok=True)
        import zipfile
        with zipfile.ZipFile(export, 'w') as z:
            z.writestr('TYPE2_MANIFEST.json', json.dumps(manifest))
        delivered.append({
            'clearup_id':cid, 'artifact':export.name, 'size':export.stat().st_size,
            'sha256':service._sha(export), 'plan_sha256':plan['plan_sha256'], 'item_count':0,
        })
    return delivered


def _seed_receipt_evidence(root: Path, rows):
    req = root / 'Data/03_Systeem/Projectmanager/Requirements/HARD_REQUIREMENT_32_5_24_PROJECTMANAGER_LIVE_TRUTH.md'
    req.parent.mkdir(parents=True, exist_ok=True)
    req.write_text('Specifiek: de gebruiker de afgesproken recovery-ZIP reeds heeft ontvangen.\n', encoding='utf-8')
    _write_json(root / service.DELIVERY_CHECKPOINT_REL, {
        'status':'READY_FOR_EXTERNAL_DOWNLOAD', 'required_count':11, 'verified_count':11,
        'failures':[], 'downloads':rows,
    })
    _write_json(root / service.EXTERNAL_GATE_REL, {
        'schema':'energie_clearup_type2_external_recovery_gate_v1',
        'status':'BLOCK_DELETE_UNTIL_EXTERNAL_COPY_CONFIRMED', 'delete_allowed':False,
        'release_version':'32.5.11',
    })


def test_524_reconciles_stale_legacy_gate_when_received_set_is_still_exact(tmp_path):
    rows = _seed_exports(tmp_path)
    _seed_receipt_evidence(tmp_path, rows)
    gate = service.reconcile_external_recovery_truth(tmp_path)
    assert gate['receipt_confirmed'] is True
    assert gate['current_set_integrity'] == 'MATCHES_DELIVERED_SET'
    assert gate['status'] == 'EXTERNAL_COPY_CONFIRMED'
    assert gate['delete_allowed'] is True
    assert len(gate['confirmed_exports']) == 11


def test_524_preserves_receipt_truth_but_blocks_delete_when_current_set_changed(tmp_path):
    rows = _seed_exports(tmp_path)
    _seed_receipt_evidence(tmp_path, rows)
    changed = tmp_path / service.EXPORT_ROOT_REL / 'ClearUp_007_Type2_recovery.zip'
    changed.write_bytes(changed.read_bytes() + b'changed')
    gate = service.reconcile_external_recovery_truth(tmp_path)
    assert gate['receipt_confirmed'] is True
    assert gate['current_set_integrity'] == 'CURRENT_SET_CHANGED_AFTER_RECEIPT'
    assert gate['status'] == 'CURRENT_SET_CHANGED_AFTER_RECEIPT'
    assert gate['delete_allowed'] is False
    assert any(row['clearup_id'] == 'ClearUp_007' for row in gate['current_set_mismatches'])
