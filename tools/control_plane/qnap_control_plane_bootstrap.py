#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import control_plane as cp
QNAP_PHYSICAL_PROJECT_ROOT = "/share/CACHEDEV1_DATA/AI Projecten/EnergieProject"

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
    raise SystemExit(cp.main())
