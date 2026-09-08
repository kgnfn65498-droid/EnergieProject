from release_test_contract import CURRENT_RELEASE, CURRENT_PM_VERSION
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(PM))

from command_ingress import CommandIngressConsumer
from command_processor import CommandProcessor
from command_store import CommandStore
from conversation_intake import (
    CLASSIFICATIONS,
    ConversationIntakeBridge,
    classify_intake,
    route_for_classification,
)
from document_sync import ManagedDocumentSync
from task_engine import TaskStore


class _UnusedDecisions:
    pass


class _UnusedMode:
    pass


def _bridge(tmp_path):
    tasks = TaskStore(tmp_path / 'RuntimeV2/state/tasks.json')
    active = tasks.start(
        '32.4.9 Conversation Intake Bridge',
        'keep current development active',
        mode='DEVELOPMENT',
        steps_total=8,
        priority=1,
    )
    reports = tmp_path / 'reports'
    (reports / 'KnowledgeBase').mkdir(parents=True)
    bridge = ConversationIntakeBridge(
        tmp_path / 'RuntimeV2/intake/items.json',
        tasks,
        ManagedDocumentSync(),
        reports,
    )
    return bridge, tasks, reports, active


def _runtime(tmp_path):
    bridge, tasks, reports, active = _bridge(tmp_path)
    commands = CommandStore(tmp_path / 'RuntimeV2/commands/queue.json')
    ingress_dir = tmp_path / 'CommandIngress'
    ingress_dir.mkdir()
    ingress = CommandIngressConsumer(
        ingress_dir,
        tmp_path / 'RuntimeV2/commands/ingress_receipts.json',
        commands,
    )
    processor = CommandProcessor(
        commands,
        _UnusedDecisions(),
        _UnusedMode(),
        tasks,
        conversation_intake=bridge,
    )
    return bridge, tasks, reports, active, commands, ingress_dir, ingress, processor


def _write_ingress(directory, ingress_id, command):
    (directory / f'{ingress_id}.json').write_text(
        json.dumps(
            {
                'schema': 'energie_pmv2_command_ingress_v1',
                'id': ingress_id,
                'command': command,
            }
        ),
        encoding='utf-8',
    )


