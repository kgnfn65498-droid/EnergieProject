from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'


def test_v3243_release_identity_and_pm_version():
    assert (ROOT / 'VERSIE.txt').read_text().strip() == '32.4.4'
    assert 'version: "32.4.4"' in (ROOT / 'slimmemeterportal_import/config.yaml').read_text()
    assert 'APP_VERSION = "32.4.4"' in (APP / 'main.py').read_text()
    assert 'TARGET_RELEASE_VERSION = "32.4.4"' in (APP / 'mode_entrypoint.py').read_text()
    assert (PM / 'VERSION.txt').read_text().strip() == '2.0.0-rc4'


def test_v3243_handoff_and_canonical_roadmap_wiring_present():
    configured = (PM / 'configured_service.py').read_text()
    orchestrator = (PM / 'orchestrator.py').read_text()
    embedded = (PM / 'embedded_config.py').read_text()
    self_audit = (PM / 'self_audit.py').read_text()
    assert (PM / 'handoff_queue.py').is_file()
    assert (PM / 'handoff_result_ingress.py').is_file()
    assert (PM / 'protected_action_executor.py').is_file()
    assert 'reconcile_canonical' in configured
    assert 'HandoffResultIngressConsumer' in orchestrator
    assert 'ProtectedActionExecutor' in orchestrator
    assert 'HandoffResultIngress' in embedded
    assert 'canonical_roadmap_v3.json' in embedded
    assert 'active_handoff_task_without_open_handoff' in self_audit
    assert 'canonical_roadmap_drift' in self_audit


def test_v3243_remote_boundaries_remain_fail_closed():
    api = (PM / 'projectmanager_api.py').read_text()
    gateway = (PM / 'command_gateway.py').read_text()
    assert 'direct RuntimeV2 command writes disabled' in api
    assert 'direct RuntimeV2 decision writes disabled' in api
    advertised = gateway.split('COMMANDS =', 1)[1].split('UNSUPPORTED_PROTECTED_INTENTS', 1)[0]
    assert "'purchase'" not in advertised
    assert "'paid_commitment'" not in advertised


def test_v3243_embedded_failure_marker_uses_atomic_persistence():
    entrypoint = (APP / 'projectmanager_v2_entrypoint.py').read_text()
    section = entrypoint.split('def _notify_failure', 1)[1].split('def _mark_success', 1)[0]
    assert 'from persistence import atomic_write_json' in section
    assert 'atomic_write_json(' in section
    assert '.write_text(' not in section
