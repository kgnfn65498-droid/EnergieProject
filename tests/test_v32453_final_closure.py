import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'slimmemeterportal_import/rootfs/app'
PM = APP / 'projectmanager_v2'
TOOLS = ROOT / 'tools'
for p in (APP, PM, TOOLS):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def _load_tool(name: str):
    path = TOOLS / f'{name}.py'
    spec = importlib.util.spec_from_file_location(f'test_{name}_32453', path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _mode(path: Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_nas_bridge_atomic_writers_are_symlink_safe_and_unpredictable(tmp_path, monkeypatch):
    import nas_container_cr_service as service
    executor = _load_tool('nas_cr_local_executor')
    probe = _load_tool('nas_cr_local_probe')

    bridge = tmp_path / 'Inbox/nas_container_cr_local'
    bridge.mkdir(parents=True)
    bridge.chmod(0o777)
    outside = tmp_path / 'outside.txt'
    outside.write_text('UNCHANGED\n', encoding='utf-8')

    for module, func, filename, payload in (
        (service, service._atomic_text, 'request.json', 'payload\n'),
        (executor, executor._atomic_json, 'result.json', {'ok': True}),
        (probe, probe._atomic_json, 'capability.json', {'ready': True}),
    ):
        monkeypatch.setattr(module.secrets, 'token_hex', lambda _n: 'a1b2c3d4e5f60718')
        target = bridge / filename
        temp = bridge / f'.{filename}.tmp-{os.getpid()}-a1b2c3d4e5f60718'
        temp.symlink_to(outside)
        with pytest.raises(FileExistsError):
            func(target, payload, mode=0o644) if module is service else func(target, payload)
        assert outside.read_text(encoding='utf-8') == 'UNCHANGED\n'
        assert not target.exists()
        temp.unlink()
        func(target, payload, mode=0o644) if module is service else func(target, payload)
        assert target.is_file() and not target.is_symlink()
        assert _mode(target) == 0o644


def test_nas_bridge_real_pm_service_executor_roundtrip_across_identities():
    assert os.geteuid() == 0, 'release verification container must run this mandatory uid-boundary test as root'
    root = Path('/tmp') / f'energie-nas-mailbox-e2e-{os.getpid()}'
    shutil.rmtree(root, ignore_errors=True)
    (root / 'App').mkdir(parents=True)
    (root / 'Inbox/nas_container_cr_local').mkdir(parents=True)
    (root / 'App/VERSIE.txt').write_text('32.4.53\n', encoding='utf-8')
    root.chmod(0o755)
    (root / 'App').chmod(0o755)
    (root / 'Inbox').chmod(0o755)
    bridge = root / 'Inbox/nas_container_cr_local'
    bridge.chmod(0o777)
    env = dict(os.environ)
    env['PYTHONPATH'] = f'{PM}:{TOOLS}:' + env.get('PYTHONPATH', '')

    def demote(uid: int):
        def _inner():
            os.setgid(uid)
            os.setuid(uid)
        return _inner

    pm_code = (
        'import json; from pathlib import Path; '
        'from nas_container_cr_service import ConfiguredNasContainerCrService; '
        f's=ConfiguredNasContainerCrService(Path({str(root)!r}), timeout_seconds=5, poll_seconds=.01); '
        'r=s.create(command_id="1"*32, expected_release="32.4.53"); '
        'print(json.dumps(r, sort_keys=True))'
    )
    pm_proc = subprocess.Popen(
        [sys.executable, '-c', pm_code], env=env, text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, preexec_fn=demote(65534)
    )
    try:
        request = bridge / 'request.json'
        deadline = __import__('time').monotonic() + 3
        while not request.exists() and __import__('time').monotonic() < deadline:
            __import__('time').sleep(.01)
        assert request.is_file(), 'PM identity did not create request through ConfiguredNasContainerCrService'
        assert _mode(request) == 0o644

        watcher_code = (
            'import json; from pathlib import Path; '
            'import nas_cr_local_executor as ex; '
            f'root=Path({str(root)!r}); req=ex._load_request(root); '
            'payload={"schema":ex.RESULT_SCHEMA,"request_id":req["request_id"],'
            '"command_id":req.get("command_id",""),"status":"GREEN","ok":True,'
            '"version":req["expected_runtime_version"],"production_containers_changed":False}; '
            'ex._atomic_json(root/"Inbox/nas_container_cr_local/result.json", payload)'
        )
        watcher = subprocess.run(
            [sys.executable, '-c', watcher_code], env=env, text=True,
            capture_output=True, preexec_fn=demote(65533), check=False
        )
        assert watcher.returncode == 0, watcher.stderr
        result_path = bridge / 'result.json'
        assert result_path.is_file() and _mode(result_path) == 0o644

        stdout, stderr = pm_proc.communicate(timeout=5)
        assert pm_proc.returncode == 0, stderr
        result = json.loads(stdout.strip())
        assert result['status'] == 'GREEN' and result['ok'] is True
        assert result['version'] == '32.4.53'
        assert result['command_id'] == '1' * 32
    finally:
        if pm_proc.poll() is None:
            pm_proc.kill()
            pm_proc.wait(timeout=2)
        shutil.rmtree(root, ignore_errors=True)


def test_pm_service_validates_watcher_owned_mailbox_without_chmod_and_fails_on_drift():
    source = (PM / 'nas_container_cr_service.py').read_text(encoding='utf-8')
    create_block = source[source.index('    def create(self, *, command_id'):source.index('        request = self._load_json', source.index('    def create(self, *, command_id'))]
    assert 'bridge_root.chmod' not in create_block
    assert 'stat.S_IMODE(self.bridge_root.stat().st_mode) != 0o777' in create_block

    import nas_container_cr_service as service
    root = Path('/tmp') / f'energie-nas-mailbox-drift-{os.getpid()}'
    shutil.rmtree(root, ignore_errors=True)
    (root / 'App').mkdir(parents=True)
    (root / 'Inbox/nas_container_cr_local').mkdir(parents=True)
    (root / 'App/VERSIE.txt').write_text('32.4.53\n', encoding='utf-8')
    bridge = root / 'Inbox/nas_container_cr_local'
    bridge.chmod(0o755)
    try:
        svc = service.ConfiguredNasContainerCrService(root, timeout_seconds=.1, poll_seconds=.01)
        with pytest.raises(RuntimeError, match='mailboxcontract 0777'):
            svc.create(expected_release='32.4.53', wait_for_result=False)
        assert _mode(bridge) == 0o755, 'PM must not mutate owner-controlled mailbox permissions'
    finally:
        shutil.rmtree(root, ignore_errors=True)


def test_nas_bridge_contract_owned_by_bootstrap_watcher_and_probe_has_no_false_cross_runtime_green():
    bootstrap = (TOOLS / 'bootstrap_release_watcher_container.sh').read_text(encoding='utf-8')
    watcher = (TOOLS / 'release_watcher.sh').read_text(encoding='utf-8')
    probe = (TOOLS / 'nas_cr_local_probe.py').read_text(encoding='utf-8')
    service = (PM / 'nas_container_cr_service.py').read_text(encoding='utf-8')
    assert 'ensure_nas_cr_mailbox_contract' in bootstrap
    assert 'chmod 0777 "$NAS_CR_LOCAL_DIR"' in bootstrap
    assert 'ensure_nas_cr_mailbox_contract' in watcher
    assert 'chmod 0777 "$NAS_CR_LOCAL_DIR"' in watcher
    process = watcher[watcher.index('process_nas_container_cr_local(){'):watcher.index('process_project_clearup_move(){')]
    assert process.index('ensure_nas_cr_mailbox_contract') < process.index('[ -f "$NAS_CR_LOCAL_REQUEST" ]')
    assert 'bridge.chmod(0o777)' in probe
    assert 'cross_runtime_mailbox_ready' not in probe
    assert "'mailbox_contract_owner': 'watcher'" in probe
    assert 'self.bridge_root.chmod' not in service




def test_nas_cr_capability_probe_proves_operation_lock_exclusive_across_processes(tmp_path):
    probe = _load_tool('nas_cr_local_probe')
    root = tmp_path / 'EnergieProject'
    bridge = root / 'Inbox/nas_container_cr_local'
    (root / 'App').mkdir(parents=True)
    bridge.mkdir(parents=True)
    bridge.chmod(0o777)
    (root / 'App/VERSIE.txt').write_text('32.4.53\n', encoding='utf-8')
    lock = root / 'Inbox/.nas-container-cr.operation.lock'
    lock.write_text('', encoding='utf-8')
    lock.chmod(0o666)

    import socket as _socket
    sock_path = tmp_path / 'docker.sock'
    server = _socket.socket(_socket.AF_UNIX, _socket.SOCK_STREAM)
    server.bind(str(sock_path))
    class Client:
        def ping(self):
            return {'ok': True}
    try:
        payload = probe.probe(root, socket_path=sock_path, client_factory=Client)
    finally:
        server.close()
    assert payload['ready'] is True and payload['status'] == 'GREEN'
    assert payload['operation_lock_exclusive'] is True


def test_hotfix_targets_filename_loop_only_when_source_has_two_matching_blocks():
    import ast
    import cr_standard_native_mcp_hotfix as hotfix
    tree = ast.parse((ROOT / 'tests/test_v32452_cr_closure.py').read_text(encoding='utf-8'))
    source = None
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == 'test_hotfix_adds_strict_atomic_temp_snapshot_policy':
            for stmt in node.body:
                if isinstance(stmt, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'live' for t in stmt.targets):
                    source = ast.literal_eval(stmt.value)
                    break
    assert isinstance(source, str)
    needle = ('        for name in sorted(filenames):\n'
              '            p = root_path / name\n'
              '            rel = PurePosixPath((root_rel / name).as_posix())\n'
              '            if _excluded(rel):\n'
              '                continue\n'
              '            if p.is_symlink():\n'
              '                continue\n')
    duplicate = ('        for name in sorted(dirnames):\n'
                 '            p = root_path / name\n'
                 '            rel = PurePosixPath((root_rel / name).as_posix())\n'
                 '            if _excluded(rel):\n'
                 '                continue\n'
                 '            if p.is_symlink():\n'
                 '                continue\n') + needle
    assert needle in source
    source = source.replace(needle, duplicate, 1)
    out = hotfix._crash_recovery_snapshot_v2(source)
    dir_segment = out[out.index('for name in sorted(dirnames):'):out.index('for name in sorted(filenames):')]
    file_start = out.index('for name in sorted(filenames):')
    file_segment = out[file_start:out.index('    return {', file_start)]
    assert '_is_known_atomic_temp' not in dir_segment
    assert '_is_known_atomic_temp' in file_segment
    assert hotfix._crash_recovery_snapshot_v2(out) == out


def test_native_reload_executor_reads_runtime_produced_fingerprint(tmp_path, monkeypatch):
    guard = _load_tool('native_mcp_runtime_guard')
    executor = _load_tool('native_mcp_reload_executor')
    native = tmp_path / 'Infra/Docker/native-mcp'
    native.mkdir(parents=True)
    (native / 'crash_recovery.py').write_text('SNAPSHOT_POLICY = "energie_cr_snapshot_v2"\n', encoding='utf-8')
    (native / 'runtime_fingerprint.py').write_text(
        'import hashlib\nfrom pathlib import Path\n'
        'def compute_fingerprint(*, native_root, project_root):\n'
        '    p=Path(native_root)/"crash_recovery.py"\n'
        '    return hashlib.sha256(p.read_bytes()).hexdigest(), ["crash_recovery.py"]\n', encoding='utf-8')
    expected, targets = guard.expected_fingerprint(tmp_path)
    request = tmp_path / executor.REQUEST
    request.parent.mkdir(parents=True)
    request.write_text(json.dumps({
        'schema': 'energie_native_mcp_reload_request_v1',
        'operation': 'restart_exact_energie_filesystem_mcp',
        'approved_by': 'Peter',
        'decision_id': 'approved-test',
        'request_id': 'a' * 32,
        'expected_fingerprint': expected,
    }), encoding='utf-8')

    marker = tmp_path / executor.RUNTIME_MARKER
    def simulated_runtime_restart():
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({
            'schema': guard.SCHEMA,
            'fingerprint': expected,
            'targets': targets,
            'producer': 'simulated_native_runtime_after_restart',
        }), encoding='utf-8')
    monkeypatch.setattr(executor, '_restart', simulated_runtime_restart)

    before = guard.probe(tmp_path)
    assert before['status'] == 'RELOAD_REQUIRED'
    result = executor.run(tmp_path, wait_seconds=1)
    assert result['status'] == 'GREEN' and result['runtime_fingerprint'] == expected
    after = guard.probe(tmp_path)
    assert after['status'] == 'GREEN' and after['ready'] is True
    runtime_marker = json.loads(marker.read_text(encoding='utf-8'))
    assert runtime_marker['producer'] == 'simulated_native_runtime_after_restart'


def _write_mode_marker(root: Path, release='32.4.53', status='REQUIRED', **extra):
    marker = root / 'Inbox/operating_mode/post_release_maintenance_required.json'
    marker.parent.mkdir(parents=True, exist_ok=True)
    payload = {'schema':'energie_post_release_maintenance_v1','status':status,'release_version':release, **extra}
    marker.write_text(json.dumps(payload), encoding='utf-8')
    return marker


def _write_closure(root: Path, status: str, release='32.4.53'):
    p = root / 'Inbox/projectmanager_v2/RuntimeV2/status/current.json'
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({'series_324_live_closure': {'status': status, 'release_version': release}}), encoding='utf-8')


