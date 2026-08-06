#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import io
import json
import logging
import random
import hashlib
import re
import shutil
import signal
import threading
import time
import urllib.error
import urllib.request
import socket
import zipfile
from calendar import monthrange
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

BASE_URL = "https://app.slimmemeterportal.nl"
OPTIONS_PATH = Path("/data/options.json")
OUTPUT_ROOT = Path("/config/output")
STATE_PATH = Path("/config/state.json")
TZ = ZoneInfo("Europe/Amsterdam")
APP_VERSION = "3.9.4"

LOGGER = logging.getLogger("slimmemeterportal_import")
STOP = threading.Event()
RUN_LOCK = threading.Lock()
STATE_LOCK = threading.RLock()


@dataclass(frozen=True)
class Options:
    api_key: str
    run_on_start: bool
    target_month: str
    schedule_enabled: bool
    schedule_day: int
    schedule_hour: int
    request_timeout_seconds: int
    retry_count: int
    usage_path_template: str
    resume_incomplete_month: bool
    retention_months: int
    verify_after_import: bool
    fail_on_validation_errors: bool
    detect_duplicates: bool
    create_month_summary: bool
    create_transfer_bundle: bool
    workflow_mode: str
    homewizard_enabled: bool
    homewizard_devices: list[dict[str, Any]]
    homewizard_sample_seconds: int
    enphase_enabled: bool
    enphase_source_url: str
    enphase_bearer_token: str
    epex_electricity_enabled: bool
    epex_electricity_url: str
    epex_gas_enabled: bool
    epex_gas_url: str
    report_trigger_enabled: bool
    report_trigger_url: str
    report_trigger_token: str
    require_all_core_sources: bool

    @classmethod
    def load(cls) -> "Options":
        try:
            raw = json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RuntimeError(f"Optiebestand ontbreekt: {OPTIONS_PATH}") from exc
        result = cls(
            api_key=str(raw.get("api_key", "")).strip(),
            run_on_start=bool(raw.get("run_on_start", False)),
            target_month=str(raw.get("target_month", "")).strip(),
            schedule_enabled=bool(raw.get("schedule_enabled", True)),
            schedule_day=int(raw.get("schedule_day", 2)),
            schedule_hour=int(raw.get("schedule_hour", 3)),
            request_timeout_seconds=int(raw.get("request_timeout_seconds", 30)),
            retry_count=int(raw.get("retry_count", 3)),
            usage_path_template=str(raw.get(
                "usage_path_template",
                "/userapi/v1/connections/{connection_id}/usage/{date}",
            )).strip(),
            resume_incomplete_month=bool(raw.get("resume_incomplete_month", True)),
            retention_months=int(raw.get("retention_months", 24)),
            verify_after_import=bool(raw.get("verify_after_import", True)),
            fail_on_validation_errors=bool(raw.get("fail_on_validation_errors", False)),
            detect_duplicates=bool(raw.get("detect_duplicates", True)),
            create_month_summary=bool(raw.get("create_month_summary", True)),
            create_transfer_bundle=bool(raw.get("create_transfer_bundle", True)),
            workflow_mode=str(raw.get("workflow_mode", "smp_only")),
            homewizard_enabled=bool(raw.get("homewizard_enabled", False)),
            homewizard_devices=list(raw.get("homewizard_devices", [])),
            homewizard_sample_seconds=int(raw.get("homewizard_sample_seconds", 900)),
            enphase_enabled=bool(raw.get("enphase_enabled", False)),
            enphase_source_url=str(raw.get("enphase_source_url", "")).strip(),
            enphase_bearer_token=str(raw.get("enphase_bearer_token", "")).strip(),
            epex_electricity_enabled=bool(raw.get("epex_electricity_enabled", False)),
            epex_electricity_url=str(raw.get("epex_electricity_url", "")).strip(),
            epex_gas_enabled=bool(raw.get("epex_gas_enabled", False)),
            epex_gas_url=str(raw.get("epex_gas_url", "")).strip(),
            report_trigger_enabled=bool(raw.get("report_trigger_enabled", False)),
            report_trigger_url=str(raw.get("report_trigger_url", "")).strip(),
            report_trigger_token=str(raw.get("report_trigger_token", "")).strip(),
            require_all_core_sources=bool(raw.get("require_all_core_sources", True)),
        )
        result.validate()
        return result

    def validate(self) -> None:
        if not self.api_key:
            raise ValueError("API-key ontbreekt.")
        if self.target_month:
            datetime.strptime(self.target_month, "%Y-%m")
        if not 1 <= self.schedule_day <= 28:
            raise ValueError("schedule_day moet 1 t/m 28 zijn.")
        if not 0 <= self.schedule_hour <= 23:
            raise ValueError("schedule_hour moet 0 t/m 23 zijn.")
        if not 5 <= self.request_timeout_seconds <= 120:
            raise ValueError("request_timeout_seconds moet 5 t/m 120 zijn.")
        if not 0 <= self.retry_count <= 10:
            raise ValueError("retry_count moet 0 t/m 10 zijn.")
        required_placeholders = {"{connection_id}", "{date}"}
        if not all(token in self.usage_path_template for token in required_placeholders):
            raise ValueError(
                "usage_path_template moet {connection_id} en {date} bevatten."
            )
        if not 1 <= self.retention_months <= 120:
            raise ValueError("retention_months moet 1 t/m 120 zijn.")
        if self.workflow_mode not in {"smp_only", "full_month_workflow"}:
            raise ValueError("workflow_mode is ongeldig.")
        if not 60 <= self.homewizard_sample_seconds <= 3600:
            raise ValueError("homewizard_sample_seconds moet 60 t/m 3600 zijn.")
        if self.enphase_enabled and not self.enphase_source_url:
            raise ValueError("Enphase is ingeschakeld maar enphase_source_url ontbreekt.")
        if self.epex_electricity_enabled and not self.epex_electricity_url:
            raise ValueError("EPEX elektriciteit is ingeschakeld maar URL ontbreekt.")
        if self.epex_gas_enabled and not self.epex_gas_url:
            raise ValueError("EPEX gas is ingeschakeld maar URL ontbreekt.")
        if self.report_trigger_enabled and not self.report_trigger_url:
            raise ValueError("Rapporttrigger is ingeschakeld maar URL ontbreekt.")
        for device in self.homewizard_devices:
            if not isinstance(device, dict):
                raise ValueError("Iedere HomeWizard-configuratie moet een object zijn.")
            if not str(device.get("label", "")).strip():
                raise ValueError("HomeWizard-apparaat mist label.")
            if not str(device.get("host", "")).strip():
                raise ValueError("HomeWizard-apparaat mist host.")
            if str(device.get("role", "other")) not in {"p1", "gas", "socket", "other"}:
                raise ValueError("HomeWizard-rol is ongeldig.")


