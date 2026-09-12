#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

RUNTIME_MODULE = 'from __future__ import annotations\n\nimport hashlib\nimport json\nimport os\nfrom datetime import datetime, timezone\nfrom pathlib import Path\n\nSCHEMA = "energie_native_mcp_runtime_v3"\nNATIVE_TARGETS = (\n    "runtime_fingerprint.py",\n    "server.py",\n    "registry.py",\n    "tools_projectmanager.py",\n    "crash_recovery.py",\n    "tools_recovery.py",\n)\n\n\ndef _file_digest(path: Path) -> bytes:\n    if not path.is_file() or path.is_symlink():\n        raise RuntimeError(f"runtime fingerprint source missing/unsafe: {path}")\n    return hashlib.sha256(path.read_bytes()).digest()\n\n\ndef compute_fingerprint(*, native_root: Path, project_root: Path | None = None) -> tuple[str, list[str]]:\n    """Fingerprint only code loaded by the Native MCP process.\n\n    project_root remains an accepted keyword for backwards-compatible callers,\n    but Projectmanager source files are deliberately not part of Native MCP\n    runtime identity. PM-only releases must not force a container restart.\n    """\n    native_root = Path(native_root).resolve()\n    digest = hashlib.sha256()\n    labels: list[str] = []\n    for name in NATIVE_TARGETS:\n        path = native_root / name\n        label = "native:" + name\n        digest.update(label.encode("utf-8") + b"\\0")\n        digest.update(_file_digest(path))\n        labels.append(label)\n    return digest.hexdigest(), labels\n\n\ndef write_runtime_marker() -> dict:\n    native_root = Path(os.environ.get("ENERGIE_NATIVE_MCP_ROOT", "/app")).resolve()\n    system_root = Path(os.environ.get("ENERGIE_SYSTEM_ROOT", "/system")).resolve()\n    fingerprint, targets = compute_fingerprint(native_root=native_root)\n    path = system_root / "Projectmanager/RuntimeEvidence/native_mcp_runtime_fingerprint.json"\n    path.parent.mkdir(parents=True, exist_ok=True)\n    if path.is_symlink():\n        raise RuntimeError("native MCP runtime marker path is symlink")\n    payload = {\n        "schema": SCHEMA,\n        "fingerprint": fingerprint,\n        "targets": targets,\n        "pid": os.getpid(),\n        "written_at": datetime.now(timezone.utc).isoformat(),\n    }\n    temp = path.with_name(path.name + f".tmp-{os.getpid()}")\n    try:\n        with temp.open("x", encoding="utf-8") as handle:\n            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)\n            handle.write("\\n")\n            handle.flush()\n            os.fsync(handle.fileno())\n        os.replace(temp, path)\n    finally:\n        temp.unlink(missing_ok=True)\n    return payload\n'
REQUIRED_INTAKE_FIELDS = ("source_channel", "source_ref", "occurred_at", "classification_hint")
RESULT_REL = Path("Inbox/logs/native_mcp_runtime_contract_hotfix_32.4.39.json")

