from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = ("Inbox/incoming", "Inbox/processing", "Inbox/processed", "Inbox/failed")


def _literal(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for part in node.values:
            out.append(part.value if isinstance(part, ast.Constant) and isinstance(part.value, str) else "{}")
        return "".join(out)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "Path" and node.args:
        return _literal(node.args[0])
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _literal(node.left)
        right = _literal(node.right)
        if right is None:
            return None
        return f"{left.rstrip('/')}/{right.lstrip('/')}" if left is not None else right
    return None


def _raw_inbox(node):
    if any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Name)
        and child.func.id == "project_system_path"
        for child in ast.walk(node)
    ):
        return None
    values = []
    for child in ast.walk(node):
        value = _literal(child)
        if value:
            normalized = value.replace("\\", "/")
            if normalized.startswith("Inbox/") or "/Inbox/" in normalized or normalized == "Inbox":
                values.append(normalized)
    return max(values, key=len) if values else None


def _allowed(path: str) -> bool:
    return any(prefix in path for prefix in ALLOWED)


def _python_writer_issues():
    write_attrs = {"write_text", "write_bytes", "mkdir", "touch", "symlink_to", "hardlink_to"}
    helper_hints = ("atomic", "write", "save", "persist", "emit")
    issues = []
    files = list(ROOT.rglob("*.py"))
    for path in files:
        if "tests" in path.parts or "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeError):
            continue
        scopes = [tree] + [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))]
        for scope in scopes:
            tainted = {}
            nodes = list(ast.walk(scope))
            for node in nodes:
                if not isinstance(node, (ast.Assign, ast.AnnAssign)) or node.value is None:
                    continue
                raw = _raw_inbox(node.value)
                if not raw:
                    continue
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                for target in targets:
                    if isinstance(target, ast.Name):
                        tainted[target.id] = raw
                    elif isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "self":
                        tainted[f"self.{target.attr}"] = raw
            for node in nodes:
                if not isinstance(node, ast.Call):
                    continue
                candidates = []
                sink = ""
                if isinstance(node.func, ast.Attribute) and node.func.attr in write_attrs:
                    candidates = [node.func.value]
                    sink = node.func.attr
                elif isinstance(node.func, ast.Attribute) and node.func.attr == "open":
                    mode = _literal(node.args[0]) if node.args else "r"
                    if mode and any(char in mode for char in "wax+"):
                        candidates = [node.func.value]
                        sink = f"open:{mode}"
                elif isinstance(node.func, ast.Name) and node.func.id == "open":
                    mode = _literal(node.args[1]) if len(node.args) > 1 else "r"
                    if mode and any(char in mode for char in "wax+"):
                        candidates = node.args[:1]
                        sink = f"open:{mode}"
                else:
                    name = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""
                    if any(hint in name.lower() for hint in helper_hints) and node.args:
                        candidates = node.args[:1]
                        sink = name
                    if (
                        isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id in {"os", "shutil"}
                        and node.func.attr in {"replace", "rename", "move", "copy", "copy2", "copyfile"}
                    ):
                        candidates = node.args[1:2]
                        sink = f"{node.func.value.id}.{node.func.attr}"
                    if (
                        isinstance(node.func, ast.Attribute)
                        and isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "tempfile"
                        and node.func.attr in {"mkstemp", "mkdtemp", "NamedTemporaryFile"}
                    ):
                        candidates = [kw.value for kw in node.keywords if kw.arg == "dir"]
                        sink = f"tempfile.{node.func.attr}"
                for candidate in candidates:
                    raw = _raw_inbox(candidate)
                    if raw is None and isinstance(candidate, ast.Name):
                        raw = tainted.get(candidate.id)
                    elif raw is None and isinstance(candidate, ast.Attribute) and isinstance(candidate.value, ast.Name) and candidate.value.id == "self":
                        raw = tainted.get(f"self.{candidate.attr}")
                    if raw and not _allowed(raw):
                        issues.append(f"{path.relative_to(ROOT)}:{node.lineno}:{sink}:{raw}")
    return sorted(set(issues))