def default_state() -> dict[str, Any]:
    return {
        "version": APP_VERSION,
        "status": "idle",
        "last_started": None,
        "last_finished": None,
        "last_target_month": None,
        "last_output": None,
        "last_error": None,
        "last_validation_status": None,
        "next_scheduled_run": None,
        "api_test": None,
        "progress_current": 0,
        "progress_total": 0,
        "progress_message": None,
        "cancel_requested": False,
        "last_integrity_status": None,
        "last_integrity_checked_at": None,
        "last_summary": None,
        "last_transfer_bundle": None,
        "workflow_sources": {"slimmemeterportal": "ready"},
        "homewizard_last_snapshot": None,
        "homewizard_last_error": None,
        "enphase_last_import": None,
        "enphase_last_error": None,
        "epex_electricity_last_import": None,
        "epex_electricity_last_error": None,
        "epex_gas_last_import": None,
        "epex_gas_last_error": None,
        "last_central_validation": None,
        "last_report_trigger": None,
        "last_report_trigger_error": None,
        "last_self_test": None,
        "installation_ready": False,
    }


def _read_state_unlocked() -> dict[str, Any]:
    if not STATE_PATH.exists():
        return default_state()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        return {**default_state(), **data}
    except Exception:
        LOGGER.exception("Statusbestand kon niet worden gelezen; standaardstatus gebruikt.")
        return default_state()


def load_state() -> dict[str, Any]:
    with STATE_LOCK:
        return _read_state_unlocked()


def update_state(**changes: Any) -> None:
    with STATE_LOCK:
        state = _read_state_unlocked()
        state.update(changes)
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp = STATE_PATH.with_suffix(".tmp")
        temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temp.replace(STATE_PATH)



