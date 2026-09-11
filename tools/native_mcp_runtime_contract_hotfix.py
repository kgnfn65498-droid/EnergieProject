#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

RUNTIME_MODULE = 'from __future__ import annotations\n\nimport hashlib\nimport json\nimport os\nfrom datetime import datetime, timezone\nfrom pathlib import Path\n\nSCHEMA = "energie_native_mcp_runtime_v2"\nNATIVE_TARGETS = (\n    "runtime_fingerprint.py",\n    "server.py",\n    "registry.py",\n    "tools_projectmanager.py",\n    "crash_recovery.py",\n    "tools_recovery.py",\n)\nPM_TARGETS = (\n    "command_gateway.py",\n    "projectmanager_api.py",\n    "secret_guard.py",\n)\n\ndef _file_digest(path: Path) -> bytes:\n    if not path.is_file() or path.is_symlink():\n        raise RuntimeError(f"runtime fingerprint source missing/unsafe: {path}")\n    return hashlib.sha256(path.read_bytes()).digest()\n\ndef compute_fingerprint(*, native_root: Path, project_root: Path) -> tuple[str, list[str]]:\n    native_root = Path(native_root).resolve()\n    project_root = Path(project_root).resolve()\n    pm_root = project_root / "App/slimmemeterportal_import/rootfs/app/projectmanager_v2"\n    digest = hashlib.sha256()\n    labels: list[str] = []\n    for name in NATIVE_TARGETS:\n        path = native_root / name\n        label = "native:" + name\n        digest.update(label.encode("utf-8") + b"\\0")\n        digest.update(_file_digest(path))\n        labels.append(label)\n    for name in PM_TARGETS:\n        path = pm_root / name\n        label = "pm:" + name\n        digest.update(label.encode("utf-8") + b"\\0")\n        digest.update(_file_digest(path))\n        labels.append(label)\n    return digest.hexdigest(), labels\n\ndef write_runtime_marker() -> dict:\n    native_root = Path(os.environ.get("ENERGIE_NATIVE_MCP_ROOT", "/app")).resolve()\n    project_root = Path(os.environ.get("ENERGIE_ROOT", "/project")).resolve()\n    system_root = Path(os.environ.get("ENERGIE_SYSTEM_ROOT", "/system")).resolve()\n    fingerprint, targets = compute_fingerprint(native_root=native_root, project_root=project_root)\n    path = system_root / "Projectmanager/RuntimeEvidence/native_mcp_runtime_fingerprint.json"\n    path.parent.mkdir(parents=True, exist_ok=True)\n    if path.is_symlink():\n        raise RuntimeError("native MCP runtime marker path is symlink")\n    payload = {\n        "schema": SCHEMA,\n        "fingerprint": fingerprint,\n        "targets": targets,\n        "pid": os.getpid(),\n        "written_at": datetime.now(timezone.utc).isoformat(),\n    }\n    temp = path.with_name(path.name + f".tmp-{os.getpid()}")\n    try:\n        with temp.open("x", encoding="utf-8") as handle:\n            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)\n            handle.write("\\n")\n            handle.flush()\n            os.fsync(handle.fileno())\n        os.replace(temp, path)\n    finally:\n        temp.unlink(missing_ok=True)\n    return payload\n'
REQUIRED_INTAKE_FIELDS = ("source_channel", "source_ref", "occurred_at", "classification_hint")
RESULT_REL = Path("Inbox/logs/native_mcp_runtime_contract_hotfix_32.4.39.json")

def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f"refuse symlink target: {path}")
    temp = path.with_name(path.name + f".tmp-{os.getpid()}")
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)

def _atomic_json(path: Path, payload: dict) -> None:
    _atomic_text(path, json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")

def apply(root: Path | str) -> dict:
    root = Path(root).resolve()
    version = (root / "App/VERSIE.txt").read_text(encoding="utf-8").strip()
    if version != "32.4.39":
        raise RuntimeError(f"runtime contract hotfix requires active 32.4.39, got {version!r}")
    native = root / "Infra/Docker/native-mcp"
    server = native / "server.py"
    tools_pm = native / "tools_projectmanager.py"
    if not server.is_file() or server.is_symlink() or not tools_pm.is_file() or tools_pm.is_symlink():
        raise RuntimeError("native MCP sources missing/unsafe")
    tools_text = tools_pm.read_text(encoding="utf-8")
    missing = [field for field in REQUIRED_INTAKE_FIELDS if field not in tools_text]
    if missing:
        raise RuntimeError("tools_projectmanager.py missing required intake fields: " + ",".join(missing))
    changed = []
    runtime = native / "runtime_fingerprint.py"
    if not runtime.is_file() or runtime.read_text(encoding="utf-8") != RUNTIME_MODULE:
        _atomic_text(runtime, RUNTIME_MODULE)
        changed.append("runtime_fingerprint.py")
    text = server.read_text(encoding="utf-8")
    import_line = "from runtime_fingerprint import write_runtime_marker\n"
    call_line = "    write_runtime_marker()\n"
    if import_line not in text:
        anchor = "from registry import mcp\n"
        if text.count(anchor) != 1:
            raise RuntimeError("server registry import anchor mismatch")
        text = text.replace(anchor, anchor + import_line, 1)
        changed.append("server.py:import")
    if call_line not in text:
        anchor = 'if __name__ == "__main__":\n'
        if text.count(anchor) != 1:
            raise RuntimeError("server main anchor mismatch")
        text = text.replace(anchor, anchor + call_line, 1)
        if "server.py:import" not in changed:
            changed.append("server.py:call")
    if text != server.read_text(encoding="utf-8"):
        _atomic_text(server, text)
    result = {
        "schema": "energie_native_mcp_runtime_contract_hotfix_v1",
        "status": "GREEN",
        "release_version": version,
        "changed": changed,
        "reload_required": bool(changed),
        "intake_schema_source_fields_present": True,
    }
    _atomic_json(root / RESULT_REL, result)
    return result

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True)
    args = parser.parse_args()
    result = apply(Path(args.root))
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