def test_development_session_uses_temporary_maintenance_and_restores_only_after_closure(tmp_path):
    from operating_modes import Mode, ModeState, load_mode_state, save_mode_state
    mode = _load_tool('post_release_mode_transition')
    root = tmp_path / 'EnergieProject'
    (root/'App').mkdir(parents=True)
    (root/'App/VERSIE.txt').write_text('32.4.53\n', encoding='utf-8')
    save_mode_state(root, ModeState(base_mode=Mode.DEVELOPMENT, effective_mode=Mode.DEVELOPMENT, development_session_active=True))
    _write_mode_marker(root)
    _write_closure(root, 'RED')
    applied = mode.apply(root)
    state = load_mode_state(root)
    assert applied['status'] == 'APPLIED'
    assert state.base_mode is Mode.DEVELOPMENT and state.effective_mode is Mode.MAINTENANCE
    assert state.development_session_active is True and state.active_transition_id
    again = mode.apply(root)
    state2 = load_mode_state(root)
    assert again['status'] == 'APPLIED' and again['changed'] is False
    assert state2.effective_mode is Mode.MAINTENANCE
    _write_closure(root, 'GREEN')
    completed = mode.apply(root)
    state3 = load_mode_state(root)
    assert completed['status'] == 'COMPLETED'
    assert state3.base_mode is Mode.DEVELOPMENT and state3.effective_mode is Mode.DEVELOPMENT
    assert state3.development_session_active is True and not state3.active_transition_id


