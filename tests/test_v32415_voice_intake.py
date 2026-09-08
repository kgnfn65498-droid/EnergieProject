import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
sys.path.insert(0, str(PM))
sys.path.insert(0, str(APP))

import conversation_intake as ci
from task_engine import TaskStore


class NullDocs:
    def sync_marked_section(self, *args, **kwargs):
        return {'changed': False}


def _bridge(tmp_path):
    return ci.ConversationIntakeBridge(
        tmp_path / 'intake/items.json',
        TaskStore(tmp_path / 'state/tasks.json'),
        NullDocs(),
        tmp_path / 'reports',
    )


def test_voice_and_typed_use_same_classification_but_preserve_distinct_source_metadata(tmp_path):
    bridge = _bridge(tmp_path)
    text = 'Dit moet als harde eis. Bouw hiervoor een test.'
    typed = bridge.accept({'text': text, 'source_channel': 'chatgpt', 'source_ref': 'typed-1'})
    voice = bridge.accept({'text': text, 'source_channel': 'voice', 'source_ref': 'voice-1', 'transcript_id': 'tr-1'})
    assert typed['classifications'] == voice['classifications']
    data = json.loads((tmp_path / 'intake/items.json').read_text(encoding='utf-8'))['items']
    sources = {item['source_ref']: item['source_channel'] for item in data}
    assert sources['typed-1'] == 'chatgpt'
    assert sources['voice-1'] == 'voice'


def test_dictation_is_a_first_class_source_channel(tmp_path):
    result = _bridge(tmp_path).accept({
        'text': 'Leg dit vast als wens.', 'source_channel': 'dictation', 'source_ref': 'dict-1', 'transcript_id': 'd-1'
    })
    assert result['status'] in {'ROUTED', 'PARTIAL'}


def test_identical_voice_event_id_is_processed_once(tmp_path):
    bridge = _bridge(tmp_path)
    command = {
        'text': 'Bouw een veilige test.', 'source_channel': 'voice', 'source_ref': 'voice-event-42', 'transcript_id': 'tr-42'
    }
    first = bridge.accept(command)
    second = bridge.accept(command)
    assert first['duplicate'] is False
    assert second['duplicate'] is True
    assert len(json.loads((tmp_path / 'intake/items.json').read_text())['items']) == 1
    assert len(TaskStore(tmp_path / 'state/tasks.json')._load()['tasks']) == 1


def test_exact_duplicate_voice_transcript_inside_short_window_dedupes_even_with_new_event_id(tmp_path):
    bridge = _bridge(tmp_path)
    t0 = datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc)
    first = bridge.accept({
        'text': 'Bouw een veilige test.', 'source_channel': 'voice', 'source_ref': 'evt-a',
        'transcript_id': 'tr-a', 'occurred_at': t0.isoformat(),
    })
    second = bridge.accept({
        'text': 'Bouw een veilige test.', 'source_channel': 'voice', 'source_ref': 'evt-b',
        'transcript_id': 'tr-b', 'occurred_at': (t0 + timedelta(seconds=3)).isoformat(),
    })
    assert first['duplicate'] is False
    assert second['duplicate'] is True
    assert second['duplicate_reason'] == 'recent_exact_transcript'
    assert len(json.loads((tmp_path / 'intake/items.json').read_text())['items']) == 1


def test_meaningful_voice_repetition_outside_dedupe_window_is_kept(tmp_path):
    bridge = _bridge(tmp_path)
    t0 = datetime(2026, 9, 8, 18, 0, tzinfo=timezone.utc)
    bridge.accept({'text': 'Bouw een veilige test.', 'source_channel': 'voice', 'source_ref': 'evt-a', 'occurred_at': t0.isoformat()})
    second = bridge.accept({'text': 'Bouw een veilige test.', 'source_channel': 'voice', 'source_ref': 'evt-b', 'occurred_at': (t0 + timedelta(seconds=30)).isoformat()})
    assert second['duplicate'] is False
    assert len(json.loads((tmp_path / 'intake/items.json').read_text())['items']) == 2


def test_voice_intake_records_transcript_metadata_and_uncertainty(tmp_path):
    bridge = _bridge(tmp_path)
    bridge.accept({
        'text': 'Installeer 32.4.15 in Home Assistant.',
        'source_channel': 'voice', 'source_ref': 'evt-c', 'transcript_id': 'tr-c', 'transcript_confidence': 0.55,
    })
    item = json.loads((tmp_path / 'intake/items.json').read_text())['items'][0]
    assert item['transcript_id'] == 'tr-c'
    assert item['transcript_confidence'] == 0.55
    assert item['transcript_uncertain'] is True
    assert item['approval_required'] is True


def test_new_chat_intent_is_detected_semantically():
    assert hasattr(ci, 'is_new_chat_intent')
    for text in (
        'nieuwe chat', 'ga verder in een nieuwe chat', 'zet over naar een nieuwe chat',
        'volgende build in een verse chat', 'bereid de nieuwe chat voor',
    ):
        assert ci.is_new_chat_intent(text) is True, text
    assert ci.is_new_chat_intent('Wat staat er in de chat?') is False
