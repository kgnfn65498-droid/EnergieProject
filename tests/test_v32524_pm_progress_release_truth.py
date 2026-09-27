from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for path in (str(APP), str(PM)):
    if path not in sys.path:
        sys.path.insert(0, path)

from development_build_contract import evaluate_build_contract
from handover import build_handover
from projectmanager_web import render_projectmanager_progress
from roadmap_regie import RoadmapRegie
from conversation_runtime import ProjectmanagerConversationRuntime


def _write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def test_524_live_required_cannot_close_via_task_completion_backdoor(tmp_path):
    path = tmp_path / 'roadmap.json'
    _write(path, {
        'schema':2,
        'items':[{
            'key':'type2-live', 'title':'Type2 live', 'status':'ACTIVE', 'executor':'handoff',
            'task_id':'task-1', 'acceptance_matrix_required':True, 'live_required':True,
            'acceptance_state':'LIVE_REQUIRED', 'carry_forward':[],
        }],
    })
    regie = RoadmapRegie(path)
    changed = regie.mark_done_for_task('task-1')
    assert changed[0]['status'] == 'BLOCKED'
    assert changed[0]['acceptance_state'] == 'LIVE_REQUIRED'
    assert changed[0]['completion_blocker'] == 'LIVE_REQUIRED_WITHOUT_LIVE_PROVEN'
    regie.mark_acceptance('type2-live', 'LIVE_PROVEN', evidence_refs=['live:type2'])
    done = regie.mark_done_for_task('task-1')[0]
    assert done['status'] == 'DONE'
    assert done['acceptance_state'] == 'CLOSED_COLD'


def test_524_terminal_instruction_is_technically_enforced_and_rendered(tmp_path):
    task = {
        'id':'t', 'title':'release repair', 'goal':'repair', 'mode':'DEVELOPMENT', 'status':'ACTIVE',
        'step':3, 'steps_total':5, 'build_contract_required':True,
        'build_metadata':{
            'thinking_level':'HOOG', 'release_version':'32.5.24',
            'estimated_total_seconds':1800, 'estimated_test_verification_seconds':600,
            'step_estimates_seconds':[300,300,300,300,600], 'original_estimate_recorded_at':'2026-09-26T18:00:00Z',
            'terminal_instruction':{
                'required':True, 'terminal':'Home Assistant add-on terminal', 'step_label':'Stap 3/5',
                'expected_duration_seconds':30, 'max_wait_seconds':120,
                'success_marker':'DONE_GREEN', 'stop_marker':'ERROR_OR_TIMEOUT',
                'return_required':'volledige uitvoer', 'reason':'geen autonome capability beschikbaar',
                'proof':{
                    'target_state':'exact 32.5.24 bounded recovery state',
                    'command_sha256':'a'*64,
                    'parser_validation':'sh -n GREEN on exact bytes',
                    'check_only_preflight':'read-only preflight GREEN before mutation',
                    'side_effects':'bounded watcher/control-plane recovery only',
                    'dangerous_class':'protected container stop/start/recreate',
                    'rollback':'restore preserved predecessor container and artifact state',
                    'post_action_readback':'Incoming/Processing/runtime exact readback',
                },
            },
        },
        'blockers':[], 'next_action':'bounded terminal fallback',
    }
    progress = {'step_label':'Stap 3/5', 'elapsed_seconds':420, 'estimated_remaining_seconds':900,
                'completed_steps':2, 'remaining_steps':3, 'progress_percent':40,
                'next_step':'bounded terminal fallback', 'status_color':'ORANGE'}
    contract = evaluate_build_contract(task, progress)
    assert contract['compliant'] is True
    assert contract['terminal_compliant'] is True

    handover = build_handover(mode={'mode':'DEVELOPMENT'}, active_task=task, release={'version':'32.5.24'}, progress=progress)
    terminal = handover['development_build_contract']['terminal_instruction']
    assert terminal['terminal'] == 'Home Assistant add-on terminal'
    assert terminal['max_wait_seconds'] == 120
    assert terminal['success_marker'] == 'DONE_GREEN'

    project = tmp_path / 'project'
    status = {'mode':'DEVELOPMENT','release':{'version':'32.5.24'},'active_task':task,'progress':progress,
              'development_build_contract':contract,'health':{'status':'ORANGE'}}
    _write(project / 'Inbox/projectmanager_v2/RuntimeV2/status/current.json', status)
    html = render_projectmanager_progress(project)
    for token in ('Stap 3/5','Geschat resterend','Home Assistant add-on terminal','max wachten 120 s','DONE_GREEN','ERROR_OR_TIMEOUT','volledige uitvoer'):
        assert token in html

    broken = dict(task)
    broken_meta = dict(task['build_metadata'])
    broken_meta['terminal_instruction'] = {'required':True, 'terminal':'HA terminal'}
    broken['build_metadata'] = broken_meta
    bad = evaluate_build_contract(broken, progress)
    assert bad['compliant'] is False
    assert bad['terminal_compliant'] is False
    assert 'max_wait_seconds' in bad['terminal_instruction']['missing']


def test_524_relevant_development_truth_speech_contains_step_and_time():
    truth = {
        'release_version':'32.5.24',
        'progress':{'step_label':'Stap 2/6','elapsed_seconds':180,'estimated_remaining_seconds':720},
        'blockers':[], 'next_action':'Type2 E2E',
    }
    speech = ProjectmanagerConversationRuntime._speech_for_truth(truth)
    assert 'Stap 2/6' in speech
    assert 'Verstreken: 180 s' in speech
    assert 'ETA: 720 s' in speech


def test_524_version_stacking_is_proactively_flagged(tmp_path):
    path = tmp_path / 'roadmap.json'
    _write(path, {'schema':2,'items':[{
        'key':'open-action','title':'open action','status':'OPEN','executor':'handoff',
        'acceptance_matrix_required':True,'live_required':True,'acceptance_state':'LIVE_REQUIRED',
        'carry_forward':['same unresolved action'],
    }]})
    regie = RoadmapRegie(path)
    assert regie.observe_release('32.5.22') == []
    assert regie.observe_release('32.5.23') == []
    alerts = regie.observe_release('32.5.24')
    assert alerts and alerts[0]['status'] == 'VERSION_STACKING_ATTENTION'
    assert alerts[0]['release_count'] == 3
    summary = regie.acceptance_summary()
    assert summary['carry_forward_alerts'][0]['key'] == 'open-action'
    assert summary['carry_forward_alerts'][0]['blocker'] == 'concrete_blocker_required'
    assert summary['carry_forward_alerts'][0]['next_action'] == 'concrete_next_action_required'