APPROVAL_TOOL_BLOCK = '\n\n# PM_APPROVAL_TOOL_VERSION=2026-09-11.v2\nAPPROVAL_INGRESS_ROOT = Path(os.environ.get(\n    \'PM_APPROVAL_INGRESS_ROOT\',\n    \'/system/Projectmanager/ApprovalIngress\',\n))\nMAX_APPROVAL_BYTES = 16384\n_APPROVAL_YES = {\'ja\', \'akkoord\', \'goedkeuren\', \'goedgekeurd\', \'yes\', \'approve\'}\n_APPROVAL_NO = {\'nee\', \'afwijzen\', \'afgekeurd\', \'no\', \'reject\'}\n_APPROVAL_CHANNELS = {\'chatgpt\', \'typed\', \'dictation\', \'voice\', \'nomad\', \'speech\'}\n\n\ndef _approval_text_token(value: str) -> str:\n    return \' \'.join(str(value or \'\').strip().lower().strip(\' .,!?:;\').split())\n\n\ndef _pending_decision(decision_id: str) -> dict:\n    status_path = RUNTIME_ROOT / \'status\' / \'current.json\'\n    try:\n        data = json.loads(status_path.read_text(encoding=\'utf-8\'))\n    except (OSError, json.JSONDecodeError) as exc:\n        raise ValueError(\'Projectmanager-status niet leesbaar voor approval.\') from exc\n    matches = [\n        item for item in (data.get(\'decisions_needed\') or [])\n        if isinstance(item, dict)\n        and item.get(\'id\') == decision_id\n        and item.get(\'status\') == \'PENDING\'\n    ]\n    if len(matches) != 1:\n        raise ValueError(\'Exacte PENDING Projectmanager-beslissing niet gevonden.\')\n    return dict(matches[0])\n\n\n@mcp.tool(annotations=WRITE_ANNOTATIONS)\ndef projectmanager_submit_approval(\n    decision_id: str,\n    explicit_user_text: str,\n    approved: bool = True,\n    source_channel: str = \'chatgpt\',\n) -> dict[str, Any]:\n    """Submit Peter\'s explicit approval/rejection for one exact pending decision.\n\n    This tool writes only an immutable approval ingress envelope. It never mutates\n    RuntimeV2 or executes the protected action directly. Remote approval stays\n    fail-closed until the secured connector/edge explicitly enables it.\n    """\n    enabled = str(os.environ.get(\'PM_REMOTE_APPROVAL_ENABLED\', \'\')).strip().lower()\n    if enabled not in {\'1\', \'true\', \'yes\', \'on\'}:\n        raise ValueError(\'Remote approval is fail-closed until secured edge is enabled.\')\n    decision_id = str(decision_id or \'\').strip()\n    if not decision_id:\n        raise ValueError(\'decision_id ontbreekt\')\n    if type(approved) is not bool:\n        raise ValueError(\'approved moet boolean zijn\')\n    channel = str(source_channel or \'\').strip().lower()\n    if channel not in _APPROVAL_CHANNELS:\n        raise ValueError(\'ongeldig approval source_channel\')\n    token = _approval_text_token(explicit_user_text)\n    allowed = _APPROVAL_YES if approved else _APPROVAL_NO\n    if token not in allowed:\n        raise ValueError(\'expliciete gebruikersgoedkeuring/afwijzing ontbreekt of is ambigu\')\n    decision = _pending_decision(decision_id)\n    ingress_id = uuid4().hex\n    envelope = {\n        \'schema\': \'energie_pmv2_approval_ingress_v1\',\n        \'id\': ingress_id,\n        \'decision_id\': decision_id,\n        \'approved\': approved,\n        \'approved_by\': \'Peter\',\n        \'explicit_user_text\': str(explicit_user_text or \'\')[:200],\n        \'source_channel\': channel,\n        \'decision_kind\': decision.get(\'kind\'),\n        \'decision_fingerprint\': decision.get(\'fingerprint\'),\n    }\n    _write_immutable(APPROVAL_INGRESS_ROOT, envelope, max_bytes=MAX_APPROVAL_BYTES)\n    return {\n        \'ok\': True,\n        \'executed\': False,\n        \'state\': \'PROPOSED_EXACT_APPROVAL_TO_LOCAL_PROJECTMANAGER\',\n        \'ingress_id\': ingress_id,\n        \'decision_id\': decision_id,\n        \'approved\': approved,\n        \'requires_local_pm_processing\': True,\n    }\n'

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



def _ensure_approval_tool(tools_text: str) -> tuple[str, bool, str]:
    marker = '# PM_APPROVAL_TOOL_VERSION=2026-09-11.v2'
    anchor = (
        '# Remote decision resolution, direct deploy/purchase/payment and arbitrary\n'
        '# RuntimeV2 writes are deliberately absent. Protected approval stays local HA.\n'
    )
    if tools_text.count(anchor) != 1:
        raise RuntimeError('tools_projectmanager approval insertion anchor mismatch')
    if marker in tools_text:
        return tools_text, False, 'approval_tool_current'
    if 'def projectmanager_submit_approval(' in tools_text:
        start = tools_text.find('\n\nAPPROVAL_INGRESS_ROOT =')
        if start < 0:
            start = tools_text.find('APPROVAL_INGRESS_ROOT =')
        end = tools_text.find(anchor)
        if start < 0 or end <= start:
            raise RuntimeError('tools_projectmanager old approval block boundaries mismatch')
        upgraded = tools_text[:start] + APPROVAL_TOOL_BLOCK + '\n' + tools_text[end:]
        return upgraded, True, 'approval_tool_upgraded'
    return tools_text.replace(anchor, APPROVAL_TOOL_BLOCK + '\n' + anchor, 1), True, 'approval_tool_added'

def apply(root: Path | str) -> dict:
    root = Path(root).resolve()
    version = (root / "App/VERSIE.txt").read_text(encoding="utf-8").strip()
    try:
        version_tuple = tuple(int(part) for part in version.split("."))
    except ValueError as exc:
        raise RuntimeError(f"invalid active release version: {version!r}") from exc
    if version_tuple < (32, 4, 39):
        raise RuntimeError(f"runtime contract hotfix requires 32.4.39+, got {version!r}")
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
    patched_tools, approval_changed, approval_change = _ensure_approval_tool(tools_text)
    if approval_changed:
        _atomic_text(tools_pm, patched_tools)
        tools_text = patched_tools
        changed.append("tools_projectmanager.py:" + approval_change)
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
        "approval_ingress_tool_present": "def projectmanager_submit_approval(" in tools_text,
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
