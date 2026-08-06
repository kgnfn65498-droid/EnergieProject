#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import io
import json
import logging
import os
import random
import hashlib
import re
import shutil
import subprocess
import sys
import signal
import threading
import time
import urllib.error
import urllib.request
import socket
import zipfile
from calendar import monthrange
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo
import ipaddress

BASE_URL = "https://app.slimmemeterportal.nl"
OPTIONS_PATH = Path("/data/options.json")
OUTPUT_ROOT = Path("/config/output")
STATE_PATH = Path("/config/state.json")
TZ = ZoneInfo("Europe/Amsterdam")
APP_VERSION = "7.0.0"
BUNDLED_REPORT_GENERATORS = Path("/app/report_generators")

CONFIG_ROOT = Path("/data")


LOGGER = logging.getLogger("slimmemeterportal_import")
STOP = threading.Event()
RUN_LOCK = threading.Lock()
WORKFLOW_LOCK = threading.Lock()
WORKFLOW_LOCK_META = threading.Lock()
WORKFLOW_ACTIVE: dict[str, Any] = {}
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
    homewizard_discovery_enabled: bool
    homewizard_discovery_cidr: str
    homewizard_discovery_timeout_seconds: int
    homewizard_devices: list[dict[str, Any]]
    homewizard_sample_seconds: int
    homeassistant_energy_sampling_enabled: bool
    homeassistant_energy_sample_seconds: int
    enphase_entity_id: str
    nordpool_entity_id: str
    nextenergy_entity_id: str
    month_input_enabled: bool
    month_input_require_homewizard: bool
    month_input_require_enphase: bool
    month_input_require_nordpool: bool
    enphase_enabled: bool
    enphase_source_url: str
    enphase_bearer_token: str
    epex_electricity_enabled: bool
    epex_electricity_output_name: str
    epex_electricity_url: str
    epex_gas_enabled: bool
    epex_gas_output_name: str
    epex_gas_url: str
    report_trigger_enabled: bool
    report_trigger_url: str
    report_trigger_token: str
    report_service_enabled: bool
    report_service_root: str
    report_service_timeout_seconds: int
    report_service_retention_months: int
    workflow_import_wait_seconds: int
    require_all_core_sources: bool
    epex_require_full_calendar_month: bool
    transfer_enabled: bool
    transfer_share_folder: str
    transfer_overwrite_existing: bool
    transfer_require_valid_month: bool
    transfer_notify_home_assistant: bool
    full_workflow_enabled: bool
    full_workflow_use_previous_month: bool
    full_workflow_stop_on_error: bool
    full_workflow_run_epex_when_enabled: bool
    automatic_month_close_enabled: bool
    automatic_month_close_day: int
    automatic_month_close_hour: int
    operation_history_months: int

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
            homewizard_discovery_enabled=bool(raw.get("homewizard_discovery_enabled", True)),
            homewizard_discovery_cidr=str(raw.get("homewizard_discovery_cidr", "")).strip(),
            homewizard_discovery_timeout_seconds=int(raw.get("homewizard_discovery_timeout_seconds", 1)),
            homewizard_devices=list(raw.get("homewizard_devices", [])),
            homewizard_sample_seconds=int(raw.get("homewizard_sample_seconds", 900)),
            homeassistant_energy_sampling_enabled=bool(raw.get("homeassistant_energy_sampling_enabled", True)),
            homeassistant_energy_sample_seconds=int(raw.get("homeassistant_energy_sample_seconds", 900)),
            enphase_entity_id=str(raw.get("enphase_entity_id", "sensor.envoy_122335051406_lifetime_energy_production")).strip(),
            nordpool_entity_id=str(raw.get("nordpool_entity_id", "sensor.nordpool_kwh_nl_eur_3_10_021")).strip(),
            nextenergy_entity_id=str(raw.get("nextenergy_entity_id", "sensor.nextenergy_actuele_stroomprijs")).strip(),
            month_input_enabled=bool(raw.get("month_input_enabled", True)),
            month_input_require_homewizard=bool(raw.get("month_input_require_homewizard", True)),
            month_input_require_enphase=bool(raw.get("month_input_require_enphase", True)),
            month_input_require_nordpool=bool(raw.get("month_input_require_nordpool", True)),
            enphase_enabled=bool(raw.get("enphase_enabled", False)),
            enphase_source_url=str(raw.get("enphase_source_url", "")).strip(),
            enphase_bearer_token=str(raw.get("enphase_bearer_token", "")).strip(),
            epex_electricity_enabled=bool(raw.get("epex_electricity_enabled", False)),
            epex_electricity_output_name=str(raw.get("epex_electricity_output_name", "EPEX stroom.csv")).strip(),
            epex_electricity_url=str(raw.get("epex_electricity_url", "")).strip(),
            epex_gas_enabled=bool(raw.get("epex_gas_enabled", False)),
            epex_gas_output_name=str(raw.get("epex_gas_output_name", "EPEX gas.csv")).strip(),
            epex_gas_url=str(raw.get("epex_gas_url", "")).strip(),
            report_trigger_enabled=bool(raw.get("report_trigger_enabled", False)),
            report_trigger_url=str(raw.get("report_trigger_url", "")).strip(),
            report_trigger_token=str(raw.get("report_trigger_token", "")).strip(),
            report_service_enabled=bool(raw.get("report_service_enabled", True)),
            report_service_root=str(raw.get("report_service_root", "Energie_Rapportservice")).strip(),
            report_service_timeout_seconds=int(raw.get("report_service_timeout_seconds", 900)),
            report_service_retention_months=int(raw.get("report_service_retention_months", 3)),
            workflow_import_wait_seconds=int(raw.get("workflow_import_wait_seconds", 120)),
            require_all_core_sources=bool(raw.get("require_all_core_sources", True)),
            epex_require_full_calendar_month=bool(raw.get("epex_require_full_calendar_month", True)),
            transfer_enabled=bool(raw.get("transfer_enabled", True)),
            transfer_share_folder=str(raw.get("transfer_share_folder", "Energie_Overdracht")).strip(),
            transfer_overwrite_existing=bool(raw.get("transfer_overwrite_existing", False)),
            transfer_require_valid_month=bool(raw.get("transfer_require_valid_month", True)),
            transfer_notify_home_assistant=bool(raw.get("transfer_notify_home_assistant", True)),
            full_workflow_enabled=bool(raw.get("full_workflow_enabled", True)),
            full_workflow_use_previous_month=bool(raw.get("full_workflow_use_previous_month", True)),
            full_workflow_stop_on_error=bool(raw.get("full_workflow_stop_on_error", True)),
            full_workflow_run_epex_when_enabled=bool(raw.get("full_workflow_run_epex_when_enabled", True)),
            automatic_month_close_enabled=bool(raw.get("automatic_month_close_enabled", False)),
            automatic_month_close_day=int(raw.get("automatic_month_close_day", 2)),
            automatic_month_close_hour=int(raw.get("automatic_month_close_hour", 4)),
            operation_history_months=int(raw.get("operation_history_months", 12)),
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
        if not 1 <= self.automatic_month_close_day <= 28:
            raise ValueError("automatic_month_close_day moet 1 t/m 28 zijn.")
        if not 0 <= self.automatic_month_close_hour <= 23:
            raise ValueError("automatic_month_close_hour moet 0 t/m 23 zijn.")
        if not 1 <= self.operation_history_months <= 60:
            raise ValueError("operation_history_months moet 1 t/m 60 zijn.")
        if self.workflow_mode not in {"smp_only", "full_month_workflow"}:
            raise ValueError("workflow_mode is ongeldig.")
        if not 1 <= self.homewizard_discovery_timeout_seconds <= 5:
            raise ValueError("homewizard_discovery_timeout_seconds moet 1 t/m 5 zijn.")
        if self.homewizard_discovery_cidr:
            try:
                network = ipaddress.ip_network(self.homewizard_discovery_cidr, strict=False)
            except ValueError as exc:
                raise ValueError("homewizard_discovery_cidr is geen geldig CIDR-netwerk.") from exc
            if network.version != 4 or network.prefixlen < 24:
                raise ValueError("HomeWizard-detectie is beperkt tot één IPv4 /24-netwerk of kleiner.")
        if not 60 <= self.homewizard_sample_seconds <= 3600:
            raise ValueError("homewizard_sample_seconds moet 60 t/m 3600 zijn.")
        if not self.transfer_share_folder:
            raise ValueError("transfer_share_folder mag niet leeg zijn.")
        transfer_folder = Path(self.transfer_share_folder)
        if transfer_folder.is_absolute() or ".." in transfer_folder.parts:
            raise ValueError("transfer_share_folder moet een veilige relatieve mapnaam zijn.")
        if not 60 <= self.homeassistant_energy_sample_seconds <= 3600:
            raise ValueError("homeassistant_energy_sample_seconds moet 60 t/m 3600 zijn.")
        if self.enphase_enabled and not self.enphase_source_url:
            raise ValueError("Enphase is ingeschakeld maar enphase_source_url ontbreekt.")
        if self.epex_electricity_enabled and not self.epex_electricity_url:
            raise ValueError("EPEX elektriciteit is ingeschakeld maar URL ontbreekt.")
        if self.epex_gas_enabled and not self.epex_gas_url:
            raise ValueError("EPEX gas is ingeschakeld maar URL ontbreekt.")
        if self.report_trigger_enabled and not self.report_trigger_url:
            raise ValueError("Rapporttrigger is ingeschakeld maar URL ontbreekt.")
        if not self.report_service_root:
            raise ValueError("report_service_root mag niet leeg zijn.")
        report_service_path = Path(self.report_service_root)
        if report_service_path.is_absolute() or ".." in report_service_path.parts:
            raise ValueError("report_service_root moet een veilige relatieve mapnaam zijn.")
        if not 60 <= self.report_service_timeout_seconds <= 3600:
            raise ValueError("report_service_timeout_seconds moet 60 t/m 3600 zijn.")
        if not 1 <= self.report_service_retention_months <= 24:
            raise ValueError("report_service_retention_months moet 1 t/m 24 zijn.")
        if not 0 <= self.workflow_import_wait_seconds <= 900:
            raise ValueError("workflow_import_wait_seconds moet 0 t/m 900 zijn.")
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
        "homewizard_last_csv_files": [],
        "homewizard_last_device_count": 0,
        "homewizard_discovery_last": None,
        "homewizard_discovery_cidr": None,
        "homewizard_discovery_count": 0,
        "homewizard_discovery_devices": [],
        "homewizard_discovery_error": None,
        "homewizard_discovery_status": "idle",
        "homewizard_mapping_last": None,
        "homewizard_mapping_count": 0,
        "homewizard_mapping_error": None,
        "homeassistant_energy_last_snapshot": None,
        "homeassistant_energy_last_error": None,
        "homeassistant_energy_last_files": [],
        "month_input_last_built": None,
        "month_input_last_month": None,
        "month_input_last_status": None,
        "month_input_last_error": None,
        "month_input_last_files": [],
        "homewizard_last_error": None,
        "enphase_last_import": None,
        "enphase_last_error": None,
        "epex_electricity_last_import": None,
        "epex_electricity_last_error": None,
        "epex_gas_last_import": None,
        "epex_gas_last_error": None,
        "epex_last_validation": None,
        "epex_last_validation_status": "not_configured",
        "transfer_last_created": None,
        "transfer_last_month": None,
        "transfer_last_status": None,
        "transfer_last_path": None,
        "transfer_last_error": None,
        "full_workflow_last_run": None,
        "full_workflow_last_month": None,
        "full_workflow_last_status": None,
        "full_workflow_last_step": None,
        "full_workflow_last_result": None,
        "full_workflow_last_error": None,
        "last_central_validation": None,
        "last_report_trigger": None,
        "last_report_trigger_error": None,
        "report_handoff_last_created": None,
        "report_handoff_last_month": None,
        "report_handoff_last_status": None,
        "report_handoff_last_path": None,
        "report_handoff_last_error": None,
        "report_generation_last_started": None,
        "report_generation_last_finished": None,
        "report_generation_last_month": None,
        "report_generation_last_status": None,
        "report_generation_last_response": None,
        "report_generation_last_error": None,
        "report_service_last_checked": None,
        "report_service_last_status": None,
        "report_service_generators": {},
        "report_service_last_output": None,
        "report_service_last_error": None,
        "report_runtime_last_checked": None,
        "report_runtime_last_status": None,
        "report_runtime_modules": {},
        "report_runtime_last_error": None,
        "report_page1_last_started": None,
        "report_page1_last_finished": None,
        "report_page1_last_status": None,
        "report_page1_last_output": None,
        "report_page1_last_log": None,
        "report_page1_last_error": None,
        "report_generators_install_last": None,
        "report_generators_install_status": None,
        "report_generators_install_files": [],
        "report_generators_install_error": None,
        "report_adapter_last_created": None,
        "report_adapter_last_month": None,
        "report_adapter_last_status": None,
        "report_adapter_last_files": [],
        "report_adapter_last_error": None,
        "report_merge_last_status": None,
        "report_merge_last_output": None,
        "report_merge_last_error": None,
        "report_output_last_created": None,
        "report_output_last_month": None,
        "report_output_last_status": None,
        "report_output_last_folder": None,
        "report_output_last_files": [],
        "report_output_last_error": None,
        "workflow_audit_last_checked": None,
        "workflow_audit_last_month": None,
        "workflow_audit_last_status": None,
        "workflow_audit_last_result": None,
        "workflow_audit_last_error": None,
        "report_retention_last_run": None,
        "report_retention_last_status": None,
        "report_retention_removed": [],
        "report_retention_last_error": None,
        "workflow_summary_last": None,
        "workflow_lock_status": "idle",
        "workflow_lock_started_at": None,
        "workflow_lock_month": None,
        "workflow_lock_step": None,
        "workflow_lock_message": None,
        "workflow_lock_last_released": None,
        "workflow_lock_last_duration_seconds": None,
        "workflow_lock_rejected_count": 0,
        "workflow_import_coordination_last": None,
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


VALIDATION_PROFILES: dict[str, dict[str, Any]] = {
    "slimmemeterportal": {
        "elektriciteit": {"mode": "daily", "expected_records_per_day": {1}},
        "electricity": {"mode": "daily", "expected_records_per_day": {1}},
        "gas": {"mode": "daily", "expected_records_per_day": {1}},
    },
    "homewizard": {
        "elektriciteit": {"mode": "quarter_hour", "expected_records_per_day": {96, 92, 100}},
        "electricity": {"mode": "quarter_hour", "expected_records_per_day": {96, 92, 100}},
        "gas": {"mode": "hourly", "expected_records_per_day": {24, 23, 25}},
    },
    "nordpool": {
        "elektriciteit": {"mode": "hourly", "expected_records_per_day": {24, 23, 25}},
        "electricity": {"mode": "hourly", "expected_records_per_day": {24, 23, 25}},
    },
}


def validation_profile(source: str, kind: str) -> dict[str, Any]:
    source_profiles = VALIDATION_PROFILES.get(source.lower(), {})
    return source_profiles.get(kind.lower(), {"mode": "unknown", "expected_records_per_day": set()})


def expected_count(kind: str, day: date, source: str = "slimmemeterportal") -> set[int]:
    profile = validation_profile(source, kind)
    expected = profile.get("expected_records_per_day", set())
    return set(expected)


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
"info_count": sum(
    1
    for connection in connection_summaries
    for day in connection.get("days", [])
    if day.get("status") == "info"
),
        },
    }









def persist_normalized_status(options: Options) -> dict[str, Any]:
    current = load_state()
    normalized = normalize_technical_status(current, options)
    changes = {
        key: value
        for key, value in normalized.items()
        if current.get(key) != value
    }
    if changes:
        update_state(**changes)
        current = {**current, **changes}
    return current


def normalize_technical_status(state: dict[str, Any], options: Options) -> dict[str, Any]:
    normalized = dict(state)

    if not options.epex_electricity_enabled and not options.epex_gas_enabled:
        normalized["epex_last_validation_status"] = "not_configured"
        normalized["epex_electricity_last_error"] = None
        normalized["epex_gas_last_error"] = None

    month_status = normalized.get("month_input_last_status")
    if month_status == "completed_info":
        validation_path = (
            MONTH_INPUT_ROOT
            / str(normalized.get("month_input_last_month") or "")
            / "month_input_validation.json"
        )
        try:
            validation = json.loads(validation_path.read_text(encoding="utf-8"))
            infos = list(validation.get("infos") or [])
            disabled_epex_info = all(
                ("EPEX stroom.csv" in message or "EPEX gas.csv" in message)
                for message in infos
            )
            if not infos or disabled_epex_info:
                normalized["month_input_last_status"] = "completed"
        except Exception:
            pass

    return normalized



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

        runtime = check_report_runtime()
        add(
            "report_runtime",
            "ok" if runtime.get("status") == "ok" else "error",
            json.dumps(runtime, ensure_ascii=False),
        )

        if options.report_trigger_enabled:
            add("report_trigger_config", "ok", options.report_trigger_url)
        else:
            add("report_trigger_config", "ok", "Bewust uitgeschakeld.")

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

    for source, enabled in requirements.items():
        if not enabled:
            continue
        status = source_status.get(source, "not_configured")
        if status != "ready":
            errors.append(f"Geactiveerde bron niet gereed: {source} ({status}).")

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



REPORT_GENERATORS = {
    "page_1": "Energierapport_Pagina1_Echte_Generator_v7",
    "page_2": "Energierapport_Pagina2_Generator_v6.0",
    "pages_3_13": "Energierapport_Pagina3_tm_13_Generator_v1.0",
}