def test_non_development_post_release_maintenance_remains_compatible(tmp_path):
    from operating_modes import Mode, ModeState, load_mode_state, save_mode_state
    mode = _load_tool('post_release_mode_transition')
    root = tmp_path / 'EnergieProject'
    (root/'App').mkdir(parents=True)
    (root/'App/VERSIE.txt').write_text('32.4.53\n', encoding='utf-8')
    save_mode_state(root, ModeState(base_mode=Mode.USER, effective_mode=Mode.USER, development_session_active=False))
    _write_mode_marker(root)
    result = mode.apply(root)
    state = load_mode_state(root)
    assert result['status'] == 'APPLIED'
    assert state.base_mode is Mode.MAINTENANCE and state.effective_mode is Mode.MAINTENANCE
    assert state.development_session_active is False


def test_watcher_rechecks_post_release_transition_without_masking_failure():
    text = (TOOLS/'release_watcher.sh').read_text(encoding='utf-8')
    loop = text[text.index('while :; do'):]
    assert 'process_post_release_maintenance_transition' in loop
    assert 'process_post_release_maintenance_transition || true' not in loop
    assert 'post-release-mode-transition-loop' in loop


def _extract_shell_function(source: str, name: str) -> str:
    start = source.index(f'{name}(){{')
    pos = start
    depth = 0
    in_single = False
    in_double = False
    escaped = False
    while pos < len(source):
        ch = source[pos]
        if escaped:
            escaped = False
        elif ch == '\\':
            escaped = True
        elif ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif not in_single and not in_double:
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    return source[start:pos + 1]
        pos += 1
    raise AssertionError(f'unclosed shell function {name}')


