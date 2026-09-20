from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / 'tools'
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
for value in (str(TOOLS), str(APP), str(PM)):
    if value not in sys.path:
        sys.path.insert(0, value)

from release_controller import Outcome, ReleaseController
from projectmanager_v2.energy_health_collector import EnergyHealthCollector


def _text(path: Path) -> str:
    return path.read_text(encoding='utf-8')


def test_58_01_controller_service_has_no_legacy_install_adoption():
    text = _text(TOOLS / 'release_controller_service.py')
    assert 'legacy_install_adoption' not in text
    assert 'adopt_exact_pre57_install' not in text


def test_58_02_controller_evidence_is_semantically_deduplicated():
    class A:
        def install(self, s): return Outcome.green('same', 'same')
        def runtime_align(self, s): return Outcome.green('same')
        def verify_live(self, s): return Outcome.green('same')
        def atomic_accept(self, s): return Outcome.green('same')
        def delivery(self, s): return Outcome.green('same', 'same')
        def rollback(self, s, reason): return Outcome.rolled_back(reason)
    c = ReleaseController()
    s = c.new_state(from_version='32.4.57', to_version='32.4.58', artifact_sha256='a'*64, artifact_name='x.zip')
    c.mark_verified(s, ['same', 'same'])
    for _ in range(8): c.cycle(s, A())
    assert s.evidence == ['same']


def test_58_03_entrypoint_does_not_start_or_install_global_operating_mode():
    text = _text(APP / 'mode_entrypoint.py')
    forbidden = (
        'operating_mode_worker', 'install_mode_web', 'install_mode_overrides',
        'crash_recovery_mode_worker', 'install_crash_recovery_mode_integration',
        'recover_startup_mode_state', 'operating_mode_tick',
    )
    assert all(token not in text for token in forbidden)


def test_58_04_main_does_not_start_automatic_post_release_clearup():
    text = _text(APP / 'main.py')
    assert 'project-clearup-post-acceptance' not in text
    assert 'target=startup_project_clearup' not in text


def test_58_05_addon_has_supervisor_api_permission_and_manager_role():
    text = _text(ROOT / 'slimmemeterportal_import/config.yaml')
    assert 'hassio_api: true' in text
    assert 'hassio_role: manager' in text


def test_58_06_publisher_uses_supported_store_reload_not_addons_reload():
    text = _text(APP / 'main.py')
    assert '"/store/reload"' in text or "'/store/reload'" in text
    assert '"/addons/reload"' not in text and "'/addons/reload'" not in text
    assert '/addons/self/rebuild' in text


def test_58_07_empty_snapshot_is_collector_error_without_false_live_source_cascade(tmp_path):
    project = tmp_path / 'project'; input_root = tmp_path / 'input'; recovery = tmp_path / 'recovery'
    (project / 'App').mkdir(parents=True); (project / 'App/VERSIE.txt').write_text('32.4.58')
    now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    q = input_root / '2026_09/HomeAssistant/QuarterHour/home_assistant_quarter_20260919_1200.json'
    q.parent.mkdir(parents=True); q.write_text(json.dumps({'entity_count': 0, 'entities': []}))
    checks = EnergyHealthCollector(project, input_root, recovery).collect(now=now)
    by_name = {item['name']: item for item in checks}
    assert by_name['current_quarter_hour_snapshot']['status'] == 'RED'
    assert not [name for name in by_name if name.startswith('live_source_')]


def test_58_08_energy_health_has_no_operating_mode_source_check():
    text = _text(PM / 'energy_health_collector.py')
    assert "'operating_mode_source'" not in text and '"operating_mode_source"' not in text


def test_58_09_release_health_uses_controller_not_old_hold_or_watcher_authority():
    from projectmanager_v2.release_health import release_health_checks
    runtime = {'release_chain': {'release_controller': {'active': True}, 'incoming': {'count': 0}, 'processing': {'stuck_count': 0}, 'installer_lock': {'active': False}, 'atomic_swap': {'state': 'ACCEPTED'}, 'publisher': {}, 'github_publication': {}}, 'projectmanager_liveness': {'active': True}}
    names = {item['name'] for item in release_health_checks(runtime)}
    assert 'release_controller_liveness' in names
    assert 'release_watcher' not in names
    assert 'release_hold_driver_liveness' not in names