def create_report_handoff(
    year: int,
    month: int,
    month_input_path: str,
    transfer_path: str,
    transfer_zip: str | None,
    central_validation: dict[str, Any],
) -> dict[str, Any]:
    month_key = f"{year:04d}_{month:02d}"
    destination = Path(transfer_path)
    destination.mkdir(parents=True, exist_ok=True)

    request = {
        "version": APP_VERSION,
        "schema": "energie_report_handoff_v1",
        "created_at": datetime.now(TZ).isoformat(),
        "status": "ready",
        "month": month_key,
        "calendar_month": f"{year:04d}-{month:02d}",
        "input_folder": month_input_path,
        "transfer_folder": transfer_path,
        "transfer_zip": transfer_zip,
        "central_validation_status": central_validation.get("status"),
        "central_validation": central_validation,
        "required_generators": REPORT_GENERATORS,
        "output_contract": {
            "folder": f"02_Output/{month_key}",
            "report_pdf": f"Energierapport_{month_key}.pdf",
            "recovery_update_zip": f"Recovery_Update_{month_key}.zip",
        },
        "instructions": [
            "Gebruik uitsluitend de officiële rapportgeneratoren.",
            "Verwerk uitsluitend records uit de doelmaand.",
            "Voer vóór rapportgeneratie de verplichte KPI- en prognosevalidatie uit.",
            "Maak één definitief PDF-rapport en één Recovery_Update ZIP.",
        ],
    }

    request_path = destination / "report_request.json"
    write_atomic_json(request_path, request)
    checksum = sha256_file(request_path)

    manifest = {
        "version": APP_VERSION,
        "created_at": datetime.now(TZ).isoformat(),
        "status": "ready",
        "month": month_key,
        "request": str(request_path),
        "sha256": checksum,
    }
    manifest_path = destination / "report_request_manifest.json"
    write_atomic_json(manifest_path, manifest)

    update_state(
        report_handoff_last_created=manifest["created_at"],
        report_handoff_last_month=month_key,
        report_handoff_last_status="ready",
        report_handoff_last_path=str(request_path),
        report_handoff_last_error=None,
    )
    return {
        **manifest,
        "manifest": str(manifest_path),
        "request_payload": request,
    }




def load_report_handoff(path: str | Path) -> dict[str, Any]:
    handoff_path = Path(path)
    if not handoff_path.exists():
        raise RuntimeError(f"Rapportaanvraag ontbreekt: {handoff_path}")
    try:
        payload = json.loads(handoff_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError(f"Rapportaanvraag is ongeldig: {exc}") from exc

    required = {
        "schema",
        "status",
        "month",
        "input_folder",
        "transfer_folder",
        "required_generators",
        "output_contract",
    }
    missing = sorted(required - set(payload))
    if missing:
        raise RuntimeError(
            "Rapportaanvraag mist verplichte velden: " + ", ".join(missing)
        )
    if payload.get("schema") != "energie_report_handoff_v1":
        raise RuntimeError("Rapportaanvraag heeft een onbekend schema.")
    if payload.get("status") != "ready":
        raise RuntimeError("Rapportaanvraag is niet gereed.")
    return payload


def validate_report_handoff_files(handoff: dict[str, Any]) -> dict[str, Any]:
    input_folder = Path(str(handoff["input_folder"]))
    transfer_folder = Path(str(handoff["transfer_folder"]))
    errors: list[str] = []

    if not input_folder.exists() or not input_folder.is_dir():
        errors.append(f"Inputmap ontbreekt: {input_folder}")
    if not transfer_folder.exists() or not transfer_folder.is_dir():
        errors.append(f"Overdrachtsmap ontbreekt: {transfer_folder}")
    if (handoff.get("required_generators") or {}) != REPORT_GENERATORS:
        errors.append("Officiële generatorconfiguratie wijkt af.")

    output_contract = handoff.get("output_contract") or {}
    for key in ("folder", "report_pdf", "recovery_update_zip"):
        if not str(output_contract.get(key, "")).strip():
            errors.append(f"Outputcontract mist {key}.")

    return {
        "status": "ok" if not errors else "error",
        "checked_at": datetime.now(TZ).isoformat(),
        "errors": errors,
        "input_folder": str(input_folder),
        "transfer_folder": str(transfer_folder),
    }




GENERATOR_BUNDLE_FOLDERS = {
    "page_1": "Energierapport_Pagina1_Echte_Generator_v7",
    "page_2": "Energierapport_Pagina2_Generator_v6_0",
    "pages_3_13": "Energierapport_Pagina3_tm_13_Generator_v1_0",
}



def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def numeric_values(rows: list[dict[str, str]], candidates: tuple[str, ...]) -> list[float]:
    values: list[float] = []
    for row in rows:
        lower = {str(k).strip().lower(): v for k, v in row.items()}
        for candidate in candidates:
            raw = lower.get(candidate.lower())
            if raw in (None, ""):
                continue
            try:
                values.append(float(str(raw).replace(",", ".")))
                break
            except ValueError:
                continue
    return values


def cumulative_delta(rows: list[dict[str, str]], candidates: tuple[str, ...]) -> float:
    values = numeric_values(rows, candidates)
    if len(values) >= 2:
        return max(0.0, values[-1] - values[0])
    if len(values) == 1:
        return max(0.0, values[0])
    return 0.0


def load_generator_example(role: str) -> dict[str, Any]:
    folder = BUNDLED_REPORT_GENERATORS / GENERATOR_BUNDLE_FOLDERS[role]
    if role == "page_1":
        path = folder / "maanddata_voorbeeld.json"
    elif role == "page_2":
        path = folder / "data/juli_2026.json"
    else:
        path = folder / "data/juli_2026.json"
    return json.loads(path.read_text(encoding="utf-8"))


def build_report_adapter_data(
    options: Options,
    handoff: dict[str, Any],
) -> dict[str, Any]:
    month_key = str(handoff["month"])
    year, month = int(month_key[:4]), int(month_key[5:7])
    input_folder = Path(str(handoff["input_folder"]))
    service_paths = report_service_paths(options)
    data_folder = service_paths["generators"] / "data" / month_key
    data_folder.mkdir(parents=True, exist_ok=True)

    p1e_rows = read_csv_rows(input_folder / "P1e.csv")
    p1g_rows = read_csv_rows(input_folder / "P1g.csv")
    enphase_rows = read_csv_rows(input_folder / "Enphase.csv")

    import_kwh = cumulative_delta(
        p1e_rows,
        (
            "total_power_import_kwh",
            "energy_import_kwh",
            "import_kwh",
            "meter_reading_import_kwh",
        ),
    )
    export_kwh = cumulative_delta(
        p1e_rows,
        (
            "total_power_export_kwh",
            "energy_export_kwh",
            "export_kwh",
            "meter_reading_export_kwh",
        ),
    )
    gas_m3 = cumulative_delta(
        p1g_rows,
        ("total_gas_m3", "gas_m3", "meter_reading_gas_m3"),
    )
    production_kwh = cumulative_delta(
        enphase_rows,
        (
            "energy_kwh",
            "lifetime_energy_kwh",
            "production_kwh",
            "value_kwh",
            "value",
        ),
    )

    if production_kwh <= 0:
        production_kwh = export_kwh
    direct_solar = max(0.0, production_kwh - export_kwh)
    house_use = max(0.0, import_kwh + direct_solar)
    net_kwh = import_kwh - export_kwh
    self_use_pct = (direct_solar / production_kwh * 100.0) if production_kwh else 0.0
    self_supply_pct = (direct_solar / house_use * 100.0) if house_use else 0.0
    days = monthrange(year, month)[1]
    month_name = datetime(year, month, 1, tzinfo=TZ).strftime("%B %Y")
    month_upper = month_name.upper()

    page1 = load_generator_example("page_1")
    page1["rapport"].update({
        "periode": f"1 t/m {days} {month_name}",
        "rapportdatum": datetime.now(TZ).strftime("%d-%m-%Y"),
        "maand": month_upper,
        "pagina": 1,
        "paginas": 13,
    })
    page1["samenvatting"] = [
        {"kleur": "groen", "tekst": f"Gemeten netverbruik bedraagt {import_kwh:.1f} kWh."},
        {"kleur": "groen", "tekst": f"Gemeten teruglevering bedraagt {export_kwh:.1f} kWh."},
        {"kleur": "groen", "tekst": f"Gemeten gasverbruik bedraagt {gas_m3:.1f} m³."},
        {"kleur": "oranje", "tekst": "Financiële prognoses blijven voorlopig totdat contractkostendata volledig is gekoppeld."},
    ]
    top = page1["kpi_boven"]
    measured = [
        ("Verbruik", import_kwh, "kWh"),
        ("Teruglevering", export_kwh, "kWh"),
        ("Netto balans", net_kwh, "kWh"),
        ("Gasverbruik", gas_m3, "m³"),
        ("Eigen verbruik", self_use_pct, "%"),
    ]
    for item, (title, value, unit) in zip(top, measured):
        item["titel"] = title
        item["waarde"] = f"{value:.1f}".replace(".", ",")
        item["eenheid"] = unit
        item["delta"] = "-"
    page1["maand"]["verbruik"]["waarde"] = round(import_kwh, 3)
    page1["maand"]["teruglevering"]["waarde"] = round(export_kwh, 3)
    page1["maand"]["gas"]["waarde"] = round(gas_m3, 3)
    page1["maand"]["netto_maanden"] = [0.0] * 12
    page1["maand"]["netto_maanden"][month - 1] = round(net_kwh, 3)
    page1["efficientie"].update({
        "zelfvoorziening": round(self_supply_pct, 1),
        "eigen_verbruik": round(self_use_pct, 1),
        "gas": round(gas_m3, 1),
        "delta_zelf": 0.0,
        "delta_eigen": 0.0,
        "delta_gas": 0.0,
    })

    page2 = load_generator_example("page_2")
    page2["meta"]["month"] = month_name
    page2["electricity"].update({
        "consumption": round(import_kwh, 1),
        "feed_in": round(export_kwh, 1),
        "net_feed_in": round(export_kwh - import_kwh, 1),
    })
    page2["gas"].update({
        "month": round(gas_m3, 1),
        "per_day": round(gas_m3 / days, 2) if days else 0.0,
    })
    page2["forecast"].update({
        "electricity_total": round(import_kwh * 12, 1),
        "feed_in_total": round(export_kwh * 12, 1),
        "net": round(net_kwh * 12, 1),
        "gas_total": round(gas_m3 * 12, 1),
    })

    pages = load_generator_example("pages_3_13")
    pages["meta"].update({
        "month": month_name,
        "period": f"1 t/m {days} {month_name}",
        "days": days,
        "status": "ECHTE MAANDDATA - voorlopige financiële modellering",
    })
    pages["dashboard"].update({
        "house": round(house_use, 1),
        "solar": round(production_kwh, 1),
        "self": round(self_use_pct, 1),
        "export": round(export_kwh, 1),
        "quality": "Bronvalidatie geslaagd",
    })
    pages["electricity"].update({
        "grid": round(import_kwh, 1),
        "feedin": round(export_kwh, 1),
        "net": round(net_kwh, 1),
        "grid_day": round(import_kwh / days, 2),
        "feedin_day": round(export_kwh / days, 2),
        "house": round(house_use, 1),
    })
    pages["solar"].update({
        "production": round(production_kwh, 1),
        "direct": round(direct_solar, 1),
        "feedin": round(export_kwh, 1),
        "self": round(self_use_pct, 1),
        "coverage": round(self_supply_pct, 1),
    })
    pages["gas"].update({
        "month": round(gas_m3, 1),
        "per_day": round(gas_m3 / days, 2),
    })

    outputs = {
        "page_1": data_folder / "page_1.json",
        "page_2": data_folder / "page_2.json",
        "pages_3_13": data_folder / "pages_3_13.json",
    }
    payloads = {"page_1": page1, "page_2": page2, "pages_3_13": pages}
    for role, path in outputs.items():
        write_atomic_json(path, payloads[role])

    result = {
        "version": APP_VERSION,
        "created_at": datetime.now(TZ).isoformat(),
        "status": "completed",
        "month": month_key,
        "input_folder": str(input_folder),
        "measurements": {
            "import_kwh": round(import_kwh, 3),
            "export_kwh": round(export_kwh, 3),
            "gas_m3": round(gas_m3, 3),
            "production_kwh": round(production_kwh, 3),
            "direct_solar_kwh": round(direct_solar, 3),
            "house_use_kwh": round(house_use, 3),
            "self_use_pct": round(self_use_pct, 3),
            "self_supply_pct": round(self_supply_pct, 3),
        },
        "files": [str(path) for path in outputs.values()],
    }
    write_atomic_json(data_folder / "adapter_result.json", result)
    update_state(
        report_adapter_last_created=result["created_at"],
        report_adapter_last_month=month_key,
        report_adapter_last_status="completed",
        report_adapter_last_files=result["files"],
        report_adapter_last_error=None,
    )
    return result


def merge_report_pdfs(
    handoff: dict[str, Any],
    work_folder: Path,
) -> dict[str, Any]:
    try:
        from pypdf import PdfReader, PdfWriter
    except ImportError as exc:
        raise RuntimeError("pypdf ontbreekt in de runtime.") from exc

    month_key = str(handoff["month"])
    sources = [
        work_folder / f"Energierapport_Pagina1_{month_key}.pdf",
        work_folder / f"Energierapport_Pagina2_{month_key}.pdf",
        work_folder / f"Energierapport_Pagina3_tm_13_{month_key}.pdf",
    ]
    missing = [str(path) for path in sources if not path.is_file() or path.stat().st_size == 0]
    if missing:
        raise RuntimeError("Rapportdelen ontbreken: " + ", ".join(missing))

    final_name = str((handoff.get("output_contract") or {}).get("report_pdf"))
    final_path = work_folder / final_name
    writer = PdfWriter()
    page_count = 0
    for source in sources:
        reader = PdfReader(str(source))
        for page in reader.pages:
            writer.add_page(page)
            page_count += 1
    with final_path.open("wb") as handle:
        writer.write(handle)

    result = {
        "status": "completed",
        "merged_at": datetime.now(TZ).isoformat(),
        "output": str(final_path),
        "sources": [str(path) for path in sources],
        "pages": page_count,
        "sha256": sha256_file(final_path),
    }
    write_atomic_json(work_folder / "merge_result.json", result)
    update_state(
        report_merge_last_status="completed",
        report_merge_last_output=str(final_path),
        report_merge_last_error=None,
    )
    return result


def create_recovery_update(
    options: Options,
    handoff: dict[str, Any],
    work_folder: Path,
) -> dict[str, Any]:
    month_key = str(handoff["month"])
    contract = handoff.get("output_contract") or {}
    recovery_path = work_folder / str(contract.get("recovery_update_zip"))
    paths = report_service_paths(options)
    manifest = {
        "version": APP_VERSION,
        "created_at": datetime.now(TZ).isoformat(),
        "status": "completed",
        "month": month_key,
        "scope": ["03_Systeem/", "04_Scripts/"],
    }

    with zipfile.ZipFile(recovery_path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "03_Systeem/Rapportservice/Recovery_Update_manifest.json",
            json.dumps(manifest, indent=2, ensure_ascii=False),
        )
        service_contract = paths["root"] / "service_contract.json"
        if service_contract.is_file():
            archive.write(service_contract, "03_Systeem/Rapportservice/service_contract.json")

        request_path = Path(str(handoff.get("_request_path", "")))
        if request_path.is_file():
            archive.write(request_path, "03_Systeem/Rapportservice/report_request.json")
            request_manifest = request_path.with_name("report_request_manifest.json")
            if request_manifest.is_file():
                archive.write(
                    request_manifest,
                    "03_Systeem/Rapportservice/report_request_manifest.json",
                )

        for name in ("adapter_result.json", "merge_result.json"):
            source = work_folder / name
            if source.is_file():
                archive.write(source, f"03_Systeem/Rapportservice/{name}")

        generators_root = paths["generators"]
        for wrapper in sorted(generators_root.glob("*.py")):
            archive.write(
                wrapper,
                f"04_Scripts/Rapportgeneratoren/wrappers/{wrapper.name}",
            )

        packages_root = generators_root / "packages"
        if packages_root.is_dir():
            for source in sorted(packages_root.rglob("*")):
                if source.is_file():
                    relative = source.relative_to(packages_root)
                    archive.write(
                        source,
                        f"04_Scripts/Rapportgeneratoren/packages/{relative}",
                    )

    result = {
        "status": "completed",
        "created_at": manifest["created_at"],
        "month": month_key,
        "path": str(recovery_path),
        "sha256": sha256_file(recovery_path),
        "size_bytes": recovery_path.stat().st_size,
    }
    write_atomic_json(work_folder / "recovery_update_result.json", result)
    return result


def publish_month_output(
    handoff: dict[str, Any],
    work_folder: Path,
) -> dict[str, Any]:
    month_key = str(handoff["month"])
    transfer_folder = Path(str(handoff["transfer_folder"]))
    output_folder = transfer_folder.parent / "02_Output" / month_key
    output_folder.mkdir(parents=True, exist_ok=True)

    contract = handoff.get("output_contract") or {}
    expected = [
        work_folder / str(contract.get("report_pdf")),
        work_folder / str(contract.get("recovery_update_zip")),
    ]
    errors: list[str] = []
    published: list[str] = []

    for source in expected:
        if not source.is_file() or source.stat().st_size == 0:
            errors.append(f"Uitvoer ontbreekt of is leeg: {source}")
            continue
        destination = output_folder / source.name
        shutil.copy2(source, destination)
        if sha256_file(source) != sha256_file(destination):
            errors.append(f"Checksum verschilt na publicatie: {destination}")
            continue
        published.append(str(destination))

    status = "completed" if not errors and len(published) == 2 else "failed"
    result = {
        "version": APP_VERSION,
        "created_at": datetime.now(TZ).isoformat(),
        "status": status,
        "month": month_key,
        "folder": str(output_folder),
        "files": published,
        "errors": errors,
    }
    write_atomic_json(output_folder / "output_manifest.json", result)
    update_state(
        report_output_last_created=result["created_at"],
        report_output_last_month=month_key,
        report_output_last_status=status,
        report_output_last_folder=str(output_folder),
        report_output_last_files=published,
        report_output_last_error=None if not errors else "; ".join(errors),
    )
    return result


def generator_wrapper_source(role: str, bundle_folder: str) -> str:
    if role == "page_1":
        entrypoint = "generate_energierapport_pagina1.py"
        data_name = "page_1.json"
        output_name = "Energierapport_Pagina1_{month_key}.pdf"
        args = '[sys.executable, str(entry), str(data_file), "-o", str(output_file)]'
    elif role == "page_2":
        entrypoint = "src/generate_p2.py"
        data_name = "page_2.json"
        output_name = "Energierapport_Pagina2_{month_key}.pdf"
        args = '[sys.executable, str(entry), "--data", str(data_file), "--output", str(output_file)]'
    else:
        entrypoint = "src/generate_pages_3_13.py"
        data_name = "pages_3_13.json"
        output_name = "Energierapport_Pagina3_tm_13_{month_key}.pdf"
        args = '[sys.executable, str(entry), "--data", str(data_file), "--output", str(output_file)]'

    return f"""#!/usr/bin/env python3
from __future__ import annotations
import argparse
import subprocess
import sys
from pathlib import Path

def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--request", required=True)
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--year", required=True, type=int)
    p.add_argument("--month", required=True, type=int)
    a = p.parse_args()

    month_key = f"{{a.year:04d}}_{{a.month:02d}}"
    root = Path(__file__).resolve().parent
    package = root / "packages" / "{bundle_folder}"
    entry = package / "{entrypoint}"
    data_file = root / "data" / month_key / "{data_name}"
    output_file = Path(a.output) / f"{output_name}"

    if not entry.is_file():
        raise SystemExit(f"Bundled generator ontbreekt: {{entry}}")
    if not data_file.is_file():
        raise SystemExit(
            "Generator-data ontbreekt: "
            + str(data_file)
            + ". Bouw eerst de maanddata-adapter."
        )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    command = {args}
    return subprocess.run(command, check=False).returncode

if __name__ == "__main__":
    raise SystemExit(main())
"""


def install_bundled_report_generators(options: Options) -> dict[str, Any]:
    paths = report_service_paths(options)
    paths["generators"].mkdir(parents=True, exist_ok=True)
    packages_root = paths["generators"] / "packages"
    data_root = paths["generators"] / "data"
    packages_root.mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)

    installed: list[str] = []
    errors: list[str] = []

    for role, official_name in REPORT_GENERATORS.items():
        bundle_folder = GENERATOR_BUNDLE_FOLDERS[role]
        source = BUNDLED_REPORT_GENERATORS / bundle_folder
        destination = packages_root / bundle_folder

        if not source.is_dir():
            errors.append(f"Bundled generatorpakket ontbreekt: {source}")
            continue

        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source, destination)

        wrapper = paths["generators"] / f"{official_name}.py"
        wrapper.write_text(
            generator_wrapper_source(role, bundle_folder),
            encoding="utf-8",
        )
        wrapper.chmod(0o755)
        installed.extend([str(destination), str(wrapper)])

    status = "completed" if not errors else "failed"
    result = {
        "version": APP_VERSION,
        "installed_at": datetime.now(TZ).isoformat(),
        "status": status,
        "root": str(paths["generators"]),
        "installed": installed,
        "errors": errors,
    }
    write_atomic_json(paths["root"] / "generator_install_result.json", result)
    update_state(
        report_generators_install_last=result["installed_at"],
        report_generators_install_status=status,
        report_generators_install_files=installed,
        report_generators_install_error=None if not errors else "; ".join(errors),
    )
    return result