def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(target: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(target.rglob("*")):
        if path.is_file() and path.name not in {
            "manifest.json",
            "integrity_report.json",
            "report_trigger_result.json",
            ".incomplete",
        }:
            files.append({
                "path": str(path.relative_to(target)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            })
    return {
        "version": APP_VERSION,
        "generated_at": datetime.now(TZ).isoformat(),
        "file_count": len(files),
        "total_bytes": sum(item["bytes"] for item in files),
        "files": files,
    }



def verify_manifest(target: Path) -> dict[str, Any]:
    manifest_path = target / "manifest.json"
    if not manifest_path.exists():
        return {
            "status": "error",
            "checked_at": datetime.now(TZ).isoformat(),
            "errors": ["manifest.json ontbreekt"],
            "files_checked": 0,
        }

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "status": "error",
            "checked_at": datetime.now(TZ).isoformat(),
            "errors": [f"manifest.json is ongeldig: {exc}"],
            "files_checked": 0,
        }

    errors: list[str] = []
    checked = 0
    for item in manifest.get("files", []):
        rel = str(item.get("path", ""))
        expected_hash = str(item.get("sha256", ""))
        expected_bytes = int(item.get("bytes", -1))
        path = target / rel
        if not path.exists():
            errors.append(f"Ontbrekend bestand: {rel}")
            continue
        if path.stat().st_size != expected_bytes:
            errors.append(f"Verkeerde grootte: {rel}")
            continue
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            errors.append(f"Hash-afwijking: {rel}")
            continue
        checked += 1

    return {
        "status": "ok" if not errors else "error",
        "checked_at": datetime.now(TZ).isoformat(),
        "errors": errors,
        "files_checked": checked,
        "manifest_file_count": manifest.get("file_count", 0),
    }



LEGACY_MANIFEST_MUTABLE_FILES = {
    "central_validation.json",
    "integrity_report.json",
    "report_trigger_result.json",
}


def verify_latest_with_legacy_repair(target: Path) -> dict[str, Any]:
    result = verify_manifest(target)
    if result.get("status") == "ok":
        return result

    manifest_path = target / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception:
        return result

    if str(manifest.get("version", "")) not in {"3.9.2", "3.9.3"}:
        return result

    errors = list(result.get("errors") or [])
    affected: set[str] = set()
    for error in errors:
        match = re.match(
            r"^(?:Hash-afwijking|Verkeerde grootte|Ontbrekend bestand): (.+)$",
            str(error),
        )
        if not match:
            return result
        affected.add(match.group(1))

    if not affected or not affected.issubset(LEGACY_MANIFEST_MUTABLE_FILES):
        return result

    write_atomic_json(target / "manifest.json", build_manifest(target))
    repaired = verify_manifest(target)
    repaired["legacy_manifest_repaired"] = repaired.get("status") == "ok"
    repaired["repaired_files"] = sorted(affected)
    return repaired



def latest_month_dir() -> Path | None:
    if not OUTPUT_ROOT.exists():
        return None
    candidates = sorted(
        [p for p in OUTPUT_ROOT.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}_\d{2}", p.name)],
        reverse=True,
    )
    return candidates[0] if candidates else None


def cleanup_retention(retention_months: int) -> None:
    if not OUTPUT_ROOT.exists():
        return
    month_dirs = sorted(
        [p for p in OUTPUT_ROOT.iterdir() if p.is_dir() and re.fullmatch(r"\d{4}_\d{2}", p.name)],
        reverse=True,
    )
    for obsolete in month_dirs[retention_months:]:
        LOGGER.info("Verwijder oude maanduitvoer volgens retentie: %s", obsolete)
        shutil.rmtree(obsolete)


def is_cancel_requested() -> bool:
    return bool(load_state().get("cancel_requested")) or STOP.is_set()



def build_usage_path(options: Options, connection_id: str, current: date) -> str:
    return options.usage_path_template.format(
        connection_id=connection_id,
        date=current.strftime("%d-%m-%Y"),
    )


def api_get(path: str, options: Options) -> Any:
    request = urllib.request.Request(
        BASE_URL + path,
        headers={
            "API-Key": options.api_key,
            "Accept": "application/json",
            "User-Agent": f"Energieproject-SMP/{APP_VERSION}",
        },
        method="GET",
    )
    last: Exception | None = None
    for attempt in range(options.retry_count + 1):
        try:
            with urllib.request.urlopen(request, timeout=options.request_timeout_seconds) as response:
                status = getattr(response, "status", 200)
                if status != 200:
                    raise RuntimeError(f"HTTP {status}")
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise RuntimeError(f"API-key geweigerd (HTTP {exc.code}).") from exc
            last = exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last = exc
        if attempt < options.retry_count:
            delay = min(30.0, 2**attempt + random.random())
            LOGGER.warning("API-poging %d mislukt; nieuwe poging over %.1f s: %s", attempt + 1, delay, last)
            STOP.wait(delay)
    raise RuntimeError(f"API-aanroep mislukt voor {path}: {last}")


def test_api() -> dict[str, Any]:
    started = datetime.now(TZ)
    try:
        options = Options.load()
        connections = api_get("/userapi/v1/connections", options)
        if not isinstance(connections, list):
            raise RuntimeError("API gaf geen lijst met aansluitingen terug.")
        result = {
            "status": "ok",
            "checked_at": started.isoformat(),
            "connections": len(connections),
            "types": sorted(
                {
                    str(item.get("connection_type") or item.get("type") or "onbekend")
                    for item in connections
                    if isinstance(item, dict)
                }
            ),
        }
    except Exception as exc:
        result = {
            "status": "error",
            "checked_at": started.isoformat(),
            "error": str(exc),
        }
    update_state(api_test=result)
    return result


def previous_month(today: date) -> tuple[int, int]:
    previous = today.replace(day=1) - timedelta(days=1)
    return previous.year, previous.month


def resolve_month(value: str, options: Options) -> tuple[int, int]:
    selected = value.strip() or options.target_month
    if selected:
        parsed = datetime.strptime(selected, "%Y-%m")
        return parsed.year, parsed.month
    return previous_month(datetime.now(TZ).date())


def flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    out: dict[str, Any] = {}
    if isinstance(value, dict):
        for key, child in value.items():
            out.update(flatten(child, f"{prefix}.{key}" if prefix else str(key)))
    elif isinstance(value, list):
        out[prefix or "value"] = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    else:
        out[prefix or "value"] = value
    return out


def records_from(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        source = payload
    elif isinstance(payload, dict):
        source = None
        for key in ("usage", "data", "values", "measurements", "readings"):
            if isinstance(payload.get(key), list):
                source = payload[key]
                break
        source = source if source is not None else [payload]
    else:
        source = [{"value": payload}]
    return [flatten(item) if isinstance(item, dict) else {"value": item} for item in source]


def expected_count(kind: str, day: date) -> set[int]:
    start = datetime(day.year, day.month, day.day, tzinfo=TZ)
    tomorrow = day + timedelta(days=1)
    end = datetime(tomorrow.year, tomorrow.month, tomorrow.day, tzinfo=TZ)
    hours = round((end.timestamp() - start.timestamp()) / 3600)
    if kind.lower() in {"elektriciteit", "electricity"}:
        return {hours * 4}
    if kind.lower() == "gas":
        return {hours}
    return set()


def safe(value: str) -> str:
    return "".join(c if c.isalnum() or c in "_-" else "_" for c in value)



def canonical_record(record: dict[str, Any]) -> str:
    return json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def duplicate_count(rows: list[dict[str, Any]]) -> int:
    seen: set[str] = set()
    duplicates = 0
    for row in rows:
        key = canonical_record(row)
        if key in seen:
            duplicates += 1
        else:
            seen.add(key)
    return duplicates


def detect_numeric_fields(rows: list[dict[str, Any]]) -> list[str]:
    numeric: list[str] = []
    fields = sorted({key for row in rows for key in row})
    for field in fields:
        values = [row.get(field) for row in rows if row.get(field) not in (None, "")]
        if not values:
            continue
        ok = True
        for value in values[:200]:
            try:
                float(str(value).replace(",", "."))
            except (TypeError, ValueError):
                ok = False
                break
        if ok:
            numeric.append(field)
    return numeric


def summarize_numeric(rows: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    summary: dict[str, dict[str, float]] = {}
    for field in detect_numeric_fields(rows):
        values: list[float] = []
        for row in rows:
            raw = row.get(field)
            if raw in (None, ""):
                continue
            try:
                values.append(float(str(raw).replace(",", ".")))
            except (TypeError, ValueError):
                continue
        if values:
            summary[field] = {
                "count": len(values),
                "sum": round(sum(values), 9),
                "min": min(values),
                "max": max(values),
                "average": round(sum(values) / len(values), 9),
            }
    return summary


def build_month_summary(
    month_iso: str,
    connection_summaries: list[dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    return {
        "version": APP_VERSION,
        "generated_at": datetime.now(TZ).isoformat(),
        "target_month": month_iso,
        "connections": connection_summaries,
        "totals": {
            "connections": len(connection_summaries),
            "records": sum(item.get("records", 0) for item in connection_summaries),
            "duplicates": sum(item.get("duplicates", 0) for item in connection_summaries),
            "error_count": len(errors),
            "warning_count": len(warnings),
        },
    }







def run_self_test() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, detail: str = "") -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    try:
        options = Options.load()
        add("config", "ok", "Configuratie geladen.")
    except Exception as exc:
        options = None
        add("config", "error", str(exc))

    try:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        probe = OUTPUT_ROOT / ".write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        add("storage", "ok", str(OUTPUT_ROOT))
    except Exception as exc:
        add("storage", "error", str(exc))

    if options is not None:
        try:
            result = test_api()
            add(
                "slimmemeterportal_api",
                "ok" if result.get("status") == "ok" else "error",
                json.dumps(result, ensure_ascii=False),
            )
        except Exception as exc:
            add("slimmemeterportal_api", "error", str(exc))

        source_status = workflow_source_status(options)
        add("workflow_sources", "ok", json.dumps(source_status, ensure_ascii=False))

        if options.report_trigger_enabled:
            add("report_trigger_config", "ok", options.report_trigger_url)
        else:
            add("report_trigger_config", "warning", "Uitgeschakeld.")

    overall = (
        "error"
        if any(item["status"] == "error" for item in checks)
        else ("warning" if any(item["status"] == "warning" for item in checks) else "ok")
    )
    result = {
        "version": APP_VERSION,
        "checked_at": datetime.now(TZ).isoformat(),
        "status": overall,
        "checks": checks,
    }
    update_state(last_self_test=result, installation_ready=(overall != "error"))
    return result


def core_source_requirements(options: Options) -> dict[str, bool]:
    return {
        "slimmemeterportal": True,
        "homewizard": options.homewizard_enabled,
        "enphase": options.enphase_enabled,
        "epex_electricity": options.epex_electricity_enabled,
        "epex_gas": options.epex_gas_enabled,
    }


def validate_central_workflow(
    options: Options,
    state: dict[str, Any],
    month_summary: dict[str, Any] | None,
) -> dict[str, Any]:
    source_status = workflow_source_status(options)
    requirements = core_source_requirements(options)
    errors: list[str] = []
    warnings: list[str] = []

    if not month_summary:
        errors.append("SlimmeMeterPortal maandsamenvatting ontbreekt.")

    for source, required in requirements.items():
        status = source_status.get(source, "not_configured")
        if required and status != "ready":
            errors.append(f"Verplichte bron niet gereed: {source} ({status}).")
        elif not required and status != "ready":
            warnings.append(f"Optionele bron niet gereed: {source} ({status}).")

    if options.require_all_core_sources:
        enabled_sources = [name for name, enabled in requirements.items() if enabled]
        for source in enabled_sources:
            if source == "homewizard" and not state.get("homewizard_last_snapshot"):
                errors.append("HomeWizard snapshot ontbreekt.")
            elif source == "enphase" and not state.get("enphase_last_import"):
                errors.append("Enphase-import ontbreekt.")
            elif source == "epex_electricity" and not state.get("epex_electricity_last_import"):
                errors.append("EPEX elektriciteitsimport ontbreekt.")
            elif source == "epex_gas" and not state.get("epex_gas_last_import"):
                errors.append("EPEX gasimport ontbreekt.")

    result = {
        "version": APP_VERSION,
        "checked_at": datetime.now(TZ).isoformat(),
        "status": "error" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": warnings,
        "source_status": source_status,
        "requirements": requirements,
        "month_summary": month_summary,
    }
    return result


def trigger_report_generation(
    options: Options,
    year: int,
    month: int,
    transfer_bundle: str | None,
    central_validation: dict[str, Any],
) -> dict[str, Any]:
    if not options.report_trigger_enabled:
        return {
            "status": "skipped",
            "triggered_at": datetime.now(TZ).isoformat(),
            "reason": "report_trigger_enabled=false",
        }

    payload = {
        "year": year,
        "month": month,
        "transfer_bundle": transfer_bundle,
        "central_validation": central_validation,
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": f"Energieproject-ReportTrigger/{APP_VERSION}",
    }
    if options.report_trigger_token:
        headers["Authorization"] = f"Bearer {options.report_trigger_token}"

    request = urllib.request.Request(
        options.report_trigger_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=min(options.request_timeout_seconds, 60)) as response:
            body = response.read().decode("utf-8", errors="replace")
            return {
                "status": "ok",
                "triggered_at": datetime.now(TZ).isoformat(),
                "http_status": getattr(response, "status", 200),
                "response": body[:4000],
            }
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, socket.timeout) as exc:
        raise RuntimeError(f"Rapporttrigger mislukt: {exc}") from exc


def fetch_external_source(
    url: str,
    timeout: int,
    bearer_token: str = "",
) -> tuple[bytes, str]:
    headers = {
        "Accept": "application/json,text/csv,text/plain,*/*",
        "User-Agent": f"Energieproject-Import/{APP_VERSION}",
    }
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content_type = response.headers.get("Content-Type", "application/octet-stream")
            return response.read(), content_type
    except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
        raise RuntimeError(f"Bron niet bereikbaar: {exc}") from exc


def store_external_source(
    source_name: str,
    content: bytes,
    content_type: str,
    captured_at: datetime | None = None,
) -> Path:
    captured_at = captured_at or datetime.now(TZ)
    target = OUTPUT_ROOT / "external_sources" / source_name / f"{captured_at:%Y_%m}"
    target.mkdir(parents=True, exist_ok=True)

    lowered = content_type.lower()
    if "json" in lowered:
        extension = ".json"
        try:
            parsed = json.loads(content.decode("utf-8"))
            rendered = json.dumps(parsed, ensure_ascii=False, indent=2).encode("utf-8")
        except Exception:
            rendered = content
    elif "csv" in lowered or "text/plain" in lowered:
        extension = ".csv"
        rendered = content
    else:
        extension = ".bin"
        rendered = content

    path = target / f"{source_name}_{captured_at:%Y-%m-%d_%H-%M-%S}{extension}"
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_bytes(rendered)
    temp.replace(path)
    return path


def run_enphase_import() -> dict[str, Any]:
    options = Options.load()
    if not options.enphase_enabled:
        raise RuntimeError("Enphase-import is uitgeschakeld.")
    content, content_type = fetch_external_source(
        options.enphase_source_url,
        min(options.request_timeout_seconds, 60),
        options.enphase_bearer_token,
    )
    path = store_external_source("enphase", content, content_type)
    result = {
        "status": "ok",
        "captured_at": datetime.now(TZ).isoformat(),
        "path": str(path),
        "bytes": len(content),
        "content_type": content_type,
    }
    update_state(enphase_last_import=str(path), enphase_last_error=None)
    return result


def run_epex_import(kind: str) -> dict[str, Any]:
    options = Options.load()
    if kind == "electricity":
        enabled = options.epex_electricity_enabled
        url = options.epex_electricity_url
        source_name = "epex_electricity"
    elif kind == "gas":
        enabled = options.epex_gas_enabled
        url = options.epex_gas_url
        source_name = "epex_gas"
    else:
        raise ValueError("Onbekend EPEX-type.")

    if not enabled:
        raise RuntimeError(f"{source_name} is uitgeschakeld.")
    content, content_type = fetch_external_source(
        url,
        min(options.request_timeout_seconds, 60),
    )
    path = store_external_source(source_name, content, content_type)
    result = {
        "status": "ok",
        "captured_at": datetime.now(TZ).isoformat(),
        "path": str(path),
        "bytes": len(content),
        "content_type": content_type,
    }
    if kind == "electricity":
        update_state(epex_electricity_last_import=str(path), epex_electricity_last_error=None)
    else:
        update_state(epex_gas_last_import=str(path), epex_gas_last_error=None)
    return result


def homewizard_get(host: str, timeout: int) -> dict[str, Any]:
    url = f"http://{host}/api/v1/data"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": f"Energieproject-HomeWizard/{APP_VERSION}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, socket.timeout) as exc:
        raise RuntimeError(f"HomeWizard {host} niet bereikbaar: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"HomeWizard {host} gaf geen JSON-object terug.")
    return payload


def collect_homewizard_snapshot(options: Options) -> dict[str, Any]:
    timestamp = datetime.now(TZ)
    result: dict[str, Any] = {
        "version": APP_VERSION,
        "captured_at": timestamp.isoformat(),
        "devices": [],
        "errors": [],
        "warnings": [],
    }

    for device in options.homewizard_devices:
        label = str(device.get("label", "")).strip()
        host = str(device.get("host", "")).strip()
        role = str(device.get("role", "other"))
        optional = bool(device.get("optional", False))
        try:
            payload = homewizard_get(host, min(options.request_timeout_seconds, 30))
            result["devices"].append({
                "label": label,
                "host": host,
                "role": role,
                "optional": optional,
                "status": "ok",
                "data": payload,
            })
        except Exception as exc:
            message = f"{label} ({host}): {exc}"
            if optional:
                result["warnings"].append(message)
                status = "warning"
            else:
                result["errors"].append(message)
                status = "error"
            result["devices"].append({
                "label": label,
                "host": host,
                "role": role,
                "optional": optional,
                "status": status,
                "error": str(exc),
            })

    result["status"] = (
        "error" if result["errors"]
        else ("warning" if result["warnings"] else "ok")
    )
    return result


def save_homewizard_snapshot(snapshot: dict[str, Any]) -> Path:
    captured = datetime.fromisoformat(snapshot["captured_at"])
    target = OUTPUT_ROOT / "homewizard_snapshots" / f"{captured:%Y_%m}"
    target.mkdir(parents=True, exist_ok=True)
    path = target / f"HomeWizard_{captured:%Y-%m-%d_%H-%M-%S}.json"
    write_atomic_json(path, snapshot)

    jsonl = target / f"HomeWizard_{captured:%Y_%m}.jsonl"
    with jsonl.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
    return path


def run_homewizard_snapshot() -> dict[str, Any]:
    options = Options.load()
    if not options.homewizard_enabled:
        raise RuntimeError("HomeWizard-import is uitgeschakeld.")
    if not options.homewizard_devices:
        raise RuntimeError("Geen HomeWizard-apparaten geconfigureerd.")
    snapshot = collect_homewizard_snapshot(options)
    path = save_homewizard_snapshot(snapshot)
    update_state(
        homewizard_last_snapshot=str(path),
        homewizard_last_error=None if snapshot["status"] != "error" else f"{len(snapshot['errors'])} fout(en)",
    )
    return snapshot


def workflow_source_status(options: Options) -> dict[str, str]:
    status = {"slimmemeterportal": "ready"}
    if options.workflow_mode == "full_month_workflow":
        status.update({
            "homewizard": (
                "ready"
                if options.homewizard_enabled and options.homewizard_devices
                else "not_configured"
            ),
            "enphase": "ready" if options.enphase_enabled else "not_configured",
            "epex_electricity": "ready" if options.epex_electricity_enabled else "not_configured",
            "epex_gas": "ready" if options.epex_gas_enabled else "not_configured",
        })
    return status


def build_transfer_bundle(target: Path, month_key: str) -> Path:
    bundle = target.parent / f"Energie_Maandimport_{month_key}.zip"
    temp = bundle.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(target.rglob("*")):
            if path.is_file() and path.name != ".incomplete":
                archive.write(path, arcname=str(Path(month_key) / path.relative_to(target)))
    temp.replace(bundle)
    return bundle


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for field in row:
            if field not in seen:
                seen.add(field)
                fields.append(field)
    with path.open("w", encoding="utf-8", newline="") as handle:
        if not fields:
            return
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_atomic_json(path: Path, value: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def run_import(year: int, month: int) -> None:
    if not RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("Er draait al een import.")
    try:
        options = Options.load()
        month_iso = f"{year:04d}-{month:02d}"
        target = OUTPUT_ROOT / f"{year:04d}_{month:02d}"
        raw = target / "raw"
        raw.mkdir(parents=True, exist_ok=True)
        incomplete_marker = target / ".incomplete"
        incomplete_marker.write_text(datetime.now(TZ).isoformat(), encoding="utf-8")

        update_state(
            status="running",
            last_started=datetime.now(TZ).isoformat(),
            last_finished=None,
            last_target_month=month_iso,
            last_error=None,
            last_validation_status=None,
            progress_current=0,
            progress_total=0,
            progress_message="Aansluitingen ophalen",
            cancel_requested=False,
            workflow_sources=workflow_source_status(options),
        )

        connections = api_get("/userapi/v1/connections", options)
        if not isinstance(connections, list) or not connections:
            raise RuntimeError("Geen aansluitingen ontvangen.")
        write_atomic_json(target / "connections.json", connections)
        total_steps = len(connections) * monthrange(year, month)[1]
        completed_steps = 0
        update_state(progress_total=total_steps, progress_current=0, progress_message="Dagdata ophalen")

        report: dict[str, Any] = {
            "version": APP_VERSION,
            "generated_at": datetime.now(TZ).isoformat(),
            "target_month": month_iso,
            "status": "running",
            "connections": [],
            "errors": [],
            "warnings": [],
        }

        for connection in connections:
            if not isinstance(connection, dict):
                report["errors"].append(f"Ongeldig aansluitingsrecord: {connection!r}")
                continue
            identifier = str(
                connection.get("connection_id")
                or connection.get("meter_identifier")
                or connection.get("id")
                or ""
            ).strip()
            kind = str(connection.get("connection_type") or connection.get("type") or "onbekend")
            if not identifier:
                report["errors"].append(f"Aansluiting zonder ID: {connection!r}")
                continue

            prefix = safe(f"{kind}_{identifier}")
            all_rows: list[dict[str, Any]] = []
            day_status: list[dict[str, Any]] = []

            for day_number in range(1, monthrange(year, month)[1] + 1):
                current = date(year, month, day_number)
                if is_cancel_requested():
                    raise RuntimeError("Import geannuleerd.")
                raw_path = raw / f"{prefix}_{current.isoformat()}.json"
                try:
                    if options.resume_incomplete_month and raw_path.exists():
                        payload = json.loads(raw_path.read_text(encoding="utf-8"))
                    else:
                        payload = api_get(
                            build_usage_path(options, identifier, current),
                            options,
                        )
                        write_atomic_json(raw_path, payload)
                    rows = records_from(payload)
                    for row in rows:
                        row.setdefault("_date", current.isoformat())
                        row.setdefault("_connection_type", kind)
                        row.setdefault("_connection_id", identifier)
                    all_rows.extend(rows)
                    expected = expected_count(kind, current)
                    day_result = {
                        "date": current.isoformat(),
                        "records": len(rows),
                        "expected_records": sorted(expected),
                        "status": "ok" if not expected or len(rows) in expected else "warning",
                    }
                    if day_result["status"] == "warning":
                        report["warnings"].append(
                            f"{kind} {current.isoformat()}: {len(rows)} records, verwacht {sorted(expected)}."
                        )
                    day_status.append(day_result)
                except Exception as exc:
                    message = f"{kind} {current.isoformat()}: {exc}"
                    LOGGER.error(message)
                    report["errors"].append(message)
                    day_status.append({
                        "date": current.isoformat(),
                        "records": 0,
                        "expected_records": sorted(expected_count(kind, current)),
                        "status": "error",
                        "error": str(exc),
                    })
                finally:
                    completed_steps += 1
                    update_state(
                        progress_current=completed_steps,
                        progress_total=total_steps,
                        progress_message=f"{kind}: {current.isoformat()}",
                    )

            csv_path = target / f"{prefix}_{year:04d}_{month:02d}.csv"
            jsonl_path = target / f"{prefix}_{year:04d}_{month:02d}.jsonl"
            write_csv(csv_path, all_rows)
            with jsonl_path.open("w", encoding="utf-8") as handle:
                for row in all_rows:
                    handle.write(json.dumps(row, ensure_ascii=False) + "\n")

            duplicates = duplicate_count(all_rows) if options.detect_duplicates else 0
            if duplicates:
                report["warnings"].append(
                    f"{kind}: {duplicates} dubbele record(s) gevonden."
                )
            connection_summary = {
                "connection_id": identifier,
                "connection_type": kind,
                "records": len(all_rows),
                "duplicates": duplicates,
                "numeric_summary": summarize_numeric(all_rows) if options.create_month_summary else {},
                "csv": csv_path.name,
                "jsonl": jsonl_path.name,
                "days": day_status,
            }
            report["connections"].append(connection_summary)

        if report["errors"]:
            report["status"] = "completed_with_errors"
        elif report["warnings"]:
            report["status"] = "completed_with_warnings"
        else:
            report["status"] = "completed"

        write_atomic_json(target / "validation_report.json", report)
        month_summary = build_month_summary(
            month_iso,
            report["connections"],
            report["errors"],
            report["warnings"],
        )
        if options.create_month_summary:
            write_atomic_json(target / "month_summary.json", month_summary)
        # Alle inhoudelijke bestanden eerst definitief maken.
        incomplete_marker.unlink(missing_ok=True)
        cleanup_retention(options.retention_months)

        central_validation = validate_central_workflow(
            options,
            load_state(),
            month_summary,
        )
        write_atomic_json(target / "central_validation.json", central_validation)

        # Manifest pas maken nadat de inhoudelijke bestanden definitief zijn.
        write_atomic_json(target / "manifest.json", build_manifest(target))

        integrity = {
            "status": "skipped",
            "checked_at": datetime.now(TZ).isoformat(),
            "errors": [],
            "files_checked": 0,
        }
        if options.verify_after_import:
            integrity = verify_manifest(target)
        write_atomic_json(target / "integrity_report.json", integrity)

        # Het overdrachtspakket bevat de definitieve maandinhoud en controle-uitkomst.
        transfer_bundle = None
        if options.create_transfer_bundle:
            transfer_bundle = build_transfer_bundle(target, f"{year:04d}_{month:02d}")

        report_trigger_result = None
        if central_validation["status"] == "ok":
            try:
                report_trigger_result = trigger_report_generation(
                    options,
                    year,
                    month,
                    str(transfer_bundle) if transfer_bundle else None,
                    central_validation,
                )
            except Exception as exc:
                report_trigger_result = {
                    "status": "error",
                    "triggered_at": datetime.now(TZ).isoformat(),
                    "error": str(exc),
                }
                if options.report_trigger_enabled:
                    report["errors"].append(str(exc))
                    report["status"] = "completed_with_errors"
        else:
            report_trigger_result = {
                "status": "skipped",
                "triggered_at": datetime.now(TZ).isoformat(),
                "reason": "central_validation_not_ok",
            }

        write_atomic_json(target / "report_trigger_result.json", report_trigger_result)

        if integrity["status"] == "error":
            LOGGER.error("Integriteitscontrole mislukt: %s", integrity.get("errors"))
            if options.fail_on_validation_errors:
                raise RuntimeError("Integriteitscontrole mislukt.")

        if options.fail_on_validation_errors and (
            report["errors"] or central_validation["status"] == "error"
        ):
            raise RuntimeError(
                "Validatie bevat fouten; import gemarkeerd als mislukt."
            )

        update_state(
            status=report["status"],
            last_finished=datetime.now(TZ).isoformat(),
            last_output=str(target),
            last_error=None if not report["errors"] else f"{len(report['errors'])} fout(en)",
            last_validation_status=report["status"],
            progress_current=total_steps,
            progress_total=total_steps,
            progress_message="Gereed",
            cancel_requested=False,
            last_integrity_status=integrity.get("status"),
            last_integrity_checked_at=integrity.get("checked_at"),
            last_summary=month_summary,
            last_transfer_bundle=str(transfer_bundle) if transfer_bundle else None,
            last_central_validation=central_validation,
            last_report_trigger=report_trigger_result,
            last_report_trigger_error=(
                report_trigger_result.get("error")
                if isinstance(report_trigger_result, dict)
                else None
            ),
        )
    except Exception as exc:
        LOGGER.exception("Import mislukt.")
        update_state(
            status="error",
            last_finished=datetime.now(TZ).isoformat(),
            last_error=str(exc),
            last_validation_status="error",
            progress_message="Afgebroken",
            cancel_requested=False,
        )
    finally:
        RUN_LOCK.release()


def next_run(options: Options) -> datetime:
    now = datetime.now(TZ)
    planned = datetime(now.year, now.month, options.schedule_day, options.schedule_hour, tzinfo=TZ)
    if planned <= now:
        if now.month == 12:
            planned = datetime(now.year + 1, 1, options.schedule_day, options.schedule_hour, tzinfo=TZ)
        else:
            planned = datetime(now.year, now.month + 1, options.schedule_day, options.schedule_hour, tzinfo=TZ)
    return planned


def scheduler() -> None:
    startup_handled = False
    last_homewizard_run: datetime | None = None
    while not STOP.is_set():
        try:
            options = Options.load()

            if options.homewizard_enabled and options.homewizard_devices:
                now = datetime.now(TZ)
                due = (
                    last_homewizard_run is None
                    or (now - last_homewizard_run).total_seconds() >= options.homewizard_sample_seconds
                )
                if due:
                    try:
                        snapshot = run_homewizard_snapshot()
                        LOGGER.info(
                            "HomeWizard snapshot: %s apparaat/apparaten, status %s.",
                            len(snapshot.get("devices", [])),
                            snapshot.get("status"),
                        )
                    except Exception as exc:
                        LOGGER.error("HomeWizard snapshot mislukt: %s", exc)
                        update_state(homewizard_last_error=str(exc))
                    last_homewizard_run = now

            if options.run_on_start and not startup_handled:
                startup_handled = True
                year, month = resolve_month("", options)
                threading.Thread(target=run_import, args=(year, month), daemon=True).start()
            if not options.schedule_enabled:
                update_state(next_scheduled_run=None)
                STOP.wait(30)
                continue
            planned = next_run(options)
            update_state(next_scheduled_run=planned.isoformat())
            wait = (planned - datetime.now(TZ)).total_seconds()
            if wait > 0:
                STOP.wait(min(60, wait))
                continue
            year, month = previous_month(datetime.now(TZ).date())
            run_import(year, month)
        except Exception as exc:
            LOGGER.error("Plannerfout: %s", exc)
            STOP.wait(30)


def month_archives() -> list[str]:
    if not OUTPUT_ROOT.exists():
        return []
    return sorted(
        [p.name for p in OUTPUT_ROOT.iterdir() if p.is_dir() and len(p.name) == 7],
        reverse=True,
    )


def zip_month(month_key: str) -> bytes:
    target = OUTPUT_ROOT / month_key
    if not target.exists() or not target.is_dir():
        raise FileNotFoundError(month_key)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(target.rglob("*")):
            if path.is_file():
                archive.write(path, arcname=str(Path(month_key) / path.relative_to(target)))
    return buffer.getvalue()


def html_page() -> bytes:
    state = load_state()
    try:
        options = Options.load()
        default_month = options.target_month or datetime.now(TZ).strftime("%Y-%m")
    except Exception:
        default_month = datetime.now(TZ).strftime("%Y-%m")

    def esc(value: Any) -> str:
        return html.escape(str(value if value is not None else ""))

    api_test = state.get("api_test") or {}
    api_text = "Nog niet getest"
    if api_test:
        api_text = (
            f"OK — {api_test.get('connections', 0)} aansluiting(en)"
            if api_test.get("status") == "ok"
            else f"Fout — {api_test.get('error', 'onbekend')}"
        )

    downloads = "".join(
        f"<li><a href='download?month={html.escape(month)}'>{html.escape(month)} downloaden</a></li>"
        for month in month_archives()
    ) or "<li>Nog geen uitvoer</li>"

    return f"""<!doctype html>
<html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SlimmeMeterPortal Import</title>
<style>
body{{font-family:system-ui;margin:0;background:#f5f7f9;color:#17202a}}
main{{max-width:800px;margin:24px auto;padding:0 16px}}
.card{{background:#fff;border-radius:14px;padding:20px;margin:14px 0;box-shadow:0 2px 12px #0001}}
dl{{display:grid;grid-template-columns:210px 1fr;gap:8px}}
button{{background:#03a9f4;color:#fff;border:0;border-radius:8px;padding:11px 16px;font-weight:700;margin-right:8px}}
input{{padding:10px;border:1px solid #bbb;border-radius:8px}}
a{{color:#0277bd}}
</style></head><body><main>
<h1>SlimmeMeterPortal Import</h1>
<div class="card"><h2>Status</h2><dl>
<dt>Versie</dt><dd>{APP_VERSION}</dd>
<dt>Status</dt><dd>{esc(state.get("status"))}</dd>
<dt>Laatste maand</dt><dd>{esc(state.get("last_target_month"))}</dd>
<dt>Laatste uitvoer</dt><dd>{esc(state.get("last_output"))}</dd>
<dt>Validatie</dt><dd>{esc(state.get("last_validation_status"))}</dd>
<dt>Laatste fout</dt><dd>{esc(state.get("last_error") or "Geen")}</dd>
<dt>Volgende run</dt><dd>{esc(state.get("next_scheduled_run") or "Uitgeschakeld")}</dd>
<dt>API-test</dt><dd>{esc(api_text)}</dd>
<dt>Integriteit</dt><dd>{esc(state.get("last_integrity_status") or "Nog niet gecontroleerd")}</dd>
<dt>Records laatste maand</dt><dd>{esc((state.get("last_summary") or {}).get("totals", {}).get("records", "Nog geen"))}</dd>
<dt>Dubbele records</dt><dd>{esc((state.get("last_summary") or {}).get("totals", {}).get("duplicates", "Nog geen"))}</dd>
<dt>Overdrachtspakket</dt><dd>{esc(state.get("last_transfer_bundle") or "Nog geen")}</dd>
<dt>Laatste HomeWizard snapshot</dt><dd>{esc(state.get("homewizard_last_snapshot") or "Nog geen")}</dd>
<dt>HomeWizard fout</dt><dd>{esc(state.get("homewizard_last_error") or "Geen")}</dd>
<dt>Laatste Enphase-import</dt><dd>{esc(state.get("enphase_last_import") or "Nog geen")}</dd>
<dt>Laatste EPEX elektriciteit</dt><dd>{esc(state.get("epex_electricity_last_import") or "Nog geen")}</dd>
<dt>Laatste EPEX gas</dt><dd>{esc(state.get("epex_gas_last_import") or "Nog geen")}</dd>
<dt>Centrale validatie</dt><dd>{esc((state.get("last_central_validation") or {}).get("status", "Nog niet uitgevoerd"))}</dd>
<dt>Rapporttrigger</dt><dd>{esc((state.get("last_report_trigger") or {}).get("status", "Nog niet uitgevoerd"))}</dd>
<dt>Rapporttrigger fout</dt><dd>{esc(state.get("last_report_trigger_error") or "Geen")}</dd>
<dt>Installatie gereed</dt><dd>{esc("Ja" if state.get("installation_ready") else "Nee")}</dd>
<dt>Zelftest</dt><dd>{esc((state.get("last_self_test") or {}).get("status", "Nog niet uitgevoerd"))}</dd>
<dt>Voortgang</dt><dd>{esc(state.get("progress_current", 0))} / {esc(state.get("progress_total", 0))} — {esc(state.get("progress_message") or "")}</dd>
</dl></div>
<div class="card"><h2>Bediening</h2>
<form method="post" action="run">
<input name="month" type="month" value="{esc(default_month)}" required>
<button type="submit">Importeer nu</button>
</form>
<form method="post" action="cancel" style="margin-top:12px">
<button type="submit">Annuleer actieve import</button>
</form>
<form method="post" action="test-api" style="margin-top:12px">
<button type="submit">Test API-verbinding</button>
</form>
<form method="post" action="verify" style="margin-top:12px">
<button type="submit">Controleer laatste maand</button>
</form>
<form method="post" action="homewizard-snapshot" style="margin-top:12px">
<button type="submit">Maak HomeWizard snapshot</button>
</form>
<form method="post" action="enphase-import" style="margin-top:12px">
<button type="submit">Importeer Enphase</button>
</form>
<form method="post" action="epex-electricity-import" style="margin-top:12px">
<button type="submit">Importeer EPEX elektriciteit</button>
</form>
<form method="post" action="epex-gas-import" style="margin-top:12px">
<button type="submit">Importeer EPEX gas</button>
</form>
<form method="post" action="central-validation" style="margin-top:12px">
<button type="submit">Voer centrale validatie uit</button>
</form>
<form method="post" action="self-test" style="margin-top:12px">
<button type="submit">Voer volledige zelftest uit</button>
</form></div>
<div class="card"><h2>Bronstatus</h2><ul>{"" .join(f"<li>{esc(k)}: {esc(v)}</li>" for k, v in (state.get("workflow_sources") or {}).items())}</ul></div>
<div class="card"><h2>Downloads</h2><ul>{downloads}</ul></div>
<div class="card"><p>API-key en planning staan op het tabblad <strong>Configuratie</strong>.</p>
<p><a href="status.json">Technische status</a> · <a href="health">Healthcheck</a></p></div>
</main></body></html>""".encode("utf-8")


ALLOWED_HTTP_CLIENTS = {"172.30.32.2", "127.0.0.1", "::1"}


class Handler(BaseHTTPRequestHandler):
    def _client_allowed(self) -> bool:
        return self.client_address[0] in ALLOWED_HTTP_CLIENTS

    def send_body(
        self,
        status: int,
        body: bytes,
        content_type: str,
        disposition: str | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if disposition:
            self.send_header("Content-Disposition", disposition)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        if not self._client_allowed():
            self.send_body(HTTPStatus.FORBIDDEN, b"Forbidden", "text/plain")
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path.endswith("/status.json") or path == "/status.json":
            body = json.dumps(load_state(), ensure_ascii=False, indent=2).encode("utf-8")
            self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
        elif path.endswith("/health") or path == "/health":
            state = load_state()
            body = json.dumps({
                "status": "ok",
                "version": APP_VERSION,
                "import_status": state.get("status"),
                "last_validation_status": state.get("last_validation_status"),
                "last_integrity_status": state.get("last_integrity_status"),
                "last_summary_totals": (state.get("last_summary") or {}).get("totals"),
                "workflow_sources": state.get("workflow_sources"),
                "last_transfer_bundle": state.get("last_transfer_bundle"),
                "homewizard_last_snapshot": state.get("homewizard_last_snapshot"),
                "homewizard_last_error": state.get("homewizard_last_error"),
                "enphase_last_import": state.get("enphase_last_import"),
                "enphase_last_error": state.get("enphase_last_error"),
                "epex_electricity_last_import": state.get("epex_electricity_last_import"),
                "epex_electricity_last_error": state.get("epex_electricity_last_error"),
                "epex_gas_last_import": state.get("epex_gas_last_import"),
                "epex_gas_last_error": state.get("epex_gas_last_error"),
                "last_central_validation": state.get("last_central_validation"),
                "last_report_trigger": state.get("last_report_trigger"),
                "last_report_trigger_error": state.get("last_report_trigger_error"),
                "last_self_test": state.get("last_self_test"),
                "installation_ready": state.get("installation_ready"),
            }).encode("utf-8")
            self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
        elif path.endswith("/download") or path == "/download":
            month = (parse_qs(parsed.query).get("month") or [""])[0]
            try:
                body = zip_month(month)
                self.send_body(
                    HTTPStatus.OK,
                    body,
                    "application/zip",
                    f'attachment; filename="SlimmeMeterPortal_{month}.zip"',
                )
            except Exception:
                self.send_body(HTTPStatus.NOT_FOUND, b"Maand niet gevonden", "text/plain")
        else:
            self.send_body(HTTPStatus.OK, html_page(), "text/html; charset=utf-8")

    def do_POST(self) -> None:
        if not self._client_allowed():
            self.send_body(HTTPStatus.FORBIDDEN, b"Forbidden", "text/plain")
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path.endswith("/cancel") or path == "/cancel":
            if RUN_LOCK.locked():
                update_state(cancel_requested=True, progress_message="Annulering aangevraagd")
                message = "Annulering aangevraagd."
            else:
                message = "Er draait geen import."
            self.send_body(
                HTTPStatus.OK,
                f"<html><meta charset='utf-8'><p>{html.escape(message)}</p><p><a href='./'>Terug</a></p></html>".encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if path.endswith("/self-test") or path == "/self-test":
            try:
                result = run_self_test()
                code = HTTPStatus.OK if result.get("status") != "error" else HTTPStatus.BAD_REQUEST
            except Exception as exc:
                result = {"status": "error", "error": str(exc)}
                code = HTTPStatus.BAD_REQUEST
            self.send_body(
                code,
                (
                    "<html><meta charset='utf-8'><p>"
                    + html.escape(json.dumps(result, ensure_ascii=False))
                    + "</p><p><a href='./'>Terug</a></p></html>"
                ).encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if path.endswith("/central-validation") or path == "/central-validation":
            try:
                options = Options.load()
                state = load_state()
                result = validate_central_workflow(
                    options,
                    state,
                    state.get("last_summary"),
                )
                update_state(last_central_validation=result)
                code = HTTPStatus.OK if result.get("status") != "error" else HTTPStatus.BAD_REQUEST
            except Exception as exc:
                result = {"status": "error", "error": str(exc)}
                code = HTTPStatus.BAD_REQUEST
            self.send_body(
                code,
                (
                    "<html><meta charset='utf-8'><p>"
                    + html.escape(json.dumps(result, ensure_ascii=False))
                    + "</p><p><a href='./'>Terug</a></p></html>"
                ).encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if path.endswith("/enphase-import") or path == "/enphase-import":
            try:
                result = run_enphase_import()
                code = HTTPStatus.OK
            except Exception as exc:
                update_state(enphase_last_error=str(exc))
                result = {"status": "error", "error": str(exc)}
                code = HTTPStatus.BAD_REQUEST
            self.send_body(
                code,
                (
                    "<html><meta charset='utf-8'><p>"
                    + html.escape(json.dumps(result, ensure_ascii=False))
                    + "</p><p><a href='./'>Terug</a></p></html>"
                ).encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if path.endswith("/epex-electricity-import") or path == "/epex-electricity-import":
            try:
                result = run_epex_import("electricity")
                code = HTTPStatus.OK
            except Exception as exc:
                update_state(epex_electricity_last_error=str(exc))
                result = {"status": "error", "error": str(exc)}
                code = HTTPStatus.BAD_REQUEST
            self.send_body(
                code,
                (
                    "<html><meta charset='utf-8'><p>"
                    + html.escape(json.dumps(result, ensure_ascii=False))
                    + "</p><p><a href='./'>Terug</a></p></html>"
                ).encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if path.endswith("/epex-gas-import") or path == "/epex-gas-import":
            try:
                result = run_epex_import("gas")
                code = HTTPStatus.OK
            except Exception as exc:
                update_state(epex_gas_last_error=str(exc))
                result = {"status": "error", "error": str(exc)}
                code = HTTPStatus.BAD_REQUEST
            self.send_body(
                code,
                (
                    "<html><meta charset='utf-8'><p>"
                    + html.escape(json.dumps(result, ensure_ascii=False))
                    + "</p><p><a href='./'>Terug</a></p></html>"
                ).encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if path.endswith("/homewizard-snapshot") or path == "/homewizard-snapshot":
            try:
                result = run_homewizard_snapshot()
                code = HTTPStatus.OK if result.get("status") != "error" else HTTPStatus.BAD_REQUEST
            except Exception as exc:
                result = {"status": "error", "error": str(exc)}
                code = HTTPStatus.BAD_REQUEST
            self.send_body(
                code,
                (
                    "<html><meta charset='utf-8'><p>"
                    + html.escape(json.dumps(result, ensure_ascii=False))
                    + "</p><p><a href='./'>Terug</a></p></html>"
                ).encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if path.endswith("/verify") or path == "/verify":
            target = latest_month_dir()
            if target is None:
                result = {"status": "error", "error": "Nog geen maanduitvoer aanwezig."}
                code = HTTPStatus.BAD_REQUEST
            else:
                result = verify_latest_with_legacy_repair(target)
                update_state(
                    last_integrity_status=result.get("status"),
                    last_integrity_checked_at=result.get("checked_at"),
                )
                code = HTTPStatus.OK if result.get("status") == "ok" else HTTPStatus.BAD_REQUEST
            self.send_body(
                code,
                (
                    "<html><meta charset='utf-8'><p>"
                    + html.escape(json.dumps(result, ensure_ascii=False))
                    + "</p><p><a href='./'>Terug</a></p></html>"
                ).encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if path.endswith("/test-api") or path == "/test-api":
            result = test_api()
            code = HTTPStatus.OK if result.get("status") == "ok" else HTTPStatus.BAD_REQUEST
            self.send_body(
                code,
                (
                    "<html><meta charset='utf-8'><p>"
                    + html.escape(json.dumps(result, ensure_ascii=False))
                    + "</p><p><a href='./'>Terug</a></p></html>"
                ).encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if not (path.endswith("/run") or path == "/run"):
            self.send_body(HTTPStatus.NOT_FOUND, b"Not found", "text/plain")
            return

        length = int(self.headers.get("Content-Length", "0"))
        form = parse_qs(self.rfile.read(length).decode("utf-8"))
        try:
            options = Options.load()
            year, month = resolve_month((form.get("month") or [""])[0], options)
            if RUN_LOCK.locked():
                raise RuntimeError("Er draait al een import.")
            threading.Thread(target=run_import, args=(year, month), daemon=True).start()
            self.send_body(
                HTTPStatus.ACCEPTED,
                b"<html><meta charset='utf-8'><p>Import gestart.</p><p><a href='./'>Terug</a></p></html>",
                "text/html; charset=utf-8",
            )
        except Exception as exc:
            self.send_body(
                HTTPStatus.BAD_REQUEST,
                f"Import kon niet starten: {html.escape(str(exc))}".encode("utf-8"),
                "text/plain; charset=utf-8",
            )

    def log_message(self, format: str, *args: Any) -> None:
        LOGGER.info("Web: " + format, *args)


def stop_handler(signum: int, frame: object) -> None:
    del signum, frame
    STOP.set()


def main() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s", force=True)
    LOGGER.info("Python-app v%s initialiseert.", APP_VERSION)
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    update_state(version=APP_VERSION)
    threading.Thread(target=scheduler, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", 8099), Handler)
    LOGGER.info("SlimmeMeterPortal Import v%s gestart.", APP_VERSION)
    try:
        server.serve_forever()
    finally:
        STOP.set()
        server.server_close()


if __name__ == "__main__":
    main()
