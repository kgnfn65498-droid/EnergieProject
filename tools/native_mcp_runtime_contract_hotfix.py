#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

RUNTIME_MODULE = 'from __future__ import annotations\n\nimport hashlib\nimport json\nimport os\nfrom datetime import datetime, timezone\nfrom pathlib import Path\n\nSCHEMA = "energie_native_mcp_runtime_v3"\nNATIVE_TARGETS = (\n    "runtime_fingerprint.py",\n    "server.py",\n    "registry.py",\n    "tools_projectmanager.py",\n    "crash_recovery.py",\n    "tools_recovery.py",\n    "tools_clearup_export.py",\n)\n\n\ndef _file_digest(path: Path) -> bytes:\n    if not path.is_file() or path.is_symlink():\n        raise RuntimeError(f"runtime fingerprint source missing/unsafe: {path}")\n    return hashlib.sha256(path.read_bytes()).digest()\n\n\ndef compute_fingerprint(*, native_root: Path, project_root: Path | None = None) -> tuple[str, list[str]]:\n    """Fingerprint only code loaded by the Native MCP process.\n\n    project_root remains an accepted keyword for backwards-compatible callers,\n    but Projectmanager source files are deliberately not part of Native MCP\n    runtime identity. PM-only releases must not force a container restart.\n    """\n    native_root = Path(native_root).resolve()\n    digest = hashlib.sha256()\n    labels: list[str] = []\n    for name in NATIVE_TARGETS:\n        path = native_root / name\n        label = "native:" + name\n        digest.update(label.encode("utf-8") + b"\\0")\n        digest.update(_file_digest(path))\n        labels.append(label)\n    return digest.hexdigest(), labels\n\n\ndef write_runtime_marker() -> dict:\n    native_root = Path(os.environ.get("ENERGIE_NATIVE_MCP_ROOT", "/app")).resolve()\n    system_root = Path(os.environ.get("ENERGIE_SYSTEM_ROOT", "/system")).resolve()\n    fingerprint, targets = compute_fingerprint(native_root=native_root)\n    path = system_root / "Projectmanager/RuntimeEvidence/native_mcp_runtime_fingerprint.json"\n    path.parent.mkdir(parents=True, exist_ok=True)\n    if path.is_symlink():\n        raise RuntimeError("native MCP runtime marker path is symlink")\n    payload = {\n        "schema": SCHEMA,\n        "fingerprint": fingerprint,\n        "targets": targets,\n        "pid": os.getpid(),\n        "written_at": datetime.now(timezone.utc).isoformat(),\n    }\n    temp = path.with_name(path.name + f".tmp-{os.getpid()}")\n    try:\n        with temp.open("x", encoding="utf-8") as handle:\n            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)\n            handle.write("\\n")\n            handle.flush()\n            os.fsync(handle.fileno())\n        os.replace(temp, path)\n    finally:\n        temp.unlink(missing_ok=True)\n    return payload\n'
CLEARUP_EXPORT_MODULE = 'from __future__ import annotations\n\nimport base64\nimport hashlib\nimport json\nimport os\nimport zipfile\nfrom datetime import datetime, timezone\nfrom pathlib import Path\nfrom typing import Any\n\nfrom registry import mcp, READ_ONLY_ANNOTATIONS, WRITE_ANNOTATIONS\n\nPROJECT_ROOT = Path(os.environ.get("ENERGIE_PROJECT_ROOT", "/project")).resolve()\nSYSTEM_ROOT = Path(os.environ.get("ENERGIE_SYSTEM_ROOT", "/system")).resolve()\nEXPORT_ROOT = SYSTEM_ROOT / "Projectmanager/ClearUp/Exports"\nCHUNK_MAX = 6144\nCLEARUP_ROOTS = {\n    "ClearUp_001": [\n        "Inbox/.bridge_patch_stage_20260914T171141Z",\n        "Inbox/live_bridge_backup_20260914T171141Z",\n        "Inbox/live_bridge_backup_queue_schema_20260914T172223Z",\n        "Inbox/.release-transition.operation.lock.backup_20260914T1812Z",\n    ],\n}\n\ndef _sha(path: Path) -> str:\n    h = hashlib.sha256()\n    with path.open("rb") as f:\n        for block in iter(lambda: f.read(1024 * 1024), b""):\n            h.update(block)\n    return h.hexdigest()\n\ndef _safe_project(rel: str) -> Path:\n    p = (PROJECT_ROOT / rel).resolve()\n    if p == PROJECT_ROOT or PROJECT_ROOT not in p.parents:\n        raise ValueError("unsafe project path")\n    return p\n\ndef _collect(clearup_id: str) -> tuple[list[str], list[dict[str, Any]]]:\n    roots = CLEARUP_ROOTS.get(clearup_id)\n    if roots is None:\n        raise ValueError("unsupported clearup_id")\n    rows: list[dict[str, Any]] = []\n    for rel in roots:\n        p = _safe_project(rel)\n        if not p.exists() or p.is_symlink():\n            raise ValueError(f"candidate missing/unsafe: {rel}")\n        seq = [p] if p.is_file() else [p, *sorted(p.rglob("*"))]\n        for q in seq:\n            if q.is_symlink():\n                raise ValueError("symlink refused")\n            r = q.relative_to(PROJECT_ROOT).as_posix()\n            if q.is_file(): rows.append({"path": r, "type": "file", "size": q.stat().st_size, "sha256": _sha(q)})\n            elif q.is_dir(): rows.append({"path": r, "type": "directory"})\n    return list(roots), rows\n\ndef _zip_path(clearup_id: str) -> Path:\n    if clearup_id not in CLEARUP_ROOTS: raise ValueError("unsupported clearup_id")\n    return EXPORT_ROOT / f"{clearup_id}_Inbox_Type1_2026-09-23.zip"\n\ndef _verify(path: Path, clearup_id: str, expected_rows: list[dict[str, Any]] | None = None) -> dict[str, Any]:\n    if not path.is_file() or path.is_symlink(): raise ValueError("recovery ZIP missing/unsafe")\n    with zipfile.ZipFile(path) as z:\n        bad = z.testzip()\n        if bad: raise ValueError(f"corrupt ZIP member: {bad}")\n        manifest = json.loads(z.read("CLEARUP_MANIFEST.json"))\n        if manifest.get("clearup_id") != clearup_id: raise ValueError("manifest clearup_id mismatch")\n        if manifest.get("roots") != CLEARUP_ROOTS[clearup_id]: raise ValueError("manifest roots mismatch")\n        rows = manifest.get("items")\n        if not isinstance(rows, list): raise ValueError("manifest items missing")\n        if expected_rows is not None and rows != expected_rows: raise ValueError("manifest/live rows mismatch")\n        names = set(z.namelist())\n        expected_files = {x["path"] for x in rows if x.get("type") == "file"}\n        if not expected_files.issubset(names): raise ValueError("ZIP payload incomplete")\n        for row in rows:\n            if row.get("type") != "file": continue\n            data = z.read(row["path"])\n            if len(data) != row["size"] or hashlib.sha256(data).hexdigest() != row["sha256"]:\n                raise ValueError(f"payload verification failed: {row[\'path\']}")\n    return manifest\n\n@mcp.tool(annotations=WRITE_ANNOTATIONS)\ndef clearup_prepare_recovery_export(clearup_id: str = "ClearUp_001") -> dict[str, Any]:\n    """Build and fully verify one allowlisted ClearUp recovery ZIP; never deletes source data."""\n    roots, rows = _collect(clearup_id)\n    EXPORT_ROOT.mkdir(parents=True, exist_ok=True)\n    out = _zip_path(clearup_id); tmp = out.with_suffix(out.suffix + f".tmp-{os.getpid()}")\n    manifest = {"schema":"energie_clearup_recovery_v2","clearup_id":clearup_id,"classification":"TYPE1","created_at":datetime.now(timezone.utc).isoformat(),"roots":roots,"items":rows,"deletion_performed":False}\n    try:\n        with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED) as z:\n            z.writestr("CLEARUP_MANIFEST.json",json.dumps(manifest,ensure_ascii=False,indent=2)+"\\n")\n            for row in rows:\n                src=PROJECT_ROOT/row["path"]\n                if row["type"]=="directory": z.writestr(row["path"].rstrip("/")+"/",b"")\n                else: z.write(src,row["path"])\n        os.replace(tmp,out)\n    finally: tmp.unlink(missing_ok=True)\n    _verify(out,clearup_id,rows)\n    return {"status":"GREEN","clearup_id":clearup_id,"artifact":out.name,"size":out.stat().st_size,"sha256":_sha(out),"roots":roots,"files":sum(1 for x in rows if x["type"]=="file"),"directories":sum(1 for x in rows if x["type"]=="directory"),"deletion_performed":False}\n\n@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)\ndef clearup_recovery_export_info(clearup_id: str = "ClearUp_001") -> dict[str, Any]:\n    """Re-verify an allowlisted recovery ZIP and return immutable export metadata."""\n    out=_zip_path(clearup_id); manifest=_verify(out,clearup_id)\n    return {"status":"GREEN","clearup_id":clearup_id,"artifact":out.name,"size":out.stat().st_size,"sha256":_sha(out),"roots":manifest["roots"],"item_count":len(manifest["items"])}\n\n@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)\ndef clearup_recovery_export_chunk(clearup_id: str = "ClearUp_001", offset: int = 0, max_bytes: int = CHUNK_MAX) -> dict[str, Any]:\n    """Return one bounded base64 chunk of a fully verified allowlisted recovery ZIP."""\n    if type(offset) is not int or offset < 0: raise ValueError("offset must be a non-negative integer")\n    if type(max_bytes) is not int or max_bytes < 1 or max_bytes > CHUNK_MAX: raise ValueError(f"max_bytes must be 1..{CHUNK_MAX}")\n    out=_zip_path(clearup_id); _verify(out,clearup_id); total=out.stat().st_size\n    if offset > total: raise ValueError("offset beyond EOF")\n    with out.open("rb") as f: f.seek(offset); data=f.read(max_bytes)\n    nxt=offset+len(data)\n    return {"status":"GREEN","clearup_id":clearup_id,"artifact":out.name,"offset":offset,"bytes":len(data),"chunk_sha256":hashlib.sha256(data).hexdigest(),"artifact_sha256":_sha(out),"total_size":total,"next_offset":nxt,"eof":nxt>=total,"base64":base64.b64encode(data).decode("ascii")}\n\n# TYPE2_CHAT_EXPORT_VERSION=2026-09-25.v1\nTYPE2_EXPORT_IDS = {f"ClearUp_{i:03d}" for i in range(2, 13)}\nTYPE2_CHUNK_MAX = 32768\n\n\ndef _type2_zip_path(clearup_id: str) -> Path:\n    if clearup_id not in TYPE2_EXPORT_IDS:\n        raise ValueError("unsupported Type2 clearup_id")\n    return EXPORT_ROOT / f"{clearup_id}_Type2_recovery.zip"\n\n\ndef _verify_type2_export(path: Path, clearup_id: str) -> dict[str, Any]:\n    if clearup_id not in TYPE2_EXPORT_IDS:\n        raise ValueError("unsupported Type2 clearup_id")\n    if not path.is_file() or path.is_symlink():\n        raise ValueError("Type2 recovery ZIP missing/unsafe")\n    try:\n        with zipfile.ZipFile(path) as z:\n            bad = z.testzip()\n            if bad:\n                raise ValueError(f"corrupt Type2 ZIP member: {bad}")\n            manifest = json.loads(z.read("TYPE2_MANIFEST.json"))\n            if manifest.get("schema") != "energie_clearup_type2_recovery_v1":\n                raise ValueError("Type2 manifest schema mismatch")\n            if manifest.get("classification") != "TYPE2" or manifest.get("clearup_id") != clearup_id:\n                raise ValueError("Type2 manifest identity mismatch")\n            if manifest.get("deletion_performed") is not False:\n                raise ValueError("Type2 recovery manifest is not pre-delete")\n            items = manifest.get("items")\n            if not isinstance(items, list) or not items:\n                raise ValueError("Type2 manifest items missing")\n            names = set(z.namelist())\n            for item in items:\n                if not isinstance(item, dict):\n                    raise ValueError("Type2 manifest item invalid")\n                rows = item.get("source_rows")\n                if not isinstance(rows, list):\n                    raise ValueError("Type2 source_rows missing")\n                for row in rows:\n                    if not isinstance(row, dict) or row.get("type") != "file":\n                        continue\n                    rel = str(row.get("path") or "")\n                    member = "original/" + rel\n                    if member not in names:\n                        raise ValueError(f"Type2 ZIP payload incomplete: {member}")\n                    data = z.read(member)\n                    if len(data) != int(row.get("size") or -1):\n                        raise ValueError(f"Type2 payload size mismatch: {member}")\n                    if hashlib.sha256(data).hexdigest() != str(row.get("sha256") or ""):\n                        raise ValueError(f"Type2 payload hash mismatch: {member}")\n    except (OSError, zipfile.BadZipFile, KeyError, json.JSONDecodeError) as exc:\n        raise ValueError("Type2 recovery ZIP verification failed") from exc\n    return manifest\n\n\n@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)\ndef clearup_type2_recovery_export_info(clearup_id: str) -> dict[str, Any]:\n    """Re-verify one allowlisted Type2 recovery ZIP and return immutable metadata."""\n    path = _type2_zip_path(clearup_id)\n    manifest = _verify_type2_export(path, clearup_id)\n    return {\n        "status": "GREEN",\n        "clearup_id": clearup_id,\n        "artifact": path.name,\n        "size": path.stat().st_size,\n        "sha256": _sha(path),\n        "plan_sha256": str(manifest.get("plan_sha256") or ""),\n        "item_count": len(manifest.get("items") or []),\n        "deletion_performed": False,\n    }\n\n\n@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)\ndef clearup_type2_recovery_export_chunk(clearup_id: str, offset: int = 0, max_bytes: int = TYPE2_CHUNK_MAX) -> dict[str, Any]:\n    """Return one bounded base64 chunk of a fully verified Type2 recovery ZIP."""\n    if type(offset) is not int or offset < 0:\n        raise ValueError("offset must be a non-negative integer")\n    if type(max_bytes) is not int or max_bytes < 1 or max_bytes > TYPE2_CHUNK_MAX:\n        raise ValueError(f"max_bytes must be 1..{TYPE2_CHUNK_MAX}")\n    info = clearup_type2_recovery_export_info(clearup_id)\n    path = _type2_zip_path(clearup_id)\n    total = path.stat().st_size\n    if offset > total:\n        raise ValueError("offset beyond EOF")\n    with path.open("rb") as handle:\n        handle.seek(offset)\n        data = handle.read(max_bytes)\n    nxt = offset + len(data)\n    return {\n        **info,\n        "offset": offset,\n        "bytes": len(data),\n        "next_offset": nxt,\n        "eof": nxt >= total,\n        "chunk_sha256": hashlib.sha256(data).hexdigest(),\n        "base64": base64.b64encode(data).decode("ascii"),\n    }\n\n'
REQUIRED_INTAKE_FIELDS = ("source_channel", "source_ref", "occurred_at", "classification_hint")
RESULT_REL = Path("Inbox/logs/native_mcp_runtime_contract_hotfix_32.4.39.json")

