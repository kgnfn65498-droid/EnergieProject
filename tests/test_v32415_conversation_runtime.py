import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(PM))
sys.path.insert(0, str(APP))

from conversation_runtime import ProjectmanagerConversationRuntime


class StubIntake:
    def __init__(self):
        self.calls = []
    def accept(self, command):
        self.calls.append(dict(command))
        return {
            'status': 'accepted', 'id': f"intake-{len(self.calls)}",
            'classification': 'action_item' if 'los' in command['text'].lower() else 'informational_context',
            'classifications': ['action_item'] if 'los' in command['text'].lower() else ['informational_context'],
            'routes': ['tasks'] if 'los' in command['text'].lower() else ['knowledge_base'],
            'approval_required': False,
            'transcript_uncertain': bool(command.get('transcript_confidence') is not None and command.get('transcript_confidence') < .7),
        }


class StubApproval:
    def __init__(self):
        self.requests = []
        self.confirms = []
    def request(self, *, action, parameters, source_channel, now=None):
        self.requests.append((action, dict(parameters), source_channel))
        return {'status': 'confirmation_required', 'prompt': 'definitief?', 'challenge': {'id': 'challenge-1', 'action': action, 'parameters': parameters}}
    def confirm(self, challenge_id, confirmation_text, *, source_channel, parameters=None, now=None):
        self.confirms.append((challenge_id, confirmation_text, source_channel, parameters))
        return {'status': 'approved', 'challenge_id': challenge_id}


class StubHandover:
    def __init__(self): self.calls = []
    def create(self, **kwargs):
        self.calls.append(dict(kwargs))
        return {'schema': 'energie_projectmanager_handover_snapshot_v1', 'status': 'ready', 'handover_id': 'hand-1', 'release_version': '32.4.15', 'pm_version': '2.0.0-rc12', 'mode': 'DEVELOPMENT', 'progress': {'step_label': 'Stap 4/6'}, 'next_step': 'fresh extract', 'blockers': []}


def _write(path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding='utf-8')


def _runtime(tmp_path):
    root = tmp_path / 'RuntimeV2'
    status = {
        'schema': 'energie_projectmanager_status_v2',
        'mode': 'DEVELOPMENT',
        'manager': {'version': '2.0.0-rc12'},
        'release': {'version': '32.4.15', 'rollback_version': '32.4.14'},
        'release_chain': {'watcher': {'active': True}, 'atomic_swap': {'state': 'ACCEPTED', 'to_version': '32.4.15'}},
        'progress': {'step': 4, 'steps_total': 6, 'step_label': 'Stap 4/6', 'percentage': 66.7, 'next_action': 'fresh extract', 'blockers': ['voice e2e']},
        'active_task': {'id': 't1', 'title': '32.4.15 closure', 'status': 'BLOCKED', 'blockers': ['voice e2e'], 'next_action': 'fresh extract'},
        'next_action': 'fresh extract',
        'open_issues': [{'id': 'i1', 'fingerprint': 'voice:e2e', 'status': 'OPEN', 'severity': 'ORANGE'}],
        'decisions_needed': [],
    }
    _write(root / 'status/current.json', status)
    intake, approval, handover = StubIntake(), StubApproval(), StubHandover()
    runtime = ProjectmanagerConversationRuntime(root, intake=intake, approval=approval, handover=handover)
    return runtime, intake, approval, handover


def test_typed_and_voice_status_use_exact_same_canonical_truth(tmp_path):
    runtime, intake, approval, handover = _runtime(tmp_path)
    typed = runtime.handle(text='Hoe staat 32.4.15 ervoor?', source_channel='chatgpt', turn_id='t-1', session_id='s1')
    voice = runtime.handle(text='Hoe staat 32.4.15 ervoor?', source_channel='voice', turn_id='v-1', session_id='s2', transcript_id='tr-1', transcript_confidence=.98)
    assert typed['status'] == voice['status'] == 'answered'
    assert typed['truth'] == voice['truth']
    assert typed['truth']['release_version'] == '32.4.15'
    assert typed['truth']['pm_version'] == '2.0.0-rc12'
    assert typed['truth']['progress']['step_label'] == 'Stap 4/6'
    assert '32.4.15' in typed['speech'] and 'Stap 4/6' in typed['speech']
    assert '32.4.15' in voice['speech'] and 'Stap 4/6' in voice['speech']


def test_voice_protected_request_creates_two_step_challenge_without_execution(tmp_path):
    runtime, intake, approval, handover = _runtime(tmp_path)
    result = runtime.handle(text='Installeer 32.4.15 in Home Assistant.', source_channel='voice', turn_id='v-2', session_id='s1', transcript_confidence=.99)
    assert result['status'] == 'confirmation_required'
    assert approval.requests == [('production_deploy', {'version': '32.4.15', 'target': 'Home Assistant'}, 'voice')]
    assert result['challenge_id'] == 'challenge-1'
    assert intake.calls == []


