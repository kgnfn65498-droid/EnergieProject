from __future__ import annotations

import inspect
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
TOOLS = ROOT / 'tools'
for value in (str(APP), str(PM), str(TOOLS)):
    if value not in sys.path:
        sys.path.insert(0, value)


def test_rc44_contract_is_carried_forward_by_rc45_release():
    # Regression family retained: 32.4.57/rc45 must preserve the rc44 rescue
    # behavior while publishing the new coherent Projectmanager identity.
    assert (PM / 'VERSION.txt').read_text(encoding='utf-8').strip() == '2.0.0-rc45'


def test_project_constitution_current_handover_and_work_ledger_exist():
    for name in ('PROJECT_CONSTITUTION.md', 'CURRENT_HANDOVER.md', 'WORK_LEDGER.md'):
        path = ROOT / name
        assert path.is_file()
        assert path.read_text(encoding='utf-8').strip()


def test_installer_publication_contract_is_shared_mode_0666():
    source = (ROOT / 'tests/fixtures/pre57/release_installer.sh').read_text(encoding='utf-8')
    block = source[source.index('write_ha_publication_required(){'):source.index('rollback_atomic_swap(){')]
    assert 'chmod 0666 "$HA_PUBLICATION_REQUIRED"' in block


def test_canonical_publication_state_is_written_shared_mode():
    import main
    source = inspect.getsource(main._write_github_publish_state)
    assert 'os.chmod(path, 0o666)' in source


def test_same_version_publication_requests_official_store_reload_then_self_rebuild():
    import main
    source = inspect.getsource(main._request_supervisor_same_version_rebuild)
    assert '/addons/reload' in source
    assert '/addons/self/rebuild' in source
    assert source.index('/addons/reload') < source.index('/addons/self/rebuild')


def test_successful_same_version_publication_records_rebuild_request_before_contract_cleanup():
    source = (APP / 'main.py').read_text(encoding='utf-8')
    start = source.index('def publish_github_release(')
    end = source.index('\ndef _write_github_publish_state', start)
    block = source[start:end]
    assert '_request_supervisor_same_version_rebuild' in block
    assert 'same_version_rebuild' in block
    assert block.index('_request_supervisor_same_version_rebuild') < block.rindex('HA_PUBLICATION_REQUIRED.unlink()')


def test_project_cr_queue_creates_transition_owned_maintenance_bridge():
    source = (PM / 'release_transition_worker.py').read_text(encoding='utf-8')
    start = source.index("if action=='QUEUE_PROJECT_CR'")
    block = source[start:start+900]
    assert '_ensure_project_cr_maintenance_bridge' in block
    helper = source[source.index('def _ensure_project_cr_maintenance_bridge'):source.index('def run_once', source.index('def _ensure_project_cr_maintenance_bridge'))]
    assert 'request_transition_owned_temporary_maintenance' in helper


def test_transition_does_not_advance_project_cr_while_current_ticket_unsettled():
    from release_transition_worker import plan_transition_step
    state = {'phase': 'PROJECT_CR', 'current_ticket': {'request_id': 'r1'}}
    facts = {'project_cr_green': True}
    assert plan_transition_step(state, facts)['action'] == 'WAIT_PROJECT_CR_RESULT'


def test_completed_project_cr_command_is_bound_back_to_transition_ticket():
    source = (PM / 'release_transition_worker.py').read_text(encoding='utf-8')
    assert 'def _settle_current_ticket' in source
    block = source[source.index('def _settle_current_ticket'):source.index('def run_once', source.index('def _settle_current_ticket'))]
    assert 'accept_executor_result' in block
    assert "command.get('transition_request_id')" in block


def test_identical_fresh_clearup_plan_id_is_allowed_for_bounded_retry():
    source = (APP / 'project_clearup_auto.py').read_text(encoding='utf-8')
    assert 'identical_fresh_plan' in source
    assert 'verse dependency-audit leverde geen nieuw plan-id op' not in source


def test_clearup_plan_uses_candidate_hashcache():
    source = (APP / 'project_clearup.py').read_text(encoding='utf-8')
    assert 'candidate_hashcache' in source
    assert 'hash_cache_hits' in source


def test_project_cr_executor_runs_only_one_deep_verify():
    source = (TOOLS / 'project_cr_local_executor.py').read_text(encoding='utf-8')
    assert 'deep_verify_files=False' in source
    assert source.count('deep_verify_files=True') == 0


def test_cr_snapshot_excludes_settled_release_debt_but_keeps_atomic_rollback():
    source = (TOOLS / 'cr_standard_native_mcp_hotfix.py').read_text(encoding='utf-8')
    assert 'def _crash_recovery_snapshot_v3' in source
    assert 'def _snapshot_release_debt_exclusions' in source
    assert 'atomic_app_swap_state.json' in source
    assert 'release_validation_hold.json' in source


def test_project_cr_stale_worker_marker_is_bounded_self_healed():
    source = (PM / 'project_cr_service.py').read_text(encoding='utf-8')
    assert 'STALE_WORKER_MARKER_SECONDS' in source
    assert 'single_worker_recovery_fence.json' in source
    assert 'stale_worker_marker_recovered' in source


def test_release_transition_broad_health_cannot_skip_executor_ticket_settlement():
    source = inspect.getsource(__import__('release_transition_worker').ReleaseTransitionWorker.run_once)
    assert '_settle_current_ticket' in source
    assert source.index('_settle_current_ticket') < source.index('plan_transition_step')


def test_continuity_documents_encode_new_chat_read_order_and_no_research_reset():
    constitution = (ROOT / 'PROJECT_CONSTITUTION.md').read_text(encoding='utf-8')
    handover = (ROOT / 'CURRENT_HANDOVER.md').read_text(encoding='utf-8')
    ledger = (ROOT / 'WORK_LEDGER.md').read_text(encoding='utf-8')
    combined = '\n'.join((constitution, handover, ledger))
    assert 'PROJECT_CONSTITUTION' in combined
    assert 'CURRENT_HANDOVER' in combined
    assert 'WORK_LEDGER' in combined
    assert 'niet opnieuw' in combined.lower() or 'nooit opnieuw' in combined.lower()
