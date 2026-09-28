from __future__ import annotations

import time
from pathlib import Path
from typing import Callable

CONTAINER = 'energie-control-plane'
CONTROL_PLANE_CAPS = ['DAC_OVERRIDE', 'DAC_READ_SEARCH', 'FOWNER']


def _host_project_root(info: dict) -> str:
    host = info.get('HostConfig') if isinstance(info, dict) else {}
    binds = host.get('Binds') if isinstance(host, dict) else []
    for bind in binds or []:
        parts = str(bind).rsplit(':', 2)
        if len(parts) == 3 and parts[1] == '/energy-inbox' and parts[0].endswith('/Inbox'):
            return parts[0][:-len('/Inbox')]
    raise RuntimeError('control-plane host project-root bind ontbreekt')


def _desired_container_payload(host_root: str) -> dict:
    base = str(host_root).rstrip('/')
    return {
        'Image': 'python:3.12-slim',
        'Env': ['PYTHONDONTWRITEBYTECODE=1', 'PYTHONUNBUFFERED=1'],
        'Cmd': [
            'python3', '/control-plane/qnap_control_plane_bootstrap.py',
            '--inbox', '/energy-inbox',
            '--approved-queue', '/pm-approved/queue.json',
            '--runtime-evidence', '/runtime-evidence',
            '--runtime-root', '/control-plane-runtime',
            '--security-root', '/control-plane-runtime',
            '--release-controller-root', '/release-controller',
            '--native-mcp-runtime-root', '/native-mcp-runtime',
            '--host-project-root', base,
            '--interval', '2',
        ],
        'Labels': {'com.energie.component': 'control-plane', 'com.energie.cr.required': 'true'},
        'Healthcheck': {
            'Test': ['CMD', 'python3', '-c', "import pathlib,socket; assert b'qnap_control_plane_bootstrap.py' in pathlib.Path('/proc/1/cmdline').read_bytes(); s=socket.socket(socket.AF_UNIX); s.settimeout(3); s.connect('/var/run/docker.sock'); s.close()"],
            'Interval': 30000000000,
            'Timeout': 5000000000,
            'Retries': 3,
            'StartPeriod': 10000000000,
        },
        'HostConfig': {
            'Binds': [
                f'{base}/Data/03_Systeem/Projectmanager/ControlPlane:/control-plane:ro',
                f'{base}/Inbox:/energy-inbox:ro',
                f'{base}/Data/03_Systeem/Projectmanager/RuntimeV2/approved_actions:/pm-approved:ro',
                f'{base}/Data/03_Systeem/Projectmanager/RuntimeEvidence:/runtime-evidence:ro',
                f'{base}/Data/03_Systeem/Projectmanager/ControlPlane/Runtime:/control-plane-runtime:rw',
                f'{base}/Data/03_Systeem/Projectmanager/ReleaseController:/release-controller:ro',
                f'{base}/Data/03_Systeem/Projectmanager/RuntimeEvidence/NativeMCP:/native-mcp-runtime:ro',
                '/var/run/docker.sock:/var/run/docker.sock:rw',
            ],
            'NetworkMode': 'none',
            'ReadonlyRootfs': True,
            'CapDrop': ['ALL'],
            'CapAdd': list(CONTROL_PLANE_CAPS),
            'SecurityOpt': ['no-new-privileges'],
            'RestartPolicy': {'Name': 'unless-stopped', 'MaximumRetryCount': 0},
            'Tmpfs': {'/tmp': 'size=16m,mode=1777'},
        },
    }


def recreate_for_binding(
    *,
    root: Path,
    info: dict,
    expected: str,
    attempt_path: Path,
    timeout_seconds: float,
    request: Callable,
    optional_json: Callable,
    atomic: Callable,
    clear_attempt: Callable,
    probe: Callable,
    existing_info: Callable,
    container_health: Callable,
    binding_current: Callable,
) -> tuple[dict, bool]:
    previous = optional_json(attempt_path)
    if str(previous.get('expected_fingerprint') or '').lower() == expected and previous.get('retry_allowed') is False:
        raise RuntimeError('control-plane bounded binding recreate already attempted for expected fingerprint')

    host_root = _host_project_root(info)
    backup = f'{CONTAINER}-type2-legacy-{expected[:12]}'
    attempt = {
        'schema': 'energie_control_plane_binding_recreate_attempt_v1',
        'expected_fingerprint': expected,
        'status': 'ATTEMPTING',
        'retry_allowed': False,
        'backup_container': backup,
        'started_at_epoch': time.time(),
    }
    atomic(attempt_path, attempt)

    def restore_previous() -> None:
        try:
            request('DELETE', f'/containers/{CONTAINER}?force=1&v=1', (204, 404))
        except Exception:
            pass
        try:
            request('POST', f'/containers/{backup}/rename?name={CONTAINER}', (204,))
        except Exception:
            return
        try:
            request('POST', f'/containers/{CONTAINER}/start', (204, 304))
        except Exception:
            pass

    try:
        request('POST', f'/containers/{CONTAINER}/stop?t=15', (204, 304))
        request('POST', f'/containers/{CONTAINER}/rename?name={backup}', (204,))
        request('POST', f'/containers/create?name={CONTAINER}', (201,), _desired_container_payload(host_root))
        request('POST', f'/containers/{CONTAINER}/start', (204, 304))

        deadline = time.monotonic() + max(1.0, float(timeout_seconds))
        final = {}
        final_healthy = False
        while time.monotonic() < deadline:
            final = probe(root, stale_seconds=30)
            try:
                current = existing_info()
                _running, final_healthy = container_health(current)
            except Exception:
                current = {}
                final_healthy = False
            if final.get('ready') is True and final_healthy and binding_current(root, current):
                break
            time.sleep(0.5)
        else:
            raise RuntimeError('control-plane recreated binding did not become current')

        request('DELETE', f'/containers/{backup}?force=1&v=1', (204, 404))
        clear_attempt(attempt_path)
        return final, True
    except Exception as exc:
        failed = {**attempt, 'status': 'RED', 'error': f'{type(exc).__name__}:{exc}', 'finished_at_epoch': time.time()}
        atomic(attempt_path, failed)
        restore_previous()
        raise RuntimeError('control-plane binding recreate failed and rollback attempted') from exc