# TYPE2_RECOVERY_DOWNLOAD_BRIDGE_VERSION=2026-09-25.v3
TYPE2_DOWNLOAD_BRIDGE_MARKER = "# TYPE2_RECOVERY_DOWNLOAD_BRIDGE_VERSION=2026-09-25.v3"
TYPE2_DOWNLOAD_BRIDGE_BLOCK = '# TYPE2_RECOVERY_DOWNLOAD_BRIDGE_VERSION=2026-09-25.v3\nimport hashlib as _type2_hashlib\nimport hmac as _type2_hmac\nimport secrets as _type2_secrets\nimport time as _type2_time\nfrom urllib.parse import urlencode as _type2_urlencode\n\n_TYPE2_DOWNLOAD_IDS = {f"ClearUp_{i:03d}" for i in range(2, 13)}\n_TYPE2_DOWNLOAD_SECRET = _type2_secrets.token_bytes(32)\n_TYPE2_DOWNLOAD_TTL_SECONDS = 300\n_TYPE2_SYSTEM_ROOT = Path(os.environ.get("ENERGIE_SYSTEM_ROOT", "/system")).resolve()\n_TYPE2_PROJECT_ROOT = Path(os.environ.get("ENERGIE_ROOT", "/project")).resolve()\n_TYPE2_EXPORT_ROOT = _TYPE2_SYSTEM_ROOT / "Projectmanager/ClearUp/Exports"\n_TYPE2_GATE_PATH = _TYPE2_SYSTEM_ROOT / "Projectmanager/ClearUp/State/TYPE2_EXTERNAL_RECOVERY_GATE.json"\n\n\ndef _type2_export_info(clearup_id: str) -> dict[str, Any]:\n    if clearup_id not in _TYPE2_DOWNLOAD_IDS:\n        raise ValueError("unsupported Type2 clearup_id")\n    from tools_clearup_export import clearup_type2_recovery_export_info\n    return clearup_type2_recovery_export_info(clearup_id)\n\n\ndef _type2_public_base_url() -> str:\n    compose = _TYPE2_PROJECT_ROOT / "Infra/docker-compose.yml"\n    try:\n        lines = compose.read_text(encoding="utf-8").splitlines()\n    except OSError:\n        return ""\n    for index, line in enumerate(lines[:-1]):\n        if line.strip() != "- --url":\n            continue\n        candidate = lines[index + 1].strip()\n        if candidate.startswith("- https://"):\n            return candidate[2:].strip().rstrip("/")\n    return ""\n\n\ndef _type2_signature(clearup_id: str, expires: int, sha256: str) -> str:\n    payload = f"{clearup_id}|{expires}|{sha256}".encode("utf-8")\n    return _type2_hmac.new(_TYPE2_DOWNLOAD_SECRET, payload, _type2_hashlib.sha256).hexdigest()\n\n\ndef _type2_download_descriptor(clearup_id: str) -> dict[str, Any]:\n    info = _type2_export_info(clearup_id)\n    expires = int(_type2_time.time()) + _TYPE2_DOWNLOAD_TTL_SECONDS\n    sha256 = str(info.get("sha256") or "")\n    signature = _type2_signature(clearup_id, expires, sha256)\n    query = _type2_urlencode({\n        "clearup_id": clearup_id,\n        "expires": str(expires),\n        "sha256": sha256,\n        "signature": signature,\n    })\n    relative_url = f"/clearup/type2/download?{query}"\n    base = _type2_public_base_url()\n    return {\n        **info,\n        "expires_epoch": expires,\n        "relative_download_url": relative_url,\n        "download_url": (base + relative_url) if base else "",\n        "deletion_performed": False,\n    }\n\n\ndef _attach_type2_recovery_downloads(payload: Any) -> Any:\n    if not isinstance(payload, dict):\n        return payload\n    try:\n        gate = json.loads(_TYPE2_GATE_PATH.read_text(encoding="utf-8"))\n    except (OSError, json.JSONDecodeError):\n        return payload\n    if gate.get("status") != "BLOCK_DELETE_UNTIL_EXTERNAL_COPY_CONFIRMED":\n        return payload\n    if gate.get("delete_allowed") is not False:\n        return payload\n    required = gate.get("required_exports") or []\n    expected = [f"ClearUp_{i:03d}_Type2_recovery.zip" for i in range(2, 13)]\n    if required != expected:\n        return payload\n    downloads = []\n    failures = []\n    for i in range(2, 13):\n        clearup_id = f"ClearUp_{i:03d}"\n        try:\n            downloads.append(_type2_download_descriptor(clearup_id))\n        except Exception as exc:\n            failures.append({"clearup_id": clearup_id, "error": f"{type(exc).__name__}: {exc}"})\n    enriched = dict(payload)\n    enriched["type2_external_recovery"] = {\n        "status": "READY_FOR_EXTERNAL_DOWNLOAD" if not failures else "PARTIAL_BLOCKED",\n        "delete_allowed": False,\n        "exports_root": "Data/03_Systeem/Projectmanager/ClearUp/Exports",\n        "downloads": downloads,\n        "failures": failures,\n        "required_count": 11,\n        "verified_count": len(downloads),\n    }\n    return enriched\n\n\nasync def _type2_recovery_download_http(request):\n    from starlette.responses import FileResponse, JSONResponse\n\n    clearup_id = str(request.query_params.get("clearup_id") or "")\n    try:\n        expires = int(request.query_params.get("expires") or "0")\n    except ValueError:\n        expires = 0\n    sha256 = str(request.query_params.get("sha256") or "").lower()\n    signature = str(request.query_params.get("signature") or "").lower()\n    if clearup_id not in _TYPE2_DOWNLOAD_IDS:\n        return JSONResponse({"status": "error", "error": "unsupported clearup_id"}, status_code=404)\n    now = int(_type2_time.time())\n    if expires <= now or expires > now + _TYPE2_DOWNLOAD_TTL_SECONDS + 30:\n        return JSONResponse({"status": "error", "error": "download link expired"}, status_code=403)\n    expected_sig = _type2_signature(clearup_id, expires, sha256)\n    if not signature or not _type2_hmac.compare_digest(signature, expected_sig):\n        return JSONResponse({"status": "error", "error": "invalid signature"}, status_code=403)\n    try:\n        info = _type2_export_info(clearup_id)\n    except Exception:\n        return JSONResponse({"status": "error", "error": "recovery export verification failed"}, status_code=409)\n    if str(info.get("sha256") or "").lower() != sha256:\n        return JSONResponse({"status": "error", "error": "recovery export identity changed"}, status_code=409)\n    path = _TYPE2_EXPORT_ROOT / str(info["artifact"])\n    if not path.is_file() or path.is_symlink():\n        return JSONResponse({"status": "error", "error": "recovery export missing"}, status_code=404)\n    return FileResponse(\n        path,\n        media_type="application/zip",\n        filename=path.name,\n        headers={"Cache-Control": "no-store"},\n    )\n\n\nif hasattr(mcp, "custom_route"):\n    mcp.custom_route(\n        "/clearup/type2/download", methods=["GET"], include_in_schema=False\n    )(_type2_recovery_download_http)\n'