def check_report_runtime() -> dict[str, Any]:
    checked_at = datetime.now(TZ).isoformat()
    modules: dict[str, dict[str, Any]] = {}
    errors: list[str] = []

    for name in ("reportlab", "pypdf"):
        try:
            module = __import__(name)
            modules[name] = {
                "status": "ok",
                "version": str(getattr(module, "__version__", "unknown")),
                "file": str(getattr(module, "__file__", "")),
            }
        except Exception as exc:
            modules[name] = {
                "status": "error",
                "error": str(exc),
            }
            errors.append(f"{name}: {exc}")

    status = "ok" if not errors else "error"
    result = {
        "version": APP_VERSION,
        "checked_at": checked_at,
        "status": status,
        "python": sys.executable,
        "modules": modules,
        "errors": errors,
    }
    update_state(
        report_runtime_last_checked=checked_at,
        report_runtime_last_status=status,
        report_runtime_modules=modules,
        report_runtime_last_error=None if not errors else "; ".join(errors),
    )
    return result



def report_service_paths(options: Options) -> dict[str, Path]:
    root = Path("/share") / options.report_service_root
    return {
        "root": root,
        "generators": root / "generators",
        "work": root / "work",
        "output": root / "output",
        "logs": root / "logs",
    }


def initialize_report_service(options: Options) -> dict[str, Any]:
    paths = report_service_paths(options)
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    runtime = check_report_runtime()
    install_result = install_bundled_report_generators(options)
    contract = {
        "version": APP_VERSION,
        "schema": "energie_report_service_v1",
        "updated_at": datetime.now(TZ).isoformat(),
        "required_generators": REPORT_GENERATORS,
        "arguments": ["--request", "--input", "--output", "--year", "--month"],
    }
    contract_path = paths["root"] / "service_contract.json"
    write_atomic_json(contract_path, contract)
    return {
        "status": (
            "ok"
            if runtime.get("status") == "ok"
            and install_result.get("status") == "completed"
            else "error"
        ),
        "root": str(paths["root"]),
        "contract": str(contract_path),
        "runtime": runtime,
        "install": install_result,
    }


def discover_report_generators(options: Options) -> dict[str, Any]:
    paths = report_service_paths(options)
    initialization = initialize_report_service(options)
    if initialization.get("runtime", {}).get("status") != "ok":
        result = {
            "version": APP_VERSION,
            "checked_at": datetime.now(TZ).isoformat(),
            "status": "runtime_error",
            "root": str(paths["root"]),
            "generators": {},
            "role_status": {
                role: "blocked"
                for role in REPORT_GENERATORS
            },
            "missing": [],
            "runtime": initialization.get("runtime"),
        }
        update_state(
            report_service_last_checked=result["checked_at"],
            report_service_last_status="runtime_error",
            report_service_generators={},
            report_service_last_error=(
                initialization.get("runtime", {}).get("errors") or ["Onbekende runtimefout"]
            )[0],
        )
        return result

    found: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    for role, name in REPORT_GENERATORS.items():
        script = paths["generators"] / f"{name}.py"
        if script.is_file():
            found[role] = {"name": name, "path": str(script), "sha256": sha256_file(script)}
        else:
            missing.append(name)
    role_status = {
        role: ("ready" if role in found else "missing")
        for role in REPORT_GENERATORS
    }
    if not missing:
        status = "ready"
    elif role_status["page_1"] == "ready":
        status = "page_1_ready"
    else:
        status = "waiting_for_generators"
    result = {
        "version": APP_VERSION,
        "checked_at": datetime.now(TZ).isoformat(),
        "status": status,
        "root": str(paths["root"]),
        "generators": found,
        "role_status": role_status,
        "missing": missing,
    }
    update_state(
        report_service_last_checked=result["checked_at"],
        report_service_last_status=status,
        report_service_generators=found,
        report_service_last_error=None,
    )
    return result



def execute_page1_generator(
    options: Options,
    handoff_path: str | Path,
    handoff: dict[str, Any],
) -> dict[str, Any]:
    started_at = datetime.now(TZ).isoformat()
    service = discover_report_generators(options)
    month_key = str(handoff["month"])
    page1 = service.get("generators", {}).get("page_1")

    update_state(
        report_page1_last_started=started_at,
        report_page1_last_status="running",
        report_page1_last_error=None,
    )

    if not page1:
        result = {
            "status": "waiting_for_page_1",
            "month": month_key,
            "generator": REPORT_GENERATORS["page_1"],
            "generator_folder": str(report_service_paths(options)["generators"]),
            "reason": "Officiële pagina 1-generator ontbreekt.",
        }
        update_state(
            report_page1_last_finished=datetime.now(TZ).isoformat(),
            report_page1_last_status=result["status"],
            report_page1_last_error=None,
        )
        return result

    paths = report_service_paths(options)
    output_folder = paths["work"] / month_key
    log_folder = paths["logs"] / month_key
    output_folder.mkdir(parents=True, exist_ok=True)
    log_folder.mkdir(parents=True, exist_ok=True)

    input_folder = Path(str(handoff["input_folder"]))
    year, month = int(month_key[:4]), int(month_key[5:7])
    expected_output = output_folder / f"Energierapport_Pagina1_{month_key}.pdf"
    command = [
        sys.executable,
        page1["path"],
        "--request", str(handoff_path),
        "--input", str(input_folder),
        "--output", str(output_folder),
        "--year", str(year),
        "--month", str(month),
    ]

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=options.report_service_timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        error = f"Pagina 1-generator overschreed {options.report_service_timeout_seconds} seconden."
        update_state(
            report_page1_last_finished=datetime.now(TZ).isoformat(),
            report_page1_last_status="failed",
            report_page1_last_error=error,
        )
        return {"status": "failed", "month": month_key, "error": error}

    log_path = log_folder / "page_1.log"
    log_path.write_text(
        "COMMAND:\n" + " ".join(command)
        + "\n\nSTDOUT:\n" + completed.stdout
        + "\n\nSTDERR:\n" + completed.stderr,
        encoding="utf-8",
    )

    errors: list[str] = []
    if completed.returncode != 0:
        errors.append(f"Pagina 1-generator stopte met code {completed.returncode}.")
    if not expected_output.is_file() or expected_output.stat().st_size == 0:
        errors.append(f"Pagina 1-PDF ontbreekt of is leeg: {expected_output}")

    status = "completed" if not errors else "failed"
    result = {
        "status": status,
        "month": month_key,
        "generator": page1,
        "returncode": completed.returncode,
        "output": str(expected_output),
        "log": str(log_path),
        "errors": errors,
    }
    write_atomic_json(output_folder / "page_1_result.json", result)
    update_state(
        report_page1_last_finished=datetime.now(TZ).isoformat(),
        report_page1_last_status=status,
        report_page1_last_output=str(expected_output) if status == "completed" else None,
        report_page1_last_log=str(log_path),
        report_page1_last_error=None if status == "completed" else "; ".join(errors),
    )
    return result



def validate_report_outputs(handoff: dict[str, Any], output_folder: Path) -> dict[str, Any]:
    contract = handoff.get("output_contract") or {}
    report_pdf = output_folder / str(contract.get("report_pdf", ""))
    recovery_zip = output_folder / str(contract.get("recovery_update_zip", ""))
    errors: list[str] = []
    if not report_pdf.is_file() or report_pdf.stat().st_size == 0:
        errors.append(f"Definitief rapport ontbreekt of is leeg: {report_pdf}")
    if not recovery_zip.is_file() or recovery_zip.stat().st_size == 0:
        errors.append(f"Recovery Update ontbreekt of is leeg: {recovery_zip}")
    return {
        "status": "ok" if not errors else "error",
        "checked_at": datetime.now(TZ).isoformat(),
        "errors": errors,
        "report_pdf": str(report_pdf),
        "recovery_update_zip": str(recovery_zip),
    }


def execute_local_report_service(options: Options, handoff_path: str | Path, handoff: dict[str, Any]) -> dict[str, Any]:
    service = discover_report_generators(options)
    month_key = str(handoff["month"])
    adapter = build_report_adapter_data(options, handoff)
    if service["status"] != "ready":
        page1_result = execute_page1_generator(options, handoff_path, handoff)
        return {
            "status": (
                "page_1_completed"
                if page1_result.get("status") == "completed"
                else "waiting_for_generators"
            ),
            "month": month_key,
            "service": service,
            "adapter": adapter,
            "page_1": page1_result,
            "reason": (
                "Pagina 1 is uitgevoerd; pagina 2 en pagina 3-13 ontbreken nog."
                if page1_result.get("status") == "completed"
                else "Officiële generatorbestanden ontbreken."
            ),
        }

    paths = report_service_paths(options)
    work_folder = paths["work"] / month_key
    output_folder = paths["output"] / month_key
    log_folder = paths["logs"] / month_key
    for folder in (work_folder, output_folder, log_folder):
        folder.mkdir(parents=True, exist_ok=True)

    runs = []
    input_folder = Path(str(handoff["input_folder"]))
    year, month = int(month_key[:4]), int(month_key[5:7])
    for role in ("page_1", "page_2", "pages_3_13"):
        generator = service["generators"][role]
        command = [
            sys.executable, generator["path"],
            "--request", str(handoff_path),
            "--input", str(input_folder),
            "--output", str(work_folder),
            "--year", str(year),
            "--month", str(month),
        ]
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=options.report_service_timeout_seconds,
            check=False,
        )
        log_path = log_folder / f"{role}.log"
        log_path.write_text(
            "COMMAND:\n" + " ".join(command)
            + "\n\nSTDOUT:\n" + completed.stdout
            + "\n\nSTDERR:\n" + completed.stderr,
            encoding="utf-8",
        )
        runs.append({
            "role": role,
            "generator": generator["name"],
            "returncode": completed.returncode,
            "log": str(log_path),
        })
        if role == "page_1":
            page1_output = work_folder / f"Energierapport_Pagina1_{month_key}.pdf"
            page1_status = (
                "completed"
                if completed.returncode == 0
                and page1_output.is_file()
                and page1_output.stat().st_size > 0
                else "failed"
            )
            update_state(
                report_page1_last_started=None,
                report_page1_last_finished=datetime.now(TZ).isoformat(),
                report_page1_last_status=page1_status,
                report_page1_last_output=str(page1_output) if page1_status == "completed" else None,
                report_page1_last_log=str(log_path),
                report_page1_last_error=None if page1_status == "completed"
                else f"{generator['name']} stopte met code {completed.returncode}.",
            )
        if completed.returncode != 0:
            error = f"{generator['name']} stopte met code {completed.returncode}."
            update_state(report_service_last_status="failed", report_service_last_error=error)
            return {"status": "failed", "month": month_key, "runs": runs, "error": error}

    merge = merge_report_pdfs(handoff, work_folder)
    recovery = create_recovery_update(options, handoff, work_folder)

    contract = handoff.get("output_contract") or {}
    for key in ("report_pdf", "recovery_update_zip"):
        source = work_folder / str(contract.get(key, ""))
        if source.is_file():
            shutil.copy2(source, output_folder / source.name)

    validation = validate_report_outputs(handoff, output_folder)
    publication = publish_month_output(handoff, work_folder)
    status = (
        "completed"
        if validation["status"] == "ok"
        and publication["status"] == "completed"
        else "failed"
    )
    result = {
        "status": status,
        "month": month_key,
        "service": service,
        "adapter": adapter,
        "runs": runs,
        "merge": merge,
        "recovery": recovery,
        "publication": publication,
        "output_folder": str(output_folder),
        "validation": validation,
    }
    write_atomic_json(output_folder / "report_service_result.json", result)
    update_state(
        report_service_last_status=status,
        report_service_last_output=str(output_folder),
        report_service_last_error=(
            None if status == "completed"
            else "; ".join(validation["errors"] + publication["errors"])
        ),
    )
    return result





def cleanup_report_service_history(options: Options, keep_months: int | None = None) -> dict[str, Any]:
    keep = keep_months or options.report_service_retention_months
    paths = report_service_paths(options)
    removed: list[str] = []
    errors: list[str] = []

    for key in ("work", "output", "logs"):
        root = paths[key]
        if not root.is_dir():
            continue
        month_dirs = sorted(
            [
                path for path in root.iterdir()
                if path.is_dir()
                and len(path.name) == 7
                and path.name[4] == "_"
                and path.name[:4].isdigit()
                and path.name[5:].isdigit()
            ],
            key=lambda path: path.name,
            reverse=True,
        )
        for old in month_dirs[keep:]:
            try:
                shutil.rmtree(old)
                removed.append(str(old))
            except Exception as exc:
                errors.append(f"{old}: {exc}")

    status = "completed" if not errors else "failed"
    result = {
        "version": APP_VERSION,
        "run_at": datetime.now(TZ).isoformat(),
        "status": status,
        "retention_months": keep,
        "removed": removed,
        "errors": errors,
    }
    update_state(
        report_retention_last_run=result["run_at"],
        report_retention_last_status=status,
        report_retention_removed=removed,
        report_retention_last_error=None if not errors else "; ".join(errors),
    )
    return result