def _run_mailbox_contract_function(function_source: str, function_name: str, mailbox: Path):
    script = (
        'set -eu\n'
        f'NAS_CR_LOCAL_DIR={str(mailbox)!r}\n'
        'log(){ :; }\n'
        + function_source + '\n'
        + f'{function_name}\n'
    )
    return subprocess.run(['sh', '-c', script], text=True, capture_output=True, check=False)


def test_watcher_mailbox_contract_rejects_symlink_and_regular_file_without_touching_target(tmp_path):
    watcher = (TOOLS / 'release_watcher.sh').read_text(encoding='utf-8')
    fn = _extract_shell_function(watcher, 'ensure_nas_cr_mailbox_contract')

    external = tmp_path / 'external'
    external.mkdir()
    external.chmod(0o755)
    symlink_mailbox = tmp_path / 'mailbox-link'
    symlink_mailbox.symlink_to(external, target_is_directory=True)
    result = _run_mailbox_contract_function(fn, 'ensure_nas_cr_mailbox_contract', symlink_mailbox)
    assert result.returncode != 0
    assert _mode(external) == 0o755, 'watcher must not chmod a symlink target'

    file_mailbox = tmp_path / 'mailbox-file'
    file_mailbox.write_text('do not replace\n', encoding='utf-8')
    result = _run_mailbox_contract_function(fn, 'ensure_nas_cr_mailbox_contract', file_mailbox)
    assert result.returncode != 0
    assert file_mailbox.read_text(encoding='utf-8') == 'do not replace\n'