TYPE2_STATUS_OLD = '@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)\ndef projectmanager_status() -> dict[str, Any]:\n    return _api().status()\n'
TYPE2_STATUS_NEW = '@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)\ndef projectmanager_status() -> dict[str, Any]:\n    return _attach_type2_recovery_downloads(_api().status())\n'

def _ensure_type2_download_bridge(tools_text: str) -> tuple[str, bool, str]:
    if TYPE2_DOWNLOAD_BRIDGE_MARKER in tools_text and TYPE2_STATUS_NEW in tools_text:
        return tools_text, False, "type2_download_bridge_current"
    old_marker = "# TYPE2_RECOVERY_DOWNLOAD_BRIDGE_VERSION=2026-09-25.v2"
    if old_marker not in tools_text and TYPE2_STATUS_OLD not in tools_text:
        return tools_text, False, "type2_download_bridge_status_tool_absent"
    api_anchor = "\n\ndef _api() -> ProjectmanagerAPI:\n"
    if tools_text.count(api_anchor) != 1:
        raise RuntimeError("tools_projectmanager Type2 download insertion anchor mismatch")
    if old_marker in tools_text:
        start = tools_text.index(old_marker)
        end = tools_text.index(api_anchor, start)
        tools_text = tools_text[:start] + TYPE2_DOWNLOAD_BRIDGE_BLOCK + tools_text[end:]
        if TYPE2_STATUS_NEW not in tools_text:
            if TYPE2_STATUS_OLD not in tools_text:
                raise RuntimeError("tools_projectmanager Type2 status wrapper missing during upgrade")
            tools_text = tools_text.replace(TYPE2_STATUS_OLD, TYPE2_STATUS_NEW, 1)
        return tools_text, True, "type2_download_bridge_upgraded_v3"
    tools_text = tools_text.replace(api_anchor, "\n\n" + TYPE2_DOWNLOAD_BRIDGE_BLOCK + api_anchor, 1)
    tools_text = tools_text.replace(TYPE2_STATUS_OLD, TYPE2_STATUS_NEW, 1)
    return tools_text, True, "type2_download_bridge_added"