def build_compact_workflow_summary(month_key: str) -> dict[str, Any]:
    state = load_state()
    result = {
        "version": APP_VERSION,
        "created_at": datetime.now(TZ).isoformat(),
        "month": month_key,
        "status": (
            "completed"
            if state.get("workflow_audit_last_status") == "completed"
            and state.get("report_output_last_status") == "completed"
            else state.get("full_workflow_last_status")
        ),
        "validation": (state.get("last_central_validation") or {}).get("status"),
        "report": state.get("report_generation_last_status"),
        "page_1": state.get("report_page1_last_status"),
        "merge": state.get("report_merge_last_status"),
        "publication": state.get("report_output_last_status"),
        "audit": state.get("workflow_audit_last_status"),
        "output_folder": state.get("report_output_last_folder"),
        "files": state.get("report_output_last_files") or [],
        "error": (
            None
            if state.get("workflow_audit_last_status") == "completed"
            and state.get("report_output_last_status") == "completed"
            else state.get("full_workflow_last_error")
        ),
    }
    update_state(workflow_summary_last=result)
    return result



def audit_completed_month_workflow(month_key: str) -> dict[str, Any]:
    state = load_state()
    checks: list[dict[str, Any]] = []

    def add(name: str, status: str, detail: Any = None) -> None:
        checks.append({"name": name, "status": status, "detail": detail})

    add("central_validation",
        "ok" if (state.get("last_central_validation") or {}).get("status") == "ok" else "error",
        state.get("last_central_validation"))
    add("report_runtime",
        "ok" if state.get("report_runtime_last_status") == "ok" else "error",
        state.get("report_runtime_modules"))
    add("report_generators",
        "ok" if state.get("report_generators_install_status") == "completed" else "error",
        state.get("report_service_generators"))
    add("report_adapter",
        "ok" if state.get("report_adapter_last_status") == "completed" else "error",
        state.get("report_adapter_last_files"))
    add("report_merge",
        "ok" if state.get("report_merge_last_status") == "completed" else "error",
        state.get("report_merge_last_output"))
    add("report_output",
        "ok" if state.get("report_output_last_status") == "completed" else "error",
        state.get("report_output_last_files"))

    output_files = [Path(path) for path in state.get("report_output_last_files") or []]
    output_errors: list[str] = []
    file_details: list[dict[str, Any]] = []
    for path in output_files:
        if not path.is_file() or path.stat().st_size == 0:
            output_errors.append(f"Ontbrekend of leeg uitvoerbestand: {path}")
            continue
        file_details.append({
            "path": str(path),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        })

    expected_names = {
        f"Energierapport_{month_key}.pdf",
        f"Recovery_Update_{month_key}.zip",
    }
    actual_names = {path.name for path in output_files if path.is_file()}
    if actual_names != expected_names:
        output_errors.append(
            f"Uitvoerbestandenset wijkt af: verwacht {sorted(expected_names)}, "
            f"gevonden {sorted(actual_names)}"
        )

    add("published_files", "ok" if not output_errors else "error",
        {"files": file_details, "errors": output_errors})

    failures = [item for item in checks if item["status"] != "ok"]
    status = "completed" if not failures else "failed"
    result = {
        "version": APP_VERSION,
        "checked_at": datetime.now(TZ).isoformat(),
        "status": status,
        "month": month_key,
        "checks": checks,
        "errors": [item["name"] for item in failures],
    }
    update_state(
        workflow_audit_last_checked=result["checked_at"],
        workflow_audit_last_month=month_key,
        workflow_audit_last_status=status,
        workflow_audit_last_result=result,
        workflow_audit_last_error=None if not failures else ", ".join(result["errors"]),
    )
    return result




def validate_report_input_files(input_folder: Path) -> dict[str, Any]:
    expected = {
        "P1e.csv",
        "P1g.csv",
        "Airco Skt.csv",
        "Mobiel Skt.csv",
        "Heater kantoor Skt.csv",
        "Heater woonkamer Skt.csv",
        "Heater lounge Skt.csv",
        "Enphase.csv",
        "Nordpool elektriciteit.csv",
        "NextEnergy actuele stroomprijs.csv",
    }
    found = {
        path.name
        for path in input_folder.glob("*.csv")
        if path.is_file() and path.stat().st_size > 0
    }
    missing = sorted(expected - found)
    result = {
        "status": "ok" if not missing else "error",
        "input_folder": str(input_folder),
        "expected": sorted(expected),
        "found": sorted(found),
        "missing": missing,
    }
    if missing:
        raise RuntimeError(
            "Rapportinput is onvolledig; ontbrekend of leeg: "
            + ", ".join(missing)
        )
    return result



def run_report_generation_from_handoff(
    options: Options,
    handoff_path: str | Path,
) -> dict[str, Any]:
    started_at = datetime.now(TZ).isoformat()
    handoff = load_report_handoff(handoff_path)
    handoff["_request_path"] = str(handoff_path)
    month_key = str(handoff["month"])
    input_validation = validate_report_input_files(
        Path(str(handoff["input_folder"]))
    )
    validation = validate_report_handoff_files(handoff)

    update_state(
        report_generation_last_started=started_at,
        report_generation_last_month=month_key,
        report_generation_last_status="running",
        report_generation_last_error=None,
    )

    if validation["status"] != "ok":
        error = "; ".join(validation["errors"])
        update_state(
            report_generation_last_finished=datetime.now(TZ).isoformat(),
            report_generation_last_status="failed",
            report_generation_last_error=error,
        )
        raise RuntimeError(error)

    if options.report_service_enabled:
        local_result = execute_local_report_service(options, handoff_path, handoff)
        result = {
            "status": local_result.get("status"),
            "started_at": started_at,
            "finished_at": datetime.now(TZ).isoformat(),
            "month": month_key,
            "handoff": str(handoff_path),
        "input_validation": input_validation,
            "validation": validation,
            "service": local_result,
        }
        update_state(
            report_generation_last_finished=result["finished_at"],
            report_generation_last_status=result["status"],
            report_generation_last_response=result,
            report_generation_last_error=local_result.get("error"),
        )
        if result["status"] == "completed":
            result["audit"] = audit_completed_month_workflow(month_key)
            if result["audit"].get("status") != "completed":
                result["status"] = "failed"
                update_state(
                    report_generation_last_status="failed",
                    report_generation_last_response=result,
                    report_generation_last_error="Eindcontrole van de maandworkflow is mislukt.",
                )
            else:
                result["retention"] = cleanup_report_service_history(options)
                result["summary"] = build_compact_workflow_summary(month_key)
                update_state(report_generation_last_response=result)
        return result

    if not options.report_trigger_enabled:
        service = discover_report_generators(options)
        result = {
            "status": "waiting_for_generators" if service["status"] != "ready" else "ready",
            "started_at": started_at,
            "finished_at": datetime.now(TZ).isoformat(),
            "month": month_key,
            "handoff": str(handoff_path),
            "validation": validation,
            "service": service,
            "reason": "Officiële generatorbestanden ontbreken." if service["status"] != "ready" else "Lokale rapportservice is uitgeschakeld.",
        }
        update_state(
            report_generation_last_finished=result["finished_at"],
            report_generation_last_status=result["status"],
            report_generation_last_response=result,
            report_generation_last_error=None,
        )
        return result

    trigger_result = trigger_report_generation(
        options,
        int(month_key[:4]),
        int(month_key[5:7]),
        handoff.get("transfer_zip"),
        handoff.get("central_validation") or {},
        report_handoff=handoff,
    )
    finished_at = datetime.now(TZ).isoformat()
    result = {
        "status": "completed" if trigger_result.get("status") == "ok" else "failed",
        "started_at": started_at,
        "finished_at": finished_at,
        "month": month_key,
        "handoff": str(handoff_path),
        "validation": validation,
        "trigger": trigger_result,
    }
    update_state(
        report_generation_last_finished=finished_at,
        report_generation_last_status=result["status"],
        report_generation_last_response=result,
        report_generation_last_error=(
            None if result["status"] == "completed" else str(trigger_result)
        ),
        last_report_trigger=trigger_result,
        last_report_trigger_error=None,
    )
    return result



def trigger_report_generation(
    options: Options,
    year: int,
    month: int,
    transfer_bundle: str | None,
    central_validation: dict[str, Any],
    report_handoff: dict[str, Any] | None = None,
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
        "report_handoff": report_handoff,
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




EPEX_TIMESTAMP_CANDIDATES = (
    "timestamp",
    "datetime",
    "date_time",
    "delivery_start",
    "start",
    "time",
    "datum_tijd",
    "datum",
    "date",
)


def safe_output_filename(value: str, fallback: str) -> str:
    value = value.strip() or fallback
    name = Path(value).name
    if name != value or name in {".", ".."}:
        raise ValueError(f"Ongeldige uitvoernaam: {value}")
    return name if name.lower().endswith(".csv") else f"{name}.csv"


def decode_csv_bytes(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise RuntimeError("CSV kon niet worden gedecodeerd.")


def sniff_csv_rows(content: bytes) -> tuple[list[dict[str, str]], list[str]]:
    text = decode_csv_bytes(content)
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(text.splitlines(), dialect=dialect)
    rows = [dict(row) for row in reader if isinstance(row, dict)]
    fields = list(reader.fieldnames or [])
    return rows, fields


def parse_epex_timestamp(value: str) -> datetime | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    normalized = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass
    for fmt in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d-%m-%Y",
        "%d/%m/%Y %H:%M",
        "%d/%m/%Y",
    ):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def detect_timestamp_field(fields: list[str], rows: list[dict[str, str]]) -> str | None:
    lowered = {field.lower().strip(): field for field in fields}
    for candidate in EPEX_TIMESTAMP_CANDIDATES:
        if candidate in lowered:
            return lowered[candidate]
    for field in fields:
        parsed = sum(
            1 for row in rows[:25]
            if parse_epex_timestamp(str(row.get(field, ""))) is not None
        )
        if parsed >= min(3, max(1, len(rows[:25]))):
            return field
    return None


def validate_epex_csv(
    content: bytes,
    *,
    year: int,
    month: int,
    kind: str,
    require_full_month: bool,
) -> dict[str, Any]:
    rows, fields = sniff_csv_rows(content)
    timestamp_field = detect_timestamp_field(fields, rows)
    timestamps: list[datetime] = []
    if timestamp_field:
        for row in rows:
            parsed = parse_epex_timestamp(str(row.get(timestamp_field, "")))
            if parsed is not None:
                timestamps.append(parsed)

    month_timestamps = [
        stamp for stamp in timestamps
        if stamp.year == year and stamp.month == month
    ]
    unique_dates = sorted({stamp.date().isoformat() for stamp in month_timestamps})
    import calendar
    days_in_month = calendar.monthrange(year, month)[1]
    expected_dates = {
        f"{year:04d}-{month:02d}-{day:02d}"
        for day in range(1, days_in_month + 1)
    }
    missing_dates = sorted(expected_dates.difference(unique_dates))

    errors: list[str] = []
    warnings: list[str] = []
    if not rows:
        errors.append("CSV bevat geen gegevensregels.")
    if not fields:
        errors.append("CSV bevat geen kolomkoppen.")
    if timestamp_field is None:
        errors.append("Geen datum-/tijdkolom herkend.")
    elif not month_timestamps:
        errors.append(f"Geen records gevonden voor {year:04d}-{month:02d}.")
    elif require_full_month and missing_dates:
        errors.append(f"Kalendermaand onvolledig: {len(missing_dates)} dag(en) ontbreken.")
    elif missing_dates:
        warnings.append(f"{len(missing_dates)} dag(en) ontbreken.")

    duplicate_timestamps = len(month_timestamps) - len({
        stamp.isoformat() for stamp in month_timestamps
    })
    if duplicate_timestamps:
        warnings.append(f"{duplicate_timestamps} dubbele tijdstempel(s).")

    return {
        "kind": kind,
        "status": "error" if errors else ("warning" if warnings else "ok"),
        "row_count": len(rows),
        "field_count": len(fields),
        "fields": fields,
        "timestamp_field": timestamp_field,
        "month_record_count": len(month_timestamps),
        "covered_days": len(unique_dates),
        "days_in_month": days_in_month,
        "missing_dates": missing_dates,
        "duplicate_timestamps": duplicate_timestamps,
        "errors": errors,
        "warnings": warnings,
    }


def latest_external_source(source_name: str, month_key: str) -> Path | None:
    root = OUTPUT_ROOT / "external_sources" / source_name / month_key
    if not root.exists():
        return None
    files = [path for path in root.iterdir() if path.is_file()]
    return max(files, key=lambda path: path.stat().st_mtime) if files else None


def run_epex_import_and_validate(month_key: str | None = None) -> dict[str, Any]:
    options = Options.load()
    month_key = month_key or datetime.now(TZ).strftime("%Y_%m")
    year, month = parse_month_key(month_key)

    results: dict[str, Any] = {
        "version": APP_VERSION,
        "checked_at": datetime.now(TZ).isoformat(),
        "month": month_key,
        "sources": {},
        "errors": [],
    }

    for kind, enabled, url, output_name, source_name in (
        (
            "electricity",
            options.epex_electricity_enabled,
            options.epex_electricity_url,
            options.epex_electricity_output_name,
            "epex_electricity",
        ),
        (
            "gas",
            options.epex_gas_enabled,
            options.epex_gas_url,
            options.epex_gas_output_name,
            "epex_gas",
        ),
    ):
        if not enabled:
            results["sources"][kind] = {
                "status": "not_configured",
                "reason": f"{source_name} is uitgeschakeld.",
            }
            if kind == "electricity":
                update_state(
                    epex_electricity_last_error=None,
                )
            else:
                update_state(
                    epex_gas_last_error=None,
                )
            continue
        if not url:
            results["sources"][kind] = {
                "status": "not_configured",
                "error": f"{source_name}_url ontbreekt.",
            }
            results["errors"].append(f"{source_name}_url ontbreekt.")
            continue

        try:
            content, content_type = fetch_external_source(
                url,
                min(options.request_timeout_seconds, 60),
            )
            validation = validate_epex_csv(
                content,
                year=year,
                month=month,
                kind=kind,
                require_full_month=options.epex_require_full_calendar_month,
            )
            raw_path = store_external_source(source_name, content, content_type)
            month_root = OUTPUT_ROOT / "epex_monthdata" / month_key
            month_root.mkdir(parents=True, exist_ok=True)
            filename = safe_output_filename(
                output_name,
                "EPEX stroom.csv" if kind == "electricity" else "EPEX gas.csv",
            )
            final_path = month_root / filename
            final_path.write_bytes(content)

            source_result = {
                **validation,
                "url": url,
                "raw_path": str(raw_path),
                "path": str(final_path),
                "bytes": len(content),
                "content_type": content_type,
            }
            results["sources"][kind] = source_result
            if validation["status"] == "error":
                results["errors"].extend(
                    f"{kind}: {error}" for error in validation["errors"]
                )

            if kind == "electricity":
                update_state(
                    epex_electricity_last_import=str(final_path),
                    epex_electricity_last_error=(
                        None if validation["status"] != "error"
                        else "; ".join(validation["errors"])
                    ),
                )
            else:
                update_state(
                    epex_gas_last_import=str(final_path),
                    epex_gas_last_error=(
                        None if validation["status"] != "error"
                        else "; ".join(validation["errors"])
                    ),
                )
        except Exception as exc:
            results["sources"][kind] = {
                "status": "error",
                "error": str(exc),
            }
            results["errors"].append(f"{kind}: {exc}")

    statuses = [
        source.get("status")
        for source in results["sources"].values()
        if isinstance(source, dict)
    ]
    if statuses and all(status == "not_configured" for status in statuses):
        results["status"] = "not_configured"
    else:
        results["status"] = (
            "error" if results["errors"] or "error" in statuses
            else ("warning" if "warning" in statuses else "ok")
        )
    validation_path = OUTPUT_ROOT / "epex_monthdata" / month_key / "EPEX_validation.json"
    validation_path.parent.mkdir(parents=True, exist_ok=True)
    write_atomic_json(validation_path, results)
    update_state(
        epex_last_validation=str(validation_path),
        epex_last_validation_status=results["status"],
    )
    return results



def ensure_storage_paths() -> None:
    try:
        CONFIG_ROOT.mkdir(parents=True, exist_ok=True)
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            f"Home Assistant-opslagmap niet beschikbaar: {CONFIG_ROOT}: {exc}"
        ) from exc


def validate_runtime_dependencies() -> None:
    try:
        ipaddress.ip_network("192.0.2.0/24")
    except Exception as exc:
        raise RuntimeError(f"Python ipaddress-module niet beschikbaar: {exc}") from exc


def derive_local_ipv4_cidr() -> str:
    """
    Bepaal een bruikbaar thuisnetwerk, maar accepteer nooit het interne
    Home Assistant-containerbereik 172.30.0.0/16 als HomeWizard-scanbereik.
    """
    candidates: list[str] = []

    try:
        hostname_ip = socket.gethostbyname(socket.gethostname())
        candidates.append(hostname_ip)
    except OSError:
        pass

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("1.1.1.1", 53))
            candidates.append(sock.getsockname()[0])
        finally:
            sock.close()
    except OSError:
        pass

    for ip_text in candidates:
        try:
            ip = ipaddress.ip_address(ip_text)
        except ValueError:
            continue
        if not isinstance(ip, ipaddress.IPv4Address):
            continue
        if ip.is_loopback or ip.is_link_local:
            continue
        if ip in ipaddress.ip_network("172.30.0.0/16"):
            continue
        if ip.is_private:
            return str(ipaddress.ip_network(f"{ip}/24", strict=False))

    raise RuntimeError(
        "Thuisnetwerk kon niet automatisch worden bepaald. "
        "Vul homewizard_discovery_cidr expliciet in, bijvoorbeeld 192.168.1.0/24."
    )