def test_bootstrap_mailbox_contract_rejects_symlink_and_regular_file_without_touching_target(tmp_path):
    bootstrap = (TOOLS / 'bootstrap_release_watcher_container.sh').read_text(encoding='utf-8')
    fn = _extract_shell_function(bootstrap, 'ensure_nas_cr_mailbox_contract')

    external = tmp_path / 'external'
    external.mkdir()
    external.chmod(0o755)
    symlink_mailbox = tmp_path / 'mailbox-link'
    symlink_mailbox.symlink_to(external, target_is_directory=True)
    result = _run_mailbox_contract_function(fn, 'ensure_nas_cr_mailbox_contract', symlink_mailbox)
    assert result.returncode != 0
    assert _mode(external) == 0o755, 'bootstrap must not chmod a symlink target'

    file_mailbox = tmp_path / 'mailbox-file'
    file_mailbox.write_text('do not replace\n', encoding='utf-8')
    result = _run_mailbox_contract_function(fn, 'ensure_nas_cr_mailbox_contract', file_mailbox)
    assert result.returncode != 0
    assert file_mailbox.read_text(encoding='utf-8') == 'do not replace\n'


def test_watcher_mailbox_contract_repairs_mode_then_pm_service_accepts(tmp_path):
    watcher = (TOOLS / 'release_watcher.sh').read_text(encoding='utf-8')
    fn = _extract_shell_function(watcher, 'ensure_nas_cr_mailbox_contract')
    root = tmp_path / 'EnergieProject'
    (root / 'App').mkdir(parents=True)
    bridge = root / 'Inbox/nas_container_cr_local'
    bridge.mkdir(parents=True)
    (root / 'App/VERSIE.txt').write_text('32.4.53\n', encoding='utf-8')
    bridge.chmod(0o755)

    repaired = _run_mailbox_contract_function(fn, 'ensure_nas_cr_mailbox_contract', bridge)
    assert repaired.returncode == 0, repaired.stderr
    assert bridge.is_dir() and not bridge.is_symlink() and _mode(bridge) == 0o777

    import nas_container_cr_service as service
    svc = service.ConfiguredNasContainerCrService(root, timeout_seconds=.1, poll_seconds=.01)
    pending = svc.create(expected_release='32.4.53', wait_for_result=False)
    assert pending['status'] == 'PENDING'
    assert (bridge / 'request.json').is_file()