def test_58_10_runtime_sources_do_not_publish_old_hold_or_watcher_heartbeat_authority(tmp_path):
    from projectmanager_v2.runtime_sources import RuntimeCollector
    root = tmp_path
    (root/'App').mkdir(); (root/'App/VERSIE.txt').write_text('32.4.58')
    rc = root/'Inbox/release_controller/runtime.json'; rc.parent.mkdir(parents=True); rc.write_text(json.dumps({'pid': 123, 'status': 'IDLE', 'phase': 'IDLE'}))
    old = root/'Inbox/watcher_heartbeat.v2'; old.write_text('1')
    chain = RuntimeCollector(root, running_release_version='32.4.58').collect(now=datetime.now(timezone.utc))['release_chain']
    assert 'release_controller' in chain
    assert 'watcher' not in chain


def test_58_11_pm_health_ui_is_domain_separated():
    text = _text(PM / 'projectmanager_web.py')
    assert 'systeem- en releasegezondheid' not in text
    for label in ('Release/runtime', 'Energiedata/live sources', 'Onderhoud/backup/hygiëne', 'Projectmanager/observability'):
        assert label in text


def test_58_12_complete_idle_controller_refreshes_runtime_liveness_without_state_reset(tmp_path, monkeypatch):
    import release_controller_service as service_module
    from release_controller import Phase, Status

    root = tmp_path / 'project'
    service = service_module.ReleaseControllerService(root, object(), stable_polls=2)
    state = service.controller.new_state(
        from_version='32.4.57', to_version='32.4.58',
        artifact_sha256='a' * 64, artifact_name='EnergieProject_v32.4.58.zip',
    )
    state.phase = Phase.COMPLETE.value
    state.status = Status.COMPLETE.value
    state.step = 8
    service.store.save(state.to_dict())

    clock = iter((1000.0, 1001.0))
    monkeypatch.setattr(service_module.time, 'time', lambda: next(clock))
    first = service.cycle()
    runtime1 = json.loads((root/'Inbox/release_controller/runtime.json').read_text())
    second = service.cycle()
    runtime2 = json.loads((root/'Inbox/release_controller/runtime.json').read_text())

    assert first.status == second.status == Status.COMPLETE.value
    assert runtime1['status'] == runtime2['status'] == 'IDLE'
    assert runtime1['phase'] == runtime2['phase'] == 'IDLE'
    assert runtime2['observed_at_epoch'] > runtime1['observed_at_epoch']
    assert runtime2['pid'] > 1


def test_58_13_active_release_runtime_has_no_hold_or_transition_dependency():
    active = (
        TOOLS/'release_controller_service.py',
        TOOLS/'minimal_release_preflight.py',
        APP/'mode_entrypoint.py',
        PM/'runtime_sources.py',
        PM/'release_health.py',
    )
    text = '\n'.join(_text(path) for path in active)
    assert 'release_validation_hold' not in text
    assert 'release_transition' not in text


def test_58_14_cr_nas_cr_hygiene_are_not_release_controller_gates():
    release_core = '\n'.join(_text(path) for path in (
        TOOLS/'release_controller_service.py',
        TOOLS/'minimal_release_preflight.py',
        TOOLS/'release_controller.py',
    ))
    for token in ('project_cr', 'nas_container_cr', 'project_hygiene', 'project_clearup', 'operating_mode'):
        assert token not in release_core


def test_58_15_legacy57_fixture_preserves_retired_adoption_contract_only_historically():
    legacy = ROOT/'tests/fixtures/legacy57/release_controller_service.py'
    assert legacy.is_file()
    assert 'legacy_install_adoption' in _text(legacy)
    assert 'legacy_install_adoption' not in _text(TOOLS/'release_controller_service.py')


def test_58_12_release_health_never_falls_back_to_legacy_watcher():
    from projectmanager_v2.release_health import release_health_checks
    runtime = {
        'release_chain': {
            'watcher': {'active': True},
            'incoming': {'count': 0},
            'processing': {'stuck_count': 0},
            'installer_lock': {'active': False},
            'atomic_swap': {'state': 'ACCEPTED'},
            'publisher': {},
            'github_publication': {},
        },
        'projectmanager_liveness': {'active': True},
        'release': {'version': '32.4.58'},
    }
    checks = release_health_checks(runtime)
    by_name = {item['name']: item for item in checks}
    assert 'release_watcher' not in by_name
    assert by_name['release_controller_liveness']['status'] == 'RED'