def classify_homewizard_device(info: dict[str, Any], data: dict[str, Any]) -> str:
    product = str(
        info.get("product_type")
        or info.get("product_name")
        or info.get("type")
        or ""
    ).lower()
    if "p1" in product or "smr" in product:
        return "p1"
    if "socket" in product or "plug" in product:
        return "socket"
    if "total_gas_m3" in data and "total_power_import_kwh" not in data:
        return "gas"
    if "total_power_import_kwh" in data and "active_power_w" in data:
        return "socket"
    return "other"


def discover_homewizard_device(host: str, timeout: int) -> dict[str, Any] | None:
    try:
        info = homewizard_info(host, timeout)
        data = homewizard_get(host, timeout)
    except Exception:
        return None

    role = classify_homewizard_device(info, data)
    label = str(
        info.get("name")
        or info.get("product_name")
        or info.get("product_type")
        or f"HomeWizard {host}"
    ).strip()
    proposal = {
        "label": label,
        "host": host,
        "role": role,
        "optional": role not in {"p1", "gas"},
        "output_name": "",
    }
    proposal["output_name"] = safe_homewizard_output_name(proposal)
    return {
        **proposal,
        "device_info": info,
        "sample_data": data,
    }



HOME_ASSISTANT_STATES_URL = "http://supervisor/core/api/states"
HOMEWIZARD_MAPPING_PATH = CONFIG_ROOT / "homewizard_mapping.json"