def test_nas_cr_executor_single_flight_across_duplicate_watchers(tmp_path):
    root = tmp_path / 'EnergieProject'
    bridge = root / 'Inbox/nas_container_cr_local'
    pm = root / 'App/slimmemeterportal_import/rootfs/app/projectmanager_v2'
    pm.mkdir(parents=True)
    bridge.mkdir(parents=True)
    bridge.chmod(0o777)
    operation_lock = root / 'Inbox/.nas-container-cr.operation.lock'
    operation_lock.write_text('', encoding='utf-8')
    operation_lock.chmod(0o666)
    (root / 'App/VERSIE.txt').write_text('32.4.53\n', encoding='utf-8')
    request = {
        'schema': 'energie_nas_container_cr_local_request_v1',
        'request_id': 'a' * 32,
        'command_id': 'b' * 32,
        'operation': 'nas_container_cr_create',
        'expected_runtime_version': '32.4.53',
        'created_at': '2026-09-13T18:56:00+00:00',
    }
    (bridge / 'request.json').write_text(json.dumps(request), encoding='utf-8')
    (bridge / 'request.json').chmod(0o644)

    (pm / 'docker_engine_unix_client.py').write_text(
        'class DockerEngineUnixClient:\n    pass\n', encoding='utf-8'
    )
    (pm / 'nas_container_cr_service.py').write_text(
        'import time\nfrom pathlib import Path\n'
        'class NasContainerCrService:\n'
        '    def __init__(self, root, docker): self.root=Path(root)\n'
        '    def create(self):\n'
        '        marker=self.root/"Inbox/nas_container_cr_local/service-starts.txt"\n'
        '        with marker.open("a", encoding="utf-8") as h: h.write("start\\n")\n'
        '        time.sleep(1.0)\n'
        '        return {"version":"32.4.53","production_containers_changed":False,\n'
        '                "backup_dir":"Backups/NAS Container","zip":"x.zip",\n'
        '                "sha256_file":"x.zip.sha256","verify_file":"x VERIFY.txt",\n'
        '                "sha256":"c"*64,"retention":{"kept":"x"}}\n',
        encoding='utf-8'
    )

    exe = TOOLS / 'nas_cr_local_executor.py'
    first = subprocess.Popen(
        [sys.executable, str(exe), '--root', str(root)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    marker = bridge / 'service-starts.txt'
    deadline = __import__('time').monotonic() + 3
    while not marker.exists() and __import__('time').monotonic() < deadline:
        __import__('time').sleep(.01)
    assert marker.exists(), 'first executor did not enter NAS CR service'

    second = subprocess.run(
        [sys.executable, str(exe), '--root', str(root)],
        capture_output=True, text=True, timeout=3, check=False,
    )
    assert second.returncode == 0, second.stderr
    assert 'ALREADY_RUNNING' in second.stdout
    assert marker.read_text(encoding='utf-8').splitlines() == ['start']
    assert (bridge / 'request.json').is_file(), 'second executor must not consume active request'

    out1, err1 = first.communicate(timeout=4)
    assert first.returncode == 0, err1
    assert marker.read_text(encoding='utf-8').splitlines() == ['start']
    assert not (bridge / 'request.json').exists()
    result = json.loads((bridge / 'result.json').read_text(encoding='utf-8'))
    assert result['status'] == 'GREEN' and result['request_id'] == 'a' * 32


def test_nas_cr_operation_lock_rejects_symlink(tmp_path):
    executor = _load_tool('nas_cr_local_executor')
    root = tmp_path / 'EnergieProject'
    inbox = root / 'Inbox'
    inbox.mkdir(parents=True)
    outside = tmp_path / 'outside.lock'
    outside.write_text('outside\n', encoding='utf-8')
    lock = inbox / '.nas-container-cr.operation.lock'
    lock.symlink_to(outside)
    with pytest.raises(OSError):
        with executor._operation_lock(root):
            pass
    assert outside.read_text(encoding='utf-8') == 'outside\n'



def test_nas_cr_operation_lock_is_outside_world_writable_mailbox_and_not_replaceable_by_pm(tmp_path):
    root = tmp_path / 'EnergieProject'
    inbox = root / 'Inbox'
    bridge = inbox / 'nas_container_cr_local'
    (root / 'App').mkdir(parents=True)
    bridge.mkdir(parents=True)
    inbox.chmod(0o755)
    bridge.chmod(0o777)
    (root / 'App/VERSIE.txt').write_text('32.4.53\n', encoding='utf-8')

    executor = _load_tool('nas_cr_local_executor')
    expected_lock = inbox / '.nas-container-cr.operation.lock'
    expected_lock.write_text('', encoding='utf-8')
    expected_lock.chmod(0o666)

    with executor._operation_lock(root) as acquired:
        assert acquired is True
        assert expected_lock.is_file()
        probe_fd = os.open(expected_lock, os.O_RDWR)
        try:
            import fcntl
            with pytest.raises(BlockingIOError):
                fcntl.flock(probe_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            os.close(probe_fd)
        assert not (bridge / '.nas-container-cr.operation.lock').exists()

    if os.geteuid() == 0:
        pid = os.fork()
        if pid == 0:
            try:
                os.setgid(65534)
                os.setuid(65534)
                try:
                    expected_lock.unlink()
                except OSError:
                    os._exit(0)
                os._exit(1)
            except BaseException:
                os._exit(2)
        _, status = os.waitpid(pid, 0)
        assert os.waitstatus_to_exitcode(status) == 0
        assert expected_lock.exists()


def test_nas_cr_duplicate_executor_stays_single_flight_when_mailbox_lock_inode_is_replaced(tmp_path):
    root = tmp_path / 'EnergieProject'
    inbox = root / 'Inbox'
    bridge = inbox / 'nas_container_cr_local'
    pm = root / 'App/slimmemeterportal_import/rootfs/app/projectmanager_v2'
    pm.mkdir(parents=True)
    bridge.mkdir(parents=True)
    inbox.chmod(0o755)
    bridge.chmod(0o777)
    (root / 'App/VERSIE.txt').write_text('32.4.53\n', encoding='utf-8')
    watcher_lock = inbox / '.nas-container-cr.operation.lock'
    watcher_lock.write_text('', encoding='utf-8')
    watcher_lock.chmod(0o666)

    request = {
        'schema': 'energie_nas_container_cr_local_request_v1',
        'request_id': 'd' * 32,
        'command_id': 'e' * 32,
        'operation': 'nas_container_cr_create',
        'expected_runtime_version': '32.4.53',
        'created_at': '2026-09-13T18:56:00+00:00',
    }
    (bridge / 'request.json').write_text(json.dumps(request), encoding='utf-8')
    (bridge / 'request.json').chmod(0o644)
    (pm / 'docker_engine_unix_client.py').write_text(
        'class DockerEngineUnixClient:\n    pass\n', encoding='utf-8'
    )
    (pm / 'nas_container_cr_service.py').write_text(
        'import time\nfrom pathlib import Path\n'
        'class NasContainerCrService:\n'
        '    def __init__(self, root, docker): self.root=Path(root)\n'
        '    def create(self):\n'
        '        marker=self.root/"Inbox/nas_container_cr_local/service-starts.txt"\n'
        '        with marker.open("a", encoding="utf-8") as h: h.write("start\\n")\n'
        '        time.sleep(1.0)\n'
        '        return {"version":"32.4.53","production_containers_changed":False,'
        '"backup_dir":"Backups/NAS Container","zip":"x.zip",'
        '"sha256_file":"x.zip.sha256","verify_file":"x VERIFY.txt",'
        '"sha256":"c"*64,"retention":{"kept":"x"}}\n',
        encoding='utf-8'
    )

    exe = TOOLS / 'nas_cr_local_executor.py'
    first = subprocess.Popen(
        [sys.executable, str(exe), '--root', str(root)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    marker = bridge / 'service-starts.txt'
    deadline = __import__('time').monotonic() + 3
    while not marker.exists() and __import__('time').monotonic() < deadline:
        __import__('time').sleep(.01)
    assert marker.exists(), 'first executor did not enter NAS CR service'

    mailbox_lock = bridge / '.nas-container-cr.operation.lock'
    mailbox_lock.write_text('replacement\n', encoding='utf-8')

    second = subprocess.run(
        [sys.executable, str(exe), '--root', str(root)],
        capture_output=True, text=True, timeout=3, check=False,
    )
    assert second.returncode == 0, second.stderr
    assert 'ALREADY_RUNNING' in second.stdout
    assert marker.read_text(encoding='utf-8').splitlines() == ['start']

    out1, err1 = first.communicate(timeout=4)
    assert first.returncode == 0, err1
    assert marker.read_text(encoding='utf-8').splitlines() == ['start']
