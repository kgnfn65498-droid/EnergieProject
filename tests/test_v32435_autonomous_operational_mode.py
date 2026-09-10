import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
sys.path.insert(0, str(PM))

from command_store import CommandStore
from decision_queue import DecisionQueue
from task_engine import TaskStore
from command_processor import CommandProcessor


class ModeStore:
    def set(self, mode, *, reason='', source=''):
        return {'mode': mode, 'reason': reason, 'source': source}


class ModeBridge:
    def __init__(self):
        self.calls = []

    def request_base_mode(self, mode, *, reason='', issued_by='', confirmed_by_user=False):
        row = {
            'requested_mode': mode,
            'reason': reason,
            'issued_by': issued_by,
            'confirmed_by_user': confirmed_by_user,
        }
        self.calls.append(row)
        return row


def test_new_remote_maintenance_is_operational_not_extra_approval(tmp_path):
    commands = CommandStore(tmp_path / 'commands.json')
    decisions = DecisionQueue(tmp_path / 'decisions.json')
    tasks = TaskStore(tmp_path / 'tasks.json')
    bridge = ModeBridge()
    processor = CommandProcessor(commands, decisions, ModeStore(), tasks, mode_bridge=bridge)

    command = commands.enqueue({
        'intent': 'start_maintenance',
        'source': 'mcp_remote',
        'title': '32.4.35 CLEARUP live maintenance',
        'goal': 'run bounded CLEARUP maintenance',
        'steps_total': 3,
    })
    finished = processor.process_next()

    assert finished['status'] == 'DONE'
    assert finished['result']['requested_mode'] == 'MAINTENANCE'
    assert finished['result']['mode_request']['confirmed_by_user'] is True
    assert bridge.calls[-1]['requested_mode'] == 'MAINTENANCE'
    assert bridge.calls[-1]['confirmed_by_user'] is True
    assert decisions.pending() == []


def test_new_remote_development_is_operational_not_extra_approval(tmp_path):
    commands = CommandStore(tmp_path / 'commands.json')
    decisions = DecisionQueue(tmp_path / 'decisions.json')
    tasks = TaskStore(tmp_path / 'tasks.json')
    bridge = ModeBridge()
    processor = CommandProcessor(commands, decisions, ModeStore(), tasks, mode_bridge=bridge)

    command = commands.enqueue({
        'intent': 'start_development',
        'source': 'mcp_remote',
        'title': 'development',
        'goal': 'development',
    })
    finished = processor.process_next()

    assert finished['status'] == 'DONE'
    assert finished['result']['requested_mode'] == 'DEVELOPMENT'
    assert finished['result']['mode_request']['confirmed_by_user'] is True
    assert decisions.pending() == []