def home_assistant_states(timeout: int = 20) -> list[dict[str, Any]]:
    token = os.environ.get("SUPERVISOR_TOKEN", "").strip()
    if not token:
        raise RuntimeError("SUPERVISOR_TOKEN ontbreekt; Home Assistant API is niet beschikbaar.")
    request = urllib.request.Request(
        HOME_ASSISTANT_STATES_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": f"Energieproject-HomeAssistant/{APP_VERSION}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Home Assistant-entiteiten konden niet worden gelezen: {exc}") from exc
    if not isinstance(payload, list):
        raise RuntimeError("Home Assistant API gaf geen entiteitenlijst terug.")
    return [item for item in payload if isinstance(item, dict)]



HOME_ASSISTANT_ENTITY_URL = "http://supervisor/core/api/states/{entity_id}"


def home_assistant_entity(entity_id: str, timeout: int = 20) -> dict[str, Any]:
    token = os.environ.get("SUPERVISOR_TOKEN", "").strip()
    if not token:
        raise RuntimeError("SUPERVISOR_TOKEN ontbreekt; Home Assistant API is niet beschikbaar.")
    request = urllib.request.Request(
        HOME_ASSISTANT_ENTITY_URL.format(entity_id=urllib.parse.quote(entity_id, safe="._")),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "User-Agent": f"Energieproject-HomeAssistant/{APP_VERSION}",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Home Assistant-entiteit {entity_id} kon niet worden gelezen: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Home Assistant-entiteit {entity_id} gaf geen JSON-object terug.")
    return payload


def normalized_entity_value(entity: dict[str, Any]) -> float:
    try:
        return float(entity.get("state"))
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"Entiteit {entity.get('entity_id', 'onbekend')} heeft geen numerieke waarde."
        ) from exc


def collect_homeassistant_energy_snapshot(options: Options) -> dict[str, Any]:
    captured_at = datetime.now(TZ).isoformat()
    sources = {
        "enphase": options.enphase_entity_id,
        "nordpool": options.nordpool_entity_id,
        "nextenergy": options.nextenergy_entity_id,
    }
    result: dict[str, Any] = {
        "version": APP_VERSION,
        "captured_at": captured_at,
        "sources": {},
        "errors": [],
    }

    for name, entity_id in sources.items():
        if not entity_id:
            continue
        try:
            entity = home_assistant_entity(entity_id)
            attributes = entity.get("attributes") or {}
            result["sources"][name] = {
                "entity_id": entity_id,
                "friendly_name": attributes.get("friendly_name"),
                "value": normalized_entity_value(entity),
                "unit": attributes.get("unit_of_measurement"),
                "device_class": attributes.get("device_class"),
                "state_class": attributes.get("state_class"),
                "last_updated": entity.get("last_updated"),
            }
        except Exception as exc:
            result["errors"].append(f"{name}: {exc}")

    result["status"] = "ok" if not result["errors"] else (
        "warning" if result["sources"] else "error"
    )
    return result


def persist_homeassistant_energy_snapshot(snapshot: dict[str, Any]) -> list[str]:
    captured = datetime.fromisoformat(snapshot["captured_at"])
    month_root = OUTPUT_ROOT / "homeassistant_energy" / f"{captured:%Y_%m}"
    month_root.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    file_map = {
        "enphase": "Enphase.csv",
        "nordpool": "Nordpool elektriciteit.csv",
        "nextenergy": "NextEnergy actuele stroomprijs.csv",
    }

    for source_name, item in snapshot.get("sources", {}).items():
        filename = file_map.get(source_name, f"{source_name}.csv")
        path = month_root / filename
        append_csv_row(
            path,
            [
                "captured_at",
                "entity_id",
                "friendly_name",
                "value",
                "unit",
                "device_class",
                "state_class",
                "last_updated",
            ],
            {
                "captured_at": snapshot["captured_at"],
                **item,
            },
        )
        written.append(str(path))

    raw_path = month_root / f"HomeAssistant_Energie_{captured:%Y-%m-%d_%H-%M-%S}.json"
    write_atomic_json(raw_path, snapshot)
    written.append(str(raw_path))
    return sorted(written)


def run_homeassistant_energy_snapshot() -> dict[str, Any]:
    options = Options.load()
    if not options.homeassistant_energy_sampling_enabled:
        raise RuntimeError("Home Assistant-energiesampling is uitgeschakeld.")
    snapshot = collect_homeassistant_energy_snapshot(options)
    files = persist_homeassistant_energy_snapshot(snapshot)
    update_state(
        homeassistant_energy_last_snapshot=snapshot["captured_at"],
        homeassistant_energy_last_error=None if snapshot["status"] != "error" else "; ".join(snapshot["errors"]),
        homeassistant_energy_last_files=files,
    )
    return snapshot



def energy_name_candidates(states: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for entity in states:
        attributes = entity.get("attributes") or {}
        if attributes.get("device_class") != "energy":
            continue
        friendly_name = str(attributes.get("friendly_name", "")).strip()
        unit = str(attributes.get("unit_of_measurement", "")).strip().lower()
        if unit != "kwh":
            continue
        try:
            value = float(entity.get("state"))
        except (TypeError, ValueError):
            continue
        candidates.append({
            "entity_id": str(entity.get("entity_id", "")),
            "friendly_name": friendly_name,
            "value_kwh": value,
        })
    return candidates


def friendly_device_name(friendly_name: str) -> str:
    suffixes = (
        " Energie import",
        " Energie Import",
        " energy import",
        " Energy import",
    )
    for suffix in suffixes:
        if friendly_name.endswith(suffix):
            return friendly_name[:-len(suffix)].strip()
    return friendly_name.strip()


def output_name_for_home_assistant_name(name: str, role: str) -> str:
    if role == "p1":
        return "P1e.csv"
    if role == "gas":
        return "P1g.csv"
    if role == "socket":
        normalized = {
            "Heater KANTOOR": "Heater kantoor",
            "Heater WOONKAMER": "Heater woonkamer",
            "Heater LOUNGE": "Heater lounge",
        }.get(name, name)
        return f"{normalized} Skt.csv"
    return f"{name}.csv"


def map_discovery_to_home_assistant(
    discovery: dict[str, Any],
    states: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    states = states if states is not None else home_assistant_states()
    candidates = energy_name_candidates(states)
    mappings: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    used_entities: set[str] = set()

    for device in discovery.get("devices", []):
        info = device.get("device_info") or {}
        sample = device.get("sample_data") or {}
        serial = str(info.get("serial", "")).strip()
        role = str(device.get("role", "other"))
        target = sample.get("total_power_import_kwh")
        best: dict[str, Any] | None = None

        if role == "p1":
            preferred = [
                item for item in candidates
                if "p1 meter" in item["friendly_name"].lower()
                and "import" in item["friendly_name"].lower()
            ]
            if preferred:
                best = min(
                    preferred,
                    key=lambda item: abs(item["value_kwh"] - float(target or 0)),
                )
        elif role == "socket" and target is not None:
            eligible = [
                item for item in candidates
                if item["entity_id"] not in used_entities
                and "socket" in item["entity_id"]
                and "energie import" in item["friendly_name"].lower()
            ]
            if eligible:
                candidate = min(
                    eligible,
                    key=lambda item: abs(item["value_kwh"] - float(target)),
                )
                if abs(candidate["value_kwh"] - float(target)) <= 0.02:
                    best = candidate

        if best is None:
            unmatched.append({
                "serial": serial,
                "host": device.get("host"),
                "role": role,
                "total_power_import_kwh": target,
            })
            continue

        used_entities.add(best["entity_id"])
        name = friendly_device_name(best["friendly_name"])
        mappings.append({
            "serial": serial,
            "label": name,
            "host": device.get("host"),
            "role": role,
            "optional": role == "socket",
            "output_name": output_name_for_home_assistant_name(name, role),
            "home_assistant_entity_id": best["entity_id"],
            "home_assistant_friendly_name": best["friendly_name"],
            "matched_value_kwh": best["value_kwh"],
        })

    result = {
        "version": APP_VERSION,
        "mapped_at": datetime.now(TZ).isoformat(),
        "status": "ok" if mappings and not unmatched else ("warning" if mappings else "error"),
        "mapping_count": len(mappings),
        "unmatched_count": len(unmatched),
        "mappings": mappings,
        "unmatched": unmatched,
    }
    ensure_storage_paths()
    write_atomic_json(HOMEWIZARD_MAPPING_PATH, result)
    update_state(
        homewizard_mapping_last=result["mapped_at"],
        homewizard_mapping_count=len(mappings),
        homewizard_mapping_error=None if mappings else "Geen apparaten gekoppeld.",
    )
    LOGGER.info(
        "HomeWizard aan Home Assistant gekoppeld: %s gekoppeld, %s niet gekoppeld.",
        len(mappings),
        len(unmatched),
    )
    return result


def load_homewizard_mapping() -> dict[str, Any] | None:
    if not HOMEWIZARD_MAPPING_PATH.exists():
        return None
    try:
        data = json.loads(HOMEWIZARD_MAPPING_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        LOGGER.error("HomeWizard mapping kon niet worden gelezen: %s", exc)
        return None
    return data if isinstance(data, dict) else None


def effective_homewizard_devices(options: Options) -> list[dict[str, Any]]:
    if options.homewizard_devices:
        return options.homewizard_devices
    mapping = load_homewizard_mapping() or {}
    mappings = mapping.get("mappings")
    return mappings if isinstance(mappings, list) else []



def discover_homewizard_devices(options: Options) -> dict[str, Any]:
    update_state(homewizard_discovery_status="running", homewizard_discovery_error=None)
    if not options.homewizard_discovery_enabled:
        raise RuntimeError("Automatische HomeWizard-detectie is uitgeschakeld.")

    cidr = options.homewizard_discovery_cidr or derive_local_ipv4_cidr()
    network = ipaddress.ip_network(cidr, strict=False)
    if network.version != 4 or network.prefixlen < 24:
        raise RuntimeError(
            "Detectie is om veiligheidsredenen beperkt tot één IPv4 /24-netwerk of kleiner."
        )

    hosts = [str(host) for host in network.hosts()]
    found: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(32, max(1, len(hosts)))) as pool:
        futures = {
            pool.submit(
                discover_homewizard_device,
                host,
                options.homewizard_discovery_timeout_seconds,
            ): host
            for host in hosts
        }
        for future in as_completed(futures):
            device = future.result()
            if device:
                found.append(device)

    found.sort(key=lambda item: (item.get("role", "other"), item.get("host", "")))
    result = {
        "status": "ok",
        "checked_at": datetime.now(TZ).isoformat(),
        "cidr": str(network),
        "hosts_scanned": len(hosts),
        "devices_found": len(found),
        "devices": found,
    }
    ensure_storage_paths()
    write_atomic_json(CONFIG_ROOT / "homewizard_discovery.json", result)
    LOGGER.info("HomeWizard-detectie afgerond: %s apparaat/apparaten gevonden in %s.", len(found), network)
    update_state(
        homewizard_discovery_last=result["checked_at"],
        homewizard_discovery_cidr=str(network),
        homewizard_discovery_count=len(found),
        homewizard_discovery_devices=found,
        homewizard_discovery_error=None,
        homewizard_discovery_status="completed",
    )
    try:
        result["home_assistant_mapping"] = map_discovery_to_home_assistant(result)
        mapped_by_serial = {
            str(item.get("serial")): item
            for item in result["home_assistant_mapping"].get("mappings", [])
        }
        for device in found:
            serial = str((device.get("device_info") or {}).get("serial", ""))
            mapped = mapped_by_serial.get(serial)
            if mapped:
                device["label"] = mapped.get("label", device.get("label"))
                device["output_name"] = mapped.get(
                    "output_name",
                    device.get("output_name"),
                )
                device["home_assistant_entity_id"] = mapped.get(
                    "home_assistant_entity_id"
                )
        result["devices"] = found
        write_atomic_json(CONFIG_ROOT / "homewizard_discovery.json", result)
        update_state(homewizard_discovery_devices=found)
    except Exception as exc:
        LOGGER.exception("Automatische koppeling met Home Assistant-namen mislukt.")
        update_state(homewizard_mapping_error=str(exc))
        result["home_assistant_mapping"] = {
            "status": "error",
            "error": str(exc),
        }
    return result



def homewizard_request(host: str, path: str, timeout: int) -> dict[str, Any]:
    url = f"http://{host}{path}"
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
        raise RuntimeError(f"HomeWizard {host}{path} niet bereikbaar: {exc}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"HomeWizard {host}{path} gaf geen JSON-object terug.")
    return payload


def homewizard_get(host: str, timeout: int) -> dict[str, Any]:
    return homewizard_request(host, "/api/v1/data", timeout)


def homewizard_info(host: str, timeout: int) -> dict[str, Any]:
    return homewizard_request(host, "/api", timeout)



HOMEWIZARD_CSV_FIELDS = {
    "p1_electricity": [
        "captured_at",
        "label",
        "host",
        "total_power_import_kwh",
        "total_power_import_t1_kwh",
        "total_power_import_t2_kwh",
        "total_power_export_kwh",
        "total_power_export_t1_kwh",
        "total_power_export_t2_kwh",
        "active_power_w",
        "active_power_l1_w",
        "active_power_l2_w",
        "active_power_l3_w",
    ],
    "p1_gas": [
        "captured_at",
        "label",
        "host",
        "total_gas_m3",
        "gas_timestamp",
    ],
    "socket": [
        "captured_at",
        "label",
        "host",
        "total_power_import_kwh",
        "total_power_export_kwh",
        "active_power_w",
        "active_voltage_v",
        "active_current_a",
        "active_reactive_power_var",
        "active_apparent_power_va",
        "power_factor",
        "frequency_hz",
    ],
}


def safe_homewizard_output_name(device: dict[str, Any]) -> str:
    configured = str(device.get("output_name", "")).strip()
    if configured:
        name = Path(configured).name
        if name != configured or name in {".", ".."}:
            raise ValueError(f"Ongeldige HomeWizard output_name: {configured}")
        return name if name.lower().endswith(".csv") else f"{name}.csv"

    role = str(device.get("role", "other"))
    label = str(device.get("label", "")).strip()
    if role == "p1":
        return "P1e.csv"
    if role == "gas":
        return "P1g.csv"
    if role == "socket":
        return f"{label} Skt.csv"
    return f"{label}.csv"


def append_csv_row(path: Path, fieldnames: list[str], row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists() and path.stat().st_size > 0
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow({key: row.get(key, "") for key in fieldnames})


def persist_homewizard_month_rows(snapshot: dict[str, Any]) -> list[str]:
    captured = datetime.fromisoformat(snapshot["captured_at"])
    month_root = OUTPUT_ROOT / "homewizard_monthdata" / f"{captured:%Y_%m}"
    written: list[str] = []

    for device in snapshot.get("devices", []):
        if device.get("status") != "ok":
            continue
        data = dict(device.get("data") or {})
        base_row = {
            "captured_at": snapshot["captured_at"],
            "label": device.get("label", ""),
            "host": device.get("host", ""),
            **data,
        }
        role = str(device.get("role", "other"))
        output_name = str(device.get("output_name", "")).strip()

        if role == "p1":
            electricity_name = output_name or "P1e.csv"
            append_csv_row(
                month_root / electricity_name,
                HOMEWIZARD_CSV_FIELDS["p1_electricity"],
                base_row,
            )
            written.append(str(month_root / electricity_name))

            if "total_gas_m3" in data:
                append_csv_row(
                    month_root / "P1g.csv",
                    HOMEWIZARD_CSV_FIELDS["p1_gas"],
                    base_row,
                )
                written.append(str(month_root / "P1g.csv"))
        elif role == "gas":
            gas_name = output_name or "P1g.csv"
            append_csv_row(
                month_root / gas_name,
                HOMEWIZARD_CSV_FIELDS["p1_gas"],
                base_row,
            )
            written.append(str(month_root / gas_name))
        elif role == "socket":
            socket_name = output_name or f"{device.get('label', '')} Skt.csv"
            append_csv_row(
                month_root / socket_name,
                HOMEWIZARD_CSV_FIELDS["socket"],
                base_row,
            )
            written.append(str(month_root / socket_name))

    return sorted(set(written))



def collect_homewizard_snapshot(options: Options) -> dict[str, Any]:
    timestamp = datetime.now(TZ)
    result: dict[str, Any] = {
        "version": APP_VERSION,
        "captured_at": timestamp.isoformat(),
        "devices": [],
        "errors": [],
        "warnings": [],
    }

    for device in effective_homewizard_devices(options):
        label = str(device.get("label", "")).strip()
        host = str(device.get("host", "")).strip()
        role = str(device.get("role", "other"))
        optional = bool(device.get("optional", False))
        try:
            timeout = min(options.request_timeout_seconds, 30)
            info = homewizard_info(host, timeout)
            payload = homewizard_get(host, timeout)
            output_name = safe_homewizard_output_name(device)
            result["devices"].append({
                "label": label,
                "host": host,
                "role": role,
                "optional": optional,
                "output_name": output_name,
                "status": "ok",
                "device_info": info,
                "data": payload,
            })
        except Exception as exc:
            message = f"{label} ({host}): {exc}"
            if optional:
                result["warnings"].append(message)
                status = "warning"
            else:
                result["errors"].append(message)
                status = "failed"
            result["devices"].append({
                "label": label,
                "host": host,
                "role": role,
                "optional": optional,
                "output_name": str(device.get("output_name", "")).strip(),
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

    written_csv = persist_homewizard_month_rows(snapshot)
    snapshot["month_csv_files"] = written_csv

    path = target / f"HomeWizard_{captured:%Y-%m-%d_%H-%M-%S}.json"
    write_atomic_json(path, snapshot)

    jsonl = target / f"HomeWizard_{captured:%Y_%m}.jsonl"
    with jsonl.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(snapshot, ensure_ascii=False) + "\n")
    return path


def run_homewizard_snapshot() -> dict[str, Any]:
    options = Options.load()
    devices = effective_homewizard_devices(options)
    if not devices:
        raise RuntimeError("Geen HomeWizard-apparaten geconfigureerd of automatisch gekoppeld.")
    snapshot = collect_homewizard_snapshot(options)
    path = save_homewizard_snapshot(snapshot)
    update_state(
        homewizard_last_snapshot=str(path),
        homewizard_last_csv_files=snapshot.get("month_csv_files", []),
        homewizard_last_device_count=len(snapshot.get("devices", [])),
        homewizard_last_error=None if snapshot["status"] != "error" else f"{len(snapshot['errors'])} fout(en)",
    )
    return snapshot


def workflow_source_status(options: Options) -> dict[str, str]:
    status = {"slimmemeterportal": "ready"}
    if options.workflow_mode == "full_month_workflow":
        status.update({
            "homewizard": (
                "ready"
                if effective_homewizard_devices(options)
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
                    expected = expected_count(kind, current, "slimmemeterportal")
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
                        "expected_records": sorted(expected_count(kind, current, "slimmemeterportal")),
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
            report["status"] = "failed"
        elif report["warnings"]:
            report["status"] = "completed_warning"
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
                    report_handoff=None,
                )
            except Exception as exc:
                report_trigger_result = {
                    "status": "error",
                    "triggered_at": datetime.now(TZ).isoformat(),
                    "error": str(exc),
                }
                if options.report_trigger_enabled:
                    report["errors"].append(str(exc))
                    report["status"] = "failed"
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



MONTH_INPUT_ROOT = OUTPUT_ROOT / "01_Input"


def parse_month_key(value: str) -> tuple[int, int]:
    if not re.fullmatch(r"\d{4}_(0[1-9]|1[0-2])", value):
        raise ValueError("Maand moet YYYY_MM zijn.")
    year_text, month_text = value.split("_", 1)
    return int(year_text), int(month_text)


def normalize_number(value: Any) -> Any:
    if isinstance(value, float) and value == 0:
        return 0.0
    return value


def csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.exists() or path.stat().st_size == 0:
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_deduplicated_csv(
    source: Path,
    target: Path,
    *,
    timestamp_field: str = "captured_at",
    transform: Any = None,
) -> dict[str, Any]:
    rows = csv_rows(source)
    seen: set[str] = set()
    output: list[dict[str, Any]] = []
    for row in rows:
        if transform:
            row = transform(dict(row))
        key = str(row.get(timestamp_field, "")).strip() or json.dumps(
            row, ensure_ascii=False, sort_keys=True
        )
        if key in seen:
            continue
        seen.add(key)
        output.append(row)

    target.parent.mkdir(parents=True, exist_ok=True)
    if output:
        fields: list[str] = []
        for row in output:
            for field in row:
                if field not in fields:
                    fields.append(field)
        with target.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(output)
    elif target.exists():
        target.unlink()

    return {
        "source": str(source),
        "target": str(target),
        "source_rows": len(rows),
        "written_rows": len(output),
        "duplicates_removed": len(rows) - len(output),
    }


def transform_enphase_row(row: dict[str, Any]) -> dict[str, Any]:
    try:
        value = float(row.get("value", ""))
    except (TypeError, ValueError):
        return row
    unit = str(row.get("unit", "")).strip().lower()
    if unit == "mwh":
        row["value"] = f"{value * 1000:.6f}".rstrip("0").rstrip(".")
        row["unit"] = "kWh"
    return row


def transform_price_row(row: dict[str, Any]) -> dict[str, Any]:
    try:
        value = float(row.get("value", ""))
    except (TypeError, ValueError):
        return row
    if value == 0:
        row["value"] = "0.0"
    return row


def expected_month_input_files(options: Options) -> list[str]:
    files = [
        "P1e.csv",
        "P1g.csv",
        "Airco Skt.csv",
        "Mobiel Skt.csv",
        "Heater kantoor Skt.csv",
        "Heater woonkamer Skt.csv",
        "Heater lounge Skt.csv",
        "Enphase.csv",
        "Nordpool elektriciteit.csv",
        "NextEnergy actuele stroomprijs.csv",
    ]
    if options.epex_electricity_enabled:
        files.append("EPEX stroom.csv")
    if options.epex_gas_enabled:
        files.append("EPEX gas.csv")
    return files


def build_month_input(month_key: str | None = None) -> dict[str, Any]:
    options = Options.load()
    if not options.month_input_enabled:
        raise RuntimeError("Maandmap-opbouw is uitgeschakeld.")

    month_key = month_key or datetime.now(TZ).strftime("%Y_%m")
    parse_month_key(month_key)

    target = MONTH_INPUT_ROOT / month_key
    target.mkdir(parents=True, exist_ok=True)

    homewizard_root = OUTPUT_ROOT / "homewizard_monthdata" / month_key
    ha_root = OUTPUT_ROOT / "homeassistant_energy" / month_key
    epex_root = OUTPUT_ROOT / "epex_monthdata" / month_key

    source_map: list[tuple[Path, Path, Any]] = []
    for filename in [
        "P1e.csv",
        "P1g.csv",
        "Airco Skt.csv",
        "Mobiel Skt.csv",
        "Heater kantoor Skt.csv",
        "Heater woonkamer Skt.csv",
        "Heater lounge Skt.csv",
    ]:
        source_map.append((homewizard_root / filename, target / filename, None))

    if options.epex_electricity_enabled:
        source_map.append(
            (epex_root / "EPEX stroom.csv", target / "EPEX stroom.csv", None)
        )
    if options.epex_gas_enabled:
        source_map.append(
            (epex_root / "EPEX gas.csv", target / "EPEX gas.csv", None)
        )

    source_map.extend([
        (ha_root / "Enphase.csv", target / "Enphase.csv", transform_enphase_row),
        (
            ha_root / "Nordpool elektriciteit.csv",
            target / "Nordpool elektriciteit.csv",
            transform_price_row,
        ),
        (
            ha_root / "NextEnergy actuele stroomprijs.csv",
            target / "NextEnergy actuele stroomprijs.csv",
            transform_price_row,
        ),
    ])

    results: list[dict[str, Any]] = []
    missing: list[str] = []
    empty: list[str] = []

    for source, destination, transform in source_map:
        if not source.exists():
            missing.append(destination.name)
            continue
        result = write_deduplicated_csv(
            source,
            destination,
            transform=transform,
        )
        results.append(result)
        if result["written_rows"] == 0:
            empty.append(destination.name)

    required: set[str] = set()
    if options.month_input_require_homewizard:
        required.update([
            "P1e.csv",
            "P1g.csv",
            "Airco Skt.csv",
            "Mobiel Skt.csv",
            "Heater kantoor Skt.csv",
            "Heater woonkamer Skt.csv",
            "Heater lounge Skt.csv",
        ])
    if options.month_input_require_enphase:
        required.add("Enphase.csv")
    if options.month_input_require_nordpool:
        required.add("Nordpool elektriciteit.csv")
    if options.epex_electricity_enabled:
        required.add("EPEX stroom.csv")
    if options.epex_gas_enabled:
        required.add("EPEX gas.csv")

    missing_required = sorted(required.intersection(missing))
    empty_required = sorted(required.intersection(empty))
    optional_missing = sorted(set(missing) - set(missing_required))
    optional_empty = sorted(set(empty) - set(empty_required))
    info_messages: list[str] = []

    if optional_missing:
        info_messages.append(
            "Optionele bestanden ontbreken: " + ", ".join(optional_missing)
        )
    if optional_empty:
        info_messages.append(
            "Optionele bestanden zijn leeg: " + ", ".join(optional_empty)
        )

    status = "completed"
    if missing_required or empty_required:
        status = "failed"
    elif info_messages:
        status = "completed_info"

    validation = {
        "version": APP_VERSION,
        "built_at": datetime.now(TZ).isoformat(),
        "month": month_key,
        "status": status,
        "target": str(target),
        "files": results,
        "expected_files": expected_month_input_files(options),
        "missing_files": sorted(missing),
        "empty_files": sorted(empty),
        "missing_required": missing_required,
        "empty_required": empty_required,
        "optional_missing": optional_missing,
        "optional_empty": optional_empty,
        "infos": info_messages,
    }
    write_atomic_json(target / "month_input_validation.json", validation)

    manifest = {
        path.name: {
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "bytes": path.stat().st_size,
        }
        for path in sorted(target.iterdir())
        if path.is_file() and path.name != "month_input_manifest.json"
    }
    write_atomic_json(target / "month_input_manifest.json", manifest)

    zip_path = target.parent / f"01_Input_{month_key}.zip"
    temp_zip = zip_path.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temp_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(target.iterdir()):
            if path.is_file():
                archive.write(path, arcname=str(Path("01_Input") / month_key / path.name))
    temp_zip.replace(zip_path)

    update_state(
        month_input_last_built=validation["built_at"],
        month_input_last_month=month_key,
        month_input_last_status=status,
        month_input_last_error=(
            None if status != "failed"
            else f"Ontbrekend: {', '.join(missing_required)}; leeg: {', '.join(empty_required)}"
        ),
        month_input_last_files=[item["target"] for item in results],
    )
    return {
        **validation,
        "zip": str(zip_path),
        "manifest_file_count": len(manifest),
    }




TRANSFER_SHARE_ROOT = Path("/share")
HOME_ASSISTANT_NOTIFY_URL = (
    "http://supervisor/core/api/services/persistent_notification/create"
)


def notify_home_assistant(title: str, message: str) -> dict[str, Any]:
    token = os.environ.get("SUPERVISOR_TOKEN", "").strip()
    if not token:
        raise RuntimeError("SUPERVISOR_TOKEN ontbreekt; notificatie kon niet worden verstuurd.")
    payload = {
        "title": title,
        "message": message,
        "notification_id": "energie_maandimport",
    }
    request = urllib.request.Request(
        HOME_ASSISTANT_NOTIFY_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": f"Energieproject-Transfer/{APP_VERSION}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            body = response.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as exc:
        raise RuntimeError(f"Home Assistant-notificatie mislukt: {exc}") from exc
    return {
        "status": "ok",
        "http_status": getattr(response, "status", 200),
        "response": body[:1000],
    }


def verify_transfer_copy(source: Path, destination: Path) -> dict[str, Any]:
    source_files = {
        str(path.relative_to(source)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(source.rglob("*"))
        if path.is_file()
    }
    destination_files = {
        str(path.relative_to(destination)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(destination.rglob("*"))
        if path.is_file()
    }
    missing = sorted(set(source_files) - set(destination_files))
    extra = sorted(set(destination_files) - set(source_files))
    mismatched = sorted(
        path for path in set(source_files).intersection(destination_files)
        if source_files[path] != destination_files[path]
    )
    return {
        "status": "ok" if not missing and not extra and not mismatched else "error",
        "source_file_count": len(source_files),
        "destination_file_count": len(destination_files),
        "missing": missing,
        "extra": extra,
        "mismatched": mismatched,
    }


def create_transfer_package(
    month_key: str | None = None,
    *,
    replace_existing: bool = False,
) -> dict[str, Any]:
    options = Options.load()
    if not options.transfer_enabled:
        raise RuntimeError("Overdracht is uitgeschakeld.")

    month_key = month_key or datetime.now(TZ).strftime("%Y_%m")
    parse_month_key(month_key)

    source = MONTH_INPUT_ROOT / month_key
    validation_path = source / "month_input_validation.json"
    if not source.exists():
        raise RuntimeError(
            f"Maandmap ontbreekt: {source}. Bouw eerst de maandmap."
        )
    if not validation_path.exists():
        raise RuntimeError("month_input_validation.json ontbreekt.")

    validation = json.loads(validation_path.read_text(encoding="utf-8"))
    missing_required = list(validation.get("missing_required") or [])
    empty_required = list(validation.get("empty_required") or [])
    validation_acceptable = (
        validation.get("status") in {"completed", "completed_info", "ok"}
        or (
            validation.get("status") == "warning"
            and not missing_required
            and not empty_required
        )
    )
    if options.transfer_require_valid_month and not validation_acceptable:
        raise RuntimeError(
            f"Overdracht geblokkeerd: maandvalidatie is {validation.get('status')} "
            f"(missing_required={missing_required}, empty_required={empty_required})."
        )

    share_folder = Path(options.transfer_share_folder)
    destination_root = TRANSFER_SHARE_ROOT / share_folder
    destination = destination_root / month_key
    staging = destination_root / f".{month_key}.staging"
    backup = destination_root / f".{month_key}.backup"

    allow_replace = bool(
        replace_existing or options.transfer_overwrite_existing
    )

    if destination.exists() and not allow_replace:
        raise RuntimeError(
            f"Doelmap bestaat al en overschrijven is uitgeschakeld: {destination}"
        )

    destination_root.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(staging, ignore_errors=True)
    shutil.rmtree(backup, ignore_errors=True)

    try:
        shutil.copytree(source, staging)
        verification = verify_transfer_copy(source, staging)
        if verification["status"] != "ok":
            raise RuntimeError(
                "Overdracht verificatie mislukt in staging."
            )

        zip_source = source.parent / f"01_Input_{month_key}.zip"
        zip_destination = destination_root / f"01_Input_{month_key}.zip"
        zip_staging = destination_root / f".01_Input_{month_key}.zip.staging"
        zip_backup = destination_root / f".01_Input_{month_key}.zip.backup"

        zip_replaced = False
        if zip_source.exists():
            shutil.copy2(zip_source, zip_staging)
            if hashlib.sha256(zip_source.read_bytes()).hexdigest() != hashlib.sha256(
                zip_staging.read_bytes()
            ).hexdigest():
                raise RuntimeError("ZIP-verificatie mislukt in staging.")

        if destination.exists():
            destination.replace(backup)
        staging.replace(destination)

        if zip_source.exists():
            if zip_destination.exists():
                if not allow_replace:
                    raise RuntimeError(
                        f"Doel-ZIP bestaat al en overschrijven is uitgeschakeld: {zip_destination}"
                    )
                zip_destination.replace(zip_backup)
            zip_staging.replace(zip_destination)
            zip_replaced = True

        shutil.rmtree(backup, ignore_errors=True)
        zip_backup.unlink(missing_ok=True)

    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        if destination.exists() and backup.exists():
            shutil.rmtree(destination, ignore_errors=True)
            backup.replace(destination)
        elif backup.exists() and not destination.exists():
            backup.replace(destination)

        zip_staging = destination_root / f".01_Input_{month_key}.zip.staging"
        zip_backup = destination_root / f".01_Input_{month_key}.zip.backup"
        zip_destination = destination_root / f"01_Input_{month_key}.zip"
        zip_staging.unlink(missing_ok=True)
        if zip_backup.exists():
            zip_destination.unlink(missing_ok=True)
            zip_backup.replace(zip_destination)
        raise

    transfer_manifest = {
        "version": APP_VERSION,
        "created_at": datetime.now(TZ).isoformat(),
        "month": month_key,
        "status": "ok",
        "source": str(source),
        "destination": str(destination),
        "zip": str(zip_destination) if zip_source.exists() else None,
        "verification": verification,
        "month_validation_status": validation.get("status"),
        "month_validation_accepted": validation_acceptable,
        "existing_destination_replaced": bool(replace_existing),
    }
    write_atomic_json(
        destination_root / f"Overdracht_{month_key}.json",
        transfer_manifest,
    )

    year, month = parse_month_key(month_key)
    report_handoff = create_report_handoff(
        year,
        month,
        str(source),
        str(destination),
        str(zip_destination) if zip_source.exists() else None,
        validation,
    )
    transfer_manifest["report_handoff"] = report_handoff

    notification = None
    notification_error = None
    if options.transfer_notify_home_assistant:
        try:
            notification = notify_home_assistant(
                "Energie maandimport gereed",
                (
                    f"Maand {month_key} is gevalideerd en klaargezet in "
                    f"{destination}. Kopieer deze map naar de echte "
                    f"Energie/01_Input/{month_key}-map op de NAS."
                ),
            )
        except Exception as exc:
            notification_error = str(exc)
            LOGGER.warning("Overdracht gereed, maar notificatie mislukt: %s", exc)

    update_state(
        transfer_last_created=transfer_manifest["created_at"],
        transfer_last_month=month_key,
        transfer_last_status="ok",
        transfer_last_path=str(destination),
        transfer_last_error=notification_error,
    )
    return {
        **transfer_manifest,
        "notification": notification,
        "notification_error": notification_error,
    }


FULL_WORKFLOW_RESULT_NAME = "workflow_result.json"


def workflow_previous_month_key() -> str:
    today = datetime.now(TZ).date()
    year, month = previous_month(today)
    return f"{year:04d}_{month:02d}"


def workflow_target_month_key(options: Options) -> str:
    if options.full_workflow_use_previous_month:
        return workflow_previous_month_key()
    if options.target_month:
        return options.target_month.replace("-", "_")
    return datetime.now(TZ).strftime("%Y_%m")



def workflow_lock_snapshot() -> dict[str, Any]:
    with WORKFLOW_LOCK_META:
        return dict(WORKFLOW_ACTIVE)


def set_workflow_lock_state(
    *,
    status: str,
    month: str | None = None,
    step: str | None = None,
    message: str | None = None,
) -> None:
    now = datetime.now(TZ)
    state = load_state()
    started_at = state.get("workflow_lock_started_at")
    duration_seconds = None

    if status != "running" and started_at:
        try:
            duration_seconds = round(
                (now - datetime.fromisoformat(str(started_at))).total_seconds(),
                3,
            )
        except Exception:
            duration_seconds = None

    with WORKFLOW_LOCK_META:
        WORKFLOW_ACTIVE.clear()
        if status == "running":
            WORKFLOW_ACTIVE.update({
                "status": status,
                "started_at": now.isoformat(),
                "month": month,
                "step": step,
                "message": message,
            })

    if status == "running":
        update_state(
            workflow_lock_status="running",
            workflow_lock_started_at=now.isoformat(),
            workflow_lock_month=month,
            workflow_lock_step=step,
            workflow_lock_message=message,
        )
    else:
        update_state(
            workflow_lock_status="idle",
            workflow_lock_started_at=None,
            workflow_lock_month=None,
            workflow_lock_step=None,
            workflow_lock_message=message,
            workflow_lock_last_released=now.isoformat(),
            workflow_lock_last_duration_seconds=duration_seconds,
        )


def update_workflow_lock_step(step: str) -> None:
    with WORKFLOW_LOCK_META:
        if WORKFLOW_ACTIVE:
            WORKFLOW_ACTIVE["step"] = step
    update_state(workflow_lock_step=step)


def coordinated_month_import(
    year: int,
    month: int,
    options: Options,
) -> dict[str, Any]:
    month_iso = f"{year:04d}-{month:02d}"
    deadline = time.monotonic() + options.workflow_import_wait_seconds
    waited = 0.0

    while RUN_LOCK.locked() and time.monotonic() < deadline:
        time.sleep(0.5)
        waited += 0.5

    if RUN_LOCK.locked():
        state = load_state()
        same_month_completed = (
            state.get("status") == "completed"
            and state.get("last_target_month") == month_iso
            and not state.get("last_error")
        )
        if same_month_completed:
            result = {
                "status": "completed_info",
                "mode": "reused_completed_import",
                "month": month_iso,
                "waited_seconds": round(waited, 1),
                "message": "Bestaande afgeronde maandimport is hergebruikt.",
            }
            update_state(workflow_import_coordination_last=result)
            return result
        raise RuntimeError(
            "Maandimport is nog actief na "
            f"{options.workflow_import_wait_seconds} seconden."
        )

    run_import(year, month)
    result = {
        "status": "completed",
        "mode": "started_by_workflow",
        "month": month_iso,
        "waited_seconds": round(waited, 1),
        "message": (
            "Maandimport gestart door workflow."
            if waited == 0
            else "Workflow heeft gewacht op de eerdere import en daarna zelf geïmporteerd."
        ),
    }
    update_state(workflow_import_coordination_last=result)
    return result



def append_workflow_step(
    steps: list[dict[str, Any]],
    *,
    name: str,
    status: str,
    started_at: str,
    finished_at: str,
    result: Any = None,
    error: str | None = None,
) -> None:
    steps.append({
        "name": name,
        "status": status,
        "started_at": started_at,
        "finished_at": finished_at,
        "result": result,
        "error": error,
    })


def run_full_month_workflow(
    month_key: str | None = None,
    *,
    collect_live_snapshots: bool | None = None,
) -> dict[str, Any]:
    options = Options.load()
    if not options.full_workflow_enabled:
        raise RuntimeError("Volledige maandworkflow is uitgeschakeld.")

    month_key = month_key or workflow_target_month_key(options)
    parse_month_key(month_key)
    year, month = parse_month_key(month_key)

    if not WORKFLOW_LOCK.acquire(blocking=False):
        active = workflow_lock_snapshot()
        state = load_state()
        rejected = int(state.get("workflow_lock_rejected_count") or 0) + 1
        update_state(workflow_lock_rejected_count=rejected)
        return {
            "version": APP_VERSION,
            "workflow": "full_month_workflow",
            "status": "busy",
            "month": month_key,
            "active": active,
            "message": "Er draait al een volledige maandworkflow.",
        }

    set_workflow_lock_state(
        status="running",
        month=month_key,
        step="Initialiseren",
        message="Volledige maandworkflow is gestart.",
    )
    current_month_key = datetime.now(TZ).strftime("%Y_%m")
    target_is_current_month = month_key == current_month_key
    if collect_live_snapshots is None:
        collect_live_snapshots = target_is_current_month

    started_monotonic = time.monotonic()
    started_at = datetime.now(TZ).isoformat()
    steps: list[dict[str, Any]] = []
    infos: list[str] = []
    warnings: list[str] = []
    errors: list[str] = []
    failed_step: str | None = None

    def execute_step(
        name: str,
        function: Any,
        *,
        required: bool = True,
    ) -> Any:
        nonlocal failed_step
        step_started = datetime.now(TZ).isoformat()
        update_state(full_workflow_last_step=name)
        update_workflow_lock_step(name)
        try:
            result = function()
            status = "ok"
            if isinstance(result, dict):
                result_status = result.get("status")
                if result_status in {"completed_info", "info", "skipped", "not_configured"}:
                    status = "info"
                elif result_status in {"completed_warning", "warning"}:
                    status = "warning"
                elif result_status in {"failed", "error"}:
                    status = "error"
                elif result_status in {"completed", "ok"}:
                    status = "ok"
            step_finished = datetime.now(TZ).isoformat()
            append_workflow_step(
                steps,
                name=name,
                status=status,
                started_at=step_started,
                finished_at=step_finished,
                result=result,
            )
            if status == "warning":
                warnings.append(f"{name}: waarschuwing")
            if status == "info":
                infos.append(f"{name}: informatie")
            if status == "error":
                message = f"{name}: stap gaf status error"
                errors.append(message)
                failed_step = name
                if required and options.full_workflow_stop_on_error:
                    raise RuntimeError(message)
            return result
        except Exception as exc:
            step_finished = datetime.now(TZ).isoformat()
            already_recorded = bool(
                steps
                and steps[-1].get("name") == name
                and steps[-1].get("status") == "error"
            )
            if not already_recorded:
                append_workflow_step(
                    steps,
                    name=name,
                    status="error",
                    started_at=step_started,
                    finished_at=step_finished,
                    error=str(exc),
                )
            failed_step = name
            error_text = f"{name}: {exc}"
            if error_text not in errors:
                errors.append(error_text)
            if required and options.full_workflow_stop_on_error:
                raise
            warnings.append(f"{name}: overgeslagen na fout")
            return None

    try:
        execute_step(
            "SlimmeMeterPortal API-test",
            test_api,
            required=True,
        )

        execute_step(
            "SlimmeMeterPortal maandimport",
            lambda: coordinated_month_import(year, month, options),
            required=True,
        )

        execute_step(
            "HomeWizard detectie",
            lambda: discover_homewizard_devices(options),
            required=False,
        )

        if collect_live_snapshots and target_is_current_month:
            execute_step(
                "HomeWizard snapshot",
                run_homewizard_snapshot,
                required=True,
            )
            execute_step(
                "Home Assistant energiesnapshot",
                run_homeassistant_energy_snapshot,
                required=True,
            )
        else:
            now_iso = datetime.now(TZ).isoformat()
            append_workflow_step(
                steps,
                name="HomeWizard snapshot",
                status="skipped",
                started_at=now_iso,
                finished_at=now_iso,
                result={
                    "status": "skipped",
                    "reason": (
                        "Historische maand gebruikt reeds opgebouwde "
                        "HomeWizard-maandbestanden."
                    ),
                },
            )
            append_workflow_step(
                steps,
                name="Home Assistant energiesnapshot",
                status="skipped",
                started_at=now_iso,
                finished_at=now_iso,
                result={
                    "status": "skipped",
                    "reason": (
                        "Historische maand gebruikt reeds opgebouwde "
                        "Home Assistant-maandbestanden."
                    ),
                },
            )
            warnings.append(
                "Historische maand: live snapshots niet aan doelmaand toegevoegd."
            )

        if options.full_workflow_run_epex_when_enabled:
            if options.epex_electricity_enabled or options.epex_gas_enabled:
                execute_step(
                    "EPEX import en validatie",
                    lambda: run_epex_import_and_validate(month_key),
                    required=(
                        options.epex_electricity_enabled
                        or options.epex_gas_enabled
                    ),
                )
            else:
                update_state(
                    epex_last_validation_status="not_configured",
                    epex_electricity_last_error=None,
                    epex_gas_last_error=None,
                )
                append_workflow_step(
                    steps,
                    name="EPEX import en validatie",
                    status="info",
                    started_at=datetime.now(TZ).isoformat(),
                    finished_at=datetime.now(TZ).isoformat(),
                    result={
                        "status": "info",
                        "reason": "EPEX-bronnen zijn nog niet geconfigureerd.",
                    },
                )
                infos.append("EPEX is nog niet geconfigureerd.")

        month_result = execute_step(
            "Maandmap bouwen",
            lambda: build_month_input(month_key),
            required=True,
        )

        if isinstance(month_result, dict):
            month_status = month_result.get("status")
            missing_required = list(month_result.get("missing_required") or [])
            empty_required = list(month_result.get("empty_required") or [])
            month_acceptable = (
                month_status in {"completed", "completed_info", "ok"}
                or (
                    month_status == "warning"
                    and not missing_required
                    and not empty_required
                )
            )
            if not month_acceptable:
                failed_step = "Maandmap bouwen"
                raise RuntimeError(
                    f"Maandmapvalidatie is {month_status} "
                    f"(missing_required={missing_required}, "
                    f"empty_required={empty_required})."
                )

        transfer_result = execute_step(
            "Overdrachtspakket maken",
            lambda: create_transfer_package(month_key, replace_existing=True),
            required=True,
        )

        report_handoff = None
        if isinstance(transfer_result, dict):
            report_handoff = transfer_result.get("report_handoff")
            append_workflow_step(
                steps,
                name="Rapportoverdracht voorbereiden",
                status="ok" if report_handoff else "error",
                started_at=datetime.now(TZ).isoformat(),
                finished_at=datetime.now(TZ).isoformat(),
                result=report_handoff or {
                    "status": "error",
                    "error": "report_handoff ontbreekt in overdrachtsresultaat.",
                },
            )
            if not report_handoff:
                errors.append("Rapportoverdracht voorbereiden: report_handoff ontbreekt.")
                failed_step = "Rapportoverdracht voorbereiden"
            else:
                report_result = execute_step(
                    "Rapportgenerator koppelen",
                    lambda: run_report_generation_from_handoff(
                        options,
                        report_handoff["request"],
                    ),
                    required=(options.report_service_enabled or options.report_trigger_enabled),
                )
                if (
                    (options.report_service_enabled or options.report_trigger_enabled)
                    and isinstance(report_result, dict)
                    and report_result.get("status") != "completed"
                ):
                    errors.append("Rapportgenerator koppelen: rapport niet voltooid.")
                    failed_step = "Rapportgenerator koppelen"

        status = "failed" if errors else ("completed_warning" if warnings else "completed")
    except Exception as exc:
        if not errors:
            errors.append(str(exc))
        status = "error"

    finished_at = datetime.now(TZ).isoformat()
    duration_seconds = round(time.monotonic() - started_monotonic, 3)
    result = {
        "version": APP_VERSION,
        "workflow": "full_month_workflow",
        "status": status,
        "month": month_key,
        "target_is_current_month": target_is_current_month,
        "live_snapshots_collected": bool(collect_live_snapshots and target_is_current_month),
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "steps_completed": sum(
            1 for step in steps if step.get("status") in {"ok", "info", "warning"}
        ),
        "steps_total": len(steps),
        "failed_step": failed_step,
        "infos": infos,
        "warnings": warnings,
        "errors": errors,
        "steps": steps,
    }

    result_root = OUTPUT_ROOT / "workflow_results" / month_key
    result_root.mkdir(parents=True, exist_ok=True)
    result_path = result_root / FULL_WORKFLOW_RESULT_NAME
    write_atomic_json(result_path, result)

    update_state(
        full_workflow_last_run=finished_at,
        full_workflow_last_month=month_key,
        full_workflow_last_status=status,
        full_workflow_last_step=failed_step or "Gereed",
        full_workflow_last_result=str(result_path),
        full_workflow_last_error=None if status in {"completed", "completed_warning"} else "; ".join(errors),
    )
    persist_normalized_status(options)

    try:
        if options.transfer_notify_home_assistant:
            if status in {"completed", "completed_warning"}:
                notify_home_assistant(
                    "Energie maandworkflow gereed",
                    (
                        f"Maand {month_key} is volledig verwerkt. "
                        f"Resultaat: {result_path}"
                    ),
                )
            else:
                notify_home_assistant(
                    "Energie maandworkflow mislukt",
                    (
                        f"Maand {month_key} stopte bij "
                        f"{failed_step or 'onbekende stap'}. "
                        f"Fout: {'; '.join(errors)}"
                    ),
                )
    except Exception as exc:
        warnings.append(f"Workflow-notificatie mislukt: {exc}")
        result["warnings"] = warnings
        write_atomic_json(result_path, result)

    set_workflow_lock_state(
        status="idle",
        month=month_key,
        step=failed_step or "Gereed",
        message=(
            "Volledige maandworkflow is afgerond."
            if status in {"completed", "completed_warning"}
            else "; ".join(errors)
        ),
    )
    WORKFLOW_LOCK.release()
    return result



def historical_month_allowed(month_key: str) -> str:
    """Validate and normalize a YYYY_MM month selected by the operator."""
    year, month = parse_month_key(month_key)
    selected = date(year, month, 1)
    current = datetime.now(TZ).date().replace(day=1)
    if selected > current:
        raise ValueError("Een toekomstige maand kan niet worden afgesloten.")
    return f"{year:04d}_{month:02d}"


def operation_status(options: Options | None = None) -> dict[str, Any]:
    """Return one compact operational view without changing workflow state."""
    options = options or Options.load()
    state = persist_normalized_status(options)
    results_root = OUTPUT_ROOT / "workflow_results"
    history: list[dict[str, Any]] = []
    if results_root.exists():
        for month_dir in sorted(
            (p for p in results_root.iterdir() if p.is_dir()),
            key=lambda p: p.name,
            reverse=True,
        )[: options.operation_history_months]:
            result_path = month_dir / FULL_WORKFLOW_RESULT_NAME
            item: dict[str, Any] = {"month": month_dir.name, "status": "unknown"}
            if result_path.is_file():
                try:
                    result = json.loads(result_path.read_text(encoding="utf-8"))
                    item.update({
                        "status": result.get("status", "unknown"),
                        "finished_at": result.get("finished_at"),
                        "duration_seconds": result.get("duration_seconds"),
                        "failed_step": result.get("failed_step"),
                        "steps_completed": result.get("steps_completed"),
                        "steps_total": result.get("steps_total"),
                    })
                except (OSError, json.JSONDecodeError) as exc:
                    item.update({"status": "unreadable", "error": str(exc)})
            history.append(item)
    return {
        "version": APP_VERSION,
        "generated_at": datetime.now(TZ).isoformat(),
        "workflow": {
            "status": state.get("workflow_lock_status"),
            "month": state.get("workflow_lock_month"),
            "step": state.get("workflow_lock_step"),
            "message": state.get("workflow_lock_message"),
        },
        "last_run": {
            "month": state.get("full_workflow_last_month"),
            "status": state.get("full_workflow_last_status"),
            "step": state.get("full_workflow_last_step"),
            "error": state.get("full_workflow_last_error"),
        },
        "automatic_month_close": {
            "enabled": options.automatic_month_close_enabled,
            "day": options.automatic_month_close_day,
            "hour": options.automatic_month_close_hour,
            "last_month": state.get("automatic_month_close_last_month"),
            "last_status": state.get("automatic_month_close_last_status"),
            "last_run": state.get("automatic_month_close_last_run"),
        },
        "history": history,
    }


def automatic_month_close_due(options: Options, now: datetime) -> str | None:
    if not options.automatic_month_close_enabled:
        return None
    if now.day < options.automatic_month_close_day or now.hour < options.automatic_month_close_hour:
        return None
    year, month = previous_month(now.date())
    month_key = f"{year:04d}_{month:02d}"
    state = load_state()
    if state.get("automatic_month_close_last_month") == month_key and state.get("automatic_month_close_last_status") in {"completed", "completed_warning"}:
        return None
    return month_key


def scheduler() -> None:
    startup_handled = False
    last_homewizard_run: datetime | None = None
    last_homeassistant_energy_run: datetime | None = None
    while not STOP.is_set():
        try:
            options = Options.load()

            if effective_homewizard_devices(options):
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

            if options.homeassistant_energy_sampling_enabled:
                now = datetime.now(TZ)
                due = (
                    last_homeassistant_energy_run is None
                    or (now - last_homeassistant_energy_run).total_seconds()
                    >= options.homeassistant_energy_sample_seconds
                )
                if due:
                    try:
                        snapshot = run_homeassistant_energy_snapshot()
                        LOGGER.info(
                            "Home Assistant energiesnapshot: %s bron(nen), status %s.",
                            len(snapshot.get("sources", {})),
                            snapshot.get("status"),
                        )
                    except Exception as exc:
                        LOGGER.error("Home Assistant energiesnapshot mislukt: %s", exc)
                        update_state(homeassistant_energy_last_error=str(exc))
                    last_homeassistant_energy_run = now

            if options.run_on_start and not startup_handled:
                startup_handled = True
                year, month = resolve_month("", options)
                threading.Thread(target=run_import, args=(year, month), daemon=True).start()

            close_month = automatic_month_close_due(options, datetime.now(TZ))
            if close_month and not WORKFLOW_LOCK.locked():
                update_state(
                    automatic_month_close_last_month=close_month,
                    automatic_month_close_last_status="running",
                    automatic_month_close_last_run=datetime.now(TZ).isoformat(),
                )
                result = run_full_month_workflow(close_month, collect_live_snapshots=False)
                update_state(
                    automatic_month_close_last_month=close_month,
                    automatic_month_close_last_status=result.get("status"),
                    automatic_month_close_last_run=datetime.now(TZ).isoformat(),
                )

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
<dt>HomeWizard detectie</dt><dd>{esc((str(state.get("homewizard_discovery_count", 0)) + " apparaat/apparaten") if state.get("homewizard_discovery_last") else state.get("homewizard_discovery_status", "Nog niet uitgevoerd"))}</dd>
<dt>HomeWizard netwerk</dt><dd>{esc(state.get("homewizard_discovery_cidr") or "Niet bepaald")}</dd>
<dt>Home Assistant-koppeling</dt><dd>{esc((str(state.get("homewizard_mapping_count", 0)) + " apparaat/apparaten") if state.get("homewizard_mapping_last") else "Nog niet uitgevoerd")}</dd>
<dt>HA energiesnapshot</dt><dd>{esc(state.get("homeassistant_energy_last_snapshot") or "Nog geen")}</dd>
<dt>Laatste maandmap</dt><dd>{esc((state.get("month_input_last_month") or "Nog geen") + " — " + (state.get("month_input_last_status") or ""))}</dd>
<dt>EPEX-validatie</dt><dd>{esc(state.get("epex_last_validation_status") or "Nog niet uitgevoerd")}</dd>
<dt>Laatste overdracht</dt><dd>{esc((state.get("transfer_last_month") or "Nog geen") + " — " + (state.get("transfer_last_status") or ""))}</dd>
<dt>Overdrachtspad</dt><dd>{esc(state.get("transfer_last_path") or "Nog geen")}</dd>
<dt>Laatste volledige workflow</dt><dd>{esc((state.get("full_workflow_last_month") or "Nog geen") + " — " + (state.get("full_workflow_last_status") or ""))}</dd>
<dt>Workflow-stap</dt><dd>{esc(state.get("full_workflow_last_step") or "Nog niet uitgevoerd")}</dd>
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
<form method="post" action="homewizard-discover" style="margin-top:12px">
<button type="submit">Detecteer HomeWizard-apparaten</button>
<p style="margin:8px 0 0">Scanbereik: instelling <code>homewizard_discovery_cidr</code>.</p>
</form>
<form method="post" action="run-full-month-workflow" style="margin-top:12px">
<input type="month" name="month" value="{esc(default_month)}" required>
<button type="submit">Verwerk maanddata</button>
<p style="margin:8px 0 0">Handmatige test gebruikt de gekozen maand. De geplande maandrun gebruikt de vorige kalendermaand.</p>
</form>
<form method="post" action="run-historical-month" style="margin-top:12px">
<label>Historische maand <input type="month" name="month" value="{esc(default_month)}" required></label>
<button type="submit">Verwerk geselecteerde historische maand</button>
<p style="margin:8px 0 0">Live snapshots worden nooit aan een historische maand toegevoegd.</p>
</form>
<form method="post" action="create-transfer-package" style="margin-top:12px">
<button type="submit">Maak overdrachtspakket</button>
</form>
<form method="post" action="epex-import-validate" style="margin-top:12px">
<button type="submit">Importeer en valideer EPEX</button>
</form>
<form method="post" action="build-month-input" style="margin-top:12px">
<button type="submit">Bouw maandmap</button>
</form>
<form method="post" action="homeassistant-energy-snapshot" style="margin-top:12px">
<button type="submit">Maak HA energiesnapshot</button>
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
<form method="post" action="check-report-runtime" style="margin-top:12px">
<button type="submit">Controleer rapportmodules</button>
</form>
<form method="post" action="build-report-adapter" style="margin-top:12px">
<button type="submit">Bouw rapportdata-adapter</button>
</form>
<form method="post" action="install-report-generators" style="margin-top:12px">
<button type="submit">Installeer officiële rapportgeneratoren</button>
</form>
<form method="post" action="run-report-page1" style="margin-top:12px">
<button type="submit">Test rapportgenerator pagina 1</button>
</form>
<form method="post" action="report-service-check" style="margin-top:12px">
<button type="submit">Controleer rapportservice</button>
</form>
<form method="post" action="run-report-generation" style="margin-top:12px">
<button type="submit">Genereer compleet maandrapport</button>
</form>
<form method="post" action="self-test" style="margin-top:12px">
<button type="submit">Voer volledige zelftest uit</button>
</form></div>
<div class="card"><h2>Bronstatus</h2><ul>{"" .join(f"<li>{esc(k)}: {esc(v)}</li>" for k, v in (state.get("workflow_sources") or {}).items())}</ul></div>
<div class="card"><h2>Downloads</h2><ul>{downloads}</ul></div>
<div class="card"><p>API-key en planning staan op het tabblad <strong>Configuratie</strong>.</p>
<p><a href="status.json">Technische status</a> · <a href="report-generation-status">Rapportstatus</a> · <a href="workflow-audit-status">Eindcontrole</a> · <a href="workflow-summary">Samenvatting</a> · <a href="workflow-lock-status">Workflowstatus</a> · <a href="operation-status">Operationele status</a> · <a href="health">Healthcheck</a></p></div>
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
            body = json.dumps(
                persist_normalized_status(Options.load()),
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
        elif path.endswith("/workflow-lock-status") or path == "/workflow-lock-status":
            state = persist_normalized_status(Options.load())
            body = json.dumps({
                "version": APP_VERSION,
                "status": state.get("workflow_lock_status"),
                "month": state.get("workflow_lock_month"),
                "step": state.get("workflow_lock_step"),
                "started_at": state.get("workflow_lock_started_at"),
                "message": state.get("workflow_lock_message"),
                "rejected_count": state.get("workflow_lock_rejected_count"),
                "last_duration_seconds": state.get("workflow_lock_last_duration_seconds"),
                "import_coordination": state.get("workflow_import_coordination_last"),
            }, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
        elif path.endswith("/workflow-summary") or path == "/workflow-summary":
            state = persist_normalized_status(Options.load())
            body = json.dumps(
                state.get("workflow_summary_last") or {},
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
        elif path.endswith("/workflow-audit-status") or path == "/workflow-audit-status":
            state = persist_normalized_status(Options.load())
            body = json.dumps({
                "version": APP_VERSION,
                "status": state.get("workflow_audit_last_status"),
                "month": state.get("workflow_audit_last_month"),
                "checked_at": state.get("workflow_audit_last_checked"),
                "result": state.get("workflow_audit_last_result"),
                "error": state.get("workflow_audit_last_error"),
            }, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
        elif path.endswith("/report-generation-status") or path == "/report-generation-status":
            state = persist_normalized_status(Options.load())
            body = json.dumps({
                "version": APP_VERSION,
                "status": state.get("report_generation_last_status"),
                "month": state.get("report_generation_last_month"),
                "started": state.get("report_generation_last_started"),
                "finished": state.get("report_generation_last_finished"),
                "response": state.get("report_generation_last_response"),
                "error": state.get("report_generation_last_error"),
            }, ensure_ascii=False, indent=2).encode("utf-8")
            self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
        elif path.endswith("/operation-status") or path == "/operation-status":
            body = json.dumps(
                operation_status(Options.load()),
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
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

        if path.endswith("/run-report-generation") or path == "/run-report-generation":
            state = load_state()
            handoff_path = state.get("report_handoff_last_path")
            if not handoff_path:
                result = {"status": "error", "error": "Geen rapportaanvraag beschikbaar."}
                code = HTTPStatus.BAD_REQUEST
            else:
                try:
                    result = run_report_generation_from_handoff(
                        Options.load(),
                        handoff_path,
                    )
                    code = HTTPStatus.OK if result.get("status") in {"ready", "completed"} else HTTPStatus.BAD_REQUEST
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

        if path.endswith("/check-report-runtime") or path == "/check-report-runtime":
            result = check_report_runtime()
            code = HTTPStatus.OK if result.get("status") == "ok" else HTTPStatus.BAD_REQUEST
            self.send_body(
                code,
                ("<html><meta charset='utf-8'><p>"
                 + html.escape(json.dumps(result, ensure_ascii=False))
                 + "</p><p><a href='./'>Terug</a></p></html>").encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if path.endswith("/build-report-adapter") or path == "/build-report-adapter":
            state = load_state()
            handoff_path = state.get("report_handoff_last_path")
            if not handoff_path:
                result = {"status": "error", "error": "Geen rapportaanvraag beschikbaar."}
                code = HTTPStatus.BAD_REQUEST
            else:
                try:
                    handoff = load_report_handoff(handoff_path)
                    result = build_report_adapter_data(Options.load(), handoff)
                    code = HTTPStatus.OK
                except Exception as exc:
                    result = {"status": "error", "error": str(exc)}
                    code = HTTPStatus.BAD_REQUEST
            self.send_body(
                code,
                ("<html><meta charset='utf-8'><p>"
                 + html.escape(json.dumps(result, ensure_ascii=False))
                 + "</p><p><a href='./'>Terug</a></p></html>").encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if path.endswith("/install-report-generators") or path == "/install-report-generators":
            try:
                result = install_bundled_report_generators(Options.load())
                code = HTTPStatus.OK if result.get("status") == "completed" else HTTPStatus.BAD_REQUEST
            except Exception as exc:
                result = {"status": "error", "error": str(exc)}
                code = HTTPStatus.BAD_REQUEST
            self.send_body(
                code,
                ("<html><meta charset='utf-8'><p>"
                 + html.escape(json.dumps(result, ensure_ascii=False))
                 + "</p><p><a href='./'>Terug</a></p></html>").encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if path.endswith("/run-report-page1") or path == "/run-report-page1":
            state = load_state()
            handoff_path = state.get("report_handoff_last_path")
            if not handoff_path:
                result = {"status": "error", "error": "Geen rapportaanvraag beschikbaar."}
                code = HTTPStatus.BAD_REQUEST
            else:
                try:
                    handoff = load_report_handoff(handoff_path)
                    result = execute_page1_generator(
                        Options.load(),
                        handoff_path,
                        handoff,
                    )
                    code = HTTPStatus.OK if result.get("status") in {"completed", "waiting_for_page_1"} else HTTPStatus.BAD_REQUEST
                except Exception as exc:
                    result = {"status": "error", "error": str(exc)}
                    code = HTTPStatus.BAD_REQUEST
            self.send_body(
                code,
                ("<html><meta charset='utf-8'><p>"
                 + html.escape(json.dumps(result, ensure_ascii=False))
                 + "</p><p><a href='./'>Terug</a></p></html>").encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if path.endswith("/report-service-check") or path == "/report-service-check":
            try:
                result = discover_report_generators(Options.load())
                code = HTTPStatus.OK
            except Exception as exc:
                result = {"status": "error", "error": str(exc)}
                code = HTTPStatus.BAD_REQUEST
            self.send_body(
                code,
                ("<html><meta charset='utf-8'><p>"
                 + html.escape(json.dumps(result, ensure_ascii=False))
                 + "</p><p><a href='./'>Terug</a></p></html>").encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if path.endswith("/self-test") or path == "/self-test":
            try:
                result = run_self_test()
                code = HTTPStatus.OK if result.get("status") != "error" else HTTPStatus.BAD_REQUEST
            except Exception as exc:
                LOGGER.exception("HomeWizard-detectie mislukt.")
                result = {"status": "error", "error": str(exc), "type": type(exc).__name__}
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

        if path.endswith("/homewizard-discover") or path == "/homewizard-discover":
            try:
                result = discover_homewizard_devices(Options.load())
                code = HTTPStatus.OK
            except Exception as exc:
                update_state(
                    homewizard_discovery_error=str(exc),
                    homewizard_discovery_status="error",
                )
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

        if path.endswith("/run-historical-month") or path == "/run-historical-month":
            length = int(self.headers.get("Content-Length", "0") or 0)
            form = parse_qs(self.rfile.read(length).decode("utf-8"))
            selected = (form.get("month") or [""])[0].strip().replace("-", "_")
            try:
                month_key = historical_month_allowed(selected)
                result = run_full_month_workflow(month_key, collect_live_snapshots=False)
                code = HTTPStatus.OK if result.get("status") in {"completed", "completed_warning"} else HTTPStatus.BAD_REQUEST
            except Exception as exc:
                result = {"status": "error", "error": str(exc)}
                code = HTTPStatus.BAD_REQUEST
            self.send_body(
                code,
                ("<html><meta charset='utf-8'><p>" + html.escape(json.dumps(result, ensure_ascii=False)) + "</p><p><a href='./'>Terug</a></p></html>").encode("utf-8"),
                "text/html; charset=utf-8",
            )
            return

        if path.endswith("/run-full-month-workflow") or path == "/run-full-month-workflow":
            try:
                content_length = int(self.headers.get("Content-Length", "0") or 0)
                form_body = self.rfile.read(content_length).decode("utf-8", errors="replace")
                form = parse_qs(form_body)
                selected_month = str((form.get("month") or [""])[0]).strip()
                month_key = (
                    selected_month.replace("-", "_")
                    if selected_month
                    else datetime.now(TZ).strftime("%Y_%m")
                )
                result = run_full_month_workflow(
                    month_key,
                    collect_live_snapshots=True,
                )
                code = HTTPStatus.OK if result.get("status") in {"completed", "completed_warning"} else HTTPStatus.BAD_REQUEST
            except Exception as exc:
                update_state(
                    full_workflow_last_status="error",
                    full_workflow_last_error=str(exc),
                )
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

        if path.endswith("/create-transfer-package") or path == "/create-transfer-package":
            try:
                result = create_transfer_package()
                code = HTTPStatus.OK
            except Exception as exc:
                update_state(
                    transfer_last_status="error",
                    transfer_last_error=str(exc),
                )
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

        if path.endswith("/epex-import-validate") or path == "/epex-import-validate":
            try:
                result = run_epex_import_and_validate()
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

        if path.endswith("/build-month-input") or path == "/build-month-input":
            try:
                result = build_month_input()
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

        if path.endswith("/homeassistant-energy-snapshot") or path == "/homeassistant-energy-snapshot":
            try:
                result = run_homeassistant_energy_snapshot()
                code = HTTPStatus.OK
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
    validate_runtime_dependencies()
    ensure_storage_paths()
    LOGGER.info("Python-app v%s initialiseert.", APP_VERSION)
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    update_state(version=APP_VERSION)
    threading.Thread(target=scheduler, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", 8099), Handler)
    LOGGER.info("SlimmeMeterPortal Import v%s gestart.", APP_VERSION)

    def startup_self_test() -> None:
        try:
            time.sleep(1)
            result = run_self_test()
            LOGGER.info(
                "Automatische zelftest afgerond: %s; installatie_gereed=%s",
                result.get("status"),
                result.get("status") != "error",
            )
        except Exception:
            LOGGER.exception("Automatische zelftest mislukt.")

    threading.Thread(target=startup_self_test, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        STOP.set()
        server.server_close()


if __name__ == "__main__":
    main()
