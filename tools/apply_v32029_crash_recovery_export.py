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
    if "def _stream_complete_recovery_download(" in text:
        print("V32_0_29_PATCH_ALREADY_PRESENT")
        return
    if "def run_complete_crash_recovery_export(" in text:
        raise RuntimeError(
            "gedeeltelijke v32.0.29 patch aangetroffen; weiger verdere automatische mutatie"
        )

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

def _recovery_path_to_project_backup(path: str) -> Path | None:
    """Map één /recovery-pad naar Backups zonder ooit erbuiten te kunnen komen."""
    value = str(path or "").strip()
    root = PROJECT_BACKUP_ROOT.resolve()
    if value == "/recovery":
        return root
    if not value.startswith("/recovery/"):
        return None
    relative_text = value.removeprefix("/recovery/")
    relative = Path(relative_text)
    if relative.is_absolute() or ".." in relative.parts:
        return None
    candidate = (root / relative).resolve()
    if candidate == root or root not in candidate.parents:
        return None
    return candidate


def _validated_export_download_path(state: dict[str, Any]) -> Path:
    """Valideer dat de laatst voorbereide export nog exact en ongewijzigd bestaat."""
    status = str(state.get("status") or "")
    download_status = str(state.get("download_status") or "")
    if status not in {"ready_for_download", "retry_available"}:
        raise RuntimeError("Geen Crash Recovery export gereed voor download.")
    if download_status not in {"ready", "retry_available"}:
        raise RuntimeError("Crash Recovery downloadstatus is niet gereed.")

    raw_path = str(state.get("export_path") or "").strip()
    expected_sha = str(state.get("export_sha256") or "").strip().lower()
    if not raw_path or not expected_sha:
        raise RuntimeError("Crash Recovery exportmetadata is onvolledig.")

    root = CRASH_RECOVERY_EXPORT_ROOT.resolve()
    candidate = Path(raw_path).resolve()
    if candidate.suffix.lower() != ".zip" or root not in candidate.parents:
        raise RuntimeError("Crash Recovery exportpad valt buiten de veilige exportroot.")
    if not candidate.is_file():
        raise RuntimeError("Crash Recovery exportbestand ontbreekt.")

    actual_sha = sha256_file(candidate).lower()
    if actual_sha != expected_sha:
        raise RuntimeError("Crash Recovery export SHA-256 wijkt af van de geverifieerde SHA.")
    return candidate


def _cleanup_completed_export(state: dict[str, Any]) -> dict[str, Any]:
    """Verwijder uitsluitend exact geregistreerde tijdelijke artefacten van deze run."""
    if str(state.get("download_status") or "") != "downloaded":
        return {
            "status": "error",
            "removed": [],
            "warnings": ["Cleanup geweigerd voordat download volledig is afgerond."],
        }

    removed: list[str] = []
    warnings: list[str] = []

    export_raw = str(state.get("export_path") or "").strip()
    if export_raw:
        export_root = CRASH_RECOVERY_EXPORT_ROOT.resolve()
        export_path = Path(export_raw).resolve()
        if export_path.suffix.lower() == ".zip" and export_root in export_path.parents:
            try:
                if export_path.exists():
                    export_path.unlink()
                    removed.append(str(export_path))
            except OSError as exc:
                warnings.append(f"Export-ZIP cleanup mislukt: {exc}")
        else:
            warnings.append("Onveilig exportpad niet verwijderd.")

    backup_name = str(state.get("backup_name") or "").strip()
    if (
        backup_name
        and Path(backup_name).name == backup_name
        and re.fullmatch(r"Energie_Complete_Backup_.*\.zip", backup_name)
    ):
        backup_root = PROJECT_BACKUP_ROOT.resolve()
        backup_path = (backup_root / backup_name).resolve()
        if backup_root in backup_path.parents:
            try:
                if backup_path.exists():
                    backup_path.unlink()
                    removed.append(str(backup_path))
            except OSError as exc:
                warnings.append(f"Complete-backup cleanup mislukt: {exc}")

            manifest_name = f"{Path(backup_name).stem}_manifest.json"
            manifest_path = (backup_root / "Manifests" / manifest_name).resolve()
            manifests_root = (backup_root / "Manifests").resolve()
            if manifests_root in manifest_path.parents:
                try:
                    if manifest_path.exists():
                        manifest_path.unlink()
                        removed.append(str(manifest_path))
                except OSError as exc:
                    warnings.append(f"Run-manifest cleanup mislukt: {exc}")
    elif backup_name:
        warnings.append("Niet-complete bronbackup bewust niet verwijderd.")

    staging_raw = str(state.get("restore_staging_path") or "").strip()
    if staging_raw:
        if staging_raw.startswith("/recovery/RestoreStaging/"):
            staging_path = _recovery_path_to_project_backup(staging_raw)
            staging_root = (PROJECT_BACKUP_ROOT / "RestoreStaging").resolve()
            if (
                staging_path is not None
                and staging_path != staging_root
                and staging_root in staging_path.parents
            ):
                try:
                    if staging_path.exists():
                        if staging_path.is_dir():
                            shutil.rmtree(staging_path)
                        else:
                            staging_path.unlink()
                        removed.append(str(staging_path))
                except OSError as exc:
                    warnings.append(f"RestoreStaging cleanup mislukt: {exc}")
        else:
            warnings.append("Onveilig RestoreStaging-pad niet verwijderd.")

    return {
        "status": "warning" if warnings else "ok",
        "removed": removed,
        "warnings": warnings,
    }