def test_second_voice_or_typed_confirmation_uses_active_challenge(tmp_path):
    runtime, intake, approval, handover = _runtime(tmp_path)
    first = runtime.handle(text='Installeer 32.4.15 in Home Assistant.', source_channel='voice', turn_id='v-2', session_id='s1')
    confirmed = runtime.handle(text='Ja, voer uit.', source_channel='chatgpt', turn_id='t-3', session_id='s1')
    assert confirmed['status'] == 'approved'
    assert approval.confirms[-1][0] == first['challenge_id']
    assert approval.confirms[-1][2] == 'chatgpt'


def test_uncertain_voice_confirmation_never_approves_protected_action(tmp_path):
    runtime, intake, approval, handover = _runtime(tmp_path)
    runtime.handle(text='Installeer 32.4.15 in Home Assistant.', source_channel='voice', turn_id='v-2', session_id='s1')
    result = runtime.handle(text='Ja, voer uit.', source_channel='voice', turn_id='v-3', session_id='s1', transcript_confidence=.42)
    assert result['status'] == 'confirmation_required'
    assert result['reason'] == 'uncertain_voice_confirmation'
    assert approval.confirms == []


def test_typed_and_voice_new_chat_use_same_handover_service(tmp_path):
    runtime, intake, approval, handover = _runtime(tmp_path)
    typed = runtime.handle(text='ga verder in een nieuwe chat', source_channel='chatgpt', turn_id='t-h', session_id='s1')
    voice = runtime.handle(text='We gaan verder in een nieuwe chat.', source_channel='voice', turn_id='v-h', session_id='s2')
    assert typed['status'] == voice['status'] == 'handover_ready'
    assert len(handover.calls) == 2
    assert handover.calls[0]['source_channel'] == 'chatgpt'
    assert handover.calls[1]['source_channel'] == 'voice'
    assert handover.calls[0]['trigger_id'] == 't-h'
    assert handover.calls[1]['trigger_id'] == 'v-h'


def test_deictic_followup_resolves_current_blocker_for_safe_development_work(tmp_path):
    runtime, intake, approval, handover = _runtime(tmp_path)
    result = runtime.handle(text='Los die blocker dan op.', source_channel='voice', turn_id='v-4', session_id='s1')
    assert result['status'] == 'accepted'
    assert result['resolved_context']['blocker'] == 'voice e2e'
    assert intake.calls[-1]['text'] == 'Los die blocker dan op.'


def test_duplicate_event_id_returns_same_result_and_does_not_repeat_side_effect(tmp_path):
    runtime, intake, approval, handover = _runtime(tmp_path)
    first = runtime.handle(text='Los die blocker dan op.', source_channel='voice', turn_id='dup-1', session_id='s1')
    second = runtime.handle(text='Los die blocker dan op.', source_channel='voice', turn_id='dup-1', session_id='s1')
    assert second == first
    assert len(intake.calls) == 1


def test_ambiguous_deictic_protected_context_does_not_execute_silently(tmp_path):
    runtime, intake, approval, handover = _runtime(tmp_path)
    status_path = tmp_path / 'RuntimeV2/status/current.json'
    status = json.loads(status_path.read_text())
    status['progress']['blockers'] = ['Installeer 32.4.15 in Home Assistant om verder te gaan']
    status['active_task']['blockers'] = status['progress']['blockers']
    _write(status_path, status)
    result = runtime.handle(text='Los die blocker dan op.', source_channel='voice', turn_id='v-5', session_id='s1')
    assert result['status'] == 'confirmation_required'
    assert approval.requests[-1][0] == 'production_deploy'
    assert intake.calls == []

def test_roadmap_task_and_knowledge_base_reads_use_same_canonical_files(tmp_path):
    runtime, intake, approval, handover = _runtime(tmp_path)
    runtime.reports_root = tmp_path / 'reports'
    _write(tmp_path / 'RuntimeV2/roadmap/queue.json', {'schema': 2, 'items': [
        {'key': 'v32415', 'title': '32.4.15 Voice closure', 'status': 'ACTIVE'},
        {'key': 'ngrok', 'title': 'ngrok audit', 'status': 'OPEN'},
    ]})
    _write(tmp_path / 'RuntimeV2/state/tasks.json', {'schema': 1, 'tasks': [
        {'id': 't1', 'title': 'Voice E2E', 'status': 'ACTIVE'}
    ]})
    kb = tmp_path / 'reports/KnowledgeBase/Knowledge_Base_Chat_Bronregister.md'
    kb.parent.mkdir(parents=True, exist_ok=True)
    kb.write_text('Voice Mode moet voor 32.5 operationeel en geaudit zijn.\n', encoding='utf-8')

    roadmap = runtime.handle(text='Wat staat er nu op de roadmap?', source_channel='voice', turn_id='rm1', session_id='s1')
    assert roadmap['status'] == 'answered'
    assert roadmap['truth']['roadmap']['items'][0]['key'] == 'v32415'
    assert roadmap['truth']['tasks'][0]['id'] == 't1'

    kb_result = runtime.handle(text='Wat staat er in de kennisbank over Voice Mode?', source_channel='chatgpt', turn_id='kb1', session_id='s1')
    assert kb_result['status'] == 'answered'
    assert 'Voice Mode moet voor 32.5' in kb_result['truth']['knowledge_base'][0]['snippet']