COMMAND_FORWARDING_MARKER = "# PM_COMMAND_FORWARDING_VERSION=2026-09-25.v1"
COMMAND_FORWARDING_BLOCK = r'''
    # PM_COMMAND_FORWARDING_VERSION=2026-09-25.v1
    optional = {
        'artifact_path': str(artifact_path or '')[:4000],
        'artifact_sha256': str(artifact_sha256 or '')[:128],
        'release_version': str(release_version or '')[:100],
        'verification_report': str(verification_report or '')[:4000],
        'source_channel': str(source_channel or '')[:100],
        'source_ref': str(source_ref or '')[:1000],
        'occurred_at': str(occurred_at or '')[:100],
        'classification_hint': str(classification_hint or '')[:100],
    }
    for key, value in optional.items():
        if value:
            payload[key] = value
'''

def _ensure_command_forwarding(tools_text: str) -> tuple[str, bool]:
    if COMMAND_FORWARDING_MARKER in tools_text:
        return tools_text, False
    start = tools_text.find("    if intent == 'conversation_intake':")
    end = tools_text.find("    return _write_command(payload)", start)
    if start < 0 or end < 0:
        # Older/minimal tools_projectmanager variants do not expose the generic
        # command writer. There is nothing to forward in that shape; keep the
        # hotfix backwards-compatible instead of turning absence into a blocker.
        if 'def projectmanager_submit_command(' not in tools_text:
            return tools_text, False
        raise RuntimeError('tools_projectmanager command forwarding anchors mismatch')
    patched = tools_text[:start] + COMMAND_FORWARDING_BLOCK + tools_text[end:]
    return patched, True

