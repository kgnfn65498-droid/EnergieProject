from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
if str(PM) not in sys.path:
    sys.path.insert(0, str(PM))

from development_context_enforcement import (
    build_development_context,
    discover_requirements,
    evaluate_full_kb,
)
from development_build_contract import evaluate_build_contract


def _w(path: Path, text='x\n'):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def _project(tmp_path: Path) -> Path:
    root = tmp_path / 'project'
    _w(root/'App/VERSIE.txt', '32.5.24\n')
    _w(root/'App/CHANGELOG.md', '# changelog\n')
    _w(root/'App/PROJECT_AFSPRAKEN.md', '# afspraken\n')
    _w(root/'Data/02_Output/Rapportages/KnowledgeBase/Knowledge_Base_Master_Index.md', '# report kb\n')
    _w(root/'Data/03_Systeem/Projectmanager/KnowledgeBase/README.md', '# pm kb\n')
    _w(root/'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/00_MASTER_DEVELOPMENT_INDEX.md', '# master\n')
    _w(root/'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/00_ACTIVE_DEVELOPMENT_CONTEXT.md', '# active\n')
    _w(root/'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/00_DEVELOPMENT_MANIFEST.md', '# manifest\n')
    _w(root/'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/01_UNIFIED_DEVELOPMENT_LEDGER.md', '# ledger\n')
    _w(root/'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/01A_LEDGER_CURRENT_TRUTH.md', '# truth\n')
    _w(root/'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/02_DECISION_LOG.md', '# decisions\n')
    _w(root/'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/03_DEVELOPMENT_CHANGELOG.md', '# dev changelog\n')
    _w(root/'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/04_SPOCK_CONTEXT.md', '# spock\n')
    _w(root/'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/05_FULL_KB_AUDIT_20260927.md', '# full kb audit\n')
    _w(root/'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/05_TICKET_ISSUE_INDEX.md', '# issues\n')
    _w(root/'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons/06_KNOWLEDGEBASE_INVENTORY_20260927.md', '# inventory\n')
    _w(root/'Data/03_Systeem/Projectmanager/Handover/CURRENT_DEVELOPMENT_HANDOVER.md', '# handover\n')
    _w(root/'Data/03_Systeem/Projectmanager/Requirements/00_REQUIREMENTS_INDEX.md', '# index\n')
    _w(root/'Data/03_Systeem/Projectmanager/Requirements/HARD_REQUIREMENT_A.md', '# A\n')
    _w(root/'Data/03_Systeem/Projectmanager/ClearUp/State/CHECKPOINT_32.5.24.json', json.dumps({'live_release':'32.5.24'}))
    return root


def test_32524_dynamic_requirement_discovery_sees_new_file_without_code_change(tmp_path):
    root = _project(tmp_path)
    before = discover_requirements(root)
    assert any(Path(p).name == 'HARD_REQUIREMENT_A.md' for p in before)
    _w(root/'Data/03_Systeem/Projectmanager/Requirements/HARD_REQUIREMENT_TEMP_DYNAMIC.md', '# temp\n')
    after = discover_requirements(root)
    assert len(after) == len(before) + 1
    assert any(Path(p).name == 'HARD_REQUIREMENT_TEMP_DYNAMIC.md' for p in after)


def test_32524_full_kb_requires_both_kb_roots_and_master_index(tmp_path):
    root = _project(tmp_path)
    full = evaluate_full_kb(root)
    assert full['status'] == 'COMPLETE'
    assert full['complete'] is True
    assert full['checks']['reporting_kb_root'] is True
    assert full['checks']['technical_pm_kb_root'] is True
    assert full['checks']['master_development_index'] is True

    for p in (root/'Data/02_Output/Rapportages/KnowledgeBase').iterdir():
        p.unlink()
    partial = evaluate_full_kb(root)
    assert partial['status'] in {'PARTIAL','RED'}
    assert partial['complete'] is False
    assert 'reporting_kb_root' in partial['missing']


