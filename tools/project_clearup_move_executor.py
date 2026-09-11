#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REQUEST_SCHEMA = "energie_project_clearup_move_request_v1"
RESULT_SCHEMA = "energie_project_clearup_move_result_v1"
REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$")
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_.-]{1,96}$")


class RequestRejected(ValueError):
    pass


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RequestRejected(f"request JSON ongeldig: {exc}") from exc
    if not isinstance(value, dict):
        raise RequestRejected("request moet een JSON-object zijn")
    return value


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise RuntimeError(f"resultaatpad mag geen symlink zijn: {path}")
    tmp = path.with_name(f".{path.name}.tmp-{os.getpid()}")
    try:
        with tmp.open("x", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _parse_utc(value: Any, field: str) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise RequestRejected(f"{field} ontbreekt")
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise RequestRejected(f"{field} ongeldig") from exc
    if parsed.tzinfo is None:
        raise RequestRejected(f"{field} moet timezone-aware zijn")
    return parsed.astimezone(timezone.utc)


def _load_state_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RequestRejected(f"{label} ontbreekt of is ongeldig: {exc}") from exc
    if not isinstance(value, dict):
        raise RequestRejected(f"{label} moet een JSON-object zijn")
    return value


def _validate_common(root: Path, request: dict[str, Any]) -> tuple[str, str, str, float]:
    if str(request.get("schema") or "") != REQUEST_SCHEMA:
        raise RequestRejected("CLEARUP watcher request schema ongeldig")
    request_id = str(request.get("request_id") or "").strip().lower()
    if not REQUEST_ID_RE.fullmatch(request_id):
        raise RequestRejected("CLEARUP watcher request_id ongeldig")
    operation = str(request.get("operation") or "").strip().lower()
    if operation not in {"apply", "restore"}:
        raise RequestRejected("CLEARUP watcher operation ongeldig")
    release_version = str(request.get("release_version") or "").strip()
    try:
        current_version = (root / "App/VERSIE.txt").read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RequestRejected(f"actieve releaseversie onleesbaar: {exc}") from exc
    if not release_version or current_version != release_version:
        raise RequestRejected(
            f"release mismatch: request={release_version or '<leeg>'} current={current_version or '<leeg>'}"
        )

    atomic = _load_state_json(root / "Inbox/atomic_app_swap_state.json", "atomic release state")
    hold = _load_state_json(root / "Inbox/operating_mode/release_validation_hold.json", "release validation hold")
    pre_acceptance = request.get("pre_acceptance") is True
    if pre_acceptance:
        if operation != "apply":
            raise RequestRejected("pre_acceptance is alleen toegestaan voor CLEARUP apply")
        if str(atomic.get("state") or "").upper() != "LIVE_ACCEPTANCE" or str(atomic.get("to_version") or "") != release_version:
            raise RequestRejected("pre-acceptance CLEARUP vereist LIVE_ACCEPTANCE voor exact deze release")
        hold_status = str(hold.get("validation_status") or "").lower()
        if not (
            hold.get("active") is True
            and str(hold.get("release_version") or "") == release_version
            and hold_status in {"required", "blocked"}
        ):
            raise RequestRejected("pre-acceptance CLEARUP release-hold hoort niet exact bij deze release")
        from_version = str(atomic.get("from_version") or "").strip()
        if not from_version or from_version == release_version:
            raise RequestRejected("pre-acceptance CLEARUP mist geldige source rollback-versie")
        rollback = root / f"App.__rollback_{from_version}"
        if rollback.is_symlink() or not rollback.is_dir():
            raise RequestRejected("pre-acceptance CLEARUP vereist de exacte rollbackdirectory")
        rollback_version = rollback / "VERSIE.txt"
        if not rollback_version.is_file() or rollback_version.read_text(encoding="utf-8").strip() != from_version:
            raise RequestRejected("pre-acceptance CLEARUP rollbackversie is ongeldig")
        if (root / "Inbox/.installer.lock").exists():
            raise RequestRejected("pre-acceptance CLEARUP weigert actieve installer lock")
        if (root / "Inbox/.atomic_app_swap.lock").exists():
            raise RequestRejected("pre-acceptance CLEARUP weigert actieve atomic swap lock")
        processing = root / "Inbox/processing"
        if processing.is_dir() and any(processing.glob("*.zip")):
            raise RequestRejected("pre-acceptance CLEARUP weigert actieve processing release")
    else:
        if str(atomic.get("state") or "").upper() != "ACCEPTED" or str(atomic.get("to_version") or "") != release_version:
            raise RequestRejected("release is niet ACCEPTED voor deze requestversie")
        if hold.get("active") is not False or str(hold.get("validation_status") or "").lower() != "ok":
            raise RequestRejected("release validation hold is niet vrijgegeven")

    clearup_root = root / "CLEARUP"
    if clearup_root.is_symlink() or not clearup_root.is_dir():
        raise RequestRejected("CLEARUP-root ontbreekt, is geen directory of is een symlink")
    try:
        if clearup_root.stat().st_dev != root.stat().st_dev:
            raise RequestRejected("CLEARUP-root staat niet op hetzelfde filesystem")
    except OSError as exc:
        raise RequestRejected(f"CLEARUP-root kan niet worden gevalideerd: {exc}") from exc

    expires_at = _parse_utc(request.get("expires_at"), "expires_at")
    remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
    if remaining <= 0:
        raise RequestRejected("CLEARUP watcher request is verlopen")
    return request_id, operation, release_version, remaining, pre_acceptance


def _load_project_clearup(root: Path):
    module_root = root / "App/slimmemeterportal_import/rootfs/app"
    if not module_root.is_dir():
        raise RequestRejected("actieve App module-root ontbreekt")
    sys.path.insert(0, str(module_root))
    try:
        import project_clearup  # type: ignore
    finally:
        try:
            sys.path.remove(str(module_root))
        except ValueError:
            pass
    return project_clearup


def execute_request(root: Path, request_path: Path) -> tuple[str, dict[str, Any]]:
    root = root.resolve()
    if request_path.is_symlink() or not request_path.is_file():
        raise RequestRejected("requestpad ontbreekt, is geen regulier bestand of is een symlink")
    request = _read_json(request_path)
    request_id, operation, release_version, remaining, pre_acceptance = _validate_common(root, request)
    clearup = _load_project_clearup(root)

    if operation == "apply":
        plan = request.get("plan")
        if not isinstance(plan, dict):
            raise RequestRejected("CLEARUP apply-plan ontbreekt")
        if str(plan.get("current_version") or "") != release_version:
            raise RequestRejected("CLEARUP plan hoort niet bij de actieve release")
        if plan.get("delete_capability") is not False:
            raise RequestRejected("CLEARUP plan delete_capability moet exact false zijn")
        if pre_acceptance:
            atomic_now = _load_state_json(root / "Inbox/atomic_app_swap_state.json", "atomic release state")
            protected_rollback = f"App.__rollback_{str(atomic_now.get('from_version') or '').strip()}"
            items = plan.get("items")
            if not isinstance(items, list):
                raise RequestRejected("pre-acceptance CLEARUP plan items ontbreken/ongeldig")
            for item in items:
                if not isinstance(item, dict):
                    raise RequestRejected("pre-acceptance CLEARUP plan item ongeldig")
                if str(item.get("source_path") or "").rstrip("/") == protected_rollback:
                    raise RequestRejected("pre-acceptance CLEARUP mag actieve rollback niet verplaatsen")
        if pre_acceptance:
            expected_fingerprint = str(plan.get("prerequisite_fingerprint") or "").strip().lower()
            if len(expected_fingerprint) != 64 or any(ch not in "0123456789abcdef" for ch in expected_fingerprint):
                raise RequestRejected("pre-acceptance CLEARUP mist geldige recovery prerequisite_fingerprint")
            module_root = root / "App/slimmemeterportal_import/rootfs/app"
            sys.path.insert(0, str(module_root))
            try:
                import project_clearup_auto  # type: ignore
                current = project_clearup_auto._current_release_cr_gate(root, app_version=release_version)
            finally:
                try:
                    sys.path.remove(str(module_root))
                except ValueError:
                    pass
            if current.get("ok") is not True or str(current.get("fingerprint") or "").lower() != expected_fingerprint:
                raise RequestRejected("pre-acceptance CLEARUP recovery fingerprint is niet meer actueel")
        confirmation = str(request.get("confirmation") or "")
        if confirmation != str(plan.get("confirmation_required") or ""):
            raise RequestRejected("CLEARUP plan confirmation mismatch")
        run_id = str(request.get("run_id") or "").strip()
        if not RUN_ID_RE.fullmatch(run_id):
            raise RequestRejected("CLEARUP run_id ongeldig")
        result = clearup.apply_clearup_plan(
            root,
            plan,
            confirmation=confirmation,
            run_id=run_id,
            deadline_monotonic=time.monotonic() + remaining,
        )
    else:
        run_id = str(request.get("restore_run_id") or "").strip()
        if not RUN_ID_RE.fullmatch(run_id):
            raise RequestRejected("CLEARUP restore_run_id ongeldig")
        confirmation = str(request.get("confirmation") or "")
        if confirmation != f"RESTORE CLEARUP {run_id}":
            raise RequestRejected("CLEARUP restore confirmation mismatch")
        result = clearup.restore_clearup_run(root, run_id, confirmation=confirmation)

    if not isinstance(result, dict):
        raise RuntimeError("CLEARUP executor resultaat is geen object")
    if result.get("delete_performed") not in (None, False):
        raise RuntimeError("CLEARUP executor rapporteert onverwachte delete")
    return request_id, result


def process(root: Path, request_path: Path, result_path: Path) -> tuple[int, dict[str, Any]]:
    request_id = ""
    try:
        raw = _read_json(request_path)
        request_id = str(raw.get("request_id") or "").strip().lower()
        request_id, result = execute_request(root, request_path)
        payload = {
            "schema": RESULT_SCHEMA,
            "request_id": request_id,
            "status": "completed",
            "result": result,
            "delete_performed": False,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        code = 0
    except RequestRejected as exc:
        payload = {
            "schema": RESULT_SCHEMA,
            "request_id": request_id,
            "status": "rejected",
            "error": f"{type(exc).__name__}: {exc}",
            "delete_performed": False,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        code = 2
    except Exception as exc:
        payload = {
            "schema": RESULT_SCHEMA,
            "request_id": request_id,
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "delete_performed": False,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        code = 1
    _atomic_write_json(result_path, payload)
    return code, payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute a release-bound EnergieProject CLEARUP move request")
    parser.add_argument("--root", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--result", required=True)
    args = parser.parse_args()
    code, payload = process(Path(args.root), Path(args.request), Path(args.result))
    print(json.dumps(payload, ensure_ascii=False), file=sys.stdout if code == 0 else sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