APPROVAL_TOOL_BLOCK = '\n\n# PM_APPROVAL_TOOL_VERSION=2026-09-12.v3\nAPPROVAL_INGRESS_ROOT = Path(os.environ.get(\n    \'PM_APPROVAL_INGRESS_ROOT\',\n    \'/system/Projectmanager/ApprovalIngress\',\n))\nMAX_APPROVAL_BYTES = 16384\n_APPROVAL_YES = {\'ja\', \'akkoord\', \'goedkeuren\', \'goedgekeurd\', \'yes\', \'approve\'}\n_APPROVAL_NO = {\'nee\', \'afwijzen\', \'afgekeurd\', \'no\', \'reject\'}\n_APPROVAL_CHANNELS = {\'chatgpt\', \'typed\', \'dictation\', \'voice\', \'nomad\', \'speech\'}\n\n\ndef _approval_text_token(value: str) -> str:\n    return \' \'.join(str(value or \'\').strip().lower().strip(\' .,!?:;\').split())\n\n\ndef _pending_decision(decision_id: str) -> dict:\n    status_path = RUNTIME_ROOT / \'status\' / \'current.json\'\n    try:\n        data = json.loads(status_path.read_text(encoding=\'utf-8\'))\n    except (OSError, json.JSONDecodeError) as exc:\n        raise ValueError(\'Projectmanager-status niet leesbaar voor approval.\') from exc\n    matches = [\n        item for item in (data.get(\'decisions_needed\') or [])\n        if isinstance(item, dict)\n        and item.get(\'id\') == decision_id\n        and item.get(\'status\') == \'PENDING\'\n    ]\n    if len(matches) != 1:\n        raise ValueError(\'Exacte PENDING Projectmanager-beslissing niet gevonden.\')\n    return dict(matches[0])\n\n\n@mcp.tool(annotations=WRITE_ANNOTATIONS)\ndef projectmanager_submit_approval(\n    decision_id: str,\n    explicit_user_text: str,\n    approved: bool = True,\n    source_channel: str = \'chatgpt\',\n) -> dict[str, Any]:\n    """Submit Peter\'s explicit approval/rejection for one exact pending decision.\n\n    This tool writes only an immutable approval ingress envelope. It never mutates\n    RuntimeV2 or executes the protected action directly. Exact decision binding and\n    explicit Peter text are mandatory; remote approval remains fail-closed until\n    the secured connector/edge explicitly enables it.\n    """\n    enabled = str(os.environ.get(\'PM_REMOTE_APPROVAL_ENABLED\', \'\')).strip().lower()\n    if enabled not in {\'1\', \'true\', \'yes\', \'on\'}:\n        raise ValueError(\'Remote approval is fail-closed until secured edge is enabled.\')\n    decision_id = str(decision_id or \'\').strip()\n    if not decision_id:\n        raise ValueError(\'decision_id ontbreekt\')\n    if type(approved) is not bool:\n        raise ValueError(\'approved moet boolean zijn\')\n    channel = str(source_channel or \'\').strip().lower()\n    if channel not in _APPROVAL_CHANNELS:\n        raise ValueError(\'ongeldig approval source_channel\')\n    token = _approval_text_token(explicit_user_text)\n    allowed = _APPROVAL_YES if approved else _APPROVAL_NO\n    if token not in allowed:\n        raise ValueError(\'expliciete gebruikersgoedkeuring/afwijzing ontbreekt of is ambigu\')\n    decision = _pending_decision(decision_id)\n    ingress_id = uuid4().hex\n    envelope = {\n        \'schema\': \'energie_pmv2_approval_ingress_v1\',\n        \'id\': ingress_id,\n        \'decision_id\': decision_id,\n        \'approved\': approved,\n        \'approved_by\': \'Peter\',\n        \'explicit_user_text\': str(explicit_user_text or \'\')[:200],\n        \'source_channel\': channel,\n        \'decision_kind\': decision.get(\'kind\'),\n        \'decision_fingerprint\': decision.get(\'fingerprint\'),\n    }\n    _write_immutable(APPROVAL_INGRESS_ROOT, envelope, max_bytes=MAX_APPROVAL_BYTES)\n    return {\n        \'ok\': True,\n        \'executed\': False,\n        \'state\': \'PROPOSED_EXACT_APPROVAL_TO_LOCAL_PROJECTMANAGER\',\n        \'ingress_id\': ingress_id,\n        \'decision_id\': decision_id,\n        \'approved\': approved,\n        \'requires_local_pm_processing\': True,\n    }\n'

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