def test_58_13_complete_idle_service_refreshes_controller_runtime(tmp_path, monkeypatch):
    import release_controller_service as rcs
    root = tmp_path
    (root / 'App').mkdir(parents=True)
    (root / 'App/VERSIE.txt').write_text('32.4.58', encoding='utf-8')
    service = rcs.ReleaseControllerService(root, object(), stable_polls=2, ingress_stale_seconds=30)
    state = ReleaseController().new_state(
        from_version='32.4.57', to_version='32.4.58', artifact_sha256='a' * 64,
        artifact_name='EnergieProject_v32.4.58.zip',
    )
    state.phase = 'COMPLETE'; state.status = 'COMPLETE'; state.step = 8
    service.store.save(state.to_dict())
    times = iter((100.0, 101.0))
    monkeypatch.setattr(rcs.time, 'time', lambda: next(times))
    first = service.cycle()
    runtime1 = json.loads((root / 'Inbox/release_controller/runtime.json').read_text())
    second = service.cycle()
    runtime2 = json.loads((root / 'Inbox/release_controller/runtime.json').read_text())
    assert first.status == 'COMPLETE' and second.status == 'COMPLETE'
    assert runtime1['status'] == 'IDLE' and runtime1['phase'] == 'IDLE'
    assert runtime2['status'] == 'IDLE' and runtime2['phase'] == 'IDLE'
    assert runtime2['observed_at_epoch'] > runtime1['observed_at_epoch']


def test_58_14_release_core_has_no_legacy_hold_transition_or_maintenance_gate():
    paths = (
        TOOLS / 'release_controller.py',
        TOOLS / 'release_controller_service.py',
        TOOLS / 'minimal_release_preflight.py',
        TOOLS / 'ha_delivery_adapter.py',
    )
    text = '\n'.join(_text(path) for path in paths).lower()
    for forbidden in ('release_validation_hold', 'release_transition', 'operating_mode', 'maintenance', 'project_cr', 'nas_cr', 'hygiene', 'clearup'):
        assert forbidden not in text


def test_58_15_cr_services_are_release_neutral_and_do_not_require_global_maintenance():
    project_cr = _text(PM / 'project_cr_service.py').lower()
    nas_cr = _text(PM / 'nas_container_cr_service.py').lower()
    assert 'maintenance' not in project_cr and 'operating_mode' not in project_cr
    assert 'maintenance' not in nas_cr and 'operating_mode' not in nas_cr
    assert 'project_cr_local' in project_cr
    assert '.nas-container-cr.lock' in nas_cr


def test_58_16_ha_delivery_requires_exact_runtime_version_before_green():
    # Strengthened in 32.4.59: exact HA runtime remains mandatory, but is no
    # longer sufficient by itself; publisher identity and settlement are also required.
    text = _text(TOOLS / 'ha_delivery_adapter.py')
    assert "Inbox/ha_runtime/current.json" in text
    assert "==s.to_version" in text.replace(' ', '')
    assert "pub_exact and ha_exact" in text
    assert "publication_contract_settled" in text


def test_58_17_watcher_is_only_a_thin_release_controller_launcher():
    text = _text(TOOLS / 'release_watcher.sh')
    assert 'release_controller_service.py' in text
    assert 'exec python3' in text
    for forbidden in ('watcher_heartbeat', 'release_installer.sh', 'release_validation_hold', 'release_transition', 'project_cr', 'clearup'):
        assert forbidden not in text


def test_58_18_n_plus_one_accepts_exact_previous_accepted_atomic_journal_as_historical(tmp_path):
    import atomic_app_swap
    from atomic_release_adapter import AtomicReleaseAdapter

    root = tmp_path / 'energy'
    app = root / 'App'
    app.mkdir(parents=True)
    (app / 'VERSIE.txt').write_text('32.4.57', encoding='utf-8')
    previous_rollback = root / 'App.__rollback_32.4.56'
    previous_rollback.mkdir()
    (previous_rollback / 'VERSIE.txt').write_text('32.4.56', encoding='utf-8')

    previous = atomic_app_swap.SwapPaths.for_release(root, '32.4.56', '32.4.57')
    atomic_app_swap.write_journal_atomic(previous, state='ACCEPTED', artifact_sha256='a' * 64)

    state = ReleaseController().new_state(
        from_version='32.4.57', to_version='32.4.58', artifact_sha256='b' * 64,
        artifact_name='EnergieProject_v32.4.58.zip',
    )
    adapter = AtomicReleaseAdapter(root, atomic_app_swap, None, None)

    assert adapter._journal(state) is None
    assert json.loads((root / 'Inbox/atomic_app_swap_state.json').read_text())['state'] == 'ACCEPTED'
    assert (root / 'App/VERSIE.txt').read_text().strip() == '32.4.57'


