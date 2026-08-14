#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "slimmemeterportal_import" / "rootfs" / "app" / "main.py"
EXPECTED_BRANCH = "feature/v32.0.29-crash-recovery-export"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: verwacht exact 1 anchor, gevonden {count}")
    return text.replace(old, new, 1)


def main() -> None:
    if os.environ.get("GITHUB_ACTIONS") == "true":
        branch = os.environ.get("GITHUB_REF_NAME", "")
        if branch != EXPECTED_BRANCH:
            raise RuntimeError(f"weigering buiten featurebranch: {branch!r}")

    text = MAIN.read_text(encoding="utf-8")
    if "def run_complete_crash_recovery_export(" in text:
        print("V32_0_29_PATCH_ALREADY_PRESENT")
        return

    text = replace_once(
        text,
        "from zoneinfo import ZoneInfo\nimport ipaddress\n",
        "from zoneinfo import ZoneInfo\nimport ipaddress\n\n"
        "APP_MODULE_ROOT = Path(__file__).resolve().parent\n"
        "if str(APP_MODULE_ROOT) not in sys.path:\n"
        "    sys.path.insert(0, str(APP_MODULE_ROOT))\n"
        "from crash_recovery_export import build_recovery_export, verify_recovery_export, sha256_file\n",
        "export module import",
    )

    text = replace_once(
        text,
        'COMPLETE_CRASH_RECOVERY_STATE_PATH = Path("/config/output/complete_crash_recovery_state.json")\n',
        'COMPLETE_CRASH_RECOVERY_STATE_PATH = Path("/config/output/complete_crash_recovery_state.json")\n'
        'CRASH_RECOVERY_EXPORT_ROOT = Path("/config/output/crash_recovery_exports")\n',
        "export root constant",
    )

    text = replace_once(
        text,
        "COMPLETE_CRASH_RECOVERY_LOCK = threading.Lock()\n",
        "COMPLETE_CRASH_RECOVERY_LOCK = threading.Lock()\n"
        "COMPLETE_CRASH_RECOVERY_EXPORT_LOCK = threading.Lock()\n",
        "export flow lock",
    )

    new_flow = r'''

def run_complete_crash_recovery_export(
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    """Run de bewezen RecoveryManager-checks en maak daarna één browserexport."""
    now = datetime.now(TZ)
    resolved_year = int(year or now.year)
    resolved_month = int(month or now.month)

    if WORKFLOW_LOCK.locked():
        result = {
            "status": "busy",
            "version": APP_VERSION,
            "year": resolved_year,
            "month": resolved_month,
            "error": "Maandworkflow is actief; Crash Recovery export is niet gestart.",
            "checked_at": now.isoformat(),
        }
        _save_complete_recovery_state(result)
        return result

    if not COMPLETE_CRASH_RECOVERY_EXPORT_LOCK.acquire(blocking=False):
        return {
            "status": "busy",
            "version": APP_VERSION,
            "year": resolved_year,
            "month": resolved_month,
            "error": "Er loopt al een complete Crash Recovery export.",
            "checked_at": now.isoformat(),
        }

    export_path: Path | None = None
    try:
        _save_complete_recovery_state({
            "status": "running",
            "version": APP_VERSION,
            "year": resolved_year,
            "month": resolved_month,
            "download_status": "not_ready",
            "cleanup_status": "not_started",
            "checked_at": datetime.now(TZ).isoformat(),
        })

        complete = run_complete_crash_recovery(resolved_year, resolved_month)
        manifest_count = _int_or_zero(complete.get("manifest_file_count"))
        verified_files = _int_or_zero(complete.get("verified_files"))
        hash_failures = complete.get("hash_failures") or []
        complete_ok = (
            str(complete.get("status") or "") == "verified"
            and bool(complete.get("deep_verified"))
            and manifest_count > 0
            and verified_files == manifest_count
            and not hash_failures
        )
        if not complete_ok:
            result = dict(complete)
            result["status"] = "error" if result.get("status") != "busy" else "busy"
            result.setdefault("error", "Complete Crash Recovery deep verify is niet volledig geslaagd.")
            result["download_status"] = "not_ready"
            result["cleanup_status"] = "not_started"
            _save_complete_recovery_state(result)
            return result

        staged = run_complete_restore_staging()
        staging_path = str(staged.get("staging_path") or "").strip()
        stage_ok = (
            str(staged.get("status") or "") == "staged"
            and (
                staging_path == "/recovery/RestoreStaging"
                or staging_path.startswith("/recovery/RestoreStaging/")
            )
            and staged.get("source_project_modified") is False
        )
        if not stage_ok:
            result = {
                "status": "error" if staged.get("status") != "busy" else "busy",
                "version": APP_VERSION,
                "year": resolved_year,
                "month": resolved_month,
                "backup_name": str(complete.get("backup_name") or ""),
                "backup_sha256": str(complete.get("sha256") or ""),
                "manifest_file_count": manifest_count,
                "verified_files": verified_files,
                "deep_verified": True,
                "restore_test_status": str(staged.get("status") or "error"),
                "source_project_modified": bool(staged.get("source_project_modified")),
                "error": str(staged.get("error") or "RestoreStaging veiligheidscontrole is niet geslaagd."),
                "download_status": "not_ready",
                "cleanup_status": "not_started",
                "checked_at": datetime.now(TZ).isoformat(),
            }
            if "RestoreStaging" not in result["error"]:
                result["error"] = "RestoreStaging veiligheidscontrole is niet geslaagd: " + result["error"]
            _save_complete_recovery_state(result)
            return result

        if not WORKFLOW_LOCK.acquire(blocking=False):
            result = {
                "status": "busy",
                "version": APP_VERSION,
                "year": resolved_year,
                "month": resolved_month,
                "error": "Maandworkflow werd actief vóór de exportsnapshot; probeer opnieuw.",
                "download_status": "not_ready",
                "cleanup_status": "not_started",
                "checked_at": datetime.now(TZ).isoformat(),
            }
            _save_complete_recovery_state(result)
            return result

        try:
            CRASH_RECOVERY_EXPORT_ROOT.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(TZ).strftime("%Y%m%dT%H%M%S")
            export_name = f"EnergieProject_Complete_Crash_Recovery_{stamp}.zip"
            export_path = CRASH_RECOVERY_EXPORT_ROOT / export_name
            built = build_recovery_export(NAS_LAYOUT_ROOT, export_path)
        finally:
            WORKFLOW_LOCK.release()

        export_verified = verify_recovery_export(export_path)
        export_ok = (
            bool(export_verified.valid)
            and export_verified.sha256 == built.sha256
            and export_verified.file_count == built.file_count
            and export_verified.top_level_ok
            and export_verified.required_roots_ok
            and not export_verified.excluded_hits
        )
        if not export_ok:
            raise RuntimeError(
                "De browserexport is na opbouw niet volledig geldig: "
                + str(export_verified.error or "onbekende verificatiefout")
            )

        result = {
            "status": "ready_for_download",
            "version": APP_VERSION,
            "year": resolved_year,
            "month": resolved_month,
            "backup_name": str(complete.get("backup_name") or ""),
            "backup_sha256": str(complete.get("sha256") or ""),
            "manifest_file_count": manifest_count,
            "verified_files": verified_files,
            "deep_verified": True,
            "restore_test_status": "staged",
            "restore_staging_path": staging_path,
            "source_project_modified": False,
            "export_path": str(export_path),
            "export_name": export_path.name,
            "export_sha256": built.sha256,
            "export_file_count": built.file_count,
            "export_total_bytes": built.total_bytes,
            "download_status": "ready",
            "cleanup_status": "pending",
            "checked_at": datetime.now(TZ).isoformat(),
        }
        _save_complete_recovery_state(result)
        return result

    except Exception as exc:
        if export_path is not None:
            try:
                export_path.resolve().relative_to(CRASH_RECOVERY_EXPORT_ROOT.resolve())
                export_path.unlink(missing_ok=True)
            except (OSError, ValueError):
                pass
        result = {
            "status": "error",
            "version": APP_VERSION,
            "year": resolved_year,
            "month": resolved_month,
            "deep_verified": False,
            "error": f"{type(exc).__name__}: {exc}",
            "download_status": "not_ready",
            "cleanup_status": "not_started",
            "checked_at": datetime.now(TZ).isoformat(),
        }
        _save_complete_recovery_state(result)
        return result
    finally:
        COMPLETE_CRASH_RECOVERY_EXPORT_LOCK.release()
'''

    text = replace_once(
        text,
        "\ndef _mcp_read_project_text(relative_path: str, timeout: float = 6.0) -> str | None:\n",
        new_flow + "\n\ndef _mcp_read_project_text(relative_path: str, timeout: float = 6.0) -> str | None:\n",
        "export flow insertion",
    )

    text = replace_once(
        text,
        '<button id="run-complete-crash-recovery-button" type="button">Maak complete Crash Recovery</button>\n'
        '<button id="run-complete-restore-staging-button" type="button" class="secondary" disabled>Test herstel naar RestoreStaging</button>\n',
        '<button id="run-complete-crash-recovery-button" type="button">Maak complete Crash Recovery</button>\n'
        '<button id="download-complete-crash-recovery-button" type="button" class="secondary" disabled onclick="window.location.href=\'api/crash-recovery/download\'">Download Crash Recovery ZIP</button>\n'
        '<button id="run-complete-restore-staging-button" type="button" class="secondary" disabled>Test herstel naar RestoreStaging</button>\n',
        "download button",
    )

    text = replace_once(
        text,
        '<p id="complete-recovery-detail" class="hint">Gebruikt uitsluitend de bestaande RecoveryManager-backend. Sluit de maand niet af en overschrijft bij de hersteltest geen productiedata.</p>',
        '<p id="complete-recovery-detail" class="hint">Maakt de volledige EnergieProject-browserbackup voor eigen opslag in iCloud. Sluit de maand niet af en RestoreStaging overschrijft geen productiedata.</p>',
        "recovery hint",
    )

    text = replace_once(
        text,
        "function renderCompleteRecovery(result){{\n",
        "function renderCompleteRecovery(result){{\n"
        "  const downloadButton=document.getElementById('download-complete-crash-recovery-button');\n"
        "  if(downloadButton) downloadButton.disabled=!['ready_for_download','retry_available'].includes(String(result.status||''));\n",
        "download state render",
    )

    text = replace_once(
        text,
        "const completeRestoreButton=document.getElementById('run-complete-restore-staging-button');\n",
        "const completeRestoreButton=document.getElementById('run-complete-restore-staging-button');\n"
        "const completeDownloadButton=document.getElementById('download-complete-crash-recovery-button');\n",
        "download button js const",
    )

    text = replace_once(
        text,
        "const response=await fetch('api/crash-recovery/complete',{{method:'POST',headers:{{'X-Requested-With':'fetch','Accept':'application/json'}}}});",
        "const response=await fetch('api/crash-recovery/export',{{method:'POST',headers:{{'X-Requested-With':'fetch','Accept':'application/json'}}}});",
        "primary export endpoint",
    )

    post_anchor = '        if path.endswith("/api/crash-recovery/complete"):\n'
    export_route = r'''        if path.endswith("/api/crash-recovery/export"):
            result = run_complete_crash_recovery_export()
            status = str(result.get("status") or "")
            code = (
                HTTPStatus.OK if status == "ready_for_download"
                else HTTPStatus.CONFLICT if status == "busy"
                else HTTPStatus.INTERNAL_SERVER_ERROR
            )
            body = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_body(code, body, "application/json; charset=utf-8")
            return

'''
    text = replace_once(text, post_anchor, export_route + post_anchor, "export POST route")

    MAIN.write_text(text, encoding="utf-8")
    print("V32_0_29_PATCH_OK")


if __name__ == "__main__":
    main()