PM_RUNTIME_ROOT_MARKER = "# PM_RUNTIME_ROOT_CANONICAL_VERSION=2026-09-25.v1"
PM_RUNTIME_ROOT_OLD = """RUNTIME_ROOT = Path(os.environ.get(
    'PM_SYSTEM_ROOT',
    '/project/Inbox/projectmanager_v2/RuntimeV2',
)).resolve()
"""
PM_RUNTIME_ROOT_NEW = """# PM_RUNTIME_ROOT_CANONICAL_VERSION=2026-09-25.v1
_pm_runtime_env = str(os.environ.get('PM_SYSTEM_ROOT', '') or '').strip()
if _pm_runtime_env in {'', '/project/Inbox/projectmanager_v2/RuntimeV2'}:
    _pm_runtime_env = '/system/Projectmanager/RuntimeV2'
RUNTIME_ROOT = Path(_pm_runtime_env).resolve()
"""

def _ensure_pm_runtime_root(tools_text: str, *, strict: bool = True) -> tuple[str, bool, str]:
    if PM_RUNTIME_ROOT_MARKER in tools_text:
        return tools_text, False, 'pm_runtime_root_current'
    count = tools_text.count(PM_RUNTIME_ROOT_OLD)
    if count == 0:
        # Historical pre-32.5.15 fixtures may use a one-line RUNTIME_ROOT assignment or
        # omit the PM status runtime entirely.  Do not rewrite those archived contracts.
        # 32.5.15+ production is strict and must match the canonical modern anchor.
        if not strict:
            return tools_text, False, 'pm_runtime_root_legacy_fixture_unchanged'
        if 'RUNTIME_ROOT = Path(' not in tools_text:
            return tools_text, False, 'pm_runtime_root_not_present'
        raise RuntimeError('tools_projectmanager PM runtime root anchor mismatch')
    if count != 1:
        raise RuntimeError('tools_projectmanager PM runtime root anchor mismatch')
    return tools_text.replace(PM_RUNTIME_ROOT_OLD, PM_RUNTIME_ROOT_NEW, 1), True, 'pm_runtime_root_canonicalized'