def test_v3249_release_identity_and_pm_version():
    assert (ROOT / 'VERSIE.txt').read_text(encoding='utf-8').strip() == CURRENT_RELEASE
    assert f'version: "{CURRENT_RELEASE}"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text(encoding='utf-8')
    assert f'APP_VERSION = "{CURRENT_RELEASE}"' in (APP / 'main.py').read_text(encoding='utf-8')
    assert f'TARGET_RELEASE_VERSION = "{CURRENT_RELEASE}"' in (APP / 'mode_entrypoint.py').read_text(encoding='utf-8')
    assert (PM / 'VERSION.txt').read_text(encoding='utf-8').strip() == CURRENT_PM_VERSION
    assert (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8').startswith(f'## {CURRENT_RELEASE}')
    addon_change = (ROOT / 'slimmemeterportal_import/CHANGELOG.md').read_text(encoding='utf-8')
    assert addon_change.startswith(f'# Changelog\n\n## {CURRENT_RELEASE}')
    assert addon_change.count('\n## ') == 1


@pytest.mark.parametrize(
    ('text', 'expected'),
    [
        ('Dit moet een harde eis zijn', 'hard_requirement'),
        ('Ik wil dit graag als wens bewaren', 'wish'),
        ('Misschien is dit een goed idee', 'idea_opportunity'),
        ('We hebben besloten dat dit de standaard wordt', 'decision'),
        ('Bouw en test deze koppeling', 'action_item'),
        ('Kom hier later op terug', 'later_return'),
        ('NextEnergy is onze huidige leverancier', 'informational_context'),
    ],
)
def test_required_classifications(text, expected):
    assert expected in CLASSIFICATIONS
    assert classify_intake(text)['classification'] == expected


def test_development_context_is_independent_and_routes_are_selective():
    value = classify_intake('Bouw en test deze koppeling')
    assert value['classification'] == 'action_item'
    assert value['development_context'] is True
    assert value['classifications'] == ['action_item']
    assert value['approval_required'] is False
    assert route_for_classification('hard_requirement') == ['knowledge_base', 'roadmap']
    assert route_for_classification('wish') == ['wishlist']
    assert route_for_classification('idea_opportunity') == ['wishlist']
    assert route_for_classification('decision') == ['knowledge_base', 'roadmap']
    assert route_for_classification('action_item') == ['tasks']
    assert route_for_classification('later_return') == ['wishlist']
    assert route_for_classification('informational_context') == ['knowledge_base']


def test_chatgpt_intake_is_end_to_end_traceable_to_canonical_store_kb_and_roadmap(tmp_path):
    bridge, tasks, reports, active, commands, ingress_dir, ingress, processor = _runtime(tmp_path)
    _write_ingress(
        ingress_dir,
        'chat-hard-001',
        {
            'intent': 'conversation_intake',
            'text': 'Dit moet voortaan een harde eis zijn',
            'source_channel': 'chatgpt',
            'source_ref': 'chat:20260905:hard-1',
            'occurred_at': '2026-09-05T23:55:00+02:00',
        },
    )

    imported = ingress.consume()
    assert imported[0]['status'] == 'IMPORTED'
    processed = processor.process_all()
    assert processed[-1]['status'] == 'DONE'
    intake_result = processed[-1]['result']['intake']
    assert intake_result['classification'] == 'hard_requirement'
    assert intake_result['routes'] == ['knowledge_base', 'roadmap']

    canonical = json.loads((tmp_path / 'RuntimeV2/intake/items.json').read_text(encoding='utf-8'))
    assert len(canonical['items']) == 1
    item = canonical['items'][0]
    assert item['source_channel'] == 'chatgpt'
    assert item['source_ref'] == 'chat:20260905:hard-1'
    assert item['ingress_id'] == 'chat-hard-001'
    assert item['status'] == 'ROUTED'

    kb = (reports / 'KnowledgeBase/Knowledge_Base_Chat_Bronregister.md').read_text(encoding='utf-8')
    roadmap = (reports / 'KnowledgeBase/EnergieProject_Roadmap.md').read_text(encoding='utf-8')
    assert 'RuntimeV2/intake/items.json' in kb and 'chat:20260905:hard-1' in kb
    assert 'RuntimeV2/intake/items.json' in roadmap and 'chat:20260905:hard-1' in roadmap
    assert tasks.active()['id'] == active['id']


def test_nomad_action_item_creates_paused_backlog_without_displacing_active_task(tmp_path):
    bridge, tasks, reports, active, commands, ingress_dir, ingress, processor = _runtime(tmp_path)
    _write_ingress(
        ingress_dir,
        'nomad-action-001',
        {
            'intent': 'conversation_intake',
            'text': 'Bouw en test deze koppeling',
            'source_channel': 'nomad',
            'source_ref': 'nomad:voice:7',
        },
    )
    assert ingress.consume()[0]['status'] == 'IMPORTED'
    finished = processor.process_all()[-1]
    assert finished['status'] == 'DONE'
    assert finished['result']['intake']['development_context'] is True

    assert tasks.active()['id'] == active['id']
    captured = [task for task in tasks.all() if task.get('intake_fingerprint')]
    assert len(captured) == 1
    assert captured[0]['status'] == 'PAUSED'
    assert captured[0]['mode'] == 'DEVELOPMENT'


def test_duplicate_source_event_is_idempotent_across_ingress_ids(tmp_path):
    bridge, tasks, reports, active, commands, ingress_dir, ingress, processor = _runtime(tmp_path)
    command = {
        'intent': 'conversation_intake',
        'text': 'Bouw deze functie',
        'source_channel': 'nomad',
        'source_ref': 'nomad:voice:duplicate-7',
    }
    _write_ingress(ingress_dir, 'dup-a', command)
    _write_ingress(ingress_dir, 'dup-b', command)
    assert [row['status'] for row in ingress.consume()] == ['IMPORTED', 'IMPORTED']
    processed = processor.process_all()
    assert [row['status'] for row in processed] == ['DONE', 'DONE']
    assert processed[0]['result']['intake']['duplicate'] is False
    assert processed[1]['result']['intake']['duplicate'] is True
    assert bridge.summary()['total'] == 1
    assert len([task for task in tasks.all() if task.get('intake_fingerprint')]) == 1
    assert tasks.active()['id'] == active['id']


def test_wish_only_projects_to_wishlist_and_voice_alias_is_accepted(tmp_path):
    bridge, tasks, reports, active = _bridge(tmp_path)
    result = bridge.accept(
        {
            'text': 'Ik wil een dashboardfilter als wens bewaren',
            'source_channel': 'voice',
            'source_ref': 'speech:wish:1',
        }
    )
    assert result['classification'] == 'wish'
    assert result['routes'] == ['wishlist']
    assert bridge.summary()['latest'][-1]['source_channel'] == 'speech'
    wishlist = (reports / 'KnowledgeBase/Wensenlijst.md').read_text(encoding='utf-8')
    assert 'speech:wish:1' in wishlist
    assert not (reports / 'KnowledgeBase/Knowledge_Base_Chat_Bronregister.md').exists()
    assert not (reports / 'KnowledgeBase/EnergieProject_Roadmap.md').exists()
    assert tasks.active()['id'] == active['id']


def test_malformed_intake_fails_closed_without_runtime_or_projection_mutation(tmp_path):
    bridge, tasks, reports, active, commands, ingress_dir, ingress, processor = _runtime(tmp_path)
    before_tasks = tasks.all()
    _write_ingress(
        ingress_dir,
        'malformed-001',
        {
            'intent': 'conversation_intake',
            'text': 'Ik wil dit bewaren',
            'source_ref': 'missing-channel',
        },
    )
    assert ingress.consume()[0]['status'] == 'IMPORTED'
    finished = processor.process_all()[-1]
    assert finished['status'] == 'FAILED'
    assert 'source_channel_required' in finished['error']
    assert not (tmp_path / 'RuntimeV2/intake/items.json').exists()
    assert tasks.all() == before_tasks
    assert tasks.active()['id'] == active['id']
    assert not (reports / 'KnowledgeBase/Wensenlijst.md').exists()
    assert not (reports / 'KnowledgeBase/Knowledge_Base_Chat_Bronregister.md').exists()


def test_secret_like_intake_is_rejected_before_canonical_write(tmp_path):
    bridge, tasks, reports, active = _bridge(tmp_path)
    with pytest.raises(ValueError, match='secret_like_content_rejected'):
        bridge.accept(
            {
                'text': 'api_key=abcdefghijklmnopqrstuvwxyz1234567890',
                'source_channel': 'chatgpt',
                'source_ref': 'secret-1',
            }
        )
    assert not (tmp_path / 'RuntimeV2/intake/items.json').exists()
    assert tasks.active()['id'] == active['id']