def _shell_writer_issues():
    issues = []
    for path in ROOT.rglob("*.sh"):
        if "tests" in path.parts:
            continue
        lines = path.read_text(encoding="utf-8").splitlines()
        aliases = {}
        for line in lines:
            m = re.match(r'([A-Z_][A-Z0-9_]*)=["\']?([^"\']*Inbox[^"\']*)', line.strip())
            if m and "energie_system_path" not in line:
                aliases[m.group(1)] = m.group(2).replace("$ROOT/", "")
        for lineno, line in enumerate(lines, 1):
            if "energie_system_path" in line:
                continue
            normalized = line.replace("\\", "/")
            for name, value in aliases.items():
                normalized = normalized.replace(f"${name}", value).replace(f"${{{name}}}", value)
            writer_cmd = re.search(r"(?:^|[;&|\s])(?:mkdir|touch|cp|mv|install|tee|mktemp|chmod|chown)(?:\s|$)", normalized)
            redirect_to_inbox = re.search(r">\s*(?:[^;]*)(?:Inbox|/energy-inbox)", normalized)
            if not (writer_cmd or redirect_to_inbox):
                continue
            if not re.search(r"(?:\$ROOT/)?Inbox(?:/|\b)|/energy/Inbox|/energy-inbox", normalized):
                continue
            if 'mkdir -p "$ROOT/Inbox"' in line and '"$PROCESSED"' in line:
                continue
            matches = re.findall(r"Inbox/[^\s\"']+", normalized)
            if matches and all(any(item == prefix or item.startswith(prefix + "/") for prefix in ALLOWED) for item in matches):
                continue
            issues.append(f"{path.relative_to(ROOT)}:{lineno}:{line.strip()}")
    return issues


def test_no_unauthorized_python_inbox_writers():
    assert _python_writer_issues() == []


def test_no_unauthorized_shell_inbox_writers():
    assert _shell_writer_issues() == []


def test_no_active_whole_inbox_rw_bindings_outside_release_mailbox_code():
    offenders = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in {".sh", ".py", ".yml", ".yaml"} or "tests" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            if "Inbox" in line and ("/energy/Inbox:rw" in line or "/energy-inbox:rw" in line):
                offenders.append(f"{path.relative_to(ROOT)}:{lineno}:{line.strip()}")
    assert offenders == []


def test_known_32528_migrated_writer_paths_use_system_contract():
    protected = (ROOT / "slimmemeterportal_import/rootfs/app/projectmanager_v2/protected_action_executor.py").read_text(encoding="utf-8")
    assert "self.project_root / 'Inbox/watcher_recreate_request.json'" not in protected
    assert "self.control_plane_request_root / 'watcher_recreate.json'" in protected

    sideband = (ROOT / "tools/sideband_bridge.py").read_text(encoding="utf-8")
    assert "root/'Inbox/project_clearup_move_request.json'" not in sideband
    assert "project_system_path(root,'Inbox/projectmanager_v2/RuntimeV2/clearup/project_clearup_move_request.json')" in sideband

    delivery = (ROOT / "tools/ha_delivery_adapter.py").read_text(encoding="utf-8")
    assert "self.root/'Inbox/ha_publication_required.json'" not in delivery
    assert "Inbox/release_controller/Publication/ha_publication_required.json" in delivery

    atomic = (ROOT / "tools/atomic_app_swap.py").read_text(encoding="utf-8")
    assert 'lock=inbox / ".atomic_app_swap.lock"' not in atomic
    assert "Inbox/release_controller/State/atomic_app_swap.lock" in atomic
    assert "dir=str(paths.inbox)" not in atomic


def test_active_directory_mapping_never_falls_back_when_canonical_directory_is_absent(tmp_path):
    import sys
    app = ROOT / "slimmemeterportal_import/rootfs/app"
    sys.path.insert(0, str(app))
    try:
        from system_path_contract import project_system_path, SCHEMA
        root = tmp_path / "p"
        marker = root / "Data/03_Systeem/Projectmanager/ClearUp/PathActivation/pm_runtime.json"
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text('{"schema":"%s","key":"pm_runtime","active":true}\n' % SCHEMA, encoding="utf-8")
        canonical = root / "Data/03_Systeem/Projectmanager/RuntimeV2/status/current.json"
        assert not canonical.parent.exists()
        assert project_system_path(root, "Inbox/projectmanager_v2/RuntimeV2/status/current.json") == canonical
        assert not (root / "Inbox/projectmanager_v2").exists()
    finally:
        try:
            sys.path.remove(str(app))
        except ValueError:
            pass