def _ensure_native_compose_runtime_root(root: Path) -> tuple[bool, str]:
    compose = root / 'Infra/docker-compose.yml'
    if not compose.exists():
        return False, 'native_compose_absent'
    if compose.is_symlink() or not compose.is_file():
        raise RuntimeError('native compose unsafe')
    text = compose.read_text(encoding='utf-8')
    old = 'PM_SYSTEM_ROOT: /project/Inbox/projectmanager_v2/RuntimeV2'
    new = 'PM_SYSTEM_ROOT: /system/Projectmanager/RuntimeV2'
    if new in text and old not in text:
        return False, 'native_compose_runtime_root_current'
    if text.count(old) != 1:
        raise RuntimeError('native compose PM_SYSTEM_ROOT anchor mismatch')
    _atomic_text(compose, text.replace(old, new, 1))
    return True, 'native_compose_runtime_root_canonicalized'


def _ensure_approval_tool(tools_text: str) -> tuple[str, bool, str]:
    marker = '# PM_APPROVAL_TOOL_VERSION=2026-09-12.v3'
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
    registry = native / "registry.py"
    clearup_export = native / "tools_clearup_export.py"
    tools_pm = native / "tools_projectmanager.py"
    if (
        not server.is_file() or server.is_symlink()
        or not tools_pm.is_file() or tools_pm.is_symlink()
    ):
        raise RuntimeError("native MCP sources missing/unsafe")
    if registry.exists() and (registry.is_symlink() or not registry.is_file()):
        raise RuntimeError("native MCP registry unsafe")
    tools_text = tools_pm.read_text(encoding="utf-8")
    missing = [field for field in REQUIRED_INTAKE_FIELDS if field not in tools_text]
    if missing:
        raise RuntimeError("tools_projectmanager.py missing required intake fields: " + ",".join(missing))
    changed = []
    if registry.is_file():
        registry_text = registry.read_text(encoding="utf-8")
        registry_marker = "# NATIVE_MCP_TOOL_ANNOTATIONS_VERSION=2026-09-25.v1"
        read_def = "READ_ONLY_ANNOTATIONS = {}"
        write_def = "WRITE_ANNOTATIONS = {}"
        have_read = read_def in registry_text
        have_write = write_def in registry_text
        if have_read != have_write:
            raise RuntimeError("registry annotation contract partially present")
        if not have_read:
            registry_text = registry_text.rstrip() + (
                "\n\n" + registry_marker + "\n" + read_def + "\n" + write_def + "\n"
            )
            _atomic_text(registry, registry_text)
            changed.append("registry.py:tool_annotations_v2026_09_25")

    patched_tools, approval_changed, approval_change = _ensure_approval_tool(tools_text)
    if approval_changed:
        _atomic_text(tools_pm, patched_tools)
        tools_text = patched_tools
        changed.append("tools_projectmanager.py:" + approval_change)
    forwarded_tools, forwarding_changed = _ensure_command_forwarding(tools_text)
    if forwarding_changed:
        _atomic_text(tools_pm, forwarded_tools)
        tools_text = forwarded_tools
        changed.append("tools_projectmanager.py:command_forwarding_v2026_09_25")
    runtime_tools, runtime_changed, runtime_change = _ensure_pm_runtime_root(
        tools_text, strict=version_tuple >= (32, 5, 15)
    )
    if runtime_changed:
        _atomic_text(tools_pm, runtime_tools)
        tools_text = runtime_tools
        changed.append("tools_projectmanager.py:" + runtime_change)
    download_tools, download_changed, download_change = _ensure_type2_download_bridge(tools_text)
    if download_changed:
        _atomic_text(tools_pm, download_tools)
        tools_text = download_tools
        changed.append("tools_projectmanager.py:" + download_change)
    runtime = native / "runtime_fingerprint.py"
    if not runtime.is_file() or runtime.read_text(encoding="utf-8") != RUNTIME_MODULE:
        _atomic_text(runtime, RUNTIME_MODULE)
        changed.append("runtime_fingerprint.py")
    if not clearup_export.is_file() or clearup_export.read_text(encoding="utf-8") != CLEARUP_EXPORT_MODULE:
        _atomic_text(clearup_export, CLEARUP_EXPORT_MODULE)
        changed.append("tools_clearup_export.py")
    text = server.read_text(encoding="utf-8")
    clearup_import = "import tools_clearup_export  # noqa: F401\n"
    if clearup_import not in text:
        preferred = "import tools_projectmanager  # noqa: F401\n"
        fallback = "from registry import mcp\n"
        if text.count(preferred) == 1:
            text = text.replace(preferred, preferred + clearup_import, 1)
        elif text.count(fallback) == 1:
            text = text.replace(fallback, clearup_import + fallback, 1)
        else:
            raise RuntimeError("server clearup export import anchor mismatch")
        changed.append("server.py:clearup_export_import")
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
    compose_changed, compose_change = _ensure_native_compose_runtime_root(root)
    if compose_changed:
        changed.append("Infra/docker-compose.yml:" + compose_change)
    result = {
        "schema": "energie_native_mcp_runtime_contract_hotfix_v1",
        "status": "GREEN",
        "release_version": version,
        "changed": changed,
        "reload_required": bool(changed),
        "intake_schema_source_fields_present": True,
        "command_forwarding_current": COMMAND_FORWARDING_MARKER in tools_text,
        "approval_ingress_tool_present": "def projectmanager_submit_approval(" in tools_text,
        "type2_download_bridge_current": TYPE2_DOWNLOAD_BRIDGE_MARKER in tools_text,
        "pm_runtime_root_canonical": PM_RUNTIME_ROOT_MARKER in tools_text,
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
