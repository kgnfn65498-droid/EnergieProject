from pathlib import Path
import importlib.util
import json

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'


def load_mod():
    spec = importlib.util.spec_from_file_location('project_clearup_32428', APP / 'project_clearup.py')
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader
    spec.loader.exec_module(mod)
    return mod


def rollback(root: Path, version: str):
    p = root / f'App.__rollback_{version}'
    p.mkdir(parents=True)
    (p / 'VERSIE.txt').write_text(version, encoding='utf-8')
    (p / 'payload.txt').write_text('stable', encoding='utf-8')


def test_pm_derived_status_is_informational_not_dependency(tmp_path: Path):
    mod = load_mod()
    for v in ('32.4.20','32.4.21','32.4.22','32.4.23'):
        rollback(tmp_path, v)
    status = tmp_path / 'Inbox/projectmanager_v2/RuntimeV2/status/current.json'
    status.parent.mkdir(parents=True)
    status.write_text(json.dumps({'rollback_excess':['App.__rollback_32.4.20']}), encoding='utf-8')

    plan = mod.build_clearup_plan(tmp_path, current_version='32.4.27', keep_rollbacks=3)
    item = next(i for i in plan['items'] if i['source_path'] == 'App.__rollback_32.4.20')
    assert item['disposition'] == 'CLEARUP'
    assert any(r['path'].endswith('status/current.json') for r in item['informational_references'])


def test_pm_snapshot_change_between_plan_and_apply_does_not_abort(tmp_path: Path):
    mod = load_mod()
    for v in ('32.4.20','32.4.21','32.4.22','32.4.23'):
        rollback(tmp_path, v)
    snap = tmp_path / 'Inbox/projectmanager_v2/RuntimeV2/snapshots/current_runtime.json'
    snap.parent.mkdir(parents=True)
    snap.write_text(json.dumps({'rollback_excess':[]}), encoding='utf-8')

    plan = mod.build_clearup_plan(tmp_path, current_version='32.4.27', keep_rollbacks=3)
    # PM observes the candidate after the plan was built; this is not a consumer.
    snap.write_text(json.dumps({'rollback_excess':['App.__rollback_32.4.20']}), encoding='utf-8')
    result = mod.apply_clearup_plan(tmp_path, plan, confirmation=plan['confirmation_required'], run_id='pm-observation')
    assert result['status'] == 'completed'
    assert not (tmp_path / 'App.__rollback_32.4.20').exists()


def test_real_active_config_reference_still_blocks(tmp_path: Path):
    mod = load_mod()
    for v in ('32.4.20','32.4.21','32.4.22','32.4.23'):
        rollback(tmp_path, v)
    cfg = tmp_path / 'Infra/active.conf'
    cfg.parent.mkdir(parents=True)
    cfg.write_text('fallback=App.__rollback_32.4.20\n', encoding='utf-8')
    plan = mod.build_clearup_plan(tmp_path, current_version='32.4.27', keep_rollbacks=3)
    item = next(i for i in plan['items'] if i['source_path'] == 'App.__rollback_32.4.20')
    assert item['disposition'] == 'REVIEW'
    assert any(r['path'] == 'Infra/active.conf' for r in item['active_references'])