def test_32524_development_context_points_to_ds9_master_and_fail_closed_truth(tmp_path):
    root = _project(tmp_path)
    context = build_development_context(root, {'release':{'version':'32.5.24'}})
    assert context['master_index'].endswith('00_MASTER_DEVELOPMENT_INDEX.md')
    assert context['requirements_dynamic_discovery'] is True
    assert context['full_kb']['status'] == 'COMPLETE'
    assert context['truth_reconciliation']['status'] == 'GREEN'

    context_conflict = build_development_context(root, {'release':{'version':'32.5.23'}})
    assert context_conflict['truth_reconciliation']['status'] == 'RED'
    assert context_conflict['truth_reconciliation']['fail_closed'] is True


def test_32524_terminal_command_proof_is_mandatory_for_new_release_contract():
    task = {
        'step':1,'steps_total':1,'build_contract_required':True,
        'build_metadata':{
            'thinking_level':'HOOG','release_version':'32.5.24',
            'estimated_total_seconds':60,'estimated_test_verification_seconds':30,
            'step_estimates_seconds':[60],'original_estimate_recorded_at':'2026-09-27T00:00:00Z',
            'terminal_instruction':{
                'required':True,'terminal':'QNAP host','step_label':'Stap 1/1',
                'expected_duration_seconds':10,'max_wait_seconds':60,
                'success_marker':'GREEN','stop_marker':'RED','return_required':'output','reason':'bounded recovery',
            },
        },
    }
    result = evaluate_build_contract(task, {})
    assert result['terminal_compliant'] is False
    assert 'rollback' in result['terminal_instruction']['proof_missing']
    assert 'command_sha256' in result['terminal_instruction']['proof_missing']


def test_32524_manager_persists_full_kb_runtime_log_and_master_current_truth(tmp_path):
    from manager_service import ManagerService
    from document_sync import ManagedDocumentSync

    root = _project(tmp_path)
    runtime_root = root/'Inbox/projectmanager_v2/RuntimeV2'
    runtime_root.mkdir(parents=True, exist_ok=True)

    class Config:
        project_root = str(root)
        reports_root = str(root/'Data/02_Output/Rapportages')

    service = ManagerService.__new__(ManagerService)
    service.config = Config()
    service.root = runtime_root
    service.document_sync = ManagedDocumentSync()
    service.issues = None
    service._sync_managed_documents = lambda _status: []

    status = {
        'release': {'version': '32.5.24'},
        'development_build_contract': {
            'contract_version': '2026-09-11.v3',
            'process_rules': ['dynamic_all_requirements_discovery_required','full_kb_runtime_enforcement_required'],
        },
    }
    status['development_context'] = build_development_context(root, status)
    result = service._sync_documents_best_effort(status)
    assert result['status'] == 'GREEN'

    runtime = json.loads((runtime_root/'development_context/current.json').read_text(encoding='utf-8'))
    assert runtime['schema'] == 'energie_pmv2_runtime_development_context_v2'
    assert runtime['requirements_dynamic_discovery'] is True
    assert runtime['full_kb']['status'] == 'COMPLETE'
    assert runtime['truth_reconciliation']['status'] == 'GREEN'
    assert runtime['static_paths']['master_index'].endswith('00_MASTER_DEVELOPMENT_INDEX.md')

    kb = root/'Data/03_Systeem/Projectmanager/KnowledgeBase/Development_Lessons'
    master = (kb/'00_MASTER_DEVELOPMENT_INDEX.md').read_text(encoding='utf-8')
    current = (kb/'01A_LEDGER_CURRENT_TRUTH.md').read_text(encoding='utf-8')
    assert 'PROJECTMANAGER_V2_RUNTIME_ROUTER' in master
    assert 'FULL_KB: **COMPLETE**' in master
    assert 'PROJECTMANAGER_V2_RUNTIME_CURRENT_TRUTH' in current
    assert 'Truth reconciliation: **GREEN**' in current
