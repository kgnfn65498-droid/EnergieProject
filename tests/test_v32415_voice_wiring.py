from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'


def test_orchestrator_wires_one_shared_conversation_runtime():
    source = (PM / 'orchestrator.py').read_text(encoding='utf-8')
    assert 'ConversationApprovalCoordinator' in source
    assert 'HandoverSnapshotService' in source
    assert 'ProjectmanagerConversationRuntime' in source
    assert 'self.conversation =' in source
    assert 'def handle_conversation(' in source


def test_entrypoint_exposes_live_runtime_conversation_without_second_manager():
    source = (APP / 'projectmanager_v2_entrypoint.py').read_text(encoding='utf-8')
    assert '_RUNTIME = None' in source
    assert 'def respond_projectmanager_conversation(' in source
    assert 'runtime.handle_conversation' in source


def test_nomad_bridge_and_http_endpoint_route_projectmanager_conversation():
    source = (APP / 'main.py').read_text(encoding='utf-8')
    assert 'respond_projectmanager_conversation' in source
    assert "source_channel='nomad'" in source or 'source_channel="nomad"' in source
    assert '/api/projectmanager/conversation' in source
    assert 'transcript_confidence' in source
    assert 'transcript_id' in source

def test_nomad_event_request_id_is_forwarded_as_voice_turn_and_transcript_id():
    source = (APP / 'assistant_event_bridge.py').read_text(encoding='utf-8')
    assert 'turn_id=request["request_id"]' in source
    assert 'transcript_id=request["request_id"]' in source