def _stream_complete_recovery_download(writer: Any) -> dict[str, Any]:
    """Stream de laatst geverifieerde export; cleanup alleen na volledige stream."""
    if not COMPLETE_CRASH_RECOVERY_EXPORT_LOCK.acquire(blocking=False):
        return {
            "status": "busy",
            "download_status": "busy",
            "cleanup_status": "pending",
            "error": "Er loopt al een Crash Recovery export/download.",
        }

    try:
        state = _complete_recovery_state()
        export_path = _validated_export_download_path(state)
        try:
            with export_path.open("rb") as handle:
                while True:
                    chunk = handle.read(1024 * 1024)
                    if not chunk:
                        break
                    writer.write(chunk)
            flush = getattr(writer, "flush", None)
            if callable(flush):
                flush()
        except (BrokenPipeError, ConnectionResetError) as exc:
            updated = dict(state)
            updated["status"] = "retry_available"
            updated["download_status"] = "retry_available"
            updated["cleanup_status"] = "pending"
            updated["download_error"] = f"{type(exc).__name__}: browserverbinding afgebroken"
            updated["checked_at"] = datetime.now(TZ).isoformat()
            _save_complete_recovery_state(updated)
            return updated

        updated = dict(state)
        updated["status"] = "downloaded"
        updated["download_status"] = "downloaded"
        updated["cleanup_status"] = "running"
        updated["downloaded_at"] = datetime.now(TZ).isoformat()
        updated["checked_at"] = updated["downloaded_at"]
        _save_complete_recovery_state(updated)

        cleanup = _cleanup_completed_export(updated)
        updated["cleanup_status"] = str(cleanup.get("status") or "warning")
        updated["cleanup_removed"] = list(cleanup.get("removed") or [])
        updated["cleanup_warnings"] = list(cleanup.get("warnings") or [])
        updated["checked_at"] = datetime.now(TZ).isoformat()
        _save_complete_recovery_state(updated)
        return updated
    finally:
        COMPLETE_CRASH_RECOVERY_EXPORT_LOCK.release()


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
        "  const canDownload=['ready_for_download','retry_available'].includes(String(result.status||'')) || ['ready','retry_available'].includes(String(result.download_status||''));\n"
        "  if(downloadButton) downloadButton.disabled=!canDownload;\n",
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

    get_anchor = '        if complete_recovery_path.endswith("/api/crash-recovery/state"):\n'
    download_route = r'''        if complete_recovery_path.endswith("/api/crash-recovery/download"):
            state = _complete_recovery_state()
            try:
                export_path = _validated_export_download_path(state)
            except Exception as exc:
                body = json.dumps(
                    {"status": "error", "error": str(exc)},
                    ensure_ascii=False,
                ).encode("utf-8")
                self.send_body(
                    HTTPStatus.CONFLICT,
                    body,
                    "application/json; charset=utf-8",
                )
                return

            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Length", str(export_path.stat().st_size))
            self.send_header(
                "Content-Disposition",
                f'attachment; filename="{export_path.name}"',
            )
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            _stream_complete_recovery_download(self.wfile)
            return

'''
    text = replace_once(text, get_anchor, download_route + get_anchor, "download GET route")

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