def test_active_shell_directory_mapping_never_falls_back_when_destination_is_absent(tmp_path):
    import subprocess
    root = tmp_path / "p"
    marker = root / "Data/03_Systeem/Projectmanager/ClearUp/PathActivation/pm_runtime.json"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text('{"schema":"energie_clearup_system_path_contract_v1","key":"pm_runtime","active":true}\n', encoding="utf-8")
    script = ROOT / "tools/system_path_contract.sh"
    cmd = f'. "{script}"; energie_system_path "{root}" pm_runtime Inbox/projectmanager_v2/RuntimeV2 Data/03_Systeem/Projectmanager/RuntimeV2'
    out = subprocess.check_output(["sh", "-c", cmd], text=True).strip()
    assert out == str(root / "Data/03_Systeem/Projectmanager/RuntimeV2")
    assert not (root / "Inbox/projectmanager_v2").exists()


def test_watcher_bootstrap_never_recreates_legacy_inbox_logs():
    text = (ROOT / "tools/bootstrap_release_watcher_container.sh").read_text(encoding="utf-8")
    assert '$INBOX/logs' not in text
    assert 'mkdir -p "$INBOX/incoming"' in text



def test_32528_type2_restore_never_recreates_retired_inbox_source(tmp_path, monkeypatch):
    import hashlib
    import importlib.util
    import json

    spec = importlib.util.spec_from_file_location(
        "writer_audit_type2_executor", ROOT / "tools/project_clearup_move_executor.py"
    )
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)

    source_rel = "Inbox/projectmanager_v2/RuntimeV2"
    destination_rel = "Data/03_Systeem/Projectmanager/RuntimeV2"
    original = b'{"status":"OLD"}\n'
    source_rows = [
        {"path": source_rel, "type": "directory"},
        {
            "path": f"{source_rel}/status.json",
            "type": "file",
            "size": len(original),
            "sha256": hashlib.sha256(original).hexdigest(),
        },
    ]
    plan = {
        "plan_sha256": "f" * 64,
        "items": [
            {
                "source": source_rel,
                "destination": destination_rel,
                "path_key": "pm_runtime",
            }
        ],
    }

    class Service:
        STAGING_ROOT_REL = Path("Data/03_Systeem/Projectmanager/ClearUp/Staging")
        EXPORT_ROOT_REL = Path("Data/03_Systeem/Projectmanager/ClearUp/Exports")
        STATE_ROOT_REL = Path("Data/03_Systeem/Projectmanager/ClearUp/State")

        @staticmethod
        def _snapshot_release_dirs(root):
            return {}

    stage = tmp_path / Service.STAGING_ROOT_REL / "ClearUp_002"
    staged = stage / "original" / source_rel
    staged.mkdir(parents=True)
    (staged / "status.json").write_bytes(original)
    manifest = {
        "clearup_id": "ClearUp_002",
        "plan_sha256": plan["plan_sha256"],
        "items": [{**plan["items"][0], "source_rows": source_rows}],
    }
    (stage / "TYPE2_MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")

    destination = tmp_path / destination_rel
    destination.mkdir(parents=True)
    (destination / "status.json").write_text('{"status":"CURRENT"}\n', encoding="utf-8")

    monkeypatch.setattr(
        mod,
        "_type2_validate_request",
        lambda root, request: ("a" * 32, "type2_restore", "ClearUp_002", plan, Service),
    )
    request = {
        "release_version": "32.5.28",
        "mailbox_snapshot_before": {},
    }
    _, result = mod.execute_type2(tmp_path, request)

    assert result["phase"] == "RESTORED"
    assert result["legacy_sources_recreated"] is False
    assert result["path_activation_retained"] is True
    assert result["restored_sources"] == []
    assert not (tmp_path / source_rel).exists()
    assert (destination / "status.json").read_text(encoding="utf-8") == '{"status":"CURRENT"}\n'
    marker = tmp_path / "Data/03_Systeem/Projectmanager/ClearUp/PathActivation/pm_runtime.json"
    activation = json.loads(marker.read_text(encoding="utf-8"))
    assert activation["active"] is True
    assert activation["source"] == source_rel
    assert activation["destination"] == destination_rel


def test_32528_clearup_dependency_audit_treats_migrated_executor_ipc_as_observation_only():
    text = (ROOT / "slimmemeterportal_import/rootfs/app/project_clearup.py").read_text(encoding="utf-8")
    assert 'Data/03_Systeem/Projectmanager/RuntimeV2/clearup/project_clearup_move_request.json' in text
    assert 'Data/03_Systeem/Projectmanager/Logs/Runtime/project_clearup_move_result.json' in text
    assert 'Inbox/project_clearup_move_request.json' in text

