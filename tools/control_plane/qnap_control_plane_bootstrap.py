#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import os
import sys
import control_plane as cp
QNAP_PHYSICAL_PROJECT_ROOT = "/share/CACHEDEV1_DATA/AI Projecten/EnergieProject"


def _ensure_control_plane_mailboxes(inbox: Path) -> dict:
    """Precreate shared producer/consumer mailboxes with live-equivalent rights.

    The PM and control-plane run under different container identities. 32.4.41
    incorrectly relied on the PM being able to mkdir below a 0755 directory
    owned by the control-plane identity. The control-plane now owns bootstrap of
    this shared IPC boundary and proves write/readback before its main loop.
    """
    inbox = Path(inbox)
    root = inbox / 'control_plane'
    paths = (root, root / 'requests', root / 'results')
    for path in paths:
        if path.is_symlink():
            raise RuntimeError(f'onveilige control-plane mailbox symlink: {path}')
        if path.exists() and not path.is_dir():
            raise RuntimeError(f'control-plane mailbox is geen directory: {path}')
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(path, 0o777)
        if path.stat().st_mode & 0o777 != 0o777:
            raise RuntimeError(f'control-plane mailbox mode readback mismatch: {path}')

    probe = root / 'requests' / f'.control_plane_write_probe.{os.getpid()}'
    try:
        fd = os.open(str(probe), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o666)
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write('control-plane shared mailbox write probe\n')
            handle.flush()
            os.fsync(handle.fileno())
        if probe.read_text(encoding='utf-8') != 'control-plane shared mailbox write probe\n':
            raise RuntimeError('control-plane mailbox write/readback mismatch')
    finally:
        try:
            probe.unlink(missing_ok=True)
        except OSError:
            pass
    return {'root': str(root), 'requests': str(root/'requests'), 'results': str(root/'results'), 'mode': '0777'}


def _argv_value(flag: str, default: str) -> str:
    try:
        index = sys.argv.index(flag)
    except ValueError:
        return default
    if index + 1 >= len(sys.argv):
        return default
    return str(sys.argv[index + 1])


def qnap_watcher_create_payload(host_project_root: str) -> dict:
    host_root = str(host_project_root).rstrip("/")
    if host_root != QNAP_PHYSICAL_PROJECT_ROOT:
        raise RuntimeError("onverwachte QNAP host project-root")
    return {
        "Image": cp.WATCHER_IMAGE,
        "Cmd": list(cp.WATCHER_COMMAND),
        "Env": [
            "ENERGIE_ROOT=/energy",
            "ENERGIE_WATCH_INTERVAL=5",
            "ENERGIE_ZIP_STABLE_POLLS=3",
            "ENERGIE_WATCHER_HEARTBEAT_STALE_SECONDS=30",
            "ENERGIE_WATCHER_CONTAINER_CONTRACT=3",
            "ENERGIE_BACKUP_RETENTION=999",
            "ENERGIE_PROCESSED_RETENTION=999",
        ],
        "HostConfig": {
            "Binds": [
                f"{host_root}:/energy",
                "/var/run/docker.sock:/var/run/docker.sock",
            ],
            "NetworkMode": "none",
            "CapDrop": ["ALL"],
            "CapAdd": list(cp.WATCHER_CAPS),
            "SecurityOpt": ["no-new-privileges"],
            "RestartPolicy": {"Name": "unless-stopped", "MaximumRetryCount": 0},
        },
    }

def _current_watcher_command(inbox: Path, approval: dict, live_version: str) -> dict:
    command_queue = Path(inbox) / "projectmanager_v2" / "RuntimeV2" / "commands" / "queue.json"
    data = cp._load_json(command_queue)
    command_id = str(approval.get("command_id") or "").strip()
    decision_id = str(approval.get("decision_id") or "").strip()
    for item in reversed(data.get("items") or []):
        if not isinstance(item, dict) or item.get("id") != command_id:
            continue
        if item.get("intent") != "watcher_recreate":
            raise RuntimeError("goedgekeurd command heeft verkeerde intent")
        if item.get("approval_decision_id") != decision_id:
            raise RuntimeError("goedgekeurd command/decision koppeling mismatch")
        if item.get("status") != "APPROVED_WAITING_EXECUTOR":
            raise RuntimeError("watcher command staat niet APPROVED_WAITING_EXECUTOR")
        if str(item.get("release_version") or "").strip() != live_version:
            raise RuntimeError("watcher command hoort niet bij actuele live release")
        return item
    raise RuntimeError("actueel goedgekeurd watcher command ontbreekt")

def qnap_load_bootstrap_watcher_request(inbox: Path, approved_queue: Path, version_path: Path):
    request = cp._load_json(Path(inbox) / "watcher_recreate_request.json")
    live_version = Path(version_path).read_text(encoding="utf-8").strip()
    stable_required = {
        "schema": "energie_watcher_recreate_request_v1",
        "operation": "recreate_exact_energie_release_watcher",
        "container": cp.WATCHER_CONTAINER,
        "contract_version": 3,
    }
    for key, expected in stable_required.items():
        if request.get(key) != expected:
            raise RuntimeError(f"watcher request mismatch: {key}")
    request_id = str(request.get("request_id") or "").lower()
    if len(request_id) != 32 or any(ch not in "0123456789abcdef" for ch in request_id):
        raise RuntimeError("watcher request_id ongeldig")
    approval = cp.find_live_approval(approved_queue, "watcher_recreate")
    _current_watcher_command(Path(inbox), approval, live_version)
    current_request = dict(request)
    current_request["release_version"] = live_version
    current_request["confirmation_required"] = f"RECREATE WATCHER {live_version}"
    return current_request, approval

cp.watcher_create_payload = qnap_watcher_create_payload
cp.load_bootstrap_watcher_request = qnap_load_bootstrap_watcher_request
if __name__ == "__main__":
    _ensure_control_plane_mailboxes(Path(_argv_value('--inbox', '/energy-inbox')))
    raise SystemExit(cp.main())