def test_58_19_atomic_journal_mismatch_still_fails_closed_when_not_exact_previous_acceptance(tmp_path):
    import atomic_app_swap
    from atomic_release_adapter import AtomicReleaseAdapter

    root = tmp_path / 'energy'
    app = root / 'App'
    app.mkdir(parents=True)
    (app / 'VERSIE.txt').write_text('32.4.57', encoding='utf-8')
    stale = atomic_app_swap.SwapPaths.for_release(root, '32.4.55', '32.4.56')
    atomic_app_swap.write_journal_atomic(stale, state='ACCEPTED', artifact_sha256='a' * 64)

    state = ReleaseController().new_state(
        from_version='32.4.57', to_version='32.4.58', artifact_sha256='b' * 64,
        artifact_name='EnergieProject_v32.4.58.zip',
    )
    adapter = AtomicReleaseAdapter(root, atomic_app_swap, None, None)

    try:
        adapter._journal(state)
    except RuntimeError as exc:
        assert 'atomic_from_version_mismatch' in str(exc) or 'atomic_to_version_mismatch' in str(exc)
    else:
        raise AssertionError('non-adjacent ACCEPTED journal must fail closed')


def test_58_20_blocked_pre_activation_generation_self_recovers_when_source_never_moved(tmp_path):
    import atomic_app_swap
    from atomic_release_adapter import AtomicReleaseAdapter

    root = tmp_path / 'energy'
    app = root / 'App'
    app.mkdir(parents=True)
    (app / 'VERSIE.txt').write_text('32.4.57', encoding='utf-8')

    previous = atomic_app_swap.SwapPaths.for_release(root, '32.4.56', '32.4.57')
    atomic_app_swap.write_journal_atomic(previous, state='ACCEPTED', artifact_sha256='a' * 64)

    state = ReleaseController().new_state(
        from_version='32.4.57', to_version='32.4.58', artifact_sha256='b' * 64,
        artifact_name='EnergieProject_v32.4.58.zip',
    )
    state.phase = 'INSTALLING'; state.step = 3
    state.status = 'BLOCKED'; state.blocker = 'rollback_unproven'
    adapter = AtomicReleaseAdapter(root, atomic_app_swap, None, None)

    outcome = adapter.install(state)
    assert outcome.status == 'ROLLED_BACK'
    assert 'source_app_restored' in outcome.evidence
    assert 'previous_atomic_acceptance_preserved' in outcome.evidence
    assert json.loads((root / 'Inbox/atomic_app_swap_state.json').read_text())['state'] == 'ACCEPTED'
    assert (root / 'App/VERSIE.txt').read_text().strip() == '32.4.57'


def test_58_21_blocked_pre_activation_recovery_refuses_candidate_or_rollback_presence(tmp_path):
    import atomic_app_swap
    from atomic_release_adapter import AtomicReleaseAdapter

    root = tmp_path / 'energy'
    app = root / 'App'
    app.mkdir(parents=True)
    (app / 'VERSIE.txt').write_text('32.4.57', encoding='utf-8')
    previous = atomic_app_swap.SwapPaths.for_release(root, '32.4.56', '32.4.57')
    atomic_app_swap.write_journal_atomic(previous, state='ACCEPTED', artifact_sha256='a' * 64)

    state = ReleaseController().new_state(
        from_version='32.4.57', to_version='32.4.58', artifact_sha256='b' * 64,
        artifact_name='EnergieProject_v32.4.58.zip',
    )
    state.phase = 'INSTALLING'; state.step = 3
    state.status = 'BLOCKED'; state.blocker = 'rollback_unproven'
    (root / 'App.__candidate_32.4.58').mkdir()
    adapter = AtomicReleaseAdapter(root, atomic_app_swap, None, None)

    outcome = adapter.install(state)
    assert outcome.status != 'ROLLED_BACK'


def test_58_22_github_repository_exposes_only_one_home_assistant_config_yaml():
    configs = sorted(path.relative_to(ROOT).as_posix() for path in ROOT.rglob('config.yaml'))
    assert configs == ['slimmemeterportal_import/config.yaml']
