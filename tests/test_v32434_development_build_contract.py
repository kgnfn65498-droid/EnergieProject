import json
import sys
from datetime import datetime, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / 'slimmemeterportal_import' / 'rootfs' / 'app'
PM = APP / 'projectmanager_v2'
for path in (str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _meta():
    return {
        'contract_version': '2026-09-11.v3',
        'thinking_level': 'HOOG',
        'release_version': '32.4.34',
        'estimated_total_seconds': 3000,
        'estimated_test_verification_seconds': 1500,
        'step_estimates_seconds': [300, 600, 600, 600, 450, 300, 150],
        'original_estimate_recorded_at': '2026-09-10T15:26:30+00:00',
    }


def test_contract_rejects_missing_thinking_and_estimates():
    from development_build_contract import evaluate_build_contract
    task = {'build_contract_required': True, 'steps_total': 7, 'build_metadata': {'release_version': '32.4.34'}}
    result = evaluate_build_contract(task)
    assert result['compliant'] is False
    assert 'thinking_level' in result['missing']
    assert 'estimated_total_seconds' in result['missing']
    assert 'estimated_test_verification_seconds' in result['missing']
    assert 'step_estimates_seconds' in result['missing']


def test_contract_accepts_complete_build_metadata_and_preserves_original_estimate():
    from development_build_contract import evaluate_build_contract
    task = {
        'build_contract_required': True,
        'steps_total': 7,
        'step': 4,
        'build_metadata': _meta(),
        'created_at': '2026-09-10T15:26:30+00:00',
    }
    progress = {'elapsed_seconds': 1200, 'estimated_remaining_seconds': 1800, 'planning_trend': 'stable'}
    result = evaluate_build_contract(task, progress)
    assert result['compliant'] is True
    assert result['thinking_level'] == 'HOOG'
    assert result['estimated_total_seconds'] == 3000
    assert result['estimated_test_verification_seconds'] == 1500
    assert result['step_estimates_seconds'] == _meta()['step_estimates_seconds']
    assert result['elapsed_seconds'] == 1200
    assert result['estimated_remaining_seconds'] == 1800
    assert result['planning_trend'] == 'stable'


def test_task_store_persists_build_metadata_without_breaking_normal_tasks(tmp_path):
    from task_engine import TaskStore
    store = TaskStore(tmp_path / 'tasks.json')
    normal = store.start('normal', 'normal', mode='USER', steps_total=1)
    assert normal.get('build_contract_required') is not True
    build = store.start('32.4.34', 'release', mode='DEVELOPMENT', steps_total=7, build_metadata=_meta())
    assert build['build_contract_required'] is True
    assert build['build_metadata']['thinking_level'] == 'HOOG'
    assert build['build_metadata']['estimated_total_seconds'] == 3000


def test_progress_and_handover_carry_contract_across_chat_boundary(tmp_path):
    from task_engine import TaskStore
    from progress_truth import build_task_progress
    from handover import build_handover
    store = TaskStore(tmp_path / 'tasks.json')
    task = store.start('32.4.34', 'release', mode='DEVELOPMENT', steps_total=7, build_metadata=_meta())
    task = store.progress(task['id'], step=4, next_action='full regression')
    progress = build_task_progress(task, now=datetime(2026, 9, 10, 16, 0, tzinfo=timezone.utc))
    assert progress['thinking_level'] == 'HOOG'
    assert progress['estimated_total_seconds'] == 3000
    assert progress['estimated_test_verification_seconds'] == 1500
    handover = build_handover(mode={'mode': 'DEVELOPMENT'}, active_task=task, release={'version': '32.4.34'}, progress=progress)
    contract = handover['development_build_contract']
    assert contract['contract_version'] == '2026-09-11.v3'
    assert contract['thinking_level'] == 'HOOG'
    assert contract['step_label'] == 'Stap 4/7'
    assert contract['cross_chat_required'] is True
    assert 'load_before_development' in contract['handover_requirements']


def test_command_processor_requires_explicit_build_contract_metadata_for_remote_release(tmp_path):
    source = (PM / 'command_processor.py').read_text(encoding='utf-8')
    assert 'build_metadata_from_command' in source
    assert 'release_version' in source
    assert 'build_metadata=' in source


def test_projectmanager_web_exposes_thinking_timing_and_contract():
    source = (PM / 'projectmanager_web.py').read_text(encoding='utf-8')
    for token in ('Denksetting', 'Test/verificatie', 'Development Build Contract'):
        assert token in source


def test_self_audit_checks_marked_build_contract():
    source = (PM / 'self_audit.py').read_text(encoding='utf-8')
    assert 'development_build_contract' in source
    assert 'build_contract_noncompliant' in source


def test_project_afspraken_has_hard_cross_chat_build_contract():
    source = (Path(__file__).resolve().parents[1] / 'PROJECT_AFSPRAKEN.md').read_text(encoding='utf-8')
    for token in (
        'Development Build Contract', 'MIDDEL', 'HOOG', 'Stap X/Y',
        'oorspronkelijke totale raming', 'test-/verificatietijd', 'chatwissel',
        'write + read-back', 'roadmap', 'sudo', 'host-`python3`',
    ):
        assert token in source
