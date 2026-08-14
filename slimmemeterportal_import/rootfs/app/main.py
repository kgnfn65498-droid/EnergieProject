#!/usr/bin/env python3
from __future__ import annotations

import csv
import html
import io
import json
import subprocess
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
import traceback
import urllib.error
import urllib.request
import socket
import zipfile
from calendar import monthrange
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo
import ipaddress

APP_MODULE_ROOT = Path(__file__).resolve().parent
if str(APP_MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_MODULE_ROOT))
from crash_recovery_export import build_recovery_export, verify_recovery_export, sha256_file

BASE_URL = "https://app.slimmemeterportal.nl"
OPTIONS_PATH = Path("/data/options.json")
AUTO_CLOSE_UI_OPTIONS_PATH = Path("/config/automatic_month_close.json")
OUTPUT_ROOT = Path("/config/output")
STATE_PATH = Path("/config/state.json")
AUTOMATIC_RUN_LEDGER_PATH = Path("/config/output/automatic_run_history.jsonl")
AUTOMATIC_COMPLETION_MARKERS_PATH = Path("/config/output/automatic_completed_months.json")
AUTOMATIC_RETRY_STATE_PATH = Path("/config/output/automatic_retry_state.json")
RETRY_DEBUG_LOG_PATH = Path("/config/output/logs/retry_debug.log")
FINALIZATION_DEBUG_LOG_PATH = Path("/config/output/logs/finalization_debug.log")
PRODUCTION_CERTIFICATE_PATH = Path("/config/output/production_certificate.json")
PRODUCTION_CERTIFICATE_HISTORY_PATH = Path("/config/output/production_certificate_history.jsonl")
PRODUCTION_CERTIFICATE_MANAGEMENT_PATH = Path("/config/output/production_certificate_management.json")
AUDIT_TRAIL_PATH = Path("/config/output/audit_trail.jsonl")
RECOVERY_STATE_PATH = Path("/config/output/recovery_state.json")
RECOVERY_HISTORY_PATH = Path("/config/output/recovery_history.jsonl")
COMPLETE_CRASH_RECOVERY_STATE_PATH = Path("/config/output/complete_crash_recovery_state.json")
CRASH_RECOVERY_EXPORT_ROOT = Path("/config/output/crash_recovery_exports")
MONITORING_STATE_PATH = Path("/config/output/monitoring_state.json")
MONITORING_HISTORY_PATH = Path("/config/output/monitoring_history.jsonl")
TZ = ZoneInfo("Europe/Amsterdam")
APP_VERSION = "32.0.30"
APP_PROCESS_STARTED_AT = datetime.now(TZ)
# v9.8: diagnosepakket verduidelijkt hergebruik van de gecertificeerde productiekern.
# Verhoog deze waarde ALLEEN wanneer workflow/scheduler/retry/certificeringskern inhoudelijk wijzigt.
PRODUCTION_CORE_REVISION = "9.4-core1"

# v32.0.10: eenduidige 24/7 NAS-layout. De fysieke projectroot bevat uitsluitend
# de vaste hoofdmappen App, Data, Backups, Inbox en Infra. De Home Assistant-share
# kan naar de bovenliggende map of rechtstreeks naar EnergieProject wijzen; beide
# mountvormen worden zonder legacy-foldernamen herkend.
NAS_SHARE_ROOT = Path("/share/Energie_NAS")
if (NAS_SHARE_ROOT / "App").is_dir() or (NAS_SHARE_ROOT / "Data").is_dir():
    NAS_LAYOUT_ROOT = NAS_SHARE_ROOT
else:
    NAS_LAYOUT_ROOT = NAS_SHARE_ROOT / "EnergieProject"
NAS_PROJECT_ROOT = NAS_LAYOUT_ROOT / "App"
NAS_DATA_ROOT = NAS_LAYOUT_ROOT / "Data"
PROJECT_BACKUP_ROOT = NAS_LAYOUT_ROOT / "Backups"
NAS_RELEASE_ROOT = NAS_LAYOUT_ROOT / "Inbox"
NAS_INFRA_ROOT = NAS_LAYOUT_ROOT / "Infra"
PROJECT_BACKUP_RETENTION = 3
PROJECT_BACKUP_PREFIX = "EnergieProject_maandbackup"
ENERGIE_MCP_URL = os.environ.get("ENERGIE_MCP_URL", "http://192.168.1.200:8000/mcp").rstrip("/")

GITHUB_PUBLISH_DIR = Path("/config/github_publisher")
GITHUB_PRIVATE_KEY = GITHUB_PUBLISH_DIR / "id_ed25519"
GITHUB_PUBLIC_KEY = GITHUB_PUBLISH_DIR / "id_ed25519.pub"
GITHUB_KNOWN_HOSTS = GITHUB_PUBLISH_DIR / "known_hosts"
GITHUB_PUBLISH_STATE = Path("/config/output/github_publication_state.json")
GITHUB_WORKTREE = GITHUB_PUBLISH_DIR / "worktree"
NAS_RELEASE_INBOX = NAS_RELEASE_ROOT / "incoming"
NAS_RELEASE_PROCESSING = NAS_RELEASE_ROOT / "processing"
NAS_RELEASE_ARCHIVE = NAS_RELEASE_ROOT / "processed"
NAS_RELEASE_FAILED = NAS_RELEASE_ROOT / "failed"
NAS_V10_LAYOUT = {
    "App": NAS_PROJECT_ROOT,
    "Data": NAS_DATA_ROOT,
    "Backups": PROJECT_BACKUP_ROOT,
    "Inbox": NAS_RELEASE_ROOT,
    "Infra": NAS_INFRA_ROOT,
    "incoming": NAS_RELEASE_INBOX,
    "processing": NAS_RELEASE_PROCESSING,
    "processed": NAS_RELEASE_ARCHIVE,
    "failed": NAS_RELEASE_FAILED,
}
LEGACY_NAS_DIRECTORIES = ()


# v7.6.0: automatische maandafsluiting is rechtstreeks vanuit de operationele
# console instelbaar en veilig testbaar. De bestaande maandworkflow blijft gelijk.
WORKFLOW_VISUAL_PHASES = [
    ("SlimmeMeterPortal API-test", 4.0, 0.3),
    ("SlimmeMeterPortal maandimport", 10.0, 1.5),
    ("HomeWizard detectie", 36.0, 8.2),
    ("HomeWizard snapshot", 4.0, 0.5),
    ("Home Assistant energiesnapshot", 3.0, 0.3),
    ("Enphase bronimport", 2.0, 0.3),
    ("EPEX import en validatie", 2.0, 0.3),
    ("Maandmap bouwen", 3.0, 0.3),
    ("Eindvalidatie vóór rapportage", 3.0, 0.3),
    ("Overdrachtspakket maken", 3.0, 0.3),
    ("Rapportgenerator koppelen", 30.0, 6.2),
]
WORKFLOW_VISUAL_TOTAL_STEPS = len(WORKFLOW_VISUAL_PHASES)

BUNDLED_REPORT_GENERATORS = Path("/app/report_generators")

CONFIG_ROOT = Path("/data")


LOGGER = logging.getLogger("slimmemeterportal_import")
STOP = threading.Event()
RUN_LOCK = threading.Lock()
WORKFLOW_LOCK = threading.Lock()
WORKFLOW_LOCK_META = threading.Lock()
WORKFLOW_ACTIVE: dict[str, Any] = {}
STATE_LOCK = threading.RLock()
AUDIT_LOCK = threading.Lock()
MONITORING_LOCK = threading.Lock()
COMPLETE_CRASH_RECOVERY_LOCK = threading.Lock()
COMPLETE_CRASH_RECOVERY_EXPORT_LOCK = threading.Lock()



def cleanup_processed_release_retention_on_app_start(keep: int = 3) -> dict[str, Any]:
    """Keep only the highest semantic EnergieProject release ZIP versions.

    This runs in the HA add-on itself, so it is independent from whichever
    watcher/installer version performed the release installation.
    """
    keep = max(1, int(keep))
    root = NAS_RELEASE_ARCHIVE
    result: dict[str, Any] = {
        "status": "ok",
        "path": str(root),
        "keep": keep,
        "before": 0,
        "after": 0,
        "kept": [],
        "removed": [],
        "ignored": [],
    }
    try:
        root.mkdir(parents=True, exist_ok=True)
        ranked: list[tuple[tuple[int, int, int], Path]] = []
        for candidate in root.glob("EnergieProject_v*.zip"):
            match = re.fullmatch(
                r"EnergieProject_v(\d+)\.(\d+)\.(\d+)\.zip",
                candidate.name,
            )
            if not match:
                result["ignored"].append(candidate.name)
                continue
            version = tuple(int(part) for part in match.groups())
            ranked.append((version, candidate))

        ranked.sort(key=lambda item: item[0], reverse=True)
        result["before"] = len(ranked)
        keep_paths = {path for _, path in ranked[:keep]}

        for _, candidate in ranked[keep:]:
            candidate.unlink()
            result["removed"].append(candidate.name)

        remaining = []
        for candidate in root.glob("EnergieProject_v*.zip"):
            match = re.fullmatch(
                r"EnergieProject_v(\d+)\.(\d+)\.(\d+)\.zip",
                candidate.name,
            )
            if match:
                remaining.append((tuple(int(part) for part in match.groups()), candidate))
        remaining.sort(key=lambda item: item[0], reverse=True)
        result["after"] = len(remaining)
        result["kept"] = [path.name for _, path in remaining]

        if result["after"] > keep:
            result["status"] = "error"
            result["error"] = (
                f"processed-retentie eindcontrole: {result['after']} > {keep}"
            )
        return result
    except Exception as exc:
        result["status"] = "error"
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


class ImportCancelled(Exception):
    """Gecontroleerde annulering van een import of maandworkflow."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


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
    workflow_step_timeout_seconds: int
    workflow_heartbeat_seconds: int
    require_all_core_sources: bool
    epex_require_full_calendar_month: bool
    transfer_enabled: bool
    transfer_share_folder: str
    transfer_overwrite_existing: bool
    transfer_require_valid_month: bool
    transfer_notify_home_assistant: bool
    workflow_notify_home_assistant: bool
    workflow_notify_on_start: bool
    full_workflow_enabled: bool
    full_workflow_use_previous_month: bool
    full_workflow_stop_on_error: bool
    full_workflow_run_epex_when_enabled: bool
    automatic_month_close_enabled: bool
    automatic_month_close_day: int
    automatic_month_close_hour: int
    automatic_month_close_retry_hours: int
    operation_history_months: int

    @classmethod
    def load(cls) -> "Options":
        try:
            raw = json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RuntimeError(f"Optiebestand ontbreekt: {OPTIONS_PATH}") from exc
        # v7.6: vier automatische-maandafsluitingsvelden mogen vanuit de
        # operationele console worden overschreven. De rest van de Home
        # Assistant add-onconfiguratie blijft uitsluitend uit options.json komen.
        try:
            ui_auto = json.loads(AUTO_CLOSE_UI_OPTIONS_PATH.read_text(encoding="utf-8"))
            if isinstance(ui_auto, dict):
                for key in (
                    "automatic_month_close_enabled",
                    "automatic_month_close_day",
                    "automatic_month_close_hour",
                    "automatic_month_close_retry_hours",
                ):
                    if key in ui_auto:
                        raw[key] = ui_auto[key]
        except FileNotFoundError:
            pass
        except Exception as exc:
            LOGGER.warning("UI-instellingen automatische maandafsluiting genegeerd: %s", exc)
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
            workflow_mode="full_month_workflow",  # v32.0.11: HA centrale API-importlaag
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
            workflow_step_timeout_seconds=int(raw.get("workflow_step_timeout_seconds", 900)),
            workflow_heartbeat_seconds=int(raw.get("workflow_heartbeat_seconds", 5)),
            require_all_core_sources=bool(raw.get("require_all_core_sources", True)),
            epex_require_full_calendar_month=bool(raw.get("epex_require_full_calendar_month", True)),
            transfer_enabled=bool(raw.get("transfer_enabled", True)),
            transfer_share_folder=str(raw.get("transfer_share_folder", "Energie_Overdracht")).strip(),
            transfer_overwrite_existing=bool(raw.get("transfer_overwrite_existing", False)),
            transfer_require_valid_month=bool(raw.get("transfer_require_valid_month", True)),
            transfer_notify_home_assistant=bool(raw.get("transfer_notify_home_assistant", True)),
            workflow_notify_home_assistant=bool(raw.get("workflow_notify_home_assistant", True)),
            workflow_notify_on_start=bool(raw.get("workflow_notify_on_start", True)),
            full_workflow_enabled=bool(raw.get("full_workflow_enabled", True)),
            full_workflow_use_previous_month=False,  # v32.0.12: full workflow = lopende maand
            full_workflow_stop_on_error=bool(raw.get("full_workflow_stop_on_error", True)),
            full_workflow_run_epex_when_enabled=bool(raw.get("full_workflow_run_epex_when_enabled", True)),
            automatic_month_close_enabled=bool(raw.get("automatic_month_close_enabled", False)),
            automatic_month_close_day=int(raw.get("automatic_month_close_day", 2)),
            automatic_month_close_hour=int(raw.get("automatic_month_close_hour", 4)),
            automatic_month_close_retry_hours=int(raw.get("automatic_month_close_retry_hours", 6)),
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
        if not 1 <= self.automatic_month_close_retry_hours <= 48:
            raise ValueError("automatic_month_close_retry_hours moet 1 t/m 48 zijn.")
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
        if not 60 <= self.workflow_step_timeout_seconds <= 3600:
            raise ValueError("workflow_step_timeout_seconds moet 60 t/m 3600 zijn.")
        if not 2 <= self.workflow_heartbeat_seconds <= 60:
            raise ValueError("workflow_heartbeat_seconds moet 2 t/m 60 zijn.")
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
        "last_error_type": None,
        "last_traceback": None,
        "smp_nas_transfer_last_status": None,
        "smp_nas_transfer_last_path": None,
        "smp_nas_transfer_last_manifest": None,
        "smp_nas_transfer_last_error": None,
        "last_validation_status": None,
        "next_scheduled_run": None,
        "api_test": None,
        "progress_current": 0,
        "progress_total": 0,
        "progress_message": None,
        "cancel_requested": False,
        "last_cancel_reason": None,
        "last_cancelled_at": None,
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
        "last_pre_report_validation": None,
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
        "audit_trail_last_event": None,
        "audit_trail_last_checked": None,
        "audit_trail_last_status": None,
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
        "full_workflow_last_trigger": None,
        "automatic_month_close_last_attempt": None,
        "automatic_month_close_next_retry": None,
        "automatic_month_close_retry_month": None,
        "automatic_month_close_retry_reason": None,
        "automatic_month_close_retry_origin": None,
        "automatic_month_close_last_preflight": None,
        "automatic_month_close_last_finalization": None,
        "automatic_month_close_test_last_result": None,
        "automatic_scheduler_acceptance_last_result": None,
        "production_acceptance": None,
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



def validate_smp_content_coverage(target: Path, month_key: str) -> dict[str, Any]:
    year, month = parse_month_key(month_key)
    now_local = datetime.now(TZ)
    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])
    is_current_month = (year, month) == (now_local.year, now_local.month)

    if is_current_month:
        calendar_expected_end = min(month_end, now_local.date() - timedelta(days=1))
    elif (year, month) < (now_local.year, now_local.month):
        calendar_expected_end = month_end
    else:
        return {
            "status": "not_due",
            "checked_at": now_local.isoformat(),
            "month": month_key,
            "calendar_expected_through": None,
            "available_through": None,
            "connections_checked": 0,
            "days_expected": 0,
            "days_with_measurements": 0,
            "empty_days": [],
            "missing_days": [],
            "errors": [],
            "warnings": [],
            "meaning": "content_coverage_not_file_integrity",
        }

    errors = []
    warnings = []
    empty_days = []
    missing_days = []
    connection_days = {}

    try:
        connections = json.loads((target / "connections.json").read_text(encoding="utf-8"))
    except Exception as exc:
        return {
            "status": "error",
            "checked_at": now_local.isoformat(),
            "month": month_key,
            "calendar_expected_through": calendar_expected_end.isoformat(),
            "available_through": None,
            "connections_checked": 0,
            "days_expected": 0,
            "days_with_measurements": 0,
            "empty_days": [],
            "missing_days": [],
            "errors": [f"connections.json niet leesbaar: {exc}"],
            "warnings": [],
            "meaning": "content_coverage_not_file_integrity",
        }

    if not isinstance(connections, list) or not connections:
        errors.append("Geen aansluitingen in connections.json.")
        connections = []

    for connection in connections:
        if not isinstance(connection, dict):
            continue
        meter = str(connection.get("meter_identifier", "")).strip()
        ctype = str(connection.get("connection_type", "")).strip().lower()
        if not meter or not ctype:
            errors.append("Aansluiting zonder meter_identifier of connection_type.")
            continue

        start_day = month_start
        raw_start = str(connection.get("start_date") or "").strip()
        if raw_start:
            try:
                start_day = max(start_day, datetime.strptime(raw_start, "%d-%m-%Y").date())
            except ValueError:
                errors.append(f"Ongeldige start_date voor {ctype}/{meter}: {raw_start}")

        keybase = f"{ctype}/{meter}"
        daymap = {}
        day = start_day
        while day <= calendar_expected_end:
            raw_path = target / "raw" / f"{ctype}_{meter}_{day.isoformat()}.json"
            key = f"{keybase}/{day.isoformat()}"
            if not raw_path.is_file():
                daymap[day] = None
                missing_days.append(key)
                day += timedelta(days=1)
                continue
            try:
                payload = json.loads(raw_path.read_text(encoding="utf-8"))
            except Exception as exc:
                daymap[day] = None
                errors.append(f"{key}: JSON niet leesbaar: {exc}")
                day += timedelta(days=1)
                continue
            usages = payload.get("usages") if isinstance(payload, dict) else None
            count = len(usages) if isinstance(usages, list) else 0
            daymap[day] = count
            if count == 0:
                empty_days.append(key)
            day += timedelta(days=1)
        connection_days[keybase] = daymap

    available_through = None
    if connection_days:
        common_days = sorted(set.intersection(*[set(m.keys()) for m in connection_days.values()]))
        for d in common_days:
            if all((connection_days[k].get(d) or 0) > 0 for k in connection_days):
                if available_through is None or d == available_through + timedelta(days=1):
                    available_through = d
                else:
                    break

    validation_end = calendar_expected_end
    if is_current_month and available_through is not None:
        validation_end = available_through

    days_expected = 0
    days_with_measurements = 0
    for keybase, daymap in connection_days.items():
        ctype = keybase.split("/", 1)[0]
        for d, count in sorted(daymap.items()):
            if d > validation_end:
                continue
            days_expected += 1
            if count is None or count == 0:
                errors.append(f"{keybase}/{d.isoformat()}: geen meetrecords binnen verplichte dekkingsreeks.")
                continue
            days_with_measurements += 1
            if ctype == "elektriciteit" and count < 92:
                errors.append(f"{keybase}/{d.isoformat()}: slechts {count} kwartierrecords.")
            elif ctype == "gas" and count < 23:
                errors.append(f"{keybase}/{d.isoformat()}: slechts {count} uurrecords.")

    status = "ok"
    if errors:
        status = "error"
    elif is_current_month and available_through is None:
        status = "error"
        errors.append("Lopende maand bevat nog geen gemeenschappelijke gevulde meetdag.")
    elif is_current_month and available_through < calendar_expected_end:
        status = "partial_current_month"
        lag_days = (calendar_expected_end - available_through).days
        warnings.append(
            f"SlimmeMeterPortal bronvertraging: meetdata beschikbaar t/m {available_through.isoformat()}, "
            f"kalender t/m {calendar_expected_end.isoformat()} ({lag_days} dag(en) achterstand)."
        )

    return {
        "status": status,
        "checked_at": now_local.isoformat(),
        "month": month_key,
        "calendar_expected_through": calendar_expected_end.isoformat(),
        "available_through": available_through.isoformat() if available_through else None,
        "connections_checked": len(connections),
        "days_expected": days_expected,
        "days_with_measurements": days_with_measurements,
        "empty_days": empty_days,
        "missing_days": missing_days,
        "errors": errors,
        "warnings": warnings,
        "meaning": "content_coverage_not_file_integrity",
    }


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


def cancellation_reason() -> str | None:
    state = load_state()
    if bool(state.get("cancel_requested")):
        explicit_reason = str(state.get("workflow_cancel_reason") or "").strip()
        if explicit_reason:
            return explicit_reason
        return "user_requested"
    if STOP.is_set():
        return "service_shutdown"
    return None


def is_cancel_requested() -> bool:
    return cancellation_reason() is not None



def build_usage_path(options: Options, connection_id: str, current: date) -> str:
    return options.usage_path_template.format(
        connection_id=connection_id,
        date=current.strftime("%d-%m-%Y"),
    )


_SMP_IPV4_RESOLVER_LOCK = threading.RLock()

@contextmanager
def _smp_ipv4_only_resolution():
    """Force SlimmeMeterPortal urllib calls through IPv4 only."""
    original = socket.getaddrinfo

    def ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return original(host, port, socket.AF_INET, type or socket.SOCK_STREAM, proto, flags)

    with _SMP_IPV4_RESOLVER_LOCK:
        socket.getaddrinfo = ipv4_getaddrinfo
        try:
            yield
        finally:
            socket.getaddrinfo = original

def _smp_transport_diagnostics() -> dict[str, object]:
    host = urlparse(BASE_URL).hostname or "app.slimmemeterportal.nl"
    result: dict[str, object] = {
        "host": host,
        "transport": "ipv4_forced",
        "ipv4_addresses": [],
        "ipv6_addresses_seen": [],
    }
    try:
        rows = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        result["ipv4_addresses"] = sorted({r[4][0] for r in rows if r[0] == socket.AF_INET})
        result["ipv6_addresses_seen"] = sorted({r[4][0] for r in rows if r[0] == socket.AF_INET6})
    except Exception as exc:
        result["dns_error"] = f"{type(exc).__name__}: {exc}"
    return result

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
            with _smp_ipv4_only_resolution():
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
            "transport": _smp_transport_diagnostics(),
            "endpoint_family": "userapi/v1",
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

        previous_pre_report = load_state().get("last_pre_report_validation")
        if previous_pre_report:
            add(
                "pre_report_validation",
                "ok" if previous_pre_report.get("status") == "ok" else previous_pre_report.get("status", "warning"),
                json.dumps(previous_pre_report, ensure_ascii=False),
            )

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



def validate_pre_report_workflow(
    options: Options,
    month_key: str,
    *,
    historical_mode: bool,
) -> dict[str, Any]:
    """Laatste, maandgebonden controle direct vóór overdracht/rapportage.

    Deze validatie gebruikt uitsluitend de doelmaand. Historische runs eisen geen
    actuele live-bronnen; beschikbare historische detailbronnen worden wel
    gerapporteerd via ``report_input``.
    """
    parse_month_key(month_key)
    month_iso = month_key.replace("_", "-")
    state = load_state()
    errors: list[str] = []
    warnings: list[str] = []
    infos: list[str] = []

    summary = state.get("last_summary") or {}
    if str(summary.get("target_month") or "") != month_iso:
        errors.append(
            "SlimmeMeterPortal maandsamenvatting hoort niet bij de doelmaand "
            f"({summary.get('target_month')!r} != {month_iso!r})."
        )
    totals = summary.get("totals") or {}
    if int(totals.get("error_count") or 0) > 0:
        errors.append("SlimmeMeterPortal maandsamenvatting bevat fouten.")
    if int(totals.get("warning_count") or 0) > 0:
        warnings.append("SlimmeMeterPortal maandsamenvatting bevat waarschuwingen.")

    if state.get("last_integrity_status") not in {"ok", "skipped"}:
        errors.append(
            "Integriteitscontrole van de doelmaand is niet geslaagd: "
            f"{state.get('last_integrity_status')}."
        )

    if state.get("month_input_last_month") != month_key:
        errors.append("01_Input maandmap is niet voor de actuele doelmaand opgebouwd.")
    month_status = state.get("month_input_last_status")
    if month_status not in {"completed", "completed_info", "ok"}:
        errors.append(f"01_Input maandmap heeft ongeldige status: {month_status}.")

    if options.full_workflow_run_epex_when_enabled and (
        options.epex_electricity_enabled or options.epex_gas_enabled
    ):
        epex_status = state.get("epex_last_validation_status")
        if epex_status not in {"ok", "completed"}:
            errors.append(f"EPEX-validatie is niet gereed: {epex_status}.")

    report_input = report_input_readiness(month_key, options)
    if report_input.get("status") != "ready":
        missing = list(report_input.get("missing") or [])
        empty = list(report_input.get("empty") or [])
        detail = ", ".join(missing + empty) or "onbekende detailbron"
        if historical_mode:
            infos.append(
                "Historische rapportinput is niet volledig; rapportage mag "
                f"informatief worden overgeslagen ({detail})."
            )
        elif options.report_service_enabled or options.report_trigger_enabled:
            errors.append(f"Rapportinput voor doelmaand is niet compleet: {detail}.")

    central = validate_central_workflow(options, state, summary)
    if historical_mode:
        # Centrale live-bronvereisten zijn voor historische runs niet leidend;
        # SMP-maanddata en de historische 01_Input-beschikbaarheid zijn leidend.
        live_source_errors = [
            item for item in central.get("errors", [])
            if item.startswith("Geactiveerde bron niet gereed:")
            or item.endswith("snapshot ontbreekt.")
            or item.endswith("-import ontbreekt.")
            or item.endswith("gasimport ontbreekt.")
            or item.endswith("elektriciteitsimport ontbreekt.")
        ]
        if live_source_errors:
            infos.extend(f"Historische live-broncontrole genegeerd: {item}" for item in live_source_errors)
        central_errors = [item for item in central.get("errors", []) if item not in live_source_errors]
    else:
        central_errors = list(central.get("errors", []) or [])
    errors.extend(item for item in central_errors if item not in errors)
    warnings.extend(item for item in (central.get("warnings", []) or []) if item not in warnings)

    result = {
        "version": APP_VERSION,
        "checked_at": datetime.now(TZ).isoformat(),
        "month": month_key,
        "historical_mode": historical_mode,
        "status": "error" if errors else ("warning" if warnings else "ok"),
        "errors": errors,
        "warnings": warnings,
        "infos": infos,
        "report_input": report_input,
        "central_validation": central,
    }
    update_state(last_pre_report_validation=result)
    validation_dir = workflow_result_dir(month_key)
    validation_dir.mkdir(parents=True, exist_ok=True)
    write_atomic_json(validation_dir / "pre_report_validation.json", result)
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


def load_financial_analysis_for_report(input_folder: Path, month_key: str) -> dict[str, Any]:
    """Load only validated financial analysis fields for the requested month.

    Missing data stays missing. EPEX is never promoted to supplier-all-in.
    """
    candidates = [
        input_folder / "Analysis" / f"energieanalyse_{month_key}.json",
        input_folder.parent / "Analysis" / f"energieanalyse_{month_key}.json",
        input_folder / f"energieanalyse_{month_key}.json",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for item in payload.get("months", []):
            if str(item.get("month")) == month_key:
                financial = item.get("financial_context") or {}
                return {
                    "source": str(path),
                    "financial_context": financial,
                    "supplier_context": payload.get("supplier_context") or {},
                }
    return {"source": None, "financial_context": {}, "supplier_context": {}}


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
    report_financial = load_financial_analysis_for_report(input_folder, month_key)
    financial_context = report_financial.get("financial_context") or {}
    supplier_context = report_financial.get("supplier_context") or {}
    financial_projection = financial_context.get("financial_projection") or {}
    projection_detail = financial_context.get("projection_detail") or {}

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

    # v23.5.0: officiële pagina-2-generator krijgt uitsluitend gevalideerde
    # financiële waarden. Voorbeeldtarieven uit het generatorpakket mogen nooit
    # als echte leverancierskosten in een productierapport terechtkomen.
    observed_variable = financial_context.get("observed_variable_electricity_cost_eur")
    observed_weighted_price = financial_context.get("observed_weighted_electricity_price_eur_per_kwh")
    contract_preview = financial_context.get("contract_formula_preview") or {}
    export_preview = contract_preview.get("export") or {}
    gas_preview = contract_preview.get("gas") or {}
    monthly_advance = (supplier_context.get("contract") or {}).get("monthly_advance_eur", 150.0)

    page2["costs"].update({
        "electricity": observed_variable if isinstance(observed_variable, (int, float)) else None,
        "feed_in_compensation": (
            export_preview.get("compensation_eur")
            if export_preview.get("available") is True else None
        ),
        "grid_costs": None,
        "gas": (
            gas_preview.get("supplier_gas_cost_eur")
            if gas_preview.get("available") is True else None
        ),
        "variable_total": None,
        "tariff_t1": observed_weighted_price if isinstance(observed_weighted_price, (int, float)) else None,
        "tariff_t2": observed_weighted_price if isinstance(observed_weighted_price, (int, float)) else None,
        "feed_in_tariff": (
            export_preview.get("effective_compensation_eur_per_kwh")
            if export_preview.get("available") is True else None
        ),
        "gas_tariff": (
            gas_preview.get("effective_price_eur_per_m3")
            if gas_preview.get("available") is True else None
        ),
        "fixed_costs_note": "niet gekoppeld" if not (supplier_context.get("contract_costs") or {}).get("valid") else "contract gevalideerd",
    })

    projected_30d = financial_projection.get("projected_30d_variable_electricity_cost_eur")
    all_in_projection = financial_projection.get("supplier_all_in_projection_eur")
    page2["term"].update({
        "current": float(monthly_advance) if isinstance(monthly_advance, (int, float)) else 150.0,
        "advice": all_in_projection if isinstance(all_in_projection, (int, float)) else None,
        "annual_cost": None,
        "balance": None,
        "coverage_pct": min(100.0, max(0.0, float((financial_context.get("projection_eligibility") or {}).get("coverage_progress_pct") or 0.0))),
    })
    page2["financial_validation"] = {
        "source": report_financial.get("source"),
        "projection_status": financial_projection.get("status"),
        "quality_gate_passed": bool(financial_projection.get("quality_gate_passed")),
        "observed_variable_electricity_cost_eur": observed_variable,
        "projected_30d_variable_electricity_cost_eur": projected_30d,
        "supplier_all_in_projection_eur": all_in_projection,
        "supplier_all_in": bool(financial_projection.get("supplier_all_in")),
        "epex_is_reference_only": True,
        "policy": "official_contract_values_only_no_assumptions",
    }

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
        "financial_report_integration": {
            "analysis_source": report_financial.get("source"),
            "projection_status": financial_projection.get("status"),
            "quality_gate_passed": bool(financial_projection.get("quality_gate_passed")),
            "supplier_all_in": bool(financial_projection.get("supplier_all_in")),
            "epex_is_reference_only": True,
            "example_financial_values_suppressed": True,
        },
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
    days_in_month = monthrange(year, month)[1]
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
    Home Assistant-containerbereik 172.32.0.1/16 als HomeWizard-scanbereik.
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
        if ip in ipaddress.ip_network("172.32.0.1/16"):
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
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(path)


def publish_smp_import_to_nas_input(source: Path, month_key: str) -> dict[str, Any]:
    """Publiceer alleen SMP-bewijs naar Data/01_Input/YYYY_MM/SlimmeMeterPortal."""
    parse_month_key(month_key)
    if not source.is_dir():
        raise RuntimeError(f"SMP-bronmap ontbreekt: {source}")

    destination_month = NAS_DATA_ROOT / "01_Input" / month_key

    # v32.0.18: Home Assistant schrijft niet meer rechtstreeks in de NAS-maandroot.
    # De door de NAS aangemaakte HomeAssistant-submap is de vaste HA-ingress.
    ingress_root = destination_month / "HomeAssistant"
    if not ingress_root.is_dir():
        raise RuntimeError(
            f"HA-ingress ontbreekt voor {month_key}: {ingress_root}. "
            "Laat eerst de normale Home Assistant energiesnapshot/kwartiercollector "
            "de maandmap voorbereiden."
        )

    destination_root = ingress_root / "SlimmeMeterPortal"
    staging = ingress_root / ".SlimmeMeterPortal.staging"
    backup = ingress_root / ".SlimmeMeterPortal.backup"
    if staging.exists():
        if staging.is_dir():
            shutil.rmtree(staging)
        else:
            staging.unlink()
    if backup.exists():
        shutil.rmtree(backup)

    staging.mkdir(parents=True, exist_ok=False)
    copied = 0
    total_bytes = 0

    try:
        for src in sorted(source.rglob("*")):
            if not src.is_file() or src.name == ".incomplete":
                continue
            rel = src.relative_to(source)
            dst = staging / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            if hashlib.sha256(src.read_bytes()).hexdigest() != hashlib.sha256(dst.read_bytes()).hexdigest():
                raise RuntimeError(f"SMP NAS-overdracht checksum fout: {rel}")
            copied += 1
            total_bytes += dst.stat().st_size

        if copied == 0:
            raise RuntimeError("SMP NAS-overdracht bevat geen bestanden.")

        evidence = {
            "version": APP_VERSION,
            "schema": "smp_ha_to_nas_v1",
            "month": month_key,
            "published_at": datetime.now(TZ).isoformat(),
            "source": str(source),
            "destination": str(destination_root),
            "file_count": copied,
            "total_bytes": total_bytes,
            "status": "ok",
        }
        write_atomic_json(staging / "ha_smp_transfer_manifest.json", evidence)

        if destination_root.exists():
            destination_root.replace(backup)
        staging.replace(destination_root)

        if backup.exists():
            shutil.rmtree(backup)

        if not (destination_root / "ha_smp_transfer_manifest.json").is_file():
            raise RuntimeError("SMP NAS-overdracht manifest ontbreekt na publicatie.")
        return evidence
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if backup.exists():
            if destination_root.exists():
                shutil.rmtree(destination_root, ignore_errors=True)
            backup.replace(destination_root)
        raise


def run_import(year: int, month: int) -> None:
    if not RUN_LOCK.acquire(blocking=False):
        raise RuntimeError("Er draait al een import.")
    try:
        options = Options.load()
        month_iso = f"{year:04d}-{month:02d}"
        month_key = f"{year:04d}_{month:02d}"
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
            last_error_type=None,
            last_traceback=None,
            smp_nas_transfer_last_status="running",
            smp_nas_transfer_last_path=None,
            smp_nas_transfer_last_manifest=None,
            smp_nas_transfer_last_error=None,
            last_validation_status=None,
            progress_current=0,
            progress_total=0,
            progress_message="Aansluitingen ophalen",
            cancel_requested=False,
            workflow_cancel_reason=None,
            workflow_sources=workflow_source_status(options),
        )

        connections = api_get("/userapi/v1/connections", options)
        if not isinstance(connections, list) or not connections:
            raise RuntimeError("Geen aansluitingen ontvangen.")
        write_atomic_json(target / "connections.json", connections)
        calendar_days = monthrange(year, month)[1]
        today = datetime.now(TZ).date()
        if year == today.year and month == today.month:
            last_day_to_fetch = today.day
        else:
            last_day_to_fetch = calendar_days
        total_steps = len(connections) * last_day_to_fetch
        completed_steps = 0
        import_started_monotonic = time.monotonic()
        workflow_month_key = f"{year:04d}_{month:02d}"
        update_state(
            progress_total=total_steps,
            progress_current=0,
            progress_message=(
                f"Dagdata ophalen t/m {last_day_to_fetch:02d}-{month:02d}-{year:04d}"
                if last_day_to_fetch < calendar_days
                else "Dagdata ophalen"
            ),
        )
        if last_day_to_fetch < calendar_days and WORKFLOW_LOCK.locked():
            append_workflow_log(
                workflow_month_key, "info", "Huidige maand begrensd tot vandaag",
                last_day=last_day_to_fetch, calendar_days=calendar_days,
            )

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

            for day_number in range(1, last_day_to_fetch + 1):
                current = date(year, month, day_number)
                reason = cancellation_reason()
                if reason:
                    raise ImportCancelled(reason)
                elapsed = time.monotonic() - import_started_monotonic
                if elapsed > options.workflow_step_timeout_seconds:
                    raise RuntimeError(
                        "SlimmeMeterPortal maandimport overschreed de workflow-timeout van "
                        f"{options.workflow_step_timeout_seconds} seconden."
                    )
                raw_path = raw / f"{prefix}_{current.isoformat()}.json"
                if WORKFLOW_LOCK.locked():
                    workflow_heartbeat(
                        workflow_month_key,
                        "SlimmeMeterPortal maandimport",
                        f"{kind}: {current.isoformat()} ophalen",
                        connection_id=identifier,
                        progress_current=completed_steps,
                        progress_total=total_steps,
                    )
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
                    if WORKFLOW_LOCK.locked():
                        append_workflow_log(
                            workflow_month_key, "info", "Dag afgerond",
                            step="SlimmeMeterPortal maandimport",
                            connection_type=kind, date=current.isoformat(),
                            progress_current=completed_steps, progress_total=total_steps,
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
        content_coverage = validate_smp_content_coverage(target, workflow_month_key)
        write_atomic_json(target / "content_coverage_report.json", content_coverage)
        if content_coverage.get("status") == "error":
            central_validation.setdefault("errors", []).extend(
                [f"SMP inhoudsdekking: {item}" for item in content_coverage.get("errors", [])]
            )
            central_validation["status"] = "error"
            central_validation["smp_content_coverage"] = "error"
        else:
            central_validation["smp_content_coverage"] = content_coverage.get("status", "unknown")
            if content_coverage.get("status") == "partial_current_month":
                central_validation.setdefault("warnings", []).extend(
                    [f"SMP inhoudsdekking: {item}" for item in content_coverage.get("warnings", [])]
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

        smp_nas_transfer = publish_smp_import_to_nas_input(target, workflow_month_key)

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
            last_error_type=None if not report["errors"] else "ImportValidationError",
            last_traceback=None,
            last_validation_status=report["status"],
            progress_current=total_steps,
            progress_total=total_steps,
            progress_message="Gereed",
            cancel_requested=False,
            workflow_cancel_reason=None,
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
            smp_nas_transfer_last_status=smp_nas_transfer.get("status"),
            smp_nas_transfer_last_path=smp_nas_transfer.get("destination"),
            smp_nas_transfer_last_manifest=smp_nas_transfer,
            smp_nas_transfer_last_error=None,
        )
    except ImportCancelled as exc:
        reason_text = {
            "user_requested": "Annulering aangevraagd door gebruiker.",
            "service_shutdown": "Import gestopt omdat de add-on wordt afgesloten.",
            "workflow_timeout": "Import gestopt omdat de maximale workflowlooptijd is overschreden.",
        }.get(exc.reason, f"Import geannuleerd: {exc.reason}")
        LOGGER.info("Import gecontroleerd geannuleerd: %s", reason_text)
        update_state(
            status="cancelled",
            last_finished=datetime.now(TZ).isoformat(),
            last_error=None,
            last_validation_status="cancelled",
            progress_message=reason_text,
            cancel_requested=False,
            last_cancel_reason=exc.reason,
            last_cancelled_at=datetime.now(TZ).isoformat(),
            last_error_type="ImportCancelled",
            last_traceback=None,
        )
    except Exception as exc:
        LOGGER.exception("Import mislukt.")
        update_state(
            status="error",
            last_finished=datetime.now(TZ).isoformat(),
            last_error=str(exc),
            last_error_type=type(exc).__name__,
            last_traceback=traceback.format_exc(),
            smp_nas_transfer_last_status="error",
            smp_nas_transfer_last_error=str(exc),
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


# v10.5.6: gestandaardiseerde, read-only analysecontext op basis van de reeds
# opgebouwde maandmappen. Deze laag verandert de maandworkflow niet en schrijft
# geen brondata terug; hij maakt kwartaal- en jaaranalyse machineleesbaar.
ANALYSIS_CONTEXT_SCHEMA = "energie_analysis_context_v1"


def _round_metric(value: float) -> float:
    return round(float(value), 3)


_EPEX_MCP_CACHE: dict[str, str | None] = {}
_MCP_TOOL_CACHE: dict[str, Any] = {}


def _mcp_call_project_tool(name: str, arguments: dict[str, Any], timeout: float = 8.0) -> Any:
    """Roep één read-only Energie-MCP tool aan en normaliseer structured/text JSON."""
    cache_key = json.dumps({"name": name, "arguments": arguments}, sort_keys=True, ensure_ascii=False)
    if cache_key in _MCP_TOOL_CACHE:
        return _MCP_TOOL_CACHE[cache_key]

    request_id = int(time.time() * 1000) % 2147483647
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments,
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {
                    "name": "energieproject-homeassistant",
                    "version": APP_VERSION,
                },
            },
        },
    }
    req = urllib.request.Request(
        ENERGIE_MCP_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2026-07-28",
            "Mcp-Method": "tools/call",
            "Mcp-Name": name,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        envelope = json.loads(raw)
        result = envelope.get("result") or {}
        structured = result.get("structuredContent")
        if structured is not None:
            _MCP_TOOL_CACHE[cache_key] = structured
            return structured

        for block in result.get("content") or []:
            if not isinstance(block, dict) or block.get("type") != "text":
                continue
            text = block.get("text")
            if not isinstance(text, str):
                continue
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError:
                decoded = text
            _MCP_TOOL_CACHE[cache_key] = decoded
            return decoded
    except Exception as exc:
        LOGGER.info("Energie MCP tool %s mislukt: %s", name, exc)

    _MCP_TOOL_CACHE[cache_key] = None
    return None



def _mcp_call_project_action(
    name: str,
    arguments: dict[str, Any],
    timeout: float = 30.0,
) -> Any:
    """Voer één expliciete MCP-actie uit zonder de read-only toolcache te hergebruiken."""
    cache_key = json.dumps(
        {"name": name, "arguments": arguments},
        sort_keys=True,
        ensure_ascii=False,
    )
    _MCP_TOOL_CACHE.pop(cache_key, None)
    try:
        return _mcp_call_project_tool(name, arguments, timeout=timeout)
    finally:
        _MCP_TOOL_CACHE.pop(cache_key, None)


def _complete_recovery_confirmation(value: Any) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            lowered = str(key).lower()
            if isinstance(item, str) and (
                "confirm" in lowered or "bevest" in lowered
            ):
                text = item.strip()
                if text:
                    return text
        for item in value.values():
            found = _complete_recovery_confirmation(item)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = _complete_recovery_confirmation(item)
            if found:
                return found
    return None


def _complete_recovery_zip_name(value: Any) -> str | None:
    if isinstance(value, dict):
        for item in value.values():
            found = _complete_recovery_zip_name(item)
            if found:
                return found
    elif isinstance(value, (list, tuple)):
        for item in value:
            found = _complete_recovery_zip_name(item)
            if found:
                return found
    elif isinstance(value, str):
        match = re.search(r"([^/\\\s]+\.zip)(?:\s|$)", value.strip())
        if match:
            return Path(match.group(1)).name
    return None


def _complete_recovery_state() -> dict[str, Any]:
    try:
        raw = json.loads(
            COMPLETE_CRASH_RECOVERY_STATE_PATH.read_text(encoding="utf-8")
        )
        return raw if isinstance(raw, dict) else {}
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_complete_recovery_state(state: dict[str, Any]) -> None:
    safe = dict(state)
    for key in list(safe):
        lowered = str(key).lower()
        if "confirm" in lowered or "bevest" in lowered:
            safe.pop(key, None)
    write_atomic_json(COMPLETE_CRASH_RECOVERY_STATE_PATH, safe)


def _int_or_zero(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def run_complete_crash_recovery(
    year: int | None = None,
    month: int | None = None,
) -> dict[str, Any]:
    """Maak de bestaande volledige RecoveryManager-backup en deep-verify hem."""
    now = datetime.now(TZ)
    resolved_year = int(year or now.year)
    resolved_month = int(month or now.month)

    if WORKFLOW_LOCK.locked():
        result = {
            "status": "busy",
            "version": APP_VERSION,
            "year": resolved_year,
            "month": resolved_month,
            "error": "Maandworkflow is actief; Crash Recovery is niet gestart.",
            "checked_at": now.isoformat(),
        }
        _save_complete_recovery_state(result)
        return result

    if not COMPLETE_CRASH_RECOVERY_LOCK.acquire(blocking=False):
        return {
            "status": "busy",
            "version": APP_VERSION,
            "year": resolved_year,
            "month": resolved_month,
            "error": "Er loopt al een Crash Recovery-actie.",
            "checked_at": now.isoformat(),
        }

    try:
        _save_complete_recovery_state({
            "status": "running",
            "version": APP_VERSION,
            "year": resolved_year,
            "month": resolved_month,
            "checked_at": datetime.now(TZ).isoformat(),
        })

        preview = _mcp_call_project_action(
            "preview_month_closure",
            {"year": resolved_year, "month": resolved_month},
            timeout=30.0,
        )
        confirmation = _complete_recovery_confirmation(preview)
        if not confirmation:
            raise RuntimeError(
                "RecoveryManager gaf geen geldige bevestiging voor complete backup."
            )

        created = _mcp_call_project_action(
            "create_complete_backup",
            {
                "year": resolved_year,
                "month": resolved_month,
                "confirmation": confirmation,
            },
            timeout=900.0,
        )
        backup_name = _complete_recovery_zip_name(created)
        if not backup_name:
            raise RuntimeError("Nieuwe complete backupnaam kon niet worden vastgesteld.")

        verified = _mcp_call_project_action(
            "verify_complete_backup",
            {
                "year": resolved_year,
                "month": resolved_month,
                "backup_name": backup_name,
                "deep_verify_files": True,
            },
            timeout=900.0,
        )
        if not isinstance(verified, dict):
            verified = {}

        manifest_count = _int_or_zero(verified.get("manifest_file_count"))
        verified_files = _int_or_zero(verified.get("verified_files"))
        hash_failures = verified.get("hash_failures") or []
        if not isinstance(hash_failures, list):
            hash_failures = [str(hash_failures)]

        verify_status = str(verified.get("status") or "").lower()
        deep_verified = bool(verified.get("deep_verified"))
        valid = (
            verify_status in {"valid", "ok", "verified"}
            and deep_verified
            and manifest_count > 0
            and verified_files == manifest_count
            and not hash_failures
        )

        result = {
            "status": "verified" if valid else "error",
            "version": APP_VERSION,
            "year": resolved_year,
            "month": resolved_month,
            "backup_name": backup_name,
            "sha256": str(
                verified.get("backup_sha256")
                or verified.get("sha256")
                or ""
            ),
            "manifest_file_count": manifest_count,
            "verified_files": verified_files,
            "hash_failures": hash_failures,
            "deep_verified": bool(valid),
            "checked_at": datetime.now(TZ).isoformat(),
            "restore_test_status": "not_run",
        }
        if not valid:
            result["error"] = "Deep verification van complete Crash Recovery is niet volledig geslaagd."

        _save_complete_recovery_state(result)
        return result

    except Exception as exc:
        result = {
            "status": "error",
            "version": APP_VERSION,
            "year": resolved_year,
            "month": resolved_month,
            "deep_verified": False,
            "error": f"{type(exc).__name__}: {exc}",
            "checked_at": datetime.now(TZ).isoformat(),
        }
        _save_complete_recovery_state(result)
        return result
    finally:
        COMPLETE_CRASH_RECOVERY_LOCK.release()


def run_complete_restore_staging() -> dict[str, Any]:
    """Test uitsluitend de laatst deep-verified backup in RestoreStaging."""
    state = _complete_recovery_state()

    if WORKFLOW_LOCK.locked():
        return {
            "status": "busy",
            "error": "Maandworkflow is actief; hersteltest is niet gestart.",
            "source_project_modified": False,
        }

    if not COMPLETE_CRASH_RECOVERY_LOCK.acquire(blocking=False):
        return {
            "status": "busy",
            "error": "Er loopt al een Crash Recovery-actie.",
            "source_project_modified": False,
        }

    try:
        if state.get("status") != "verified" or not state.get("deep_verified"):
            return {
                "status": "error",
                "error": "Geen deep-verified complete Crash Recovery beschikbaar.",
                "source_project_modified": False,
            }

        backup_name = str(state.get("backup_name") or "").strip()
        year = _int_or_zero(state.get("year"))
        month = _int_or_zero(state.get("month"))
        if not backup_name or not year or not month:
            return {
                "status": "error",
                "error": "Recoverymetadata is onvolledig.",
                "source_project_modified": False,
            }

        preview = _mcp_call_project_action(
            "preview_backup_restore",
            {"year": year, "month": month, "backup_name": backup_name},
            timeout=30.0,
        )
        confirmation = _complete_recovery_confirmation(preview)
        if not confirmation:
            raise RuntimeError(
                "RecoveryManager gaf geen geldige bevestiging voor RestoreStaging."
            )

        staged = _mcp_call_project_action(
            "stage_backup_restore",
            {
                "year": year,
                "month": month,
                "backup_name": backup_name,
                "confirmation": confirmation,
            },
            timeout=900.0,
        )
        if not isinstance(staged, dict):
            staged = {}

        staging_path = str(
            staged.get("staging")
            or staged.get("staging_path")
            or staged.get("path")
            or ""
        ).strip()
        safe_path = (
            staging_path == "/recovery/RestoreStaging"
            or staging_path.startswith("/recovery/RestoreStaging/")
        )
        source_modified = staged.get("source_project_modified")

        stage_status = str(staged.get("status") or "").lower()
        extracted = _int_or_zero(staged.get("extracted"))
        valid = (
            safe_path
            and source_modified is False
            and (
                stage_status in {"staged", "ok"}
                or extracted > 0
            )
        )

        result = {
            "status": "staged" if valid else "error",
            "backup_name": backup_name,
            "staging_path": staging_path,
            "source_project_modified": bool(source_modified),
            "checked_at": datetime.now(TZ).isoformat(),
        }
        if not valid:
            result["error"] = (
                "Hersteltest voldeed niet aan de geïsoleerde RestoreStaging-veiligheidscontrole."
            )

        updated = dict(state)
        updated["restore_test_status"] = result["status"]
        updated["restore_test_checked_at"] = result["checked_at"]
        updated["restore_staging_path"] = staging_path if safe_path else ""
        updated["source_project_modified"] = bool(source_modified)
        _save_complete_recovery_state(updated)
        return result

    except Exception as exc:
        result = {
            "status": "error",
            "error": f"{type(exc).__name__}: {exc}",
            "source_project_modified": False,
            "checked_at": datetime.now(TZ).isoformat(),
        }
        updated = dict(state)
        updated["restore_test_status"] = "error"
        updated["restore_test_checked_at"] = result["checked_at"]
        updated["restore_test_error"] = result["error"]
        _save_complete_recovery_state(updated)
        return result
    finally:
        COMPLETE_CRASH_RECOVERY_LOCK.release()



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


def _crash_recovery_export_filename(now: datetime) -> str:
    """Bestandsnaam voor browser/iCloud Crash Recovery zonder onveilige dubbele punt."""
    return now.strftime("%Y-%m-%d %H.%M CrashRecovery EnergieProject.zip")


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
            export_name = _crash_recovery_export_filename(datetime.now(TZ))
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


def _mcp_read_project_text(relative_path: str, timeout: float = 6.0) -> str | None:
    """Lees één projecttekstbestand via de read-only Energie MCP op de QNAP."""
    if relative_path in _EPEX_MCP_CACHE:
        return _EPEX_MCP_CACHE[relative_path]

    request_id = int(time.time() * 1000) % 2147483647
    payload = {
        "jsonrpc": "2.0",
        "id": request_id,
        "method": "tools/call",
        "params": {
            "name": "read_text_file",
            "arguments": {"path": relative_path},
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {
                    "name": "energieproject-homeassistant",
                    "version": APP_VERSION,
                },
            },
        },
    }
    req = urllib.request.Request(
        ENERGIE_MCP_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2026-07-28",
            "Mcp-Method": "tools/call",
            "Mcp-Name": "read_text_file",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
        envelope = json.loads(raw)
        result = envelope.get("result") or {}
        structured = result.get("structuredContent")
        text: str | None = None
        if isinstance(structured, dict):
            candidate = structured.get("content")
            if isinstance(candidate, str):
                text = candidate
        if text is None:
            for block in result.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "text":
                    continue
                candidate = block.get("text")
                if not isinstance(candidate, str):
                    continue
                try:
                    decoded = json.loads(candidate)
                    if isinstance(decoded, dict) and isinstance(decoded.get("content"), str):
                        text = decoded["content"]
                    else:
                        text = candidate
                except json.JSONDecodeError:
                    text = candidate
                if text is not None:
                    break
        _EPEX_MCP_CACHE[relative_path] = text
        return text
    except Exception as exc:
        LOGGER.info("Energie MCP read mislukt voor %s: %s", relative_path, exc)
        _EPEX_MCP_CACHE[relative_path] = None
        return None


def _read_epex_text_rows(text: str | None) -> list[dict[str, str]]:
    if not text:
        return []
    try:
        return [dict(row) for row in csv.DictReader(io.StringIO(text.lstrip("\ufeff")), delimiter=";")]
    except csv.Error:
        return []


def _epex_price_stats_rows(rows: list[dict[str, str]], *, unit: str) -> dict[str, Any]:
    fields = ("prijs_excl_btw", "prijs_incl_btw", "prijs_incl_btw_en_eb")
    series: dict[str, list[float]] = {field: [] for field in fields}
    frequencies: set[str] = set()
    for row in rows:
        frequency = str(row.get("frequentie") or "").strip()
        if frequency:
            frequencies.add(frequency)
        for field in fields:
            raw = row.get(field)
            try:
                if raw not in (None, ""):
                    series[field].append(float(str(raw).replace(",", ".")))
            except (TypeError, ValueError):
                continue
    selected = series["prijs_incl_btw_en_eb"]
    if not selected:
        return {
            "available": False, "observations": 0, "average": None, "minimum": None,
            "maximum": None, "price_field": "prijs_incl_btw_en_eb", "unit": unit,
            "frequency": None, "components": {},
        }
    components: dict[str, Any] = {}
    for field, values in series.items():
        if values:
            components[field] = {
                "average": _round_metric(sum(values) / len(values)),
                "minimum": _round_metric(min(values)),
                "maximum": _round_metric(max(values)),
            }
    return {
        "available": True,
        "observations": len(selected),
        "average": _round_metric(sum(selected) / len(selected)),
        "minimum": _round_metric(min(selected)),
        "maximum": _round_metric(max(selected)),
        "price_field": "prijs_incl_btw_en_eb",
        "unit": unit,
        "frequency": sorted(frequencies)[0] if len(frequencies) == 1 else ("mixed" if frequencies else None),
        "components": components,
    }


def _epex_mcp_month_context(month_key: str) -> dict[str, Any] | None:
    month_dash = month_key.replace("_", "-")
    year = month_key[:4]
    mcp_epex_root = "05_Maanddata/EPEX"
    index_text = _mcp_read_project_text(f"{mcp_epex_root}/EPEX_index.csv")
    index_rows = _read_epex_text_rows(index_text)
    if not index_rows:
        mcp_epex_root = "Data/05_Maanddata/EPEX"
        index_text = _mcp_read_project_text(f"{mcp_epex_root}/EPEX_index.csv")
        index_rows = _read_epex_text_rows(index_text)
    if not index_rows:
        return None
    index = {str(row.get("maand") or "").strip(): row for row in index_rows if row.get("maand")}
    index_row = index.get(month_dash, {})
    electricity_rows = _read_epex_text_rows(
        _mcp_read_project_text(f"{mcp_epex_root}/{year}/{month_dash}_stroom.csv")
    )
    gas_rows = _read_epex_text_rows(
        _mcp_read_project_text(f"{mcp_epex_root}/{year}/{month_dash}_gas.csv")
    )
    if not index_row and not electricity_rows and not gas_rows:
        return {
            "source": f"Energie_MCP/{mcp_epex_root}",
            "resolved_path": f"{ENERGIE_MCP_URL} :: {mcp_epex_root}",
            "source_found": True,
            "transport": "mcp_streamable_http_read_only",
            "coverage": {"status": "month_not_available", "first_date": None, "last_date": None, "source_gaps": 0},
            "electricity": {"available": False, "observations": 0, "average": None, "minimum": None, "maximum": None, "price_field": "prijs_incl_btw_en_eb", "unit": "EUR/kWh", "frequency": None, "components": {}},
            "gas": {"available": False, "observations": 0, "average": None, "minimum": None, "maximum": None, "price_field": "prijs_incl_btw_en_eb", "unit": "EUR/m3", "frequency": None, "components": {}},
            "interpretation": "De EPEX-bron is via de Energie MCP bereikbaar, maar voor deze kalendermaand is nog geen EPEX-v6 maandbestand/indexregel beschikbaar.",
        }
    source_gaps_raw = str(index_row.get("bronhiaten") or "").strip()
    try:
        source_gaps = int(source_gaps_raw) if source_gaps_raw else 0
    except ValueError:
        source_gaps = None
    return {
        "source": f"Energie_MCP/{mcp_epex_root}",
        "resolved_path": f"{ENERGIE_MCP_URL} :: {mcp_epex_root}",
        "source_found": True,
        "transport": "mcp_streamable_http_read_only",
        "coverage": {
            "status": str(index_row.get("volledigheid") or "").strip() or "bestanden_aanwezig_zonder_index",
            "first_date": index_row.get("eerste_datum") or None,
            "last_date": index_row.get("laatste_datum") or None,
            "source_gaps": source_gaps,
        },
        "electricity": _epex_price_stats_rows(electricity_rows, unit="EUR/kWh"),
        "gas": _epex_price_stats_rows(gas_rows, unit="EUR/m3"),
        "interpretation": (
            "Prijsstatistiek uit de bestaande EPEX-v6 maandbestanden, read-only via de Energie MCP. "
            "average/minimum/maximum gebruiken prijs_incl_btw_en_eb; dit is geen leverancier-all-in prijs."
        ),
    }


def _resolve_epex_history_root() -> Path | None:
    """Vind EPEX op bekende HA-mounts en via begrensde autodetectie."""
    candidates = (
        NAS_SHARE_ROOT / "05_Maanddata" / "EPEX",
        NAS_SHARE_ROOT / "EPEX",
        NAS_DATA_ROOT / "05_Maanddata" / "EPEX",
        NAS_DATA_ROOT / "EPEX",
        Path("/media/Energie_NAS") / "05_Maanddata" / "EPEX",
        Path("/media/Energie_NAS") / "EPEX",
    )
    for candidate in candidates:
        if (candidate / "EPEX_index.csv").is_file():
            return candidate
    for base in (Path("/share"), Path("/media")):
        if not base.is_dir():
            continue
        try:
            for index_file in base.glob("**/EPEX_index.csv"):
                parent = index_file.parent
                if parent.name == "EPEX":
                    return parent
        except (OSError, PermissionError):
            continue
    return None


EPEX_HISTORY_ROOT = _resolve_epex_history_root()


def _read_epex_rows(path: Path) -> list[dict[str, str]]:
    """Lees de officiële EPEX-v6 maandbestanden (UTF-8 BOM, puntkomma)."""
    if not path.is_file():
        return []
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle, delimiter=";")]
    except (OSError, UnicodeError, csv.Error):
        return []


def _epex_price_stats(path: Path, *, unit: str) -> dict[str, Any]:
    """Vat EPEX-v6 prijsrecords samen met expliciete prijsdefinitie."""
    rows = _read_epex_rows(path)
    fields = ("prijs_excl_btw", "prijs_incl_btw", "prijs_incl_btw_en_eb")
    series: dict[str, list[float]] = {field: [] for field in fields}
    frequencies: set[str] = set()
    for row in rows:
        frequency = str(row.get("frequentie") or "").strip()
        if frequency:
            frequencies.add(frequency)
        for field in fields:
            raw = row.get(field)
            try:
                if raw not in (None, ""):
                    series[field].append(float(str(raw).replace(",", ".")))
            except (TypeError, ValueError):
                continue

    selected = series["prijs_incl_btw_en_eb"]
    if not selected:
        return {
            "available": False,
            "observations": 0,
            "average": None,
            "minimum": None,
            "maximum": None,
            "price_field": "prijs_incl_btw_en_eb",
            "unit": unit,
            "frequency": sorted(frequencies)[0] if len(frequencies) == 1 else None,
            "components": {},
        }

    components: dict[str, Any] = {}
    for field, values in series.items():
        if values:
            components[field] = {
                "average": _round_metric(sum(values) / len(values)),
                "minimum": _round_metric(min(values)),
                "maximum": _round_metric(max(values)),
            }

    return {
        "available": True,
        "observations": len(selected),
        "average": _round_metric(sum(selected) / len(selected)),
        "minimum": _round_metric(min(selected)),
        "maximum": _round_metric(max(selected)),
        "price_field": "prijs_incl_btw_en_eb",
        "unit": unit,
        "frequency": sorted(frequencies)[0] if len(frequencies) == 1 else ("mixed" if frequencies else None),
        "components": components,
    }


def _epex_index() -> dict[str, dict[str, str]]:
    if EPEX_HISTORY_ROOT is None:
        return {}
    path = EPEX_HISTORY_ROOT / "EPEX_index.csv"
    rows = _read_epex_rows(path)
    return {str(row.get("maand") or "").strip(): row for row in rows if row.get("maand")}


def _epex_month_context(month_key: str) -> dict[str, Any]:
    if EPEX_HISTORY_ROOT is None:
        mcp_context = _epex_mcp_month_context(month_key)
        if mcp_context is not None:
            return mcp_context

    year = int(month_key[:4])
    month_dash = month_key.replace("_", "-")
    index_row = _epex_index().get(month_dash, {})
    year_root = EPEX_HISTORY_ROOT / str(year) if EPEX_HISTORY_ROOT is not None else None
    electricity_path = year_root / f"{month_dash}_stroom.csv" if year_root is not None else Path("/nonexistent/epex_stroom.csv")
    gas_path = year_root / f"{month_dash}_gas.csv" if year_root is not None else Path("/nonexistent/epex_gas.csv")

    coverage_status = str(index_row.get("volledigheid") or "").strip() or (
        "bestanden_aanwezig_zonder_index" if electricity_path.is_file() or gas_path.is_file() else "not_available"
    )
    source_gaps_raw = str(index_row.get("bronhiaten") or "").strip()
    try:
        source_gaps = int(source_gaps_raw) if source_gaps_raw else 0
    except ValueError:
        source_gaps = None

    return {
        "source": "05_Maanddata/EPEX",
        "resolved_path": str(EPEX_HISTORY_ROOT) if EPEX_HISTORY_ROOT is not None else None,
        "source_found": EPEX_HISTORY_ROOT is not None,
        "coverage": {
            "status": coverage_status,
            "first_date": index_row.get("eerste_datum") or None,
            "last_date": index_row.get("laatste_datum") or None,
            "source_gaps": source_gaps,
        },
        "electricity": _epex_price_stats(electricity_path, unit="EUR/kWh"),
        "gas": _epex_price_stats(gas_path, unit="EUR/m3"),
        "interpretation": (
            "Prijsstatistiek uit de bestaande EPEX-v6 maandbestanden. "
            "average/minimum/maximum gebruiken 'prijs_incl_btw_en_eb' uit die bron; "
            "dit is geen leverancier-all-in prijs en bevat geen leveranciersopslag of vaste kosten."
        ),
    }


def _month_energy_metrics(month_key: str) -> dict[str, Any]:
    parse_month_key(month_key)
    folder = MONTH_INPUT_ROOT / month_key
    p1e_path = folder / "P1e.csv"
    p1g_path = folder / "P1g.csv"
    enphase_path = folder / "Enphase.csv"
    p1e_rows = read_csv_rows(p1e_path)
    p1g_rows = read_csv_rows(p1g_path)
    enphase_rows = read_csv_rows(enphase_path)

    has_p1e = p1e_path.is_file() and bool(p1e_rows)
    has_p1g = p1g_path.is_file() and bool(p1g_rows)
    has_enphase = enphase_path.is_file() and bool(enphase_rows)

    import_kwh = cumulative_delta(
        p1e_rows,
        ("total_power_import_kwh", "energy_import_kwh", "import_kwh", "meter_reading_import_kwh"),
    ) if has_p1e else None
    export_kwh = cumulative_delta(
        p1e_rows,
        ("total_power_export_kwh", "energy_export_kwh", "export_kwh", "meter_reading_export_kwh"),
    ) if has_p1e else None
    gas_m3 = cumulative_delta(p1g_rows, ("total_gas_m3", "gas_m3", "meter_reading_gas_m3")) if has_p1g else None
    production_kwh = cumulative_delta(
        enphase_rows,
        ("energy_kwh", "lifetime_energy_kwh", "production_kwh", "value_kwh", "value"),
    ) if has_enphase else None

    production_source = "enphase" if has_enphase else "not_available"
    if production_kwh is None and export_kwh is not None and export_kwh > 0:
        production_kwh = export_kwh
        production_source = "export_fallback"

    # Afgeleide zonne-KPI's zijn alleen betrouwbaar wanneer productie en
    # teruglevering dezelfde periode representeren. Een productie lager dan
    # teruglevering is fysiek onmogelijk voor een gelijk meetvenster en wijst
    # dus op onvolledige/asynchrone brondekking. In dat geval: onbekend, geen 0.
    solar_balance_status = "not_available"
    direct_solar_kwh = None
    house_use_kwh = None
    self_use_pct = None
    self_supply_pct = None
    if production_kwh is not None and export_kwh is not None and import_kwh is not None:
        if production_kwh + 1e-6 >= export_kwh:
            solar_balance_status = "ok"
            direct_solar_kwh = max(0.0, production_kwh - export_kwh)
            house_use_kwh = max(0.0, import_kwh + direct_solar_kwh)
            self_use_pct = (direct_solar_kwh / production_kwh * 100.0) if production_kwh > 0 else None
            self_supply_pct = (direct_solar_kwh / house_use_kwh * 100.0) if house_use_kwh > 0 else None
        else:
            solar_balance_status = "inconsistent_period_coverage"

    validation_path = folder / "month_input_validation.json"
    validation: dict[str, Any] = {}
    try:
        if validation_path.is_file():
            validation = json.loads(validation_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        validation = {"status": "unreadable"}

    available_sources = [
        name for name, file_name in (
            ("P1e", "P1e.csv"), ("P1g", "P1g.csv"), ("Enphase", "Enphase.csv"),
        ) if (folder / file_name).is_file()
    ]

    def metric(value: float | None) -> float | None:
        return _round_metric(value) if value is not None else None

    result = {
        "month": month_key,
        "year": int(month_key[:4]),
        "quarter": (int(month_key[5:7]) - 1) // 3 + 1,
        "metrics": {
            "grid_import_kwh": metric(import_kwh),
            "grid_export_kwh": metric(export_kwh),
            "net_grid_kwh": metric((import_kwh - export_kwh) if import_kwh is not None and export_kwh is not None else None),
            "gas_m3": metric(gas_m3),
            "solar_production_kwh": metric(production_kwh),
            "direct_solar_use_kwh": metric(direct_solar_kwh),
            "house_use_kwh": metric(house_use_kwh),
            "self_use_pct": metric(self_use_pct),
            "self_supply_pct": metric(self_supply_pct),
        },
        "price_context": _epex_month_context(month_key),
        "quality": {
            "month_input_validation": validation.get("status") or "not_available",
            "production_source": production_source,
            "solar_balance_status": solar_balance_status,
            "available_sources": available_sources,
            "missing_is_null": True,
        },
    }
    result["financial_context"] = _financial_month_context(result)
    return result


def _financial_month_context(item: dict[str, Any]) -> dict[str, Any]:
    """Conservatieve financiële laag op bewezen maanddekking."""
    metrics = item.get("metrics") or {}
    prices = item.get("price_context") or {}
    electricity_price = (prices.get("electricity") or {}).get("average")
    gas_price = (prices.get("gas") or {}).get("average")
    grid_import = metrics.get("grid_import_kwh")
    gas_m3 = metrics.get("gas_m3")

    electricity_cost = (
        _round_metric(float(grid_import) * float(electricity_price))
        if grid_import is not None and electricity_price is not None else None
    )
    gas_cost = (
        _round_metric(float(gas_m3) * float(gas_price))
        if gas_m3 is not None and gas_price is not None else None
    )
    market_total = (
        _round_metric(sum(v for v in (electricity_cost, gas_cost) if v is not None))
        if electricity_cost is not None or gas_cost is not None else None
    )

    missing = []
    for name, value in (
        ("grid_import_kwh", grid_import),
        ("electricity_price", electricity_price),
        ("gas_m3", gas_m3),
        ("gas_price", gas_price),
    ):
        if value is None:
            missing.append(name)

    return {
        "status": "available" if not missing else ("partial" if market_total is not None else "not_available"),
        "market_variable_cost_estimate_eur": market_total,
        "electricity_import_cost_estimate_eur": electricity_cost,
        "gas_cost_estimate_eur": gas_cost,
        "grid_export_credit_eur": None,
        "supplier_all_in_cost_eur": None,
        "missing_inputs": missing,
        "basis": {
            "electricity": "grid_import_kwh × EPEX gemiddelde prijs_incl_btw_en_eb",
            "gas": "gas_m3 × EPEX gemiddelde prijs_incl_btw_en_eb",
            "export": "niet berekend zonder contractuele terugleververgoeding",
        },
        "limitations": [
            "Geen leveranciersopslag of vaste kosten opgenomen.",
            "Geen terugleververgoeding afgeleid uit afnameprijs.",
            "Alleen bruikbaar wanneer verbruik en prijsdata dezelfde kalendermaand afdekken.",
        ],
    }


def _aggregate_analysis_period(items: list[dict[str, Any]]) -> dict[str, Any]:
    additive = (
        "grid_import_kwh", "grid_export_kwh", "net_grid_kwh", "gas_m3",
        "solar_production_kwh", "direct_solar_use_kwh", "house_use_kwh",
    )
    totals: dict[str, float | None] = {}
    coverage: dict[str, int] = {}
    for key in additive:
        values = [
            float((item.get("metrics") or {}).get(key))
            for item in items
            if (item.get("metrics") or {}).get(key) is not None
        ]
        coverage[key] = len(values)
        totals[key] = _round_metric(sum(values)) if values else None

    solar = totals["solar_production_kwh"]
    house = totals["house_use_kwh"]
    direct = totals["direct_solar_use_kwh"]
    totals["self_use_pct"] = _round_metric(direct / solar * 100.0) if direct is not None and solar not in (None, 0) else None
    totals["self_supply_pct"] = _round_metric(direct / house * 100.0) if direct is not None and house not in (None, 0) else None
    return {
        "months_present": [str(item.get("month")) for item in items],
        "month_count": len(items),
        "metrics": totals,
        "metric_month_coverage": coverage,
    }


def _ha_month_entity_snapshot_series(month_key: str, entity_id: str) -> list[dict[str, Any]]:
    """Lees HA-entiteit uit de definitieve Data-root; MCP blijft read-only fallback."""
    series: list[dict[str, Any]] = []
    local_folders = (
        NAS_DATA_ROOT / "01_Input" / month_key / "HomeAssistant" / "QuarterHour",
        MONTH_INPUT_ROOT / month_key / "HomeAssistant" / "QuarterHour",
    )
    for folder in local_folders:
        if not folder.is_dir():
            continue
        for snapshot in sorted(folder.glob("home_assistant_quarter_*.json")):
            file_match = re.search(r'home_assistant_quarter_(\d{8}T\d{6}Z)\.json$', snapshot.name)
            if not file_match:
                continue
            try:
                payload = json.loads(snapshot.read_text(encoding="utf-8"))
            except Exception:
                continue
            entities = payload.get("entities") if isinstance(payload, dict) else None
            if not isinstance(entities, list):
                continue
            for entity in entities:
                if not isinstance(entity, dict) or entity.get("entity_id") != entity_id:
                    continue
                try:
                    value = float(str(entity.get("state")).replace(",", "."))
                except (TypeError, ValueError):
                    break
                series.append({
                    "snapshot_timestamp": file_match.group(1),
                    "entity_timestamp": entity.get("last_updated") or entity.get("last_changed"),
                    "value": value,
                    "transport": "nas_data_filesystem_read_only" if folder.is_relative_to(NAS_DATA_ROOT) else "local_filesystem_read_only",
                })
                break
        if series:
            dedup = {item["snapshot_timestamp"]: item for item in series}
            return [dedup[key] for key in sorted(dedup)]

    path = f"01_Input/{month_key}/HomeAssistant/QuarterHour"
    files_result = _mcp_call_project_tool(
        "search_files",
        {"path": path, "pattern": "home_assistant_quarter_*.json", "max_results": 500},
        timeout=12.0,
    )
    file_paths: list[str] = []
    if isinstance(files_result, dict):
        items = files_result.get("matches")
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str):
                    file_paths.append(item)
                elif isinstance(item, dict):
                    candidate = item.get("path") or item.get("name")
                    if isinstance(candidate, str):
                        file_paths.append(candidate)
    elif isinstance(files_result, list):
        for item in files_result:
            if isinstance(item, str):
                file_paths.append(item)
            elif isinstance(item, dict):
                candidate = item.get("path") or item.get("relative_path") or item.get("name")
                if isinstance(candidate, str):
                    file_paths.append(candidate)

    for candidate in sorted(set(file_paths)):
        full_path = candidate if candidate.startswith("01_Input/") else f"{path}/{candidate.rsplit('/',1)[-1]}"
        file_match = re.search(r'home_assistant_quarter_(\d{8}T\d{6}Z)\.json$', full_path)
        if not file_match:
            continue
        content_result = _mcp_call_project_tool(
            "read_text_file",
            {"path": full_path},
            timeout=8.0,
        )
        raw = None
        if isinstance(content_result, str):
            raw = content_result
        elif isinstance(content_result, dict):
            for key in ("content", "text", "data"):
                if isinstance(content_result.get(key), str):
                    raw = content_result[key]
                    break
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except Exception:
            continue
        entities = payload.get("entities") if isinstance(payload, dict) else None
        if not isinstance(entities, list):
            continue
        for entity in entities:
            if not isinstance(entity, dict) or entity.get("entity_id") != entity_id:
                continue
            try:
                value = float(str(entity.get("state")).replace(",", "."))
            except (TypeError, ValueError):
                break
            series.append({
                "snapshot_timestamp": file_match.group(1),
                "entity_timestamp": entity.get("last_updated") or entity.get("last_changed"),
                "value": value,
                "transport": "mcp_search_files_read_text_file",
            })
            break

    # Compatibiliteitsfallback voor MCP-servers zonder list_files/read_text resultaatvorm.
    if not series:
        search_result = _mcp_call_project_tool(
            "search_content",
            {"query": entity_id, "path": path, "case_sensitive": True,
             "max_results": 500, "context_lines": 8},
            timeout=12.0,
        )
        if isinstance(search_result, dict):
            for match in search_result.get("matches") or []:
                if not isinstance(match, dict):
                    continue
                path_value = str(match.get("path") or "")
                file_match = re.search(r'home_assistant_quarter_(\d{8}T\d{6}Z)\.json$', path_value)
                if not file_match:
                    continue
                lines = []
                if isinstance(match.get("matching_text"), str):
                    lines.append(match["matching_text"])
                for ctx in match.get("context") or []:
                    if isinstance(ctx, dict) and isinstance(ctx.get("text"), str):
                        lines.append(ctx["text"])
                joined = "\n".join(lines)
                # Entityblok begrenzen zodat een state van een buur-entiteit niet wordt gekoppeld.
                pos = joined.find(entity_id)
                if pos < 0:
                    continue
                window = joined[pos:pos+1200]
                m = re.search(r'"state"\s*:\s*"([-+]?\d+(?:[.,]\d+)?)"', window)
                if not m:
                    continue
                try:
                    value=float(m.group(1).replace(",", "."))
                except ValueError:
                    continue
                series.append({"snapshot_timestamp": file_match.group(1), "entity_timestamp": None, "value": value})

    dedup={item["snapshot_timestamp"]: item for item in series}
    return [dedup[key] for key in sorted(dedup)]




def _nextenergy_consumption_weighted_month(month_key: str) -> dict[str, Any]:
    """Koppel P1-importdelta's aan de NextEnergy-prijs uit dezelfde snapshots."""
    output = {
        "month": month_key, "available": False,
        "price_entity_id": None,
        "import_entity_id": "sensor.p1_meter_energie_import",
        "matched_intervals": 0, "import_kwh_observed": None,
        "weighted_average_eur_per_kwh": None, "observed_import_cost_eur": None,
        "first_snapshot": None, "last_snapshot": None,
        "coverage": "not_available", "transport": "mcp_search_files_read_text_file",
        "quality": "not_available",
        "reader_status": "not_started",
    }
    try:
        price_entity = str(Options.load().nextenergy_entity_id or "").strip()
        output["price_entity_id"] = price_entity or None
        if not price_entity:
            return output
        output["reader_status"] = "reading"
        prices = _ha_month_entity_snapshot_series(month_key, price_entity)
        imports = _ha_month_entity_snapshot_series(month_key, output["import_entity_id"])
        output["price_snapshots_found"] = len(prices)
        output["import_snapshots_found"] = len(imports)
        output["reader_status"] = "series_loaded"
        p = {x["snapshot_timestamp"]: x["value"] for x in prices}
        e = {x["snapshot_timestamp"]: x["value"] for x in imports}
        common = sorted(set(p) & set(e))
        if len(common) < 2:
            return output
        prev = e[common[0]]
        kwh = cost = 0.0
        used = []
        for stamp in common[1:]:
            current = e[stamp]
            delta = current - prev
            prev = current
            if delta <= 0:
                continue
            kwh += delta
            cost += delta * p[stamp]
            used.append(stamp)
        if not used or kwh <= 0:
            return output
        first_dt = datetime.strptime(used[0], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        last_dt = datetime.strptime(used[-1], "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        observed_hours = max((last_dt - first_dt).total_seconds() / 3600.0, 0.0)
        daily_import = (kwh / (observed_hours / 24.0)) if observed_hours > 0 else None
        daily_cost = (cost / (observed_hours / 24.0)) if observed_hours > 0 else None
        output.update({
            "available": True,
            "matched_intervals": len(used),
            "import_kwh_observed": _round_metric(kwh),
            "weighted_average_eur_per_kwh": _round_metric(cost / kwh),
            "observed_import_cost_eur": round(cost, 2),
            "first_snapshot": used[0], "last_snapshot": used[-1],
            "observed_window_hours": _round_metric(observed_hours),
            "observed_daily_import_run_rate_kwh": _round_metric(daily_import) if daily_import is not None else None,
            "observed_daily_variable_cost_run_rate_eur": round(daily_cost, 2) if daily_cost is not None else None,
            "coverage": "partial_observed_window",
            "quality": "consumption_weighted_observed",
            "reader_status": "weighted_ok",
        })
        return output
    except Exception as exc:
        output["quality"] = "error"; output["error"] = str(exc)
        return output


def _nextenergy_month_telemetry(month_key: str) -> dict[str, Any]:
    """Historische NextEnergy-prijsobservaties: NAS/MCP eerst, lokale fallback daarna."""
    result = {
        "month": month_key,
        "available": False,
        "entity_id": None,
        "observations": 0,
        "average_eur_per_kwh": None,
        "minimum_eur_per_kwh": None,
        "maximum_eur_per_kwh": None,
        "first_timestamp": None,
        "last_timestamp": None,
        "source": None,
        "transport": None,
        "quality": "not_available",
    }
    try:
        options = Options.load()
        entity_id = str(options.nextenergy_entity_id or "").strip()
        result["entity_id"] = entity_id or None
        if not entity_id:
            return result

        values: list[float] = []
        timestamps: list[str] = []

        # Primair productiepad na NAS-consolidatie: rechtstreeks uit Data/01_Input.
        nas_folder = NAS_DATA_ROOT / "01_Input" / month_key / "HomeAssistant" / "QuarterHour"
        if nas_folder.is_dir():
            for snapshot in sorted(nas_folder.glob("home_assistant_quarter_*.json")):
                try:
                    payload = json.loads(snapshot.read_text(encoding="utf-8"))
                except Exception:
                    continue
                entities = payload.get("entities") if isinstance(payload, dict) else None
                if not isinstance(entities, list):
                    continue
                for entity in entities:
                    if not isinstance(entity, dict) or entity.get("entity_id") != entity_id:
                        continue
                    try:
                        value = float(str(entity.get("state")).replace(",", "."))
                    except (TypeError, ValueError):
                        continue
                    values.append(value)
                    stamp = entity.get("last_updated") or entity.get("last_changed")
                    if isinstance(stamp, str) and stamp:
                        timestamps.append(stamp)
                    break
            if values:
                result["source"] = str(nas_folder)
                result["transport"] = "nas_data_filesystem_read_only"

        # Read-only MCP fallback voor installaties waar Data niet rechtstreeks gemount is.
        mcp_path = f"01_Input/{month_key}/HomeAssistant/QuarterHour"
        search_result = None
        if not values:
            search_result = _mcp_call_project_tool(
            "search_content",
            {
                "query": entity_id,
                "path": mcp_path,
                "case_sensitive": True,
                "max_results": 500,
                "context_lines": 3,
            },
            timeout=12.0,
        )
        if isinstance(search_result, dict):
            matches = search_result.get("matches") or []
            for match in matches:
                if not isinstance(match, dict):
                    continue
                state_value = None
                timestamp = None
                lines = []
                matching_text = match.get("matching_text")
                if isinstance(matching_text, str):
                    lines.append(matching_text)
                for ctx in match.get("context") or []:
                    if isinstance(ctx, dict) and isinstance(ctx.get("text"), str):
                        lines.append(ctx["text"])

                for line in lines:
                    state_match = re.search(r'"state"\s*:\s*"([-+]?\d+(?:[.,]\d+)?)"', line)
                    if state_match:
                        try:
                            state_value = float(state_match.group(1).replace(",", "."))
                        except ValueError:
                            pass
                    ts_match = re.search(
                        r'"(?:last_updated|last_changed)"\s*:\s*"([^"]+)"',
                        line,
                    )
                    if ts_match:
                        timestamp = ts_match.group(1)

                # Bestandsnaam bevat ook een betrouwbare snapshot-timestamp.
                if not timestamp:
                    path_value = str(match.get("path") or "")
                    file_match = re.search(r'home_assistant_quarter_(\d{8}T\d{6}Z)\.json$', path_value)
                    if file_match:
                        timestamp = file_match.group(1)

                if state_value is not None:
                    values.append(state_value)
                    if timestamp:
                        timestamps.append(timestamp)

            if values:
                result["source"] = mcp_path
                result["transport"] = "mcp_search_content_read_only"

        # Ontwikkel-/fallbackpad: als snapshots lokaal beschikbaar zijn.
        if not values:
            folder = MONTH_INPUT_ROOT / month_key / "HomeAssistant" / "QuarterHour"
            if folder.is_dir():
                for snapshot in sorted(folder.glob("home_assistant_quarter_*.json")):
                    try:
                        payload = json.loads(snapshot.read_text(encoding="utf-8"))
                    except Exception:
                        continue
                    entities = payload.get("entities") if isinstance(payload, dict) else None
                    if not isinstance(entities, list):
                        continue
                    for entity in entities:
                        if not isinstance(entity, dict) or entity.get("entity_id") != entity_id:
                            continue
                        try:
                            value = float(str(entity.get("state")).replace(",", "."))
                        except (TypeError, ValueError):
                            continue
                        values.append(value)
                        stamp = entity.get("last_updated") or entity.get("last_changed")
                        if isinstance(stamp, str) and stamp:
                            timestamps.append(stamp)
                        break
                if values:
                    result["source"] = str(folder)
                    result["transport"] = "local_filesystem_read_only"

        if not values:
            return result

        result.update({
            "available": True,
            "observations": len(values),
            "average_eur_per_kwh": _round_metric(sum(values) / len(values)),
            "minimum_eur_per_kwh": _round_metric(min(values)),
            "maximum_eur_per_kwh": _round_metric(max(values)),
            "first_timestamp": min(timestamps) if timestamps else None,
            "last_timestamp": max(timestamps) if timestamps else None,
            "quality": "observed_unweighted",
        })
        return result
    except Exception as exc:
        result["quality"] = "error"
        result["error"] = str(exc)
        return result


def _supplier_contract_context() -> dict[str, Any]:
    """Bekende contractcontext + live NextEnergy-prijstelemetrie zonder bedragen te verzinnen."""
    contract = {
        "supplier": "NextEnergy",
        "contract_start": "2026-07-15",
        "electricity_pricing": "dynamic",
        "gas_pricing": "variable",
        "monthly_advance_eur": 150.0,
        "termination_notice_workdays": 5,
    }
    live = {
        "available": False,
        "entity_id": None,
        "price_eur_per_kwh": None,
        "unit": None,
        "last_updated": None,
        "error": None,
    }
    try:
        options = Options.load()
        entity_id = str(options.nextenergy_entity_id or "").strip()
        live["entity_id"] = entity_id or None
        if entity_id:
            entity = home_assistant_entity(entity_id)
            attrs = entity.get("attributes") or {}
            live.update({
                "available": True,
                "price_eur_per_kwh": _round_metric(normalized_entity_value(entity)),
                "unit": attrs.get("unit_of_measurement"),
                "last_updated": entity.get("last_updated"),
            })
    except Exception as exc:
        live["error"] = str(exc)

    return {
        "contract": contract,
        "live_electricity_price": live,
        "cost_model": {
            "supplier_fixed_costs_known": False,
            "supplier_markup_known": False,
            "export_compensation_known": False,
            "gas_supplier_formula_known": False,
            "consumption_weighted_import_available": False,
            "projection_ready_months": [],
            "projection_engine": {"stage": "prepared_gated", "target_release": "10.6",
                "current_release_target": "11.1", "thirty_day_variable_projection_logic_ready": True, "supplier_all_in_projection_ready": False, "activation_requires_observed_days": 7.0},
            "projection_observation_status": [],
            "financial_readiness": {"components": {}, "completed_components": 0, "total_components": 0, "progress_pct": 0.0, "decision_ready": False, "next_required_components": []},
            "projection_policy": {"minimum_observed_days": 7.0, "automatic_month_extrapolation": False, "automatic_contract_year_extrapolation": False},
            "all_in_ready": False,
        },
        "interpretation": (
            "Live NextEnergy-prijs is alleen referentie voor actuele dynamische stroomprijs. "
            "Kwartier-snapshots leveren daarnaast historische prijsobservaties voor trendanalyse. "
            "Maandkosten worden pas leverancier-all-in wanneer opslag, vaste kosten, "
            "terugleververgoeding en gasformule officieel zijn gekoppeld."
        ),
    }



CONTRACT_COSTS_FILE = NAS_PROJECT_ROOT / "00_Config" / "nextenergy_contract_costs.json"


def load_nextenergy_contract_costs() -> dict[str, Any]:
    """Lees uitsluitend expliciete NextEnergy-contractwaarden; onbekend blijft null."""
    result: dict[str, Any] = {
        "source": str(CONTRACT_COSTS_FILE),
        "available": False,
        "valid": False,
        "supplier": "NextEnergy",
        "effective_from": None,
        "supplier_fixed_costs_eur_per_month": None,
        "supplier_markup_eur_per_kwh": None,
        "export_compensation_eur_per_kwh": None,
        "export_compensation_formula": None,
        "gas_supplier_formula": None,
        "validation_errors": [],
    }
    if not CONTRACT_COSTS_FILE.is_file():
        result["validation_errors"] = ["contract_costs_file_not_found"]
        return result

    try:
        raw = json.loads(CONTRACT_COSTS_FILE.read_text(encoding="utf-8"))
    except Exception as exc:
        result["validation_errors"] = [f"contract_costs_file_unreadable:{type(exc).__name__}"]
        return result

    if not isinstance(raw, dict):
        result["validation_errors"] = ["contract_costs_file_must_be_json_object"]
        return result

    result["available"] = True
    errors: list[str] = []
    supplier = raw.get("supplier")
    if supplier not in (None, "NextEnergy"):
        errors.append("supplier_must_be_NextEnergy")
    result["supplier"] = supplier or "NextEnergy"

    effective_from = raw.get("effective_from")
    if effective_from is not None and not isinstance(effective_from, str):
        errors.append("effective_from_must_be_string")
    result["effective_from"] = effective_from

    for field in (
        "supplier_fixed_costs_eur_per_month",
        "supplier_markup_eur_per_kwh",
        "export_compensation_eur_per_kwh",
    ):
        value = raw.get(field)
        if value is not None:
            if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
                errors.append(f"{field}_must_be_non_negative_number_or_null")
                value = None
        result[field] = value

    export_formula = raw.get("export_compensation_formula")
    if export_formula is not None and not isinstance(export_formula, dict):
        errors.append("export_compensation_formula_must_be_object_or_null")
        export_formula = None
    if isinstance(export_formula, dict):
        allowed_export = {"type", "markup_eur_per_kwh", "bonus_factor", "notes"}
        unknown_export = sorted(set(export_formula) - allowed_export)
        if unknown_export:
            errors.append("export_compensation_formula_unknown_fields:" + ",".join(unknown_export))
        formula_type = export_formula.get("type")
        if formula_type not in (None, "market_price_minus_markup"):
            errors.append("export_compensation_formula.type_unsupported")
        for key in ("markup_eur_per_kwh", "bonus_factor"):
            value = export_formula.get(key)
            if value is not None and (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or value < 0
            ):
                errors.append(f"export_compensation_formula.{key}_must_be_non_negative_number_or_null")
    result["export_compensation_formula"] = export_formula

    gas_formula = raw.get("gas_supplier_formula")
    if gas_formula is not None and not isinstance(gas_formula, dict):
        errors.append("gas_supplier_formula_must_be_object_or_null")
        gas_formula = None
    if isinstance(gas_formula, dict):
        allowed = {"type", "fixed_eur_per_m3", "markup_eur_per_m3", "notes"}
        unknown = sorted(set(gas_formula) - allowed)
        if unknown:
            errors.append("gas_supplier_formula_unknown_fields:" + ",".join(unknown))
        if gas_formula.get("type") not in (None, "fixed", "market_price_plus_markup"):
            errors.append("gas_supplier_formula.type_unsupported")
        for key in ("fixed_eur_per_m3", "markup_eur_per_m3"):
            value = gas_formula.get(key)
            if value is not None and (
                not isinstance(value, (int, float))
                or isinstance(value, bool)
                or value < 0
            ):
                errors.append(f"gas_supplier_formula.{key}_must_be_non_negative_number_or_null")
    result["gas_supplier_formula"] = gas_formula
    result["validation_errors"] = errors
    result["valid"] = not errors
    return result


def build_contract_validation_status(contract_costs: dict[str, Any]) -> dict[str, Any]:
    """Maak expliciet zichtbaar welke officiële all-in contractcomponenten ontbreken."""
    component_checks = {
        "supplier_fixed_costs": isinstance(contract_costs.get("supplier_fixed_costs_eur_per_month"), (int, float)),
        "supplier_markup": isinstance(contract_costs.get("supplier_markup_eur_per_kwh"), (int, float)),
        "export_compensation": (
            isinstance(contract_costs.get("export_compensation_eur_per_kwh"), (int, float))
            or isinstance(contract_costs.get("export_compensation_formula"), dict)
        ),
        "gas_supplier_formula": isinstance(contract_costs.get("gas_supplier_formula"), dict),
    }
    missing = [key for key, value in component_checks.items() if not value]
    file_valid = bool(contract_costs.get("valid"))
    return {
        "schema": "nextenergy_contract_validation_v1",
        "file_available": bool(contract_costs.get("available")),
        "file_valid": file_valid,
        "effective_from": contract_costs.get("effective_from"),
        "components": component_checks,
        "validated_component_count": sum(1 for value in component_checks.values() if value),
        "required_component_count": len(component_checks),
        "missing_components": missing,
        "all_required_components_present": bool(file_valid and not missing),
        "validation_errors": list(contract_costs.get("validation_errors") or []),
        "policy": "official_contract_values_only_no_assumptions",
    }


def apply_nextenergy_contract_costs(supplier_context: dict[str, Any]) -> None:
    """Koppel alleen gevalideerde contractcomponenten aan het cost model."""
    contract_costs = load_nextenergy_contract_costs()
    supplier_context["contract_costs"] = contract_costs
    supplier_context["contract_validation"] = build_contract_validation_status(contract_costs)
    model = supplier_context.setdefault("cost_model", {})

    if not contract_costs.get("valid"):
        model["supplier_fixed_costs_known"] = False
        model["supplier_markup_known"] = False
        model["export_compensation_known"] = False
        model["gas_supplier_formula_known"] = False
        return

    model["supplier_fixed_costs_known"] = isinstance(
        contract_costs.get("supplier_fixed_costs_eur_per_month"), (int, float)
    )
    model["supplier_markup_known"] = isinstance(
        contract_costs.get("supplier_markup_eur_per_kwh"), (int, float)
    )
    model["export_compensation_known"] = (
        isinstance(contract_costs.get("export_compensation_eur_per_kwh"), (int, float))
        or isinstance(contract_costs.get("export_compensation_formula"), dict)
    )
    model["gas_supplier_formula_known"] = isinstance(
        contract_costs.get("gas_supplier_formula"), dict
    )



def calculate_export_compensation(
    export_kwh: float | None,
    market_price_eur_per_kwh: float | None,
    contract_costs: dict[str, Any],
) -> dict[str, Any]:
    """Bereken alleen met expliciet gevalideerde contractregels; anders null."""
    result = {
        "available": False,
        "export_kwh": export_kwh,
        "market_price_eur_per_kwh": market_price_eur_per_kwh,
        "compensation_eur": None,
        "effective_compensation_eur_per_kwh": None,
        "method": None,
        "reason": None,
    }
    if not isinstance(export_kwh, (int, float)) or export_kwh < 0:
        result["reason"] = "export_kwh_not_available"
        return result

    flat = contract_costs.get("export_compensation_eur_per_kwh")
    if isinstance(flat, (int, float)):
        result["available"] = True
        result["method"] = "flat_contract_rate"
        result["effective_compensation_eur_per_kwh"] = round(float(flat), 6)
        result["compensation_eur"] = round(float(export_kwh) * float(flat), 2)
        return result

    formula = contract_costs.get("export_compensation_formula")
    if not isinstance(formula, dict):
        result["reason"] = "export_compensation_contract_rule_not_available"
        return result
    if formula.get("type") != "market_price_minus_markup":
        result["reason"] = "export_compensation_formula_unsupported"
        return result
    if not isinstance(market_price_eur_per_kwh, (int, float)):
        result["reason"] = "market_price_not_available"
        return result

    markup = formula.get("markup_eur_per_kwh")
    bonus_factor = formula.get("bonus_factor")
    if markup is None:
        markup = 0.0
    if bonus_factor is None:
        bonus_factor = 1.0
    if not isinstance(markup, (int, float)) or not isinstance(bonus_factor, (int, float)):
        result["reason"] = "export_compensation_formula_incomplete"
        return result

    effective = (float(market_price_eur_per_kwh) - float(markup)) * float(bonus_factor)
    result["available"] = True
    result["method"] = "market_price_minus_markup"
    result["effective_compensation_eur_per_kwh"] = round(effective, 6)
    result["compensation_eur"] = round(float(export_kwh) * effective, 2)
    return result


def calculate_gas_supplier_cost(
    gas_m3: float | None,
    market_price_eur_per_m3: float | None,
    contract_costs: dict[str, Any],
) -> dict[str, Any]:
    """Gasberekening blijft geblokkeerd zonder expliciete contractformule."""
    result = {
        "available": False,
        "gas_m3": gas_m3,
        "market_price_eur_per_m3": market_price_eur_per_m3,
        "supplier_gas_cost_eur": None,
        "effective_price_eur_per_m3": None,
        "method": None,
        "reason": None,
    }
    if not isinstance(gas_m3, (int, float)) or gas_m3 < 0:
        result["reason"] = "gas_m3_not_available"
        return result
    formula = contract_costs.get("gas_supplier_formula")
    if not isinstance(formula, dict):
        result["reason"] = "gas_supplier_formula_not_available"
        return result

    formula_type = formula.get("type")
    fixed = formula.get("fixed_eur_per_m3")
    markup = formula.get("markup_eur_per_m3")

    if formula_type == "fixed":
        if not isinstance(fixed, (int, float)):
            result["reason"] = "gas_fixed_rate_not_available"
            return result
        effective = float(fixed)
    elif formula_type == "market_price_plus_markup":
        if not isinstance(market_price_eur_per_m3, (int, float)):
            result["reason"] = "gas_market_price_not_available"
            return result
        if markup is None:
            markup = 0.0
        if not isinstance(markup, (int, float)):
            result["reason"] = "gas_markup_invalid"
            return result
        effective = float(market_price_eur_per_m3) + float(markup)
    else:
        result["reason"] = "gas_supplier_formula_unsupported"
        return result

    result["available"] = True
    result["method"] = formula_type
    result["effective_price_eur_per_m3"] = round(effective, 6)
    result["supplier_gas_cost_eur"] = round(float(gas_m3) * effective, 2)
    return result



def build_cost_saving_decision_support(
    *,
    financial_projection: dict[str, Any],
    contract_validation: dict[str, Any],
    monthly_advance_eur: float,
) -> dict[str, Any]:
    quality_gate_passed = bool(financial_projection.get("quality_gate_passed"))
    supplier_all_in = bool(financial_projection.get("supplier_all_in"))
    supplier_all_in_projection = financial_projection.get("supplier_all_in_projection_eur")
    all_contract_components_present = bool(contract_validation.get("all_required_components_present"))

    recommendation_publishable = (
        quality_gate_passed
        and supplier_all_in
        and all_contract_components_present
        and isinstance(supplier_all_in_projection, (int, float))
    )

    result: dict[str, Any] = {
        "objective": "energy_cost_saving",
        "monthly_advance_eur": monthly_advance_eur,
        "quality_gate_passed": quality_gate_passed,
        "supplier_all_in_ready": supplier_all_in,
        "contract_components_complete": all_contract_components_present,
        "recommendation_publishable": recommendation_publishable,
        "decision": None,
        "projected_monthly_difference_eur": None,
        "recommended_advance_eur": None,
        "recommendation_strength": None,
        "safety_margin_pct": 5.0,
        "reason": None,
    }

    if not quality_gate_passed:
        result["reason"] = "waiting_for_minimum_observation_quality"
        return result
    if not all_contract_components_present or not supplier_all_in:
        result["reason"] = "waiting_for_official_supplier_all_in_contract_data"
        return result
    if not isinstance(supplier_all_in_projection, (int, float)):
        result["reason"] = "supplier_all_in_projection_not_available"
        return result

    difference = round(float(monthly_advance_eur) - float(supplier_all_in_projection), 2)
    result["projected_monthly_difference_eur"] = difference
    result["recommended_advance_eur"] = round(max(0.0, float(supplier_all_in_projection) * 1.05), 2)

    if difference >= 15.0:
        result["decision"] = "advance_may_be_reduced"
    elif difference <= -15.0:
        result["decision"] = "advance_should_be_increased"
    else:
        result["decision"] = "keep_current_advance"

    result["reason"] = "validated_supplier_all_in_projection"
    absolute_gap = abs(difference)
    if absolute_gap < 15.0:
        result["recommendation_strength"] = "hold"
    elif absolute_gap < 30.0:
        result["recommendation_strength"] = "moderate"
    else:
        result["recommendation_strength"] = "strong"
    return result


def build_analysis_context(year: int | None = None) -> dict[str, Any]:
    months: list[dict[str, Any]] = []
    if MONTH_INPUT_ROOT.is_dir():
        for folder in sorted(MONTH_INPUT_ROOT.iterdir()):
            if not folder.is_dir() or not re.fullmatch(r"\d{4}_\d{2}", folder.name):
                continue
            if year is not None and int(folder.name[:4]) != year:
                continue
            try:
                months.append(_month_energy_metrics(folder.name))
            except Exception as exc:
                months.append({
                    "month": folder.name,
                    "year": int(folder.name[:4]),
                    "quarter": (int(folder.name[5:7]) - 1) // 3 + 1,
                    "metrics": {},
                    "quality": {"status": "error", "error": str(exc)},
                })

    quarters: list[dict[str, Any]] = []
    years: list[dict[str, Any]] = []
    for yr in sorted({int(item["year"]) for item in months}):
        year_items = [item for item in months if int(item["year"]) == yr]
        year_entry = {"year": yr, **_aggregate_analysis_period(year_items)}
        year_entry["complete_calendar_year"] = len(year_items) == 12
        years.append(year_entry)
        for quarter in range(1, 5):
            quarter_items = [item for item in year_items if int(item["quarter"]) == quarter]
            if not quarter_items:
                continue
            q_entry = {"year": yr, "quarter": quarter, **_aggregate_analysis_period(quarter_items)}
            q_entry["complete_quarter"] = len(quarter_items) == 3
            quarters.append(q_entry)

    warnings: list[str] = []
    no_source_months = [item["month"] for item in months if not (item.get("quality") or {}).get("available_sources")]
    inconsistent_months = [
        item["month"] for item in months
        if (item.get("quality") or {}).get("solar_balance_status") == "inconsistent_period_coverage"
    ]
    if no_source_months:
        warnings.append("Geen bruikbare bronbestanden: " + ", ".join(no_source_months))
    if inconsistent_months:
        warnings.append("Zonne-KPI's niet berekend wegens ongelijke brondekking: " + ", ".join(inconsistent_months))

    epex_months_available = [
        item["month"] for item in months
        if (item.get("price_context") or {}).get("electricity", {}).get("available")
        or (item.get("price_context") or {}).get("gas", {}).get("available")
    ]
    epex_source_reachable = any(bool((item.get("price_context") or {}).get("source_found")) for item in months)
    financial_months_available = [
        item["month"] for item in months
        if (item.get("financial_context") or {}).get("status") == "available"
    ]
    financial_months_partial = [
        item["month"] for item in months
        if (item.get("financial_context") or {}).get("status") == "partial"
    ]
    supplier_context = _supplier_contract_context()
    apply_nextenergy_contract_costs(supplier_context)
    supplier_live_connected = bool(
        (supplier_context.get("live_electricity_price") or {}).get("available")
    )
    supplier_price_history = [
        _nextenergy_month_telemetry(str(item.get("month")))
        for item in months
    ]
    supplier_price_history = [
        item for item in supplier_price_history if item.get("available")
    ]
    supplier_context["monthly_electricity_price_telemetry"] = supplier_price_history
    weighted_attempts = [
        _nextenergy_consumption_weighted_month(str(month.get("month")))
        for month in months
    ]
    supplier_context["monthly_consumption_weighted_electricity_diagnostics"] = weighted_attempts
    supplier_context["monthly_consumption_weighted_electricity"] = [
        item for item in weighted_attempts if item.get("available")
    ]
    weighted_by_month = {
        str(item.get("month")): item
        for item in supplier_context["monthly_consumption_weighted_electricity"]
        if item.get("available")
    }
    for month in months:
        weighted = weighted_by_month.get(str(month.get("month")))
        if not weighted:
            continue
        financial = month.setdefault("financial_context", {})
        financial["status"] = "partial_observed"
        financial["observed_import_kwh"] = weighted.get("import_kwh_observed")
        financial["observed_weighted_electricity_price_eur_per_kwh"] = weighted.get("weighted_average_eur_per_kwh")
        financial["observed_variable_electricity_cost_eur"] = weighted.get("observed_import_cost_eur")
        financial["observed_window_hours"] = weighted.get("observed_window_hours")
        financial["observed_daily_import_run_rate_kwh"] = weighted.get("observed_daily_import_run_rate_kwh")
        financial["observed_daily_variable_cost_run_rate_eur"] = weighted.get("observed_daily_variable_cost_run_rate_eur")
        observed_hours = weighted.get("observed_window_hours")
        coverage_days = (float(observed_hours) / 24.0) if isinstance(observed_hours, (int, float)) else None
        financial["observed_coverage_days"] = _round_metric(coverage_days) if coverage_days is not None else None
        minimum_days = 7.0
        observed_days = _round_metric(coverage_days) if coverage_days is not None else None
        progress_pct = (
            min(100.0, max(0.0, (float(coverage_days) / minimum_days) * 100.0))
            if coverage_days is not None else 0.0
        )
        remaining_days = (
            max(0.0, minimum_days - float(coverage_days))
            if coverage_days is not None else minimum_days
        )
        eligible = bool(coverage_days is not None and coverage_days >= minimum_days)
        financial["projection_eligibility"] = {
            "eligible": eligible,
            "minimum_observed_days": minimum_days,
            "observed_days": observed_days,
            "coverage_progress_pct": round(progress_pct, 1),
            "remaining_observation_days": _round_metric(remaining_days),
            "reason": (
                "minimum_observation_window_met"
                if eligible else "insufficient_observation_window"
            ),
        }
        # 10.6-voorbereiding: berekenbare projectievelden bestaan al, maar worden
        # uitsluitend gevuld wanneer de kwaliteitsdrempel werkelijk gehaald is.
        candidate_import_30d = (
            _round_metric(float(weighted.get("observed_daily_import_run_rate_kwh")) * 30.0)
            if isinstance(weighted.get("observed_daily_import_run_rate_kwh"), (int, float))
            else None
        )
        candidate_variable_cost_30d = (
            round(float(weighted.get("observed_daily_variable_cost_run_rate_eur")) * 30.0, 2)
            if isinstance(weighted.get("observed_daily_variable_cost_run_rate_eur"), (int, float))
            else None
        )
        monthly_advance = supplier_context.get("contract", {}).get("monthly_advance_eur")
        advance_gap = (
            round(float(monthly_advance) - float(candidate_variable_cost_30d), 2)
            if isinstance(monthly_advance, (int, float))
            and isinstance(candidate_variable_cost_30d, (int, float))
            else None
        )
        contract_costs = supplier_context.get("contract_costs") or {}
        observed_supplier_markup = (
            round(float(weighted.get("import_kwh_observed")) * float(contract_costs.get("supplier_markup_eur_per_kwh")), 2)
            if isinstance(weighted.get("import_kwh_observed"), (int, float))
            and isinstance(contract_costs.get("supplier_markup_eur_per_kwh"), (int, float))
            else None
        )
        observed_fixed_prorated = (
            round(float(contract_costs.get("supplier_fixed_costs_eur_per_month")) * min(1.0, float(coverage_days) / 30.0), 2)
            if isinstance(contract_costs.get("supplier_fixed_costs_eur_per_month"), (int, float))
            and coverage_days is not None
            else None
        )
        observed_supplier_electricity_cost = (
            round(
                float(weighted.get("observed_import_cost_eur"))
                + float(observed_supplier_markup or 0.0)
                + float(observed_fixed_prorated or 0.0),
                2,
            )
            if isinstance(weighted.get("observed_import_cost_eur"), (int, float))
            and isinstance(contract_costs.get("supplier_markup_eur_per_kwh"), (int, float))
            and isinstance(contract_costs.get("supplier_fixed_costs_eur_per_month"), (int, float))
            else None
        )
        month_metrics = month.get("metrics") or {}
        price_context = month.get("price_context") or {}
        electricity_price_context = price_context.get("electricity") or {}
        gas_price_context = price_context.get("gas") or {}
        financial["contract_formula_preview"] = {
            "export": calculate_export_compensation(
                month_metrics.get("grid_export_kwh"),
                electricity_price_context.get("average"),
                contract_costs,
            ),
            "gas": calculate_gas_supplier_cost(
                month_metrics.get("gas_m3"),
                gas_price_context.get("average"),
                contract_costs,
            ),
            "scope": "validated_contract_rules_only",
            "included_in_supplier_all_in": False,
        }

        financial["observed_supplier_component_costs"] = {
            "available": observed_supplier_electricity_cost is not None,
            "scope": "electricity_observed_window_only",
            "market_variable_cost_eur": weighted.get("observed_import_cost_eur"),
            "supplier_markup_cost_eur": observed_supplier_markup,
            "fixed_delivery_cost_prorated_eur": observed_fixed_prorated,
            "observed_supplier_electricity_cost_eur": observed_supplier_electricity_cost,
            "gas_included": False,
            "export_credit_included": False,
            "network_costs_included": False,
            "supplier_all_in": False,
        }

        financial["projection_candidate_validation"] = {
            "publishable": eligible,
            "quality_gate_passed": eligible,
            "basis": "observed_daily_run_rate",
            "candidate_30d_import_kwh": candidate_import_30d,
            "candidate_30d_variable_electricity_cost_eur": candidate_variable_cost_30d,
            "candidate_30d_supplier_markup_eur": (
                round(float(candidate_import_30d) * float(contract_costs.get("supplier_markup_eur_per_kwh")), 2)
                if isinstance(candidate_import_30d, (int, float))
                and isinstance(contract_costs.get("supplier_markup_eur_per_kwh"), (int, float))
                else None
            ),
            "candidate_30d_fixed_delivery_eur": (
                contract_costs.get("supplier_fixed_costs_eur_per_month")
                if isinstance(contract_costs.get("supplier_fixed_costs_eur_per_month"), (int, float))
                else None
            ),
            "candidate_30d_supplier_electricity_cost_eur": (
                round(
                    float(candidate_variable_cost_30d)
                    + float(candidate_import_30d) * float(contract_costs.get("supplier_markup_eur_per_kwh"))
                    + float(contract_costs.get("supplier_fixed_costs_eur_per_month")),
                    2,
                )
                if isinstance(candidate_variable_cost_30d, (int, float))
                and isinstance(candidate_import_30d, (int, float))
                and isinstance(contract_costs.get("supplier_markup_eur_per_kwh"), (int, float))
                and isinstance(contract_costs.get("supplier_fixed_costs_eur_per_month"), (int, float))
                else None
            ),
            "supplier_electricity_projection_scope": "electricity_only_not_all_in",
            "monthly_advance_eur": monthly_advance,
            "candidate_variable_cost_vs_advance_gap_eur": advance_gap,
            "advance_comparison_scope": "variable_electricity_only_not_all_in",
            "warning": None if eligible else "validation_only_not_a_financial_projection",
        }
        financial["projection_preview"] = {
            "status": "eligible_not_all_in" if eligible else "blocked_insufficient_observation",
            "basis": "observed_daily_run_rate",
            "projected_30d_import_kwh": (
                _round_metric(float(weighted.get("observed_daily_import_run_rate_kwh")) * 30.0)
                if eligible and isinstance(weighted.get("observed_daily_import_run_rate_kwh"), (int, float))
                else None
            ),
            "projected_30d_variable_electricity_cost_eur": (
                round(float(weighted.get("observed_daily_variable_cost_run_rate_eur")) * 30.0, 2)
                if eligible and isinstance(weighted.get("observed_daily_variable_cost_run_rate_eur"), (int, float))
                else None
            ),
            "supplier_all_in_projection": False,
        }
        # v10.6.0: productiematige 30-dagenprognose. Alleen publiceren na de
        # bewezen 7-dagengate. Leverancier-all-in blijft afzonderlijk geblokkeerd
        # totdat alle officiële contractcomponenten daadwerkelijk bekend zijn.
        projected_import_30d = (
            _round_metric(float(weighted.get("observed_daily_import_run_rate_kwh")) * 30.0)
            if eligible and isinstance(weighted.get("observed_daily_import_run_rate_kwh"), (int, float))
            else None
        )
        projected_variable_cost_30d = (
            round(float(weighted.get("observed_daily_variable_cost_run_rate_eur")) * 30.0, 2)
            if eligible and isinstance(weighted.get("observed_daily_variable_cost_run_rate_eur"), (int, float))
            else None
        )
        projected_markup_30d = (
            round(float(projected_import_30d) * float(contract_costs.get("supplier_markup_eur_per_kwh")), 2)
            if isinstance(projected_import_30d, (int, float))
            and isinstance(contract_costs.get("supplier_markup_eur_per_kwh"), (int, float))
            else None
        )
        projected_fixed_30d = (
            round(float(contract_costs.get("supplier_fixed_costs_eur_per_month")), 2)
            if eligible and isinstance(contract_costs.get("supplier_fixed_costs_eur_per_month"), (int, float))
            else None
        )
        projected_supplier_electricity_30d = (
            round(float(projected_variable_cost_30d) + float(projected_markup_30d) + float(projected_fixed_30d), 2)
            if all(isinstance(value, (int, float)) for value in (projected_variable_cost_30d, projected_markup_30d, projected_fixed_30d))
            else None
        )
        financial["financial_projection"] = {
            "engine_version": APP_VERSION,
            "status": "published" if eligible else "blocked_insufficient_observation",
            "quality_gate_passed": eligible,
            "minimum_observed_days": minimum_days,
            "basis": "observed_consumption_weighted_nextenergy_run_rate",
            "projected_30d_import_kwh": projected_import_30d,
            "projected_30d_variable_electricity_cost_eur": projected_variable_cost_30d,
            "projected_30d_supplier_markup_eur": projected_markup_30d,
            "projected_30d_fixed_delivery_eur": projected_fixed_30d,
            "projected_30d_supplier_electricity_cost_eur": projected_supplier_electricity_30d,
            "monthly_advance_eur": monthly_advance,
            "projected_variable_cost_vs_advance_gap_eur": (
                round(float(monthly_advance) - float(projected_variable_cost_30d), 2)
                if isinstance(monthly_advance, (int, float))
                and isinstance(projected_variable_cost_30d, (int, float))
                else None
            ),
            "supplier_all_in_projection_eur": None,
            "supplier_all_in": False,
            "epex_is_reference_only": True,
            "note": "EPEX is markt-/referentieprijs en wordt niet als leverancier-all-in prijs gepresenteerd.",
        }
        # v10.7.0: prognoseverdieping. Naast de 30-dagenwaarde publiceren we
        # een bandbreedte en een kalendermaand-run-rate, maar uitsluitend nadat
        # de bestaande 7-dagen kwaliteitsgate is gehaald. Dit blijft
        # elektriciteit-only totdat officiële all-in contractcomponenten bestaan.
        observed_days = float(weighted.get("observed_window_hours") or 0.0) / 24.0
        month_days = monthrange(int(str(month.get("month"))[:4]), int(str(month.get("month"))[5:7]))[1]
        daily_import = weighted.get("observed_daily_import_run_rate_kwh")
        daily_cost = weighted.get("observed_daily_variable_cost_run_rate_eur")
        projected_calendar_import = (
            _round_metric(float(daily_import) * month_days)
            if eligible and isinstance(daily_import, (int, float)) else None
        )
        projected_calendar_cost = (
            round(float(daily_cost) * month_days, 2)
            if eligible and isinstance(daily_cost, (int, float)) else None
        )
        projected_cost_low = (
            round(float(projected_variable_cost_30d) * 0.85, 2)
            if isinstance(projected_variable_cost_30d, (int, float)) else None
        )
        projected_cost_high = (
            round(float(projected_variable_cost_30d) * 1.15, 2)
            if isinstance(projected_variable_cost_30d, (int, float)) else None
        )
        financial["projection_detail"] = {
            "engine_version": APP_VERSION,
            "status": "published" if eligible else "blocked_insufficient_observation",
            "quality_gate_passed": eligible,
            "observed_days": round(observed_days, 3),
            "calendar_month_days": month_days,
            "projected_calendar_month_import_kwh": projected_calendar_import,
            "projected_calendar_month_variable_electricity_cost_eur": projected_calendar_cost,
            "projected_30d_variable_cost_band_eur": {
                "low": projected_cost_low,
                "base": projected_variable_cost_30d,
                "high": projected_cost_high,
                "method": "base_run_rate_plus_minus_15pct",
            },
            "scope": "variable_electricity_only_not_supplier_all_in",
            "supplier_all_in": False,
            "epex_is_reference_only": True,
        }

        financial["nextenergy_weighted_import"] = {
            key: weighted.get(key) for key in (
                "matched_intervals", "first_snapshot", "last_snapshot",
                "observed_window_hours", "coverage", "quality", "transport"
            )
        }
        note = "NextEnergy-verbruikgewogen kosten dekken alleen de beschikbare kwartiersnapshotperiode; niet extrapoleren naar een volledige maand."
        limitations = financial.setdefault("limitations", [])
        if note not in limitations:
            limitations.append(note)

    financial_months_partial = sorted(set(financial_months_partial) | set(weighted_by_month))
    supplier_context["cost_model"]["consumption_weighted_import_available"] = bool(weighted_by_month)
    projection_months = []
    for month in months:
        financial = month.get("financial_context") or {}
        eligibility = financial.get("projection_eligibility") or {}
        if eligibility.get("eligible"):
            projection_months.append(str(month.get("month")))
    supplier_context["cost_model"]["projection_ready_months"] = projection_months
    supplier_components_ready = all(
        bool(supplier_context["cost_model"].get(key))
        for key in (
            "supplier_fixed_costs_known",
            "supplier_markup_known",
            "export_compensation_known",
            "gas_supplier_formula_known",
        )
    )
    missing_all_in_dependencies = [
        key for key in (
            "supplier_fixed_costs", "supplier_markup",
            "export_compensation", "gas_supplier_formula",
        )
        if not {
            "supplier_fixed_costs": bool(supplier_context["cost_model"].get("supplier_fixed_costs_known")),
            "supplier_markup": bool(supplier_context["cost_model"].get("supplier_markup_known")),
            "export_compensation": bool(supplier_context["cost_model"].get("export_compensation_known")),
            "gas_supplier_formula": bool(supplier_context["cost_model"].get("gas_supplier_formula_known")),
        }[key]
    ]
    supplier_context["cost_model"]["projection_engine"] = {
        "stage": "production_active",
        "engine_version": APP_VERSION,
        "target_release": "10.6",
                "current_release_target": "11.1",
        "thirty_day_variable_projection_logic_ready": True,
        "supplier_all_in_projection_ready": bool(supplier_components_ready and projection_months),
        "activation_requires_observed_days": 7.0,
        "remaining_all_in_dependencies": missing_all_in_dependencies,
    }
    readiness_components = {
        "weighted_electricity_import": bool(weighted_by_month),
        "observation_quality_gate": bool(projection_months),
        "thirty_day_variable_projection_logic": True,
        "monthly_advance_context": isinstance(
            supplier_context.get("contract", {}).get("monthly_advance_eur"), (int, float)
        ),
        "supplier_fixed_costs": bool(supplier_context["cost_model"].get("supplier_fixed_costs_known")),
        "supplier_markup": bool(supplier_context["cost_model"].get("supplier_markup_known")),
        "export_compensation": bool(supplier_context["cost_model"].get("export_compensation_known")),
        "gas_supplier_formula": bool(supplier_context["cost_model"].get("gas_supplier_formula_known")),
    }
    completed = sum(1 for value in readiness_components.values() if value)
    total = len(readiness_components)
    supplier_context["cost_model"]["financial_readiness"] = {
        "components": readiness_components,
        "completed_components": completed,
        "total_components": total,
        "progress_pct": round((completed / total) * 100.0, 1) if total else 0.0,
        "decision_ready": all(readiness_components.values()),
        "next_required_components": [
            key for key, value in readiness_components.items() if not value
        ],
        "note": (
            "Voortgang betreft technische/contractuele bouwblokken. "
            "Een vergelijking met het maandvoorschot is geen all-in kostenprognose "
            "zolang leverancier-, teruglever- en gascomponenten ontbreken."
        ),
    }
    supplier_context["cost_model"]["all_in_ready"] = bool(supplier_components_ready and projection_months)
    supplier_context["cost_model"]["projection_observation_status"] = [
        {
            "month": str(month.get("month")),
            **((month.get("financial_context") or {}).get("projection_eligibility") or {}),
        }
        for month in months
        if (month.get("financial_context") or {}).get("projection_eligibility")
    ]
    supplier_context["cost_model"]["projection_policy"] = {
        "minimum_observed_days": 7.0,
        "automatic_month_extrapolation": False,
        "automatic_contract_year_extrapolation": False,
        "reason": "run-rate is observational until minimum coverage and supplier all-in components are available",
    }


    latest_financial_projection = {}
    if months:
        latest_financial_projection = ((months[-1].get("financial_context") or {}).get("financial_projection") or {})
    validated_contract = supplier_context.get("contract_validation") or {}
    decision_support = build_cost_saving_decision_support(
        financial_projection=latest_financial_projection,
        contract_validation=validated_contract,
        monthly_advance_eur=float((supplier_context.get("contract") or {}).get("monthly_advance_eur") or 150.0),
    )

    return {
        "schema": ANALYSIS_CONTEXT_SCHEMA,
        "version": APP_VERSION,
        "generated_at": datetime.now(TZ).isoformat(),
        "price_status": {
            "epex_source_reachable": epex_source_reachable,
            "months_with_price_data": epex_months_available,
            "latest_month_with_price_data": epex_months_available[-1] if epex_months_available else None,
        },
        "financial_status": {
            "months_fully_costable": financial_months_available,
            "months_partially_costable": financial_months_partial,
            "supplier_live_price_connected": supplier_live_connected,
            "supplier_price_history_connected": bool(supplier_price_history),
            "supplier_price_history_transport": (supplier_price_history[0].get("transport") if supplier_price_history else None),
            "supplier_contract_costs_connected": bool((supplier_context.get("contract_costs") or {}).get("valid")),
            "export_credit_connected": bool(supplier_context["cost_model"].get("export_compensation_known")),
            "ready_for_all_in_costs": bool(supplier_context["cost_model"].get("all_in_ready")),
        },
        "supplier_context": supplier_context,
        "production_consolidation": {
            "release": APP_VERSION,
            "financial_engine_active": True,
            "official_report_integration_active": True,
            "strict_contract_gating": True,
            "minimum_observed_days": 7.0,
            "epex_reference_only": True,
            "supplier_all_in_requires_validated_contract": True,
            "status": "production_ready_guarded",
            "major_release": "11.0",
            "phase": "financial_reporting_production_baseline",
            "v20_savings_opportunity_engine": {
                "objective": "turn_validated_energy_measurements_into_actionable_cost_saving_opportunities",
                "primary_goal": "reduce_total_energy_costs",
                "opportunity_types": ["energy_contract", "home_battery", "appliance_replacement", "load_shifting"],
                "energy_contract": {"status": "guarded", "requires_supplier_all_in": True, "requires_official_contract_values": True, "may_use_epex_as_supplier_price": False},
                "home_battery": {
                    "status": "analysis_ready_guarded",
                    "candidate_product_policy": "candidate_not_preselected",
                    "known_candidate": "Marstek Venus 3",
                    "required_inputs": ["validated_import_profile", "validated_export_profile", "dynamic_price_profile", "battery_purchase_price", "usable_capacity_kwh", "roundtrip_efficiency", "power_limits"],
                    "outputs_when_complete": ["estimated_annual_savings_eur", "simple_payback_years", "buy_wait_or_reject"],
                    "missing_inputs_may_be_assumed": False
                },
                "appliance_replacement": {
                    "status": "analysis_ready_guarded",
                    "measurement_source": "HomeWizard_socket_or_validated_device_measurement",
                    "compare_against": ["nameplate_or_official_consumption", "replacement_purchase_price", "replacement_expected_consumption"],
                    "outputs_when_complete": ["measured_annual_cost_eur", "replacement_annual_cost_eur", "annual_savings_eur", "simple_payback_years", "replace_or_keep"],
                    "replacement_recommendation_requires_positive_financial_case": True,
                    "missing_inputs_may_be_assumed": False
                },
                "load_shifting": {
                    "status": "analysis_ready_guarded",
                    "requires_dynamic_price_profile": True,
                    "requires_measured_load_profile": True,
                    "outputs_when_complete": ["shiftable_kwh", "estimated_savings_eur", "recommended_time_windows"]
                },
                "recommendation_policy": {
                    "publish_only_when_required_inputs_complete": True,
                    "show_blocking_inputs_when_incomplete": True,
                    "candidate_numbers_may_drive_recommendation": False,
                    "missing_values_render_as": "Niet beschikbaar"
                },
                "roadmap_state": "v20_reporting_baseline_complete_savings_development_continues",
                "status": "savings_opportunity_engine_active_guarded"
            },
            "v20_savings_priority_engine": {
                "objective": "rank_only_validated_savings_opportunities_by_financial_value",
                "source": "v20_savings_opportunity_engine",
                "ranking_dimensions": [
                    "estimated_annual_savings_eur",
                    "simple_payback_years",
                    "data_completeness",
                    "implementation_effort"
                ],
                "priority_order": [
                    "highest_validated_annual_savings",
                    "shortest_validated_payback",
                    "lowest_implementation_effort"
                ],
                "opportunity_contracts": {
                    "energy_contract": {
                        "required_for_ranking": ["validated_supplier_all_in_current", "validated_alternative_supplier_all_in"],
                        "rank_when_complete": True
                    },
                    "home_battery": {
                        "required_for_ranking": ["estimated_annual_savings_eur", "simple_payback_years"],
                        "candidate_product_policy": "candidate_not_preselected",
                        "known_candidate": "Marstek Venus 3",
                        "rank_when_complete": True
                    },
                    "appliance_replacement": {
                        "required_for_ranking": ["measured_annual_cost_eur", "replacement_annual_cost_eur", "annual_savings_eur", "simple_payback_years"],
                        "rank_when_complete": True
                    },
                    "load_shifting": {
                        "required_for_ranking": ["shiftable_kwh", "estimated_savings_eur"],
                        "rank_when_complete": True
                    }
                },
                "blocked_opportunity_policy": {
                    "include_in_financial_ranking": False,
                    "show_as_waiting_for_data": True,
                    "missing_values_render_as": "Niet beschikbaar",
                    "zero_substitution_allowed": False
                },
                "recommendation_output": {
                    "top_opportunity": "highest_ranked_complete_opportunity_or_null",
                    "annual_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "action": "buy_replace_switch_shift_keep_wait_or_null",
                    "reason_required": True
                },
                "roadmap_state": "v20_savings_opportunities_can_be_prioritized_when_financially_complete",
                "status": "savings_priority_engine_active_guarded"
            },
            "v24_action_handoff_runtime": {
                "objective": "translate_one_publishable_v23_portfolio_recommendation_into_a_guarded_traceable_execution_handoff_without_automatic_external_action",
                "source_recommendation_runtime": "v23_portfolio_recommendation_runtime",
                "roadmap_step": "1/5",
                "handoff_states": ["waiting_for_data", "keep_current", "ready_for_user_action"],
                "activation_policy": {
                    "publishable_v23_recommendation_required": True,
                    "positive_validated_annual_savings_required_for_change": True,
                    "complete_traceable_financial_case_required": True,
                    "candidate_values_may_not_activate_handoff": True,
                    "missing_values_may_not_be_assumed": True,
                    "zero_substitution_allowed": False,
                    "supplier_all_in_requires_official_contract_validation": True,
                    "automatic_refresh_after_new_data": True,
                    "manual_override_allowed": False
                },
                "execution_policy": {
                    "automatic_purchase_switch_or_device_control": False,
                    "user_confirmation_required_before_external_action": True,
                    "handoff_is_advisory_until_user_acts": True,
                    "preserve_source_recommendation_and_evidence": True
                },
                "handoff_output_contract": {
                    "state": "required",
                    "recommended_action": "validated_action_keep_or_wait",
                    "domain": "validated_domain_or_null",
                    "annual_savings_eur": "validated_value_or_null",
                    "monthly_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "implementation_effort": "validated_value_or_null",
                    "action_prerequisites": "validated_list",
                    "primary_blocker": "validated_blocker_or_null",
                    "evidence_reference": "required",
                    "data_quality": "required"
                },
                "blocked_policy": {
                    "state": "waiting_for_data",
                    "numeric_value": None,
                    "rendering": "Niet beschikbaar",
                    "external_action_allowed": False
                },
                "report_handoff": {
                    "page1_management_summary": "validated_action_or_guarded_wait",
                    "page1_financial_kpis": "validated_publishable_numeric_values_only",
                    "page2_financial_analysis": "validated_case_prerequisites_and_financial_basis",
                    "pages3_13_context": "evidence_blockers_quality_and_traceability"
                },
                "roadmap_state": "v24_step_1_of_5_action_handoff_runtime_active_guarded",
                "next_step": "v24_action_tracking_runtime",
                "status": "action_handoff_runtime_active_guarded"
            },
            "v24_action_tracking_runtime": {
                "objective": "track_the_lifecycle_of_one_guarded_user_action_without_claiming_execution_or_savings_before_validated_evidence_exists",
                "source_handoff_runtime": "v24_action_handoff_runtime",
                "roadmap_step": "2/5",
                "tracking_states": ["waiting_for_data", "ready_for_user_action", "user_action_pending", "user_action_reported", "evidence_pending", "validated_execution"],
                "tracking_policy": {
                    "tracking_starts_only_from_guarded_handoff": True,
                    "user_report_may_record_intent_or_execution_but_not_financial_result": True,
                    "execution_requires_traceable_validation_evidence": True,
                    "realized_savings_may_not_be_claimed_before_measurement": True,
                    "candidate_values_may_not_be_promoted_to_actuals": True,
                    "missing_values_may_not_be_assumed": True,
                    "zero_substitution_allowed": False,
                    "automatic_refresh_after_new_data": True,
                    "manual_financial_override_allowed": False
                },
                "tracking_output_contract": {
                    "tracking_state": "required",
                    "action_id": "stable_traceable_identifier_required_when_action_exists",
                    "recommended_action": "validated_source_action_keep_or_wait",
                    "domain": "validated_source_domain_or_null",
                    "handoff_evidence_reference": "required",
                    "user_action_status": "pending_reported_or_null",
                    "execution_evidence_reference": "validated_reference_or_null",
                    "execution_validated_at": "validated_timestamp_or_null",
                    "realized_savings_eur": None,
                    "primary_blocker": "validated_blocker_or_null",
                    "data_quality": "required"
                },
                "execution_validation_policy": {
                    "contract_switch": "official_supplier_or_contract_evidence_required",
                    "battery_purchase": "purchase_and_installation_evidence_required",
                    "appliance_replacement": "replacement_and_measurement_evidence_required",
                    "load_shift": "measured_load_profile_change_required",
                    "self_report_alone_confirms_financial_savings": False
                },
                "report_handoff": {
                    "page1_management_summary": "validated_action_status_or_guarded_wait",
                    "page1_financial_kpis": "no_realized_savings_until_measurement_validation",
                    "page2_financial_analysis": "action_status_execution_evidence_and_original_business_case",
                    "pages3_13_context": "tracking_evidence_blockers_quality_and_audit_trail"
                },
                "roadmap_state": "v24_step_2_of_5_action_tracking_runtime_active_guarded",
                "next_step": "v24_realized_savings_runtime",
                "status": "action_tracking_runtime_active_guarded"
            },
            "v24_realized_savings_runtime": {
                "objective": "measure_realized_financial_savings_only_after_validated_execution_and_comparable_post_action_measurement_evidence",
                "source_tracking_runtime": "v24_action_tracking_runtime",
                "roadmap_step": "3/5",
                "realization_states": ["waiting_for_validated_execution", "measurement_baseline_pending", "post_action_measurement_pending", "comparison_pending", "realized_savings_validated"],
                "measurement_policy": {
                    "validated_execution_required": True,
                    "traceable_pre_action_baseline_required": True,
                    "traceable_post_action_measurement_required": True,
                    "comparable_measurement_windows_required": True,
                    "weather_or_usage_normalization_required_when_material": True,
                    "realized_savings_must_be_derived_from_measured_difference": True,
                    "business_case_estimate_may_not_be_promoted_to_actual": True,
                    "self_report_may_not_create_realized_savings": True,
                    "candidate_values_may_not_be_promoted_to_actuals": True,
                    "missing_values_may_not_be_assumed": True,
                    "zero_substitution_allowed": False,
                    "automatic_refresh_after_new_measurements": True,
                    "manual_financial_override_allowed": False
                },
                "realized_savings_output_contract": {
                    "realization_state": "required",
                    "action_id": "stable_traceable_identifier_required",
                    "domain": "validated_source_domain_or_null",
                    "baseline_evidence_reference": "validated_reference_or_null",
                    "post_action_evidence_reference": "validated_reference_or_null",
                    "baseline_cost_eur": "validated_comparable_value_or_null",
                    "post_action_cost_eur": "validated_comparable_value_or_null",
                    "realized_savings_eur": "validated_measured_difference_or_null",
                    "realized_savings_period": "validated_period_or_null",
                    "annualized_realized_savings_eur": "validated_value_or_null_only_when_annualization_gate_passes",
                    "variance_vs_business_case_eur": "validated_value_or_null",
                    "primary_blocker": "validated_blocker_or_null",
                    "data_quality": "required"
                },
                "annualization_policy": {
                    "automatic_annualization_from_short_window": False,
                    "requires_representative_validated_period": True,
                    "seasonality_must_be_accounted_for_when_material": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar"
                },
                "report_handoff": {
                    "page1_management_summary": "validated_realized_result_or_guarded_wait",
                    "page1_financial_kpis": "validated_realized_savings_only",
                    "page2_financial_analysis": "baseline_post_action_comparison_and_original_business_case",
                    "pages3_13_context": "measurement_evidence_normalization_blockers_quality_and_audit_trail"
                },
                "roadmap_state": "v24_step_3_of_5_realized_savings_runtime_active_guarded",
                "next_step": "v24_variance_learning_runtime",
                "status": "realized_savings_runtime_active_guarded"
            },
            "v24_variance_learning_runtime": {
                "objective": "compare_validated_realized_savings_with_the_original_business_case_and_learn_only_from_traceable_measured_variance",
                "source_realized_savings_runtime": "v24_realized_savings_runtime",
                "roadmap_step": "4/5",
                "learning_states": ["waiting_for_realized_savings", "variance_pending", "variance_validated", "learning_available"],
                "variance_policy": {
                    "validated_realized_savings_required": True,
                    "original_business_case_reference_required": True,
                    "comparable_period_and_scope_required": True,
                    "variance_must_be_derived_from_validated_values": True,
                    "positive_or_negative_variance_must_be_preserved": True,
                    "candidate_values_may_not_drive_learning": True,
                    "missing_values_may_not_be_assumed": True,
                    "zero_substitution_allowed": False,
                    "automatic_refresh_after_new_measurements": True,
                    "manual_financial_override_allowed": False
                },
                "learning_policy": {
                    "learning_may_adjust_future_assumptions_only_after_repeated_validated_evidence": True,
                    "single_short_window_may_not_rewrite_financial_model": True,
                    "seasonality_and_usage_context_must_be_preserved": True,
                    "supplier_contract_changes_must_remain_separately_validated": True,
                    "audit_trail_required_for_model_adjustment": True
                },
                "variance_learning_output_contract": {
                    "learning_state": "required",
                    "action_id": "stable_traceable_identifier_required",
                    "domain": "validated_source_domain_or_null",
                    "business_case_savings_eur": "validated_original_value_or_null",
                    "realized_savings_eur": "validated_measured_value_or_null",
                    "variance_eur": "validated_realized_minus_business_case_or_null",
                    "variance_pct": "validated_value_or_null_when_denominator_valid",
                    "variance_reason": "validated_explanation_or_null",
                    "future_model_adjustment": "guarded_adjustment_or_null",
                    "evidence_reference": "validated_reference_or_null",
                    "primary_blocker": "validated_blocker_or_null",
                    "data_quality": "required"
                },
                "report_handoff": {
                    "page1_management_summary": "validated_learning_signal_or_guarded_wait",
                    "page1_financial_kpis": "validated_realized_and_variance_values_only",
                    "page2_financial_analysis": "business_case_realized_result_variance_and_explanation",
                    "pages3_13_context": "learning_evidence_context_quality_and_audit_trail"
                },
                "roadmap_state": "v24_step_4_of_5_variance_learning_runtime_active_guarded",
                "next_step": "v24_completion_gate",
                "status": "variance_learning_runtime_active_guarded"
            },
            "v24_completion_gate": {
                "objective": "close_v24_with_one_guarded_auditable_action_to_realized_savings_learning_chain_ready_for_next_major_development",
                "roadmap_step": "5/5",
                "chain_components": {
                    "action_handoff_runtime": "ready_guarded",
                    "action_tracking_runtime": "ready_guarded",
                    "realized_savings_runtime": "ready_guarded",
                    "variance_learning_runtime": "ready_guarded"
                },
                "external_dependencies": {
                    "observation_gate": "minimum_7_observed_days",
                    "supplier_contract_gate": "official_contract_values_required",
                    "validated_execution_gate": "traceable_execution_evidence_required",
                    "realized_savings_gate": "comparable_before_after_measurement_required"
                },
                "completion_policy": {
                    "external_data_may_remain_blocked_at_release_completion": True,
                    "automatic_transition_after_external_gates": True,
                    "manual_override_allowed": False,
                    "candidate_values_may_drive_action_or_learning": False,
                    "business_case_estimate_may_be_promoted_to_realized": False,
                    "missing_values_may_be_assumed": False,
                    "zero_substitution_allowed": False,
                    "epex_supplier_all_in_allowed": False
                },
                "learning_safety_policy": {
                    "single_short_window_may_rewrite_financial_model": False,
                    "repeated_validated_evidence_required_for_model_adjustment": True,
                    "seasonality_and_usage_context_preserved": True,
                    "supplier_contract_changes_separately_validated": True,
                    "audit_trail_required": True
                },
                "publication_policy": {
                    "publish_realized_savings_only_after_measurement_validation": True,
                    "publish_variance_only_from_validated_business_case_and_realized_values": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "reason_and_data_quality_required": True
                },
                "report_completion_gate": {
                    "page1_management_summary": "validated_action_realized_result_learning_signal_or_guarded_wait",
                    "page1_financial_kpis": "validated_realized_and_variance_values_only",
                    "page2_financial_analysis": "validated_business_case_execution_measurement_and_variance_chain",
                    "pages3_13_context": "validated_evidence_blockers_quality_and_audit_trail",
                    "candidate_values_primary_output_allowed": False
                },
                "roadmap_state": "v24_complete_guarded_action_to_realized_savings_learning_chain",
                "next_major_release": "25.0.0",
                "status": "v24_complete_external_data_gates_remain"
            },
            "v25_savings_ledger_runtime": {
                "objective": "maintain_one_guarded_auditable_ledger_of_validated_realized_savings_across_actions_without_double_counting",
                "source_completion_gate": "v24_completion_gate",
                "roadmap_step": "1/5",
                "ledger_entry_states": ["blocked", "eligible", "booked", "reversed_or_corrected"],
                "eligibility_policy": {
                    "validated_realized_savings_required": True,
                    "stable_action_id_required": True,
                    "traceable_measurement_evidence_required": True,
                    "realized_period_required": True,
                    "candidate_values_may_not_be_booked": True,
                    "business_case_estimates_may_not_be_booked": True,
                    "self_report_alone_may_not_be_booked": True,
                    "missing_values_may_not_be_assumed": True,
                    "manual_financial_override_allowed": False
                },
                "double_counting_policy": {
                    "deduplication_key": "stable_action_id_plus_validated_evidence_reference_plus_realized_period",
                    "same_validated_savings_may_be_booked_twice": False,
                    "overlapping_measurement_periods_require_explicit_separation": True,
                    "correction_preserves_original_audit_entry": True
                },
                "ledger_value_policy": {
                    "positive_realized_savings_preserved": True,
                    "negative_realized_impact_preserved": True,
                    "negative_values_may_be_clamped_to_zero": False,
                    "zero_substitution_for_missing_allowed": False,
                    "annualization_requires_existing_v24_annualization_gate": True
                },
                "ledger_output_contract": {
                    "ledger_entry_id": "stable_traceable_identifier_required",
                    "action_id": "validated_action_identifier_required",
                    "domain": "validated_domain_required",
                    "realized_savings_eur": "validated_measured_value_required",
                    "realized_savings_period": "validated_period_required",
                    "annualized_realized_savings_eur": "validated_value_or_null",
                    "evidence_reference": "validated_reference_required",
                    "booking_state": "required",
                    "correction_reference": "validated_reference_or_null",
                    "data_quality": "required"
                },
                "publication_policy": {
                    "booked_values_are_actuals_not_estimates": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "audit_trail_required": True
                },
                "roadmap_state": "v25_step_1_of_5_validated_savings_ledger_runtime_active_guarded",
                "next_step": "v25_cumulative_portfolio_impact_runtime",
                "status": "savings_ledger_runtime_active_guarded"
            },
            "v25_cumulative_portfolio_impact_runtime": {
                "objective": "aggregate_only_validated_booked_savings_ledger_entries_into_auditable_cumulative_portfolio_impact_without_double_counting_or_estimate_promotion",
                "source_runtime": "v25_savings_ledger_runtime",
                "roadmap_step": "2/5",
                "eligibility_policy": {
                    "booked_ledger_entries_only": True,
                    "validated_realized_savings_required": True,
                    "blocked_or_eligible_unbooked_entries_excluded": True,
                    "candidate_values_excluded": True,
                    "business_case_estimates_excluded": True,
                    "manual_financial_override_allowed": False,
                    "missing_values_may_not_be_assumed": True
                },
                "aggregation_policy": {
                    "deduplicate_using_ledger_identity": True,
                    "positive_and_negative_realized_impacts_preserved": True,
                    "negative_values_may_be_clamped_to_zero": False,
                    "overlapping_periods_require_validated_separation": True,
                    "corrections_replace_effect_without_erasing_audit_history": True,
                    "annualized_totals_require_entry_level_annualization_gate": True
                },
                "portfolio_output_contract": {
                    "validated_action_count": "integer_from_booked_unique_entries",
                    "cumulative_realized_savings_eur": "sum_of_validated_booked_realized_values_or_null",
                    "cumulative_annualized_realized_savings_eur": "sum_only_when_all_included_annualized_values_are_validated_or_null",
                    "positive_impact_eur": "validated_sum_or_null",
                    "negative_impact_eur": "validated_sum_or_null",
                    "period_coverage": "validated_covered_periods_required",
                    "evidence_references": "traceable_ledger_references_required",
                    "data_quality": "required"
                },
                "publication_policy": {
                    "portfolio_total_is_actual_not_estimate": True,
                    "partial_validated_portfolio_must_be_labelled_partial": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "audit_trail_required": True
                },
                "roadmap_state": "v25_step_2_of_5_cumulative_portfolio_impact_runtime_active_guarded",
                "next_step": "v25_monthly_budget_impact_runtime",
                "status": "cumulative_portfolio_impact_runtime_active_guarded"
            },
            "v25_monthly_budget_impact_runtime": {
                "objective": "translate_only_validated_realized_portfolio_impact_into_a_guarded_monthly_budget_context_without_treating_partial_measurements_or_estimates_as_monthly_savings",
                "source_runtime": "v25_cumulative_portfolio_impact_runtime",
                "roadmap_step": "3/5",
                "monthly_advance_reference_eur": 150.0,
                "eligibility_policy": {
                    "validated_booked_portfolio_impact_required": True,
                    "realized_period_coverage_required": True,
                    "monthly_equivalent_requires_validated_period_normalization": True,
                    "partial_measurement_window_may_not_be_extrapolated_automatically": True,
                    "annualized_estimate_may_not_be_divided_by_twelve_without_validated_annualization": True,
                    "candidate_values_excluded": True,
                    "business_case_estimates_excluded": True,
                    "manual_financial_override_allowed": False,
                    "missing_values_may_not_be_assumed": True
                },
                "budget_impact_policy": {
                    "reference_monthly_advance_eur": 150.0,
                    "validated_monthly_realized_savings_may_reduce_effective_budget_burden": True,
                    "validated_monthly_negative_impact_may_increase_effective_budget_burden": True,
                    "negative_values_may_be_clamped_to_zero": False,
                    "advance_change_recommendation_requires_existing_supplier_all_in_decision_gate": True,
                    "ledger_savings_alone_may_not_change_supplier_advance": True,
                    "double_counting_with_supplier_cost_projection_forbidden": True,
                    "zero_substitution_for_missing_allowed": False
                },
                "budget_output_contract": {
                    "monthly_advance_reference_eur": "configured_reference_value",
                    "validated_monthly_realized_impact_eur": "validated_normalized_value_or_null",
                    "effective_monthly_budget_burden_eur": "reference_minus_validated_realized_impact_or_null",
                    "cumulative_realized_savings_eur": "traceable_portfolio_value_or_null",
                    "period_coverage": "validated_covered_periods_required",
                    "advance_change_recommendation": "existing_guarded_supplier_decision_or_null",
                    "evidence_references": "traceable_ledger_references_required",
                    "data_quality": "required"
                },
                "publication_policy": {
                    "monthly_budget_impact_is_actual_only_when_period_normalization_validated": True,
                    "partial_or_noncomparable_period_remains_unavailable": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "candidate_values_primary_output_allowed": False,
                    "audit_trail_required": True
                },
                "roadmap_state": "v25_step_3_of_5_monthly_budget_impact_runtime_active_guarded",
                "next_step": "v25_report_publication_runtime",
                "status": "monthly_budget_impact_runtime_active_guarded"
            },
            "v31_conversation_context_runtime": {
                "objective": "expose_one_guarded_machine_readable_energy_context_for_natural_language_chat_and_voice_questions_without_bypassing_existing_financial_data_quality_or_authority_gates",
                "roadmap_step": "1/4",
                "source_chain": [
                    "production_consolidation",
                    "financial_status",
                    "supplier_context",
                    "months",
                    "quarters",
                    "years"
                ],
                "conversation_domains": [
                    "project_status",
                    "energy_use",
                    "solar",
                    "gas",
                    "prices",
                    "financial_projection",
                    "savings_opportunities",
                    "device_measurement",
                    "battery",
                    "supplier_contract",
                    "report_status",
                    "data_quality"
                ],
                "context_contract": {
                    "current_release_required": True,
                    "latest_available_measurement_context_required": True,
                    "financial_gate_state_required": True,
                    "data_quality_required": True,
                    "source_traceability_required": True,
                    "blocked_dependencies_required_when_material": True,
                    "actual_forecast_and_candidate_values_must_remain_separate": True,
                    "missing_values_may_not_be_assumed": True
                },
                "answer_policy": {
                    "ordinary_language_questions_supported": True,
                    "answer_from_validated_project_context_first": True,
                    "state_when_requested_value_is_unavailable": True,
                    "do_not_invent_missing_financial_values": True,
                    "do_not_present_candidate_as_actual": True,
                    "do_not_cross_user_authority_gate": True,
                    "show_primary_blocker_when_action_is_blocked": True,
                    "preserve_evidence_reference_when_available": True
                },
                "safety_policy": {
                    "automatic_purchase_allowed": False,
                    "automatic_supplier_switch_allowed": False,
                    "automatic_contract_acceptance_allowed": False,
                    "automatic_advance_payment_change_allowed": False,
                    "automatic_device_control_change_allowed": False,
                    "manual_financial_override_allowed": False,
                    "zero_substitution_allowed": False,
                    "double_counting_allowed": False
                },
                "roadmap_state": "v31_step_1_of_4_conversation_context_runtime_active_guarded",
                "next_step": "v31_conversation_intent_runtime",
                "status": "conversation_context_runtime_active_guarded"
            },
            "v31_conversation_intent_runtime": {
                "objective": "classify_natural_language_chat_or_voice_requests_into_guarded_energy_project_intents_and_bind_each_intent_to_existing_validated_runtime_sources",
                "roadmap_step": "2/4",
                "source_runtime": "v31_conversation_context_runtime",
                "supported_intents": {
                    "status": "summarize_current_project_and_data_readiness",
                    "explain": "explain_energy_financial_or_quality_result",
                    "compare": "compare_validated_periods_devices_or_financial_cases",
                    "diagnose": "identify_current_blockers_or_missing_inputs",
                    "recommend": "surface_only_guarded_publishable_recommendation_or_wait_state",
                    "report": "describe_or_prepare_existing_official_report_context",
                    "measure": "explain_measurement_need_and_next_validated_measurement_step",
                    "history": "summarize_validated_historical_energy_context"
                },
                "routing_contract": {
                    "one_primary_intent_required": True,
                    "domain_binding_required": True,
                    "source_runtime_binding_required": True,
                    "financial_gate_check_required_for_numeric_advice": True,
                    "authority_gate_check_required_for_external_action": True,
                    "ambiguity_may_fall_back_to_explain_or_status": True,
                    "unknown_intent_may_not_trigger_external_action": True
                },
                "response_contract": {
                    "answer_state": "available_blocked_or_partial",
                    "primary_answer": "validated_project_context_or_explicit_unavailable",
                    "reason": "required_when_blocked_or_partial",
                    "data_quality": "required",
                    "source_context": "required",
                    "next_safe_action": "validated_next_step_or_null"
                },
                "safety_policy": {
                    "recommend_intent_requires_existing_publishable_decision": True,
                    "report_intent_may_not_create_unvalidated_financial_values": True,
                    "diagnose_intent_may_not_modify_system": True,
                    "measure_intent_is_advisory_only": True,
                    "unknown_intent_external_execution_allowed": False
                },
                "roadmap_state": "v31_step_2_of_4_conversation_intent_runtime_active_guarded",
                "next_step": "v31_conversation_response_runtime",
                "status": "conversation_intent_runtime_active_guarded"
            },
            "v31_conversation_response_runtime": {
                "objective": "produce_guarded_machine_readable_response_guidance_for_natural_language_chat_and_voice_without_creating_unvalidated_energy_or_financial_facts",
                "roadmap_step": "3/4",
                "source_runtime": "v31_conversation_intent_runtime",
                "response_modes": [
                    "direct_answer",
                    "explanation",
                    "comparison",
                    "blocked_reason",
                    "safe_recommendation",
                    "measurement_next_step",
                    "report_handoff"
                ],
                "response_contract": {
                    "primary_answer_required": True,
                    "answer_state_required": True,
                    "data_quality_required": True,
                    "source_context_required": True,
                    "reason_required_when_blocked_or_partial": True,
                    "next_safe_action_required_when_material": True,
                    "financial_numbers_require_existing_validated_source": True,
                    "candidate_values_must_be_labelled_candidate": True,
                    "missing_values_must_be_stated_unavailable": True,
                    "primary_blocker_must_be_exposed_when_present": True
                },
                "language_policy": {
                    "ordinary_dutch_supported": True,
                    "ordinary_english_supported": True,
                    "voice_friendly_short_answer_supported": True,
                    "technical_detail_may_follow_primary_answer": True,
                    "machine_internal_gate_names_need_not_be_exposed_unless_useful": True
                },
                "recommendation_policy": {
                    "publish_only_existing_guarded_recommendation": True,
                    "financial_recommendation_requires_publishable_decision": True,
                    "blocked_recommendation_returns_wait_or_measurement_state": True,
                    "no_purchase_execution": True,
                    "no_supplier_switch_execution": True,
                    "no_contract_acceptance_execution": True,
                    "no_device_control_execution": True
                },
                "failure_policy": {
                    "unknown_or_ambiguous_request_defaults_to_safe_explanation": True,
                    "missing_financial_context_blocks_numeric_financial_advice": True,
                    "invalid_or_stale_context_may_not_be_presented_as_current": True,
                    "zero_substitution_allowed": False,
                    "fabricated_source_allowed": False
                },
                "roadmap_state": "v31_step_3_of_4_conversation_response_runtime_active_guarded",
                "next_step": "v31_chat_voice_completion_and_report_handoff",
                "status": "conversation_response_runtime_active_guarded"
            },
            "v31_chat_voice_completion_and_report_handoff": {
                "objective": "complete_v31_with_one_guarded_chat_voice_chain_and_auditable_handoff_to_existing_official_report_and_print_surfaces_without_external_execution",
                "roadmap_step": "4/4",
                "source_runtimes": [
                    "v31_conversation_context_runtime",
                    "v31_conversation_intent_runtime",
                    "v31_conversation_response_runtime"
                ],
                "completion_contract": {
                    "context_runtime_required": True,
                    "intent_runtime_required": True,
                    "response_runtime_required": True,
                    "report_handoff_required": True,
                    "print_handoff_required": True,
                    "current_release_identity_required": True,
                    "financial_and_quality_gates_must_remain_active": True,
                    "source_traceability_required": True,
                    "missing_values_may_not_be_assumed": True
                },
                "report_handoff": {
                    "management_summary": "existing_guarded_report_context_only",
                    "financial_kpis": "existing_publishable_validated_values_only",
                    "financial_analysis": "existing_guarded_financial_context_only",
                    "data_quality_context": "existing_quality_and_blocker_context",
                    "chat_response_may_request_report_generation": True,
                    "chat_response_may_not_invent_report_values": True
                },
                "print_handoff": {
                    "printable_output_uses_existing_official_report_contract": True,
                    "portrait_layout_preserved": True,
                    "official_template_policy_preserved": True,
                    "blocked_values_render_unavailable": True,
                    "candidate_values_primary_output_allowed": False
                },
                "voice_policy": {
                    "voice_answer_may_be_shorter_than_report_detail": True,
                    "technical_detail_may_follow_on_request": True,
                    "financial_numbers_still_require_validated_source": True,
                    "voice_may_not_cross_user_authority_gate": True
                },
                "safety_closure": {
                    "automatic_purchase_allowed": False,
                    "automatic_supplier_switch_allowed": False,
                    "automatic_contract_acceptance_allowed": False,
                    "automatic_advance_payment_change_allowed": False,
                    "automatic_device_control_change_allowed": False,
                    "manual_financial_override_allowed": False,
                    "zero_substitution_allowed": False,
                    "fabricated_source_allowed": False
                },
                "completion_states": {
                    "complete_guarded": "all_v31_chat_voice_and_handoff_contracts_present",
                    "complete_blocked_external": "v31_complete_but_external_financial_or_data_gates_still_block_specific_answers",
                    "incomplete": "one_or_more_required_v31_contracts_missing"
                },
                "roadmap_state": "v31_step_4_of_4_chat_voice_completion_and_report_handoff_active_guarded",
                "v31_release_state": "complete_after_home_assistant_validation",
                "next_major_release": "32.0.10",
                "status": "v31_chat_voice_completion_and_report_handoff_active_guarded"
            },
            "v32_final_integration_runtime": {
                "objective": "close_the_current_development_program_with_one_guarded_integrated_runtime_contract_covering_release_identity_reporting_financial_gates_chat_voice_backup_recovery_and_final_validation",
                "roadmap_step": "1/3",
                "integration_contract": {
                    "release_identity_runtime_required": True,
                    "financial_guardrails_required": True,
                    "official_report_contract_required": True,
                    "chat_voice_handoff_required": True,
                    "savings_action_chain_required": True,
                    "backup_recovery_contract_required": True,
                    "final_validation_contract_required": True,
                    "historical_actuals_must_remain_immutable": True,
                    "missing_values_may_not_be_assumed": True
                },
                "cross_runtime_consistency": {
                    "single_release_version_required": True,
                    "single_guarded_financial_policy_required": True,
                    "single_missing_value_policy_required": True,
                    "single_external_execution_authority_policy_required": True,
                    "single_official_report_template_policy_required": True
                },
                "safety_policy": {
                    "automatic_external_execution_allowed": False,
                    "automatic_supplier_switch_allowed": False,
                    "automatic_purchase_allowed": False,
                    "automatic_contract_acceptance_allowed": False,
                    "automatic_advance_payment_change_allowed": False,
                    "automatic_device_control_change_allowed": False,
                    "manual_financial_override_allowed": False,
                    "zero_substitution_allowed": False,
                    "fabricated_source_allowed": False
                },
                "roadmap_state": "v32_step_1_of_3_final_integration_runtime_active_guarded",
                "next_step": "v32_backup_recovery_runtime",
                "status": "final_integration_runtime_active_guarded"
            },
            "v32_backup_recovery_runtime": {
                "objective": "define_a_guarded_recoverable_release_state_for_the_energy_project_with_traceable_backup_contents_version_identity_and_recovery_validation",
                "roadmap_step": "2/3",
                "backup_contract": {
                    "current_release_version_required": True,
                    "manifest_required": True,
                    "sha256_inventory_required": True,
                    "project_agreements_required": True,
                    "roadmap_required": True,
                    "install_instructions_required": True,
                    "test_instructions_required": True,
                    "emergency_recovery_instructions_required": True,
                    "backup_may_not_silently_mix_release_versions": True
                },
                "recovery_contract": {
                    "restore_requires_matching_release_identity": True,
                    "restore_requires_manifest_validation": True,
                    "restore_requires_python_compile_check": True,
                    "restore_requires_runtime_smoke_check": True,
                    "home_assistant_validation_required_after_restore": True,
                    "previous_known_good_release_must_remain_recoverable": True
                },
                "retention_policy": {
                    "minimum_known_good_releases": 3,
                    "current_release_plus_previous_releases": True,
                    "corrupt_or_incomplete_backup_may_not_be_marked_good": True
                },
                "roadmap_state": "v32_step_2_of_3_backup_recovery_runtime_active_guarded",
                "next_step": "v32_final_validation_gate",
                "status": "backup_recovery_runtime_active_guarded"
            },
            "v32_final_validation_gate": {
                "objective": "mark_the_current_program_complete_only_after_static_runtime_integrity_backup_recovery_and_home_assistant_release_identity_validation",
                "roadmap_step": "3/3",
                "validation_contract": {
                    "full_regression_suite_required": True,
                    "python_compile_required": True,
                    "runtime_smoke_required": True,
                    "manifest_validation_required": True,
                    "zip_integrity_required": True,
                    "release_identity_validation_required": True,
                    "home_assistant_analysis_required": True,
                    "known_external_data_gates_may_remain_blocked": True
                },
                "completion_policy": {
                    "external_financial_data_dependencies_do_not_block_software_completion": True,
                    "software_integrity_failures_do_block_completion": True,
                    "release_identity_mismatch_blocks_completion": True,
                    "missing_backup_or_recovery_contract_blocks_completion": True,
                    "future_changes_after_completion_should_be_targeted_fixes_or_explicit_new_roadmap": True
                },
                "completion_states": {
                    "awaiting_home_assistant_validation": "all_local_checks_passed_but_final_ha_analysis_not_yet_validated",
                    "complete_guarded": "all_required_local_and_home_assistant_validation_passed",
                    "blocked": "one_or_more_required_software_validation_checks_failed"
                },
                "roadmap_state": "v32_step_3_of_3_final_validation_gate_active_guarded",
                "release_state": "awaiting_home_assistant_validation",
                "next_step_after_success": "maintenance_only_or_explicit_new_roadmap",
                "status": "final_validation_gate_active_guarded"
            },
            "release_identity_runtime": {
                "release_version": APP_VERSION,
                "release_family": "v32_final_integration",
                "validation_marker": "current_release_runtime_identity",
                "purpose": "make_home_assistant_runtime_release_identity_explicit_in_energy_analysis",
                "must_match_app_version": True,
                "must_match_addon_config_version": True,
                "status": "release_identity_active"
            },
            "v30_completion_gate_runtime": {
                "objective": "close_v30_only_when_the_full_optimization_chain_is_traceable_financially_guarded_non_executing_and_ready_for_safe_follow_up",
                "roadmap_step": "4/4",
                "source_runtimes": [
                    "v30_optimization_candidate_runtime",
                    "v30_optimization_selection_runtime",
                    "v30_optimization_execution_plan_runtime"
                ],
                "completion_contract": {
                    "candidate_discovery_runtime_required": True,
                    "single_selection_runtime_required": True,
                    "execution_plan_runtime_required": True,
                    "validated_financial_basis_required_for_numeric_advice": True,
                    "measurement_and_success_gate_required": True,
                    "rollback_gate_required": True,
                    "evidence_traceability_required": True,
                    "explicit_user_authority_required_before_external_execution": True,
                    "historical_actuals_must_remain_immutable": True,
                    "blocked_values_must_remain_non_numeric": True
                },
                "completion_states": {
                    "complete_guarded": "all_v30_runtime_contracts_present_and_external_execution_remains_user_gated",
                    "complete_measure_first": "optimization_chain_complete_but_more_measurement_is_required_before_numeric_action_advice",
                    "complete_blocked": "optimization_chain_complete_but_financial_or_evidence_gate_blocks_action",
                    "incomplete": "one_or_more_required_v30_runtime_contracts_missing"
                },
                "safety_closure": {
                    "automatic_external_execution_allowed": False,
                    "automatic_supplier_switch_allowed": False,
                    "automatic_purchase_allowed": False,
                    "automatic_contract_acceptance_allowed": False,
                    "automatic_advance_payment_change_allowed": False,
                    "automatic_device_control_change_allowed": False,
                    "manual_financial_override_allowed": False,
                    "missing_values_may_be_assumed": False,
                    "zero_substitution_allowed": False,
                    "double_counting_allowed": False
                },
                "publication_policy": {
                    "publish_v30_completion_state": True,
                    "publish_remaining_blockers": True,
                    "publish_financial_readiness_without_invented_values": True,
                    "publish_user_authority_requirement": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "audit_trail_required": True
                },
                "roadmap_state": "v30_step_4_of_4_completion_gate_active_guarded",
                "v30_release_state": "complete_after_home_assistant_validation",
                "next_step": "post_v30_roadmap_bundle",
                "status": "v30_completion_gate_active_guarded"
            },
            "v30_optimization_execution_plan_runtime": {
                "objective": "convert_the_single_guarded_optimization_selection_into_a_traceable_non_executing_plan_with_financial_measurement_authority_and_rollback_gates",
                "roadmap_step": "3/4",
                "source_runtime": "v30_optimization_selection_runtime",
                "execution_plan_contract": {
                    "single_selected_candidate_required": True,
                    "validated_positive_expected_euro_value_required": True,
                    "financial_basis_required": True,
                    "measurement_baseline_required": True,
                    "success_metric_required": True,
                    "rollback_condition_required": True,
                    "evidence_references_required": True,
                    "explicit_user_authority_required_before_external_execution": True,
                    "execution_plan_is_advisory_until_authorized": True
                },
                "plan_states": {
                    "blocked": "selection_or_required_financial_measurement_gate_not_ready",
                    "measure_first": "baseline_or_success_metric_requires_additional_measurement",
                    "ready_for_user_review": "guarded_plan_complete_but_no_external_execution_authority",
                    "user_authorized": "explicit_user_authority_recorded_for_the_specific_plan",
                    "hold": "selected_case_no_longer_justifies_execution"
                },
                "execution_boundaries": {
                    "automatic_external_execution_allowed": False,
                    "automatic_supplier_switch_allowed": False,
                    "automatic_purchase_allowed": False,
                    "automatic_contract_acceptance_allowed": False,
                    "automatic_advance_payment_change_allowed": False,
                    "automatic_device_control_change_allowed": False,
                    "historical_actuals_rewrite_allowed": False,
                    "manual_financial_override_allowed": False,
                    "missing_values_may_be_assumed": False,
                    "zero_substitution_allowed": False,
                    "double_counting_allowed": False
                },
                "rollback_policy": {
                    "rollback_plan_required_before_authorization": True,
                    "financial_underperformance_must_remain_visible": True,
                    "negative_realized_value_must_be_preserved": True,
                    "user_can_stop_or_reject_plan_at_any_time": True
                },
                "publication_policy": {
                    "publish_plan_as_advice_not_execution": True,
                    "publish_financial_basis_and_expected_value_only_when_validated": True,
                    "publish_measurement_baseline_and_success_metric": True,
                    "publish_blockers_and_authority_state": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "audit_trail_required": True
                },
                "roadmap_state": "v30_step_3_of_4_optimization_execution_plan_runtime_active_guarded",
                "next_step": "v30_completion_gate",
                "status": "optimization_execution_plan_runtime_active_guarded"
            },
            "v30_optimization_selection_runtime": {
                "objective": "select_at_most_one_primary_energy_cost_optimization_action_from_validated_candidates_using_financial_value_confidence_effort_and_user_authority_gates",
                "roadmap_step": "2/4",
                "source_runtime": "v30_adaptive_optimization_candidate_runtime",
                "selection_contract": {
                    "validated_candidate_required": True,
                    "maximum_primary_selection": 1,
                    "positive_validated_expected_euro_value_required": True,
                    "confidence_required": True,
                    "implementation_effort_required": True,
                    "external_gate_open_required": True,
                    "user_authority_gate_required_before_execution": True,
                    "evidence_references_required": True,
                    "data_quality_required": True
                },
                "selection_policy": {
                    "primary_sort": "validated_expected_euro_value_descending",
                    "secondary_sort": "confidence_descending",
                    "tertiary_sort": "implementation_effort_ascending",
                    "blocked_candidates_excluded": True,
                    "measure_first_candidates_excluded": True,
                    "negative_or_zero_value_candidates_excluded": True,
                    "ties_remain_advisory_until_user_choice": True
                },
                "selection_states": {
                    "blocked": "no_candidate_passes_all_financial_measurement_or_external_gates",
                    "measure_first": "best_candidate_requires_additional_measurement",
                    "advisory_selection": "one_candidate_is_financially_preferred_but_user_authority_gate_not_open",
                    "user_approved_for_execution_planning": "preferred_candidate_and_explicit_user_authority_validated",
                    "hold": "no_positive_validated_case_currently_justifies_action"
                },
                "safety_policy": {
                    "automatic_external_execution_allowed": False,
                    "automatic_supplier_switch_allowed": False,
                    "automatic_purchase_allowed": False,
                    "automatic_contract_acceptance_allowed": False,
                    "automatic_advance_payment_change_allowed": False,
                    "automatic_device_control_change_allowed": False,
                    "candidate_value_may_become_realized_savings": False,
                    "manual_financial_override_allowed": False,
                    "zero_substitution_allowed": False,
                    "double_counting_allowed": False
                },
                "publication_policy": {
                    "publish_maximum_one_primary_selection": True,
                    "publish_reason_and_blocker": True,
                    "publish_expected_euro_value_only_when_validated": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "audit_trail_required": True
                },
                "roadmap_state": "v30_step_2_of_4_optimization_selection_runtime_active_guarded",
                "next_step": "v30_optimization_execution_plan_runtime",
                "status": "optimization_selection_runtime_active_guarded"
            },
            "v30_adaptive_optimization_candidate_runtime": {
                "objective": "derive_guarded_cost_optimization_candidates_from_validated_forecasts_current_tariff_context_and_measured_energy_patterns_without_automatic_external_execution",
                "roadmap_step": "1/4",
                "source_chain": [
                    "v29_forecast_calibration_runtime",
                    "v29_calibrated_savings_forecast_runtime",
                    "v29_forecast_publication_runtime",
                    "v29_completion_gate"
                ],
                "optimization_domains": [
                    "load_shifting",
                    "supplier_contract",
                    "monthly_advance",
                    "device_replacement",
                    "home_battery"
                ],
                "candidate_contract": {
                    "validated_financial_context_required": True,
                    "validated_measurement_context_required_when_material": True,
                    "forecast_and_actuals_must_remain_separate": True,
                    "candidate_expected_euro_value_required_for_ranking": True,
                    "confidence_required": True,
                    "implementation_effort_required": True,
                    "external_gate_state_required": True,
                    "evidence_references_required": True,
                    "data_quality_required": True
                },
                "candidate_states": {
                    "blocked": "required_external_financial_or_measurement_gate_closed",
                    "measure_first": "potential_exists_but_measurement_or_confidence_incomplete",
                    "financially_evaluable": "validated_inputs_complete_but_final_action_not_selected",
                    "eligible_for_optimization": "validated_positive_financial_case_and_required_gates_open",
                    "hold": "validated_case_does_not_currently_justify_change"
                },
                "ranking_policy": {
                    "maximum_primary_candidates": 3,
                    "rank_by_validated_expected_euro_value_first": True,
                    "confidence_is_secondary": True,
                    "implementation_effort_is_tiebreaker": True,
                    "blocked_candidates_excluded_from_numeric_ranking": True,
                    "candidate_values_may_not_become_realized_savings": True,
                    "negative_expected_value_preserved": True
                },
                "safety_policy": {
                    "automatic_supplier_switch_allowed": False,
                    "automatic_purchase_allowed": False,
                    "automatic_contract_acceptance_allowed": False,
                    "automatic_advance_payment_change_allowed": False,
                    "automatic_device_control_change_allowed": False,
                    "historical_actuals_rewrite_allowed": False,
                    "manual_financial_override_allowed": False,
                    "missing_values_may_be_assumed": False,
                    "zero_substitution_allowed": False,
                    "double_counting_allowed": False
                },
                "publication_policy": {
                    "eligible_candidate_may_be_published_as_advice_only_after_required_gates": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "candidate_label_required": True,
                    "audit_trail_required": True
                },
                "roadmap_state": "v30_step_1_of_4_adaptive_optimization_candidate_runtime_active_guarded",
                "next_step": "v30_optimization_selection_runtime",
                "status": "adaptive_optimization_candidate_runtime_active_guarded"
            },
            "v29_forecast_publication_runtime": {
                "objective": "publish_only_validated_calibrated_savings_forecasts_with_visible_uncertainty_and_clear_separation_from_actuals_and_business_case_values",
                "roadmap_step": "3/4",
                "source_runtime": "v29_calibrated_savings_forecast_runtime",
                "publication_contract": {
                    "validated_forecast_required": True,
                    "actuals_business_case_and_forecast_visibly_separate": True,
                    "uncertainty_required": True,
                    "confidence_required": True,
                    "forecast_horizon_required": True,
                    "evidence_references_required": True,
                    "negative_forecast_adjustment_preserved": True,
                    "candidate_values_primary_output_allowed": False
                },
                "report_surface_contract": {
                    "page1_management_summary": "validated_calibrated_forecast_or_guarded_wait",
                    "page1_financial_kpis": "validated_forecast_values_with_uncertainty_only",
                    "page2_financial_analysis": "business_case_prior_forecast_calibrated_forecast_variance_and_confidence",
                    "pages3_13_context": "evidence_context_blockers_quality_and_audit_trail"
                },
                "safety_policy": {
                    "forecast_may_be_presented_as_realized_savings": False,
                    "historical_actuals_rewrite_allowed": False,
                    "candidate_forecast_may_drive_user_action": False,
                    "automatic_annualization_from_short_window": False,
                    "partial_period_promotion_allowed": False,
                    "zero_substitution_allowed": False,
                    "double_counting_allowed": False,
                    "manual_financial_override_allowed": False
                },
                "roadmap_state": "v29_step_3_of_4_forecast_publication_runtime_active_guarded",
                "next_step": "v29_completion_gate",
                "status": "forecast_publication_runtime_active_guarded"
            },
            "v29_completion_gate": {
                "objective": "complete_v29_with_one_guarded_chain_from_validated_outcome_learning_to_forecast_calibration_calibrated_savings_forecast_and_official_publication",
                "roadmap_step": "4/4",
                "chain_components": {
                    "forecast_calibration_runtime": "ready_guarded",
                    "calibrated_savings_forecast_runtime": "ready_guarded",
                    "forecast_publication_runtime": "ready_guarded"
                },
                "external_dependencies": {
                    "learning_gate": "repeated_validated_outcomes_required",
                    "context_gate": "seasonality_weather_usage_or_supplier_context_required_when_material",
                    "confidence_gate": "validated_confidence_required",
                    "forecast_horizon_gate": "validated_forecast_horizon_required"
                },
                "completion_policy": {
                    "external_data_may_remain_blocked_at_release_completion": True,
                    "automatic_transition_after_external_gates": True,
                    "historical_actuals_rewrite_allowed": False,
                    "candidate_values_may_drive_forecast_or_action": False,
                    "single_event_calibration_allowed": False,
                    "partial_period_promotion_allowed": False,
                    "missing_values_may_be_assumed": False,
                    "zero_substitution_allowed": False,
                    "double_counting_allowed": False,
                    "manual_financial_override_allowed": False
                },
                "publication_policy": {
                    "publish_only_validated_calibrated_forecasts": True,
                    "actuals_business_case_and_forecast_visibly_separate": True,
                    "uncertainty_and_confidence_required": True,
                    "negative_forecast_adjustment_preserved": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "audit_trail_required": True
                },
                "roadmap_state": "v29_complete_guarded_forecast_calibration_and_publication_chain",
                "next_major_release": "32.0.10",
                "status": "v29_complete_external_learning_context_and_confidence_gates_remain"
            },
            "v29_calibrated_savings_forecast_runtime": {
                "objective": "apply_only_validated_forecast_calibration_to_future_savings_expectations_while_preserving_actuals_business_cases_and_uncertainty",
                "roadmap_step": "2/4",
                "source_runtime": "v29_forecast_calibration_runtime",
                "forecast_contract": {
                    "validated_calibration_required": True,
                    "historical_actuals_immutable": True,
                    "business_case_value_preserved_separately": True,
                    "calibrated_forecast_separate_from_realized_savings": True,
                    "uncertainty_required": True,
                    "confidence_required": True,
                    "forecast_horizon_required": True,
                    "evidence_references_required": True
                },
                "forecast_states": {
                    "blocked": "validated_calibration_not_available",
                    "candidate": "calibration_exists_but_required_context_or_confidence_incomplete",
                    "validated": "calibration_context_confidence_and_horizon_validated",
                    "hold": "validated_calibration_does_not_justify_change"
                },
                "forecast_item_contract": {
                    "domain": "validated_domain_required",
                    "forecast_state": "required",
                    "business_case_savings_eur": "validated_reference_value_or_null",
                    "prior_forecast_savings_eur": "validated_forecast_or_null",
                    "calibrated_forecast_savings_eur": "validated_value_or_null",
                    "forecast_variance_eur": "validated_calibrated_minus_prior_or_null",
                    "forecast_horizon": "validated_period_required",
                    "uncertainty": "validated_range_or_state_required",
                    "confidence": "required",
                    "evidence_references": "required",
                    "primary_blocker": "validated_blocker_or_null",
                    "data_quality": "required"
                },
                "financial_guardrails": {
                    "calibrated_forecast_may_not_become_realized_savings": True,
                    "candidate_values_may_not_become_validated_forecast": True,
                    "historical_actuals_rewrite_allowed": False,
                    "automatic_annualization_from_short_window": False,
                    "partial_period_promotion_allowed": False,
                    "zero_substitution_allowed": False,
                    "double_counting_allowed": False,
                    "negative_forecast_adjustment_preserved": True,
                    "manual_financial_override_allowed": False
                },
                "publication_policy": {
                    "publish_only_validated_calibrated_forecast": True,
                    "actuals_business_case_and_forecast_visibly_separate": True,
                    "uncertainty_visible_when_forecast_published": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "audit_trail_required": True
                },
                "roadmap_state": "v29_step_2_of_4_calibrated_savings_forecast_runtime_active_guarded",
                "next_step": "v29_forecast_publication_runtime",
                "status": "calibrated_savings_forecast_runtime_active_guarded"
            },
            "v29_forecast_calibration_runtime": {
                "objective": "calibrate_future_energy_and_financial_forecasts_from_repeated_validated_outcomes_without_erasing_observed_history_or_promoting_low_quality_signals",
                "roadmap_step": "1/4",
                "source_chain": [
                    "v28_execution_outcome_verification_runtime",
                    "v28_verified_outcome_portfolio_runtime",
                    "v28_outcome_learning_runtime",
                    "v28_completion_gate"
                ],
                "calibration_contract": {
                    "repeated_validated_learning_signal_required": True,
                    "minimum_independent_evidence_events": 2,
                    "historical_actuals_must_remain_immutable": True,
                    "forecast_adjustment_must_be_separate_from_actuals": True,
                    "seasonality_context_required_when_material": True,
                    "weather_context_required_when_material": True,
                    "occupancy_or_usage_context_required_when_material": True,
                    "supplier_contract_context_required_when_material": True,
                    "confidence_required": True,
                    "audit_trail_required": True
                },
                "calibration_states": {
                    "insufficient_evidence": "repeated_validated_evidence_gate_closed",
                    "calibration_candidate": "repeated_signal_exists_but_context_or_confidence_gate_incomplete",
                    "calibration_validated": "repeated_signal_and_required_context_validated",
                    "hold": "validated_evidence_does_not_justify_forecast_adjustment"
                },
                "calibration_item_contract": {
                    "domain": "validated_domain_required",
                    "calibration_state": "required",
                    "baseline_forecast_value": "validated_forecast_or_null",
                    "proposed_adjustment_value": "validated_adjustment_or_null",
                    "calibrated_forecast_value": "validated_value_or_null",
                    "confidence": "required",
                    "evidence_count": "nonnegative_integer",
                    "evidence_references": "validated_references_required",
                    "context_adjustments": "validated_context_or_null",
                    "primary_blocker": "validated_blocker_or_null",
                    "data_quality": "required"
                },
                "financial_guardrails": {
                    "candidate_values_may_not_become_actuals": True,
                    "historical_actuals_rewrite_allowed": False,
                    "single_event_calibration_allowed": False,
                    "automatic_annualization_from_short_window": False,
                    "partial_period_promotion_allowed": False,
                    "zero_substitution_allowed": False,
                    "double_counting_allowed": False,
                    "negative_learning_signal_preserved": True,
                    "manual_financial_override_allowed": False
                },
                "publication_policy": {
                    "calibrated_forecast_publishable_only_when_validated": True,
                    "actuals_and_forecasts_must_be_visibly_separate": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "audit_trail_required": True
                },
                "roadmap_state": "v29_step_1_of_4_forecast_calibration_runtime_active_guarded",
                "next_step": "v29_calibrated_savings_forecast_runtime",
                "status": "forecast_calibration_runtime_active_guarded"
            },
            "v28_outcome_learning_runtime": {
                "objective": "learn_from_validated_execution_outcomes_without_rewriting_future_financial_models_from_single_or_low_quality_events",
                "roadmap_step": "3/4",
                "source_runtime": "v28_verified_outcome_portfolio_runtime",
                "learning_contract": {
                    "validated_outcome_required": True,
                    "business_case_reference_required": True,
                    "variance_reason_required": True,
                    "repeated_evidence_required_for_model_adjustment": True,
                    "single_event_model_rewrite_allowed": False,
                    "short_window_model_rewrite_allowed": False,
                    "seasonality_context_required_when_material": True,
                    "usage_context_required_when_material": True,
                    "supplier_contract_changes_separately_validated": True,
                    "audit_trail_required": True
                },
                "learning_outputs": {
                    "validated_learning_signal": "positive_negative_or_neutral",
                    "variance_pattern": "validated_pattern_or_null",
                    "future_assumption_adjustment": "guarded_adjustment_or_null",
                    "confidence": "validated_state_required",
                    "evidence_count": "nonnegative_integer",
                    "primary_blocker": "validated_blocker_or_null",
                    "data_quality": "required"
                },
                "safety_policy": {
                    "candidate_values_may_drive_learning": False,
                    "missing_values_may_be_assumed": False,
                    "zero_substitution_allowed": False,
                    "negative_outcomes_may_be_discarded": False,
                    "manual_financial_override_allowed": False
                },
                "roadmap_state": "v28_step_3_of_4_outcome_learning_runtime_active_guarded",
                "next_step": "v28_completion_gate",
                "status": "outcome_learning_runtime_active_guarded"
            },
            "v28_completion_gate": {
                "objective": "complete_v28_with_one_guarded_closed_loop_chain_from_execution_verification_to_verified_portfolio_and_learning",
                "roadmap_step": "4/4",
                "chain_components": {
                    "execution_outcome_verification_runtime": "ready_guarded",
                    "verified_outcome_portfolio_runtime": "ready_guarded",
                    "outcome_learning_runtime": "ready_guarded"
                },
                "external_dependencies": {
                    "validated_execution_gate": "traceable_user_execution_evidence_required",
                    "measurement_gate": "comparable_pre_and_post_action_measurement_required",
                    "normalization_gate": "validated_normalization_required_when_material",
                    "learning_gate": "repeated_validated_evidence_required_for_model_adjustment"
                },
                "completion_policy": {
                    "external_data_may_remain_blocked_at_release_completion": True,
                    "automatic_transition_after_external_gates": True,
                    "candidate_values_may_drive_actuals_or_learning": False,
                    "single_event_model_rewrite_allowed": False,
                    "partial_period_promotion_allowed": False,
                    "missing_values_may_be_assumed": False,
                    "zero_substitution_allowed": False,
                    "double_counting_allowed": False,
                    "manual_financial_override_allowed": False
                },
                "publication_policy": {
                    "publish_realized_values_only_from_validated_outcomes": True,
                    "publish_learning_only_from_validated_repeated_evidence": True,
                    "negative_realized_impact_preserved": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "audit_trail_required": True
                },
                "roadmap_state": "v28_complete_guarded_execution_outcome_learning_chain",
                "next_major_release": "32.0.10",
                "status": "v28_complete_external_execution_measurement_and_learning_gates_remain"
            },
            "v28_verified_outcome_portfolio_runtime": {
                "objective": "aggregate_only_validated_execution_outcomes_into_a_traceable_savings_portfolio_without_double_counting_or_estimate_promotion",
                "roadmap_step": "2/4",
                "source_runtime": "v28_execution_outcome_verification_runtime",
                "portfolio_contract": {
                    "stable_action_id_required": True,
                    "outcome_validated_required_for_realized_totals": True,
                    "maximum_primary_outcomes": 3,
                    "estimated_and_realized_values_separated": True,
                    "negative_realized_impact_preserved": True,
                    "duplicate_action_ids_forbidden": True,
                    "overlapping_measurement_windows_require_explicit_allocation": True,
                    "missing_values_may_not_be_assumed": True
                },
                "portfolio_metrics": {
                    "validated_realized_savings_eur": "sum_of_validated_nonduplicated_outcomes_or_null",
                    "validated_realized_cost_eur": "sum_of_validated_negative_outcomes_or_null",
                    "net_validated_impact_eur": "validated_savings_plus_validated_cost_or_null",
                    "business_case_total_eur": "sum_of_referenced_validated_business_cases_or_null",
                    "variance_total_eur": "validated_net_impact_minus_business_case_total_or_null",
                    "validated_action_count": "nonnegative_integer",
                    "pending_action_count": "nonnegative_integer"
                },
                "allocation_guardrails": {
                    "double_counting_allowed": False,
                    "automatic_overlap_allocation_allowed": False,
                    "automatic_annualization_allowed": False,
                    "candidate_values_in_realized_totals_allowed": False,
                    "partial_period_promotion_allowed": False,
                    "zero_substitution_allowed": False
                },
                "publication_policy": {
                    "portfolio_totals_publishable_only_from_validated_outcomes": True,
                    "pending_outcomes_remain_separate": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "audit_trail_required": True
                },
                "roadmap_state": "v28_step_2_of_4_verified_outcome_portfolio_active_guarded",
                "next_step": "v28_outcome_learning_runtime",
                "status": "verified_outcome_portfolio_runtime_active_guarded"
            },
            "v28_execution_outcome_verification_runtime": {
                "objective": "verify_the_real_world_outcome_of_user_executed_energy_actions_before_any_realized_financial_result_is_accepted_or_learned",
                "roadmap_step": "1/4",
                "source_chain": [
                    "v27_execution_readiness_runtime",
                    "v27_execution_plan_runtime",
                    "v27_execution_plan_publication_runtime",
                    "v27_completion_gate"
                ],
                "verification_states": {
                    "waiting_for_user_execution": "no_validated_execution_evidence_yet",
                    "execution_evidence_pending": "user_action_reported_but_traceable_evidence_missing",
                    "measurement_pending": "execution_validated_but_required_post_action_measurement_incomplete",
                    "comparison_pending": "baseline_and_post_action_measurement_exist_but_comparison_not_validated",
                    "outcome_validated": "execution_and_comparable_financial_outcome_validated"
                },
                "verification_contract": {
                    "stable_action_id_required": True,
                    "validated_execution_evidence_required": True,
                    "pre_action_baseline_required_when_financial_savings_claimed": True,
                    "post_action_measurement_required_when_financial_savings_claimed": True,
                    "comparable_measurement_window_required": True,
                    "normalization_required_when_material": True,
                    "business_case_reference_required": True,
                    "self_report_alone_may_not_create_realized_savings": True,
                    "candidate_values_may_not_be_promoted_to_actuals": True,
                    "missing_values_may_not_be_assumed": True
                },
                "outcome_contract": {
                    "action_id": "stable_traceable_identifier_required",
                    "domain": "validated_domain_required",
                    "verification_state": "required",
                    "execution_evidence_reference": "validated_reference_or_null",
                    "baseline_evidence_reference": "validated_reference_or_null",
                    "post_action_evidence_reference": "validated_reference_or_null",
                    "business_case_savings_eur": "validated_original_value_or_null",
                    "realized_savings_eur": "validated_measured_value_or_null",
                    "variance_eur": "validated_realized_minus_business_case_or_null",
                    "measurement_period": "validated_period_or_null",
                    "primary_blocker": "validated_blocker_or_null",
                    "data_quality": "required"
                },
                "financial_guardrails": {
                    "automatic_annualization_from_short_window": False,
                    "partial_period_promotion_allowed": False,
                    "zero_substitution_allowed": False,
                    "double_counting_allowed": False,
                    "negative_realized_impact_preserved": True,
                    "manual_financial_override_allowed": False
                },
                "authority_boundaries": {
                    "automatic_purchase_allowed": False,
                    "automatic_supplier_switch_allowed": False,
                    "automatic_contract_acceptance_allowed": False,
                    "automatic_advance_payment_change_allowed": False,
                    "automatic_device_control_change_allowed": False
                },
                "publication_policy": {
                    "realized_savings_publishable_only_when_outcome_validated": True,
                    "variance_publishable_only_from_validated_values": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "audit_trail_required": True
                },
                "roadmap_state": "v28_step_1_of_4_execution_outcome_verification_active_guarded",
                "next_step": "v28_verified_outcome_portfolio_runtime",
                "status": "execution_outcome_verification_runtime_active_guarded"
            },
            "v27_execution_plan_publication_runtime": {
                "objective": "publish_guarded_execution_plans_to_official_report_surfaces_without_crossing_user_authority_or_financial_validation_boundaries",
                "roadmap_step": "3/4",
                "source_runtime": "v27_execution_plan_runtime",
                "publication_policy": {
                    "maximum_primary_plans": 3,
                    "ready_for_user_action_requires_all_required_gates_open": True,
                    "measurement_plan_requires_explicit_measurement_need": True,
                    "blocked_external_requires_explicit_dependency": True,
                    "hold_requires_validated_non_action_case": True,
                    "candidate_values_primary_output_allowed": False,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "reason_required": True,
                    "evidence_reference_required": True,
                    "data_quality_required": True
                },
                "report_surface_contract": {
                    "page1_management_summary": "top_guarded_execution_plans_or_wait_state",
                    "page1_financial_kpis": "validated_publishable_execution_values_only",
                    "page2_financial_analysis": "execution_plan_financial_basis_measurement_and_blockers",
                    "pages3_13_context": "execution_evidence_measurement_success_stop_rollback_and_quality"
                },
                "authority_boundaries": {
                    "automatic_purchase_allowed": False,
                    "automatic_supplier_switch_allowed": False,
                    "automatic_contract_acceptance_allowed": False,
                    "automatic_advance_payment_change_allowed": False,
                    "automatic_device_control_change_allowed": False
                },
                "roadmap_state": "v27_step_3_of_4_execution_plan_publication_active_guarded",
                "next_step": "v27_completion_gate",
                "status": "execution_plan_publication_runtime_active_guarded"
            },
            "v27_completion_gate": {
                "objective": "complete_v27_with_one_guarded_chain_from_execution_readiness_to_traceable_execution_plan_and_official_publication",
                "roadmap_step": "4/4",
                "chain_components": {
                    "execution_readiness_runtime": "ready_guarded",
                    "execution_plan_runtime": "ready_guarded",
                    "execution_plan_publication_runtime": "ready_guarded"
                },
                "external_dependencies": {
                    "observation_gate": "minimum_7_observed_days",
                    "supplier_contract_gate": "official_contract_values_required",
                    "supplier_all_in_gate": "validated_supplier_components_required",
                    "measurement_gate": "validated_domain_measurement_required",
                    "user_action_gate": "explicit_user_action_required_before_external_execution"
                },
                "completion_policy": {
                    "external_data_may_remain_blocked_at_release_completion": True,
                    "automatic_transition_after_external_gates": True,
                    "automatic_external_execution_allowed": False,
                    "manual_financial_override_allowed": False,
                    "candidate_values_may_drive_execution": False,
                    "partial_period_may_be_promoted_to_full_period": False,
                    "missing_values_may_be_assumed": False,
                    "zero_substitution_allowed": False,
                    "double_counting_allowed": False
                },
                "publication_policy": {
                    "publish_maximum_primary_plans": 3,
                    "publish_ready_for_user_action_only_when_all_required_gates_open": True,
                    "publish_measurement_plan_only_with_explicit_measurement_need": True,
                    "publish_blocked_external_only_with_explicit_dependency": True,
                    "publish_hold_only_from_validated_case": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "audit_trail_required": True
                },
                "roadmap_state": "v27_complete_guarded_execution_planning_chain",
                "next_major_release": "32.0.10",
                "status": "v27_complete_external_data_and_user_action_gates_remain"
            },
            "v27_execution_plan_runtime": {
                "objective": "turn_execution_ready_energy_actions_into_small_traceable_plans_without_crossing_financial_or_device_control_authority_boundaries",
                "roadmap_step": "2/4",
                "source_runtime": "v27_execution_readiness_runtime",
                "plan_contract": {
                    "maximum_primary_plans": 3,
                    "execution_ready_source_required": True,
                    "validated_financial_case_required": True,
                    "evidence_reference_required": True,
                    "implementation_effort_required": True,
                    "owner_or_required_user_action_required": True,
                    "measurement_plan_required_when_applicable": True,
                    "success_criterion_required": True,
                    "stop_condition_required": True,
                    "rollback_path_required_when_applicable": True
                },
                "plan_states": {
                    "ready_for_user_action": "all_required_gates_open_and_user_action_is_next",
                    "measurement_plan": "measurement_is_next_required_step",
                    "blocked_external": "external_data_contract_or_measurement_dependency_closed",
                    "hold": "validated_case_does_not_currently_justify_execution"
                },
                "authority_boundaries": {
                    "automatic_purchase_allowed": False,
                    "automatic_supplier_switch_allowed": False,
                    "automatic_contract_acceptance_allowed": False,
                    "automatic_advance_payment_change_allowed": False,
                    "automatic_device_control_change_allowed": False,
                    "manual_financial_override_allowed": False
                },
                "financial_guardrails": {
                    "candidate_values_may_not_be_promoted_to_realized": True,
                    "partial_period_promotion_allowed": False,
                    "missing_values_may_not_be_assumed": True,
                    "zero_substitution_allowed": False,
                    "double_counting_allowed": False,
                    "negative_financial_value_preserved": True
                },
                "plan_item_contract": {
                    "priority": "positive_integer_or_null",
                    "domain": "validated_domain_required",
                    "plan_state": "required",
                    "next_action": "validated_action_or_wait_state",
                    "required_user_action": "explicit_action_or_null",
                    "validated_expected_euro_value": "validated_value_or_null",
                    "confidence": "required",
                    "implementation_effort": "required",
                    "measurement_plan": "required_when_applicable",
                    "success_criterion": "required",
                    "stop_condition": "required",
                    "rollback_path": "required_when_applicable",
                    "primary_blocker": "validated_blocker_or_null",
                    "evidence_reference": "required",
                    "data_quality": "required"
                },
                "roadmap_state": "v27_step_2_of_4_execution_plan_runtime_active_guarded",
                "next_step": "v27_execution_plan_publication_runtime",
                "status": "execution_plan_runtime_active_guarded"
            },
            "v27_execution_readiness_runtime": {
                "objective": "convert_guarded_financial_actions_into_execution_ready_steps_only_when_required_evidence_measurement_and_external_gates_are_open",
                "roadmap_step": "1/4",
                "source_chain": [
                    "v26_decision_value_prioritization_runtime",
                    "v26_action_queue_runtime",
                    "v26_action_queue_publication_runtime",
                    "v26_completion_gate"
                ],
                "readiness_contract": {
                    "maximum_primary_actions": 3,
                    "validated_financial_case_required": True,
                    "validated_evidence_reference_required": True,
                    "required_external_gates_must_be_open": True,
                    "implementation_effort_required": True,
                    "measurement_plan_required_when_savings_need_validation": True,
                    "rollback_or_stop_condition_required": True,
                    "candidate_values_may_not_be_treated_as_realized": True,
                    "missing_values_may_not_be_assumed": True
                },
                "execution_states": {
                    "ready_to_execute": "financial_case_validated_and_all_required_gates_open",
                    "ready_to_measure": "measurement_is_the_next_required_action",
                    "blocked_external": "required_external_data_or_contract_gate_closed",
                    "hold": "validated_case_does_not_currently_justify_execution"
                },
                "domain_guardrails": {
                    "supplier": "official_contract_components_and_supplier_all_in_gate_required_before_switch_or_advance_change",
                    "device_replacement": "validated_device_consumption_payback_and_replacement_case_required",
                    "battery": "validated_household_profile_regulatory_power_limit_and_financial_case_required",
                    "load_shift": "validated_tariff_window_and_measurable_shift_opportunity_required"
                },
                "execution_item_contract": {
                    "priority": "positive_integer_or_null",
                    "domain": "validated_domain_required",
                    "execution_state": "required",
                    "action": "validated_action_or_wait_state",
                    "validated_expected_euro_value": "validated_value_or_null",
                    "confidence": "required",
                    "implementation_effort": "required",
                    "required_input": "validated_dependency_or_null",
                    "measurement_plan": "required_when_applicable",
                    "stop_condition": "required",
                    "evidence_reference": "required",
                    "data_quality": "required"
                },
                "safety_policy": {
                    "automatic_supplier_switch_allowed": False,
                    "automatic_purchase_allowed": False,
                    "automatic_advance_payment_change_allowed": False,
                    "automatic_device_control_change_allowed": False,
                    "manual_financial_override_allowed": False,
                    "double_counting_allowed": False,
                    "partial_period_promotion_allowed": False
                },
                "roadmap_state": "v27_step_1_of_4_execution_readiness_runtime_active_guarded",
                "next_step": "v27_execution_plan_runtime",
                "status": "execution_readiness_runtime_active_guarded"
            },
            "v26_action_queue_publication_runtime": {
                "objective": "publish_the_guarded_action_queue_into_official_report_surfaces_without_promoting_blocked_candidate_or_unvalidated_financial_values",
                "roadmap_step": "3/4",
                "source_runtime": "v26_action_queue_runtime",
                "publication_policy": {
                    "maximum_primary_actions": 3,
                    "act_now_requires_all_required_gates_open": True,
                    "measure_first_requires_explicit_measurement_gap": True,
                    "wait_for_data_requires_explicit_blocker": True,
                    "do_not_pursue_requires_validated_non_positive_or_unjustified_case": True,
                    "candidate_values_primary_output_allowed": False,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "reason_required": True,
                    "evidence_reference_required": True,
                    "data_quality_required": True
                },
                "report_surface_contract": {
                    "page1_management_summary": "top_guarded_actions_or_wait_state",
                    "page1_financial_kpis": "validated_publishable_action_values_only",
                    "page2_financial_analysis": "ranked_action_queue_financial_basis_and_blockers",
                    "pages3_13_context": "action_evidence_measurement_needs_quality_and_traceability"
                },
                "roadmap_state": "v26_step_3_of_4_action_queue_publication_active_guarded",
                "next_step": "v26_completion_gate",
                "status": "action_queue_publication_runtime_active_guarded"
            },
            "v26_completion_gate": {
                "objective": "complete_v26_with_one_guarded_chain_from_financial_value_prioritization_to_traceable_action_queue_and_official_publication",
                "roadmap_step": "4/4",
                "chain_components": {
                    "decision_value_prioritization_runtime": "ready_guarded",
                    "action_queue_runtime": "ready_guarded",
                    "action_queue_publication_runtime": "ready_guarded"
                },
                "external_dependencies": {
                    "observation_gate": "minimum_7_observed_days",
                    "supplier_contract_gate": "official_contract_values_required",
                    "supplier_all_in_gate": "validated_supplier_components_required",
                    "measurement_gate": "validated_domain_measurement_required"
                },
                "completion_policy": {
                    "external_data_may_remain_blocked_at_release_completion": True,
                    "automatic_transition_after_external_gates": True,
                    "manual_financial_override_allowed": False,
                    "candidate_values_may_drive_action": False,
                    "partial_period_may_be_promoted_to_full_period": False,
                    "missing_values_may_be_assumed": False,
                    "zero_substitution_allowed": False,
                    "double_counting_allowed": False
                },
                "publication_policy": {
                    "publish_maximum_primary_actions": 3,
                    "publish_act_now_only_when_all_required_gates_open": True,
                    "publish_measure_first_only_with_explicit_measurement_gap": True,
                    "publish_wait_for_data_only_with_explicit_blocker": True,
                    "publish_do_not_pursue_only_from_validated_case": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "audit_trail_required": True
                },
                "roadmap_state": "v26_complete_guarded_financial_action_queue_chain",
                "next_major_release": "32.0.10",
                "status": "v26_complete_external_data_gates_remain"
            },
            "v26_action_queue_runtime": {
                "objective": "materialize_the_guarded_decision_value_ranking_into_a_small_traceable_action_queue_without_bypassing_external_financial_gates",
                "roadmap_step": "2/4",
                "source_runtime": "v26_decision_value_prioritization_runtime",
                "queue_policy": {
                    "maximum_primary_actions": 3,
                    "ranked_actions_only": True,
                    "blocked_actions_remain_visible": True,
                    "blocked_actions_may_not_be_promoted_to_act_now": True,
                    "candidate_values_may_not_drive_queue_position": True,
                    "missing_values_may_not_be_assumed": True,
                    "automatic_refresh_after_new_data": True,
                    "manual_financial_override_allowed": False
                },
                "queue_states": [
                    "act_now",
                    "measure_first",
                    "wait_for_data",
                    "do_not_pursue"
                ],
                "current_external_gate_awareness": {
                    "observation_quality_gate": "minimum_7_observed_days",
                    "supplier_contract_gate": "official_contract_values_required",
                    "supplier_all_in_gate": "all_required_supplier_components_present",
                    "measurement_gate": "validated_domain_measurement_required"
                },
                "queue_item_contract": {
                    "priority": "positive_integer_or_null",
                    "decision_class": "required",
                    "domain": "validated_domain_required",
                    "recommended_action": "validated_action_keep_or_wait",
                    "validated_expected_euro_value": "validated_value_or_null",
                    "confidence": "validated_state_required",
                    "implementation_effort": "validated_value_or_null",
                    "primary_blocker": "validated_blocker_or_null",
                    "next_required_input": "validated_dependency_or_null",
                    "evidence_reference": "required",
                    "data_quality": "required"
                },
                "publication_policy": {
                    "act_now_requires_all_required_gates_open": True,
                    "measure_first_requires_explicit_measurement_gap": True,
                    "wait_for_data_requires_external_blocker": True,
                    "do_not_pursue_requires_validated_non_positive_case_or_unjustified_effort": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar"
                },
                "roadmap_state": "v26_step_2_of_4_action_queue_runtime_active_guarded",
                "next_step": "v26_action_queue_publication_runtime",
                "status": "action_queue_runtime_active_guarded"
            },
            "v26_decision_value_prioritization_runtime": {
                "objective": "rank_only_actionable_energy_decisions_by_validated_financial_value_confidence_and_effort_without_promoting_estimates_to_realized_savings",
                "roadmap_step": "1/4",
                "source_chain": [
                    "v25_savings_ledger_runtime",
                    "v25_cumulative_portfolio_impact_runtime",
                    "v25_monthly_budget_impact_runtime",
                    "v25_report_publication_runtime"
                ],
                "ranking_contract": {
                    "primary_metric": "validated_expected_euro_value",
                    "confidence_required": True,
                    "implementation_effort_required": True,
                    "measurement_readiness_required": True,
                    "data_quality_required": True,
                    "blocked_or_missing_financial_value_rankable": False,
                    "candidate_value_may_be_labelled_realized": False,
                    "negative_financial_value_preserved": True
                },
                "decision_classes": {
                    "act_now": "validated_value_and_required_execution_gates_open",
                    "measure_first": "financial_potential_exists_but_measurement_or_confidence_gate_closed",
                    "wait_for_data": "required_external_data_gate_closed",
                    "do_not_pursue": "validated_net_value_non_positive_or_effort_not_justified"
                },
                "guardrails": {
                    "supplier_switch_requires_official_contract_components": True,
                    "advance_payment_change_requires_supplier_all_in_gate": True,
                    "device_replacement_requires_validated_consumption_and_payback_case": True,
                    "battery_recommendation_requires_household_profile_and_regulatory_power_limit": True,
                    "partial_period_extrapolation_without_validated_normalization": False,
                    "missing_values_may_not_be_assumed": True,
                    "double_counting_forbidden": True
                },
                "output_contract": {
                    "maximum_primary_actions": 3,
                    "reason_required": True,
                    "evidence_reference_required": True,
                    "blocked_gate_required": True,
                    "estimated_or_realized_label_required": True
                },
                "roadmap_state": "v26_step_1_of_4_decision_value_prioritization_active_guarded",
                "next_step": "v26_action_queue_runtime",
                "status": "decision_value_prioritization_runtime_active_guarded"
            },
            "v25_report_publication_runtime": {
                "objective": "publish_only_validated_realized_savings_portfolio_and_monthly_budget_impact_into_official_report_surfaces_with_traceable_evidence_and_without_estimate_promotion",
                "source_runtime": "v25_monthly_budget_impact_runtime",
                "roadmap_step": "4/5",
                "eligibility_policy": {
                    "validated_savings_ledger_required": True,
                    "validated_cumulative_portfolio_impact_required": True,
                    "validated_monthly_budget_impact_required_for_numeric_monthly_output": True,
                    "candidate_values_excluded_from_primary_report": True,
                    "business_case_estimates_excluded_from_realized_savings_output": True,
                    "partial_measurement_window_may_not_be_presented_as_full_month": True,
                    "supplier_advance_recommendation_requires_existing_supplier_all_in_gate": True,
                    "missing_values_may_not_be_assumed": True
                },
                "report_surface_contract": {
                    "page1_management_summary": "validated_realized_savings_and_guarded_budget_impact_or_wait_state",
                    "page1_financial_kpis": "validated_publishable_numeric_values_only",
                    "page2_financial_analysis": "traceable_ledger_portfolio_and_budget_impact",
                    "pages3_13_context": "evidence_period_coverage_blockers_and_data_quality",
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "audit_trail_required": True
                },
                "publication_policy": {
                    "realized_savings_label_requires_validated_actual": True,
                    "partial_validated_portfolio_must_be_labelled_partial": True,
                    "double_counting_with_supplier_projection_forbidden": True,
                    "negative_realized_impact_preserved": True,
                    "candidate_values_primary_output_allowed": False,
                    "zero_substitution_for_missing_allowed": False
                },
                "roadmap_state": "v25_step_4_of_5_report_publication_runtime_active_guarded",
                "next_step": "v25_completion_gate",
                "status": "report_publication_runtime_active_guarded"
            },
            "v25_completion_gate": {
                "objective": "complete_v25_with_one_guarded_auditable_chain_from_validated_realized_savings_ledger_to_portfolio_budget_and_official_report_publication",
                "roadmap_step": "5/5",
                "chain_components": {
                    "savings_ledger_runtime": "ready_guarded",
                    "cumulative_portfolio_impact_runtime": "ready_guarded",
                    "monthly_budget_impact_runtime": "ready_guarded",
                    "report_publication_runtime": "ready_guarded"
                },
                "external_dependencies": {
                    "realized_measurement_gate": "validated_pre_and_post_measurement_required_for_actual_savings",
                    "supplier_contract_gate": "official_contract_values_required_for_supplier_all_in_decisions",
                    "period_normalization_gate": "validated_comparable_period_required_for_monthly_budget_numeric_output"
                },
                "completion_policy": {
                    "external_data_may_remain_blocked_at_release_completion": True,
                    "automatic_transition_after_external_gates": True,
                    "manual_financial_override_allowed": False,
                    "candidate_values_may_drive_reported_actuals": False,
                    "business_case_estimate_may_be_promoted_to_realized": False,
                    "partial_period_may_be_promoted_to_full_month": False,
                    "missing_values_may_be_assumed": False,
                    "zero_substitution_allowed": False
                },
                "publication_policy": {
                    "publish_validated_realized_savings_only": True,
                    "publish_validated_monthly_budget_impact_only": True,
                    "supplier_advance_change_requires_supplier_all_in_gate": True,
                    "double_counting_forbidden": True,
                    "negative_realized_impact_preserved": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "reason_and_data_quality_required": True
                },
                "roadmap_state": "v25_step_5_of_5_completion_gate_active_guarded",
                "next_major_release": "32.0.10",
                "status": "v25_complete_external_data_gates_remain"
            },
            "v23_completion_publication_gate": {
                "objective": "close_v23_with_one_guarded_auditable_savings_portfolio_recommendation_publication_chain_ready_for_v24",
                "chain_components": {
                    "savings_portfolio_runtime": "ready_guarded",
                    "portfolio_evaluation_runtime": "ready_guarded",
                    "portfolio_ranking_runtime": "ready_guarded",
                    "portfolio_selection_runtime": "ready_guarded",
                    "portfolio_recommendation_runtime": "ready_guarded"
                },
                "external_dependencies": {
                    "observation_gate": "minimum_7_observed_days",
                    "supplier_contract_gate": "official_contract_values_required",
                    "opportunity_inputs_gate": "complete_validated_inputs_required"
                },
                "completion_policy": {
                    "external_data_may_remain_blocked_at_release_completion": True,
                    "automatic_transition_after_external_gates": True,
                    "manual_override_allowed": False,
                    "candidate_values_may_drive_action": False,
                    "missing_values_may_be_assumed": False,
                    "zero_substitution_allowed": False,
                    "epex_supplier_all_in_allowed": False
                },
                "publication_policy": {
                    "publish_only_actionable_positive_financial_case": True,
                    "keep_current_may_publish_only_as_validated_no_change": True,
                    "blocked_or_incomplete_action": "wait_for_data",
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "reason_and_data_quality_required": True
                },
                "report_publication_gate": {
                    "page1_management_summary": "publishable_recommendation_or_guarded_wait",
                    "page1_financial_kpis": "validated_publishable_numeric_values_only",
                    "page2_financial_analysis": "validated_selected_case_and_alternatives_only",
                    "pages3_13_context": "validated_evidence_blockers_and_quality",
                    "candidate_values_primary_output_allowed": False
                },
                "roadmap_state": "v23_complete_guarded_savings_portfolio_chain_ready_for_v24",
                "next_major_release": "24.0.0",
                "status": "v23_complete_external_data_gates_remain"
            },
            "v23_portfolio_recommendation_runtime": {
                "objective": "translate_guarded_portfolio_selection_into_one_clear_auditable_user_recommendation",
                "source_selection_runtime": "v23_portfolio_selection_runtime",
                "recommendation_states": ["waiting_for_data", "keep_current", "actionable"],
                "recommendation_policy": {
                    "actionable_requires_selected_action": True,
                    "positive_validated_annual_savings_required": True,
                    "reason_and_data_quality_required": True,
                    "blocked_selection_becomes_waiting_for_data": True,
                    "candidate_values_may_not_be_published_as_advice": True,
                    "missing_values_may_not_be_assumed": True,
                    "zero_substitution_allowed": False,
                    "automatic_refresh_after_new_data": True,
                    "manual_override_allowed": False
                },
                "user_output_contract": {
                    "state": "required",
                    "headline": "required",
                    "recommended_action": "validated_action_keep_or_wait",
                    "domain": "validated_domain_or_null",
                    "annual_savings_eur": "validated_value_or_null",
                    "monthly_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "reason": "required",
                    "primary_blocker": "validated_blocker_or_null",
                    "alternatives": "validated_ranked_alternatives",
                    "data_quality": "required"
                },
                "report_handoff": {
                    "page1_management_summary": "headline_action_reason",
                    "page1_financial_kpis": "validated_numeric_values_only",
                    "page2_financial_analysis": "selected_case_and_validated_alternatives",
                    "pages3_13_context": "domain_evidence_blockers_and_quality",
                    "blocked_rendering": "Niet beschikbaar"
                },
                "status": "portfolio_recommendation_runtime_active_guarded"
            },
            "v23_portfolio_selection_runtime": {
                "objective": "select_one_best_guarded_cost_saving_action_from_the_validated_portfolio_ranking",
                "source_ranking_runtime": "v23_portfolio_ranking_runtime",
                "selection_states": ["waiting_for_data", "keep_current", "selected_action"],
                "selection_policy": {
                    "rank_1_validated_opportunity_only": True,
                    "positive_annual_savings_required": True,
                    "complete_traceable_financial_case_required": True,
                    "blocked_domains_may_not_be_selected": True,
                    "validated_no_action_may_not_be_selected_as_savings_action": True,
                    "candidate_values_may_not_drive_selection": True,
                    "missing_values_may_not_be_assumed": True,
                    "zero_substitution_allowed": False,
                    "automatic_reselection_after_new_data": True,
                    "manual_override_allowed": False
                },
                "allowed_actions": ["switch_contract", "buy_battery", "replace_appliance", "shift_load", "keep_current", "wait_for_data"],
                "selection_output_contract": {
                    "selection_state": "required",
                    "selected_domain": "validated_rank_1_domain_or_null",
                    "recommended_action": "validated_action_keep_or_wait",
                    "annual_savings_eur": "validated_value_or_null",
                    "monthly_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "implementation_effort": "validated_low_medium_high_or_null",
                    "alternatives": "remaining_validated_ranked_opportunities",
                    "blocked_domains": "validated_visible_list",
                    "reason": "required",
                    "data_quality": "required"
                },
                "no_selection_policy": {
                    "no_validated_ranked_opportunity": "wait_for_data_or_keep_current",
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "publish_change_action": False
                },
                "decision_handoff": {
                    "selected_action": "eligible_for_guarded_user_recommendation",
                    "keep_current": "publish_validated_no_change_result",
                    "waiting_for_data": "publish_blockers_only"
                },
                "status": "portfolio_selection_runtime_active_guarded"
            },
            "v23_portfolio_ranking_runtime": {
                "objective": "rank_only_validated_portfolio_opportunities_into_one_deterministic_cost_saving_order",
                "source_evaluation_runtime": "v23_portfolio_evaluation_runtime",
                "eligible_evaluation_state": "validated_opportunity",
                "ranking_order": [
                    "highest_validated_annual_savings_eur",
                    "shortest_validated_simple_payback_years",
                    "lowest_implementation_effort"
                ],
                "ranking_policy": {
                    "validated_opportunities_only": True,
                    "positive_annual_savings_required": True,
                    "blocked_domains_excluded_from_numeric_ranking": True,
                    "validated_no_action_excluded_from_savings_ranking": True,
                    "financially_evaluable_must_finish_evaluation_first": True,
                    "candidate_values_may_not_drive_ranking": True,
                    "missing_values_may_not_be_assumed": True,
                    "zero_substitution_allowed": False,
                    "automatic_reranking_after_new_data": True,
                    "manual_override_allowed": False
                },
                "implementation_effort_scale": [
                    "low",
                    "medium",
                    "high"
                ],
                "ranking_output_contract": {
                    "rank": "positive_integer_or_null",
                    "domain": "required",
                    "recommended_action": "validated_action_or_wait",
                    "annual_savings_eur": "validated_value_or_null",
                    "monthly_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "implementation_effort": "validated_low_medium_high_or_null",
                    "reason": "required",
                    "data_quality": "required"
                },
                "blocked_domain_contract": {
                    "remain_visible": True,
                    "rank": None,
                    "annual_savings_eur": None,
                    "simple_payback_years": None,
                    "rendering": "Niet beschikbaar"
                },
                "portfolio_selection_handoff": {
                    "top_ranked_opportunity": "rank_1_validated_opportunity_or_null",
                    "alternatives": "remaining_validated_ranked_opportunities",
                    "no_ranked_opportunity_action": "wait_for_data_or_keep_current",
                    "blocked_domains": "visible_outside_numeric_ranking"
                },
                "status": "portfolio_ranking_runtime_active_guarded"
            },
            "v23_portfolio_evaluation_runtime": {
                "objective": "evaluate_each_savings_domain_with_one_deterministic_guarded_state_and_explicit_blockers",
                "source_portfolio_runtime": "v23_savings_portfolio_runtime",
                "evaluation_states": [
                    "blocked",
                    "input_incomplete",
                    "financially_evaluable",
                    "validated_opportunity",
                    "validated_no_action"
                ],
                "domain_gate_contracts": {
                    "energy_contract": [
                        "observation_quality_gate",
                        "official_current_supplier_all_in",
                        "validated_alternative_supplier_all_in"
                    ],
                    "home_battery": [
                        "validated_import_profile",
                        "validated_export_profile",
                        "dynamic_price_profile",
                        "battery_purchase_price",
                        "usable_capacity_kwh",
                        "roundtrip_efficiency",
                        "power_limits"
                    ],
                    "appliance_replacement": [
                        "validated_device_measurement",
                        "official_or_nameplate_consumption",
                        "replacement_purchase_price",
                        "replacement_expected_consumption"
                    ],
                    "load_shifting": [
                        "dynamic_price_profile",
                        "measured_load_profile"
                    ]
                },
                "blocker_resolution_policy": {
                    "first_required_gate_failure_is_primary_blocker": True,
                    "all_missing_required_inputs_remain_visible": True,
                    "automatic_re_evaluation_after_new_data": True,
                    "candidate_values_may_not_resolve_blocker": True,
                    "missing_values_may_not_be_assumed": True,
                    "manual_override_allowed": False
                },
                "financial_evaluation_policy": {
                    "financially_evaluable_requires_complete_validated_inputs": True,
                    "validated_opportunity_requires_positive_annual_savings": True,
                    "zero_or_negative_savings_result": "validated_no_action",
                    "annual_savings_eur_required_for_opportunity": True,
                    "payback_required_when_purchase_or_replacement_cost_exists": True,
                    "zero_substitution_allowed": False
                },
                "evaluation_output_contract": {
                    "domain": "required",
                    "evaluation_state": "required",
                    "primary_blocker": "validated_blocker_or_null",
                    "missing_inputs": "validated_list",
                    "annual_savings_eur": "validated_value_or_null",
                    "monthly_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "recommended_action": "validated_action_keep_or_wait",
                    "reason": "required",
                    "data_quality": "required"
                },
                "portfolio_handoff": {
                    "validated_opportunity": "eligible_for_portfolio_ranking",
                    "validated_no_action": "visible_not_ranked_as_savings_action",
                    "blocked": "visible_wait_for_data",
                    "input_incomplete": "visible_wait_for_data",
                    "financially_evaluable": "evaluate_before_ranking"
                },
                "status": "portfolio_evaluation_runtime_active_guarded"
            },
            "v23_savings_portfolio_runtime": {
                "objective": "combine_all_guarded_cost_saving_domains_into_one_financial_portfolio_without_bypassing_existing_gates",
                "primary_goal": "reduce_total_energy_costs",
                "source_decision_chain": "v22_completion_gate",
                "portfolio_domains": [
                    "energy_contract",
                    "home_battery",
                    "appliance_replacement",
                    "load_shifting"
                ],
                "domain_sources": {
                    "energy_contract": "validated_supplier_all_in_comparison",
                    "home_battery": "validated_battery_business_case",
                    "appliance_replacement": "validated_device_replacement_business_case",
                    "load_shifting": "validated_dynamic_price_shift_case"
                },
                "portfolio_policy": {
                    "validated_opportunities_only": True,
                    "blocked_domains_remain_visible": True,
                    "rank_by_validated_annual_savings_first": True,
                    "payback_is_secondary_priority": True,
                    "implementation_effort_is_tiebreaker": True,
                    "candidate_values_may_not_drive_ranking": True,
                    "missing_values_may_not_be_assumed": True,
                    "zero_substitution_allowed": False,
                    "automatic_refresh_after_new_data": True,
                    "manual_override_allowed": False
                },
                "portfolio_output_contract": {
                    "top_action": "validated_action_or_wait_for_data",
                    "top_domain": "validated_domain_or_null",
                    "annual_savings_eur": "validated_value_or_null",
                    "monthly_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "alternative_actions": "validated_complete_opportunities_only",
                    "blocked_domains": "validated_list",
                    "reason": "required",
                    "data_quality": "required"
                },
                "report_handoff": {
                    "page1_management_summary": "top_validated_action_or_wait",
                    "page1_financial_kpis": "validated_portfolio_values_only",
                    "page2_financial_analysis": "portfolio_financial_basis_and_alternatives",
                    "pages3_13_context": "domain_specific_evidence_and_blockers",
                    "blocked_rendering": "Niet beschikbaar"
                },
                "status": "savings_portfolio_runtime_active_guarded"
            },
            "v22_completion_gate": {
                "objective": "close_v22_with_one_guarded_auditable_financial_decision_publication_chain_ready_for_v23",
                "chain_components": {
                    "financial_decision_runtime": "ready_guarded",
                    "decision_evidence_runtime": "ready_guarded",
                    "decision_confidence_runtime": "ready_guarded",
                    "decision_confidence_resolution_runtime": "ready_guarded",
                    "decision_publication_runtime": "ready_guarded",
                    "decision_publication_payload_runtime": "ready_guarded"
                },
                "external_dependencies": {
                    "observation_gate": "minimum_7_observed_days",
                    "supplier_contract_gate": "official_contract_values_required",
                    "opportunity_inputs_gate": "complete_validated_inputs_required"
                },
                "completion_policy": {
                    "external_data_may_remain_blocked_at_release_completion": True,
                    "automatic_transition_after_external_gates": True,
                    "manual_override_allowed": False,
                    "candidate_values_may_drive_action": False,
                    "missing_values_may_be_assumed": False,
                    "zero_substitution_allowed": False,
                    "epex_supplier_all_in_allowed": False
                },
                "publication_policy": {
                    "publish_only_actionable_positive_financial_case": True,
                    "blocked_or_informational_action": "wait_for_data",
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar"
                },
                "roadmap_state": "v22_complete_guarded_auditable_decision_publication_chain_ready_for_v23",
                "next_major_release": "23.5.0",
                "status": "v22_complete_external_data_gates_remain"
            },
            "v22_decision_publication_payload_runtime": {
                "objective": "materialize_one_auditable_user_facing_publication_payload_from_guarded_decision_state",
                "source_publication_runtime": "v22_decision_publication_runtime",
                "payload_states": ["blocked", "informational", "publishable"],
                "payload_contract": {
                    "publication_state": "required",
                    "action_label": "validated_action_or_wait",
                    "headline": "required",
                    "reason": "required",
                    "annual_savings_eur": "validated_value_or_null",
                    "monthly_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "primary_blocker": "validated_blocker_or_null",
                    "blocked_dependencies": "validated_list",
                    "data_quality": "required",
                    "evidence_status": "required"
                },
                "materialization_policy": {
                    "blocked_action": "wait_for_data",
                    "informational_action": "wait_for_data",
                    "publishable_action_requires_validated_positive_financial_case": True,
                    "numeric_values_require_publishable_or_explicit_informational_context": True,
                    "candidate_values_never_enter_action_payload": True,
                    "missing_values_remain_null": True,
                    "zero_substitution_allowed": False,
                    "automatic_refresh_after_new_data": True
                },
                "report_handoff": {
                    "page1_management_summary": "payload_headline_reason_and_action",
                    "page1_financial_kpis": "publishable_validated_numeric_values_only",
                    "page2_financial_recommendation": "publishable_action_and_financial_basis_only",
                    "pages3_13_context": "informational_or_publishable_evidence_context",
                    "blocked_rendering": "Niet beschikbaar"
                },
                "audit_policy": {
                    "preserve_publication_state": True,
                    "preserve_primary_blocker": True,
                    "preserve_data_quality": True,
                    "preserve_evidence_status": True,
                    "manual_override_allowed": False
                },
                "status": "decision_publication_payload_runtime_active_guarded"
            },
            "v22_decision_publication_runtime": {
                "objective": "publish_one_user_facing_financial_decision_only_from_resolved_actionable_confidence",
                "source_resolution_runtime": "v22_decision_confidence_resolution_runtime",
                "publication_states": ["blocked", "informational", "publishable"],
                "state_mapping": {"blocked": "blocked", "limited": "informational", "validated": "informational", "actionable": "publishable"},
                "publication_policy": {
                    "publishable_requires_actionable_confidence": True,
                    "informational_may_explain_evidence": True,
                    "informational_may_not_recommend_change": True,
                    "blocked_must_explain_primary_blocker": True,
                    "financial_values_require_validated_traceable_evidence": True,
                    "candidate_values_may_not_be_published_as_advice": True,
                    "missing_values_may_not_be_assumed": True,
                    "automatic_republication_after_new_data": True,
                    "manual_override_allowed": False
                },
                "user_output_contract": {
                    "publication_state": "blocked_informational_or_publishable",
                    "decision": "validated_decision_or_wait_for_data",
                    "action_label": "switch_buy_replace_shift_keep_or_wait",
                    "annual_savings_eur": "validated_value_or_null",
                    "monthly_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "primary_blocker": "validated_blocker_or_null",
                    "reason": "required",
                    "data_quality": "required"
                },
                "report_policy": {
                    "page1_management_action_requires_publishable": True,
                    "page1_financial_kpi_requires_publishable": True,
                    "page2_financial_recommendation_requires_publishable": True,
                    "pages3_13_may_show_informational_context": True,
                    "blocked_rendering": "Niet beschikbaar",
                    "zero_substitution_allowed": False
                },
                "status": "decision_publication_runtime_active_guarded"
            },
            "v22_decision_confidence_resolution_runtime": {
                "objective": "resolve_financial_decision_confidence_into_one_deterministic_guarded_runtime_state",
                "source_confidence_runtime": "v22_decision_confidence_runtime",
                "resolution_order": [
                    "required_gate_failure",
                    "traceable_partial_evidence",
                    "complete_traceable_evidence",
                    "positive_complete_financial_case"
                ],
                "state_resolution": {
                    "required_gate_failure": "blocked",
                    "traceable_partial_evidence": "limited",
                    "complete_traceable_evidence": "validated",
                    "positive_complete_financial_case": "actionable"
                },
                "current_external_gate_sources": {
                    "observation_quality_gate": "projection_eligibility.eligible",
                    "supplier_contract_gate": "contract_validation.all_required_components_present",
                    "opportunity_input_gate": "v21_financial_action_readiness"
                },
                "resolution_policy": {
                    "first_unresolved_required_gate_wins": True,
                    "actionable_requires_all_required_gates": True,
                    "validated_does_not_imply_positive_financial_case": True,
                    "candidate_values_may_not_change_state": True,
                    "missing_values_may_not_change_state_to_ready": True,
                    "automatic_transition_after_new_data": True,
                    "manual_override_allowed": False
                },
                "output_contract": {
                    "resolved_confidence_state": "blocked_limited_validated_or_actionable",
                    "primary_blocker": "first_unresolved_required_gate_or_null",
                    "blocked_dependencies": "validated_list",
                    "decision": "validated_decision_or_wait_for_data",
                    "annual_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "reason": "required",
                    "data_quality": "required"
                },
                "publication_policy": {
                    "publish_change_action_only_when_actionable": True,
                    "blocked_or_limited_action": "wait_for_data",
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "zero_substitution_allowed": False
                },
                "status": "decision_confidence_resolution_runtime_active_guarded"
            },
            "v22_decision_confidence_runtime": {
                "objective": "derive_a_guarded_confidence_state_for_each_financial_decision_from_evidence_quality_and_gate_completeness",
                "source_evidence_runtime": "v22_decision_evidence_runtime",
                "confidence_states": ["blocked", "limited", "validated", "actionable"],
                "confidence_inputs": {
                    "traceable_inputs": "v22_decision_evidence_runtime",
                    "observation_quality_gate": "projection_eligibility.eligible",
                    "supplier_contract_gate": "contract_validation.all_required_components_present",
                    "financial_case": "validated_financial_evaluation",
                    "blocked_dependencies": "v21_blocked_dependency_runtime"
                },
                "confidence_policy": {
                    "blocked_when_required_gate_false": True,
                    "limited_requires_traceable_partial_evidence": True,
                    "validated_requires_complete_traceable_evidence": True,
                    "actionable_requires_positive_complete_financial_case": True,
                    "candidate_values_may_not_raise_confidence": True,
                    "missing_values_may_not_be_assumed": True,
                    "automatic_recalculation_after_new_data": True
                },
                "output_contract": {
                    "confidence_state": "required",
                    "confidence_reason": "required",
                    "decision": "validated_decision_or_wait_for_data",
                    "annual_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "blocked_dependencies": "validated_list",
                    "data_quality": "required"
                },
                "publication_policy": {
                    "actionable_decision_requires_actionable_confidence": True,
                    "blocked_or_limited_decision": "wait_for_data",
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "zero_substitution_allowed": False
                },
                "status": "decision_confidence_runtime_active_guarded"
            },
            "v22_decision_evidence_runtime": {
                "objective": "attach_auditable_evidence_and_blockers_to_each_guarded_financial_decision",
                "source_decision_runtime": "v22_financial_decision_runtime",
                "evidence_contract": {
                    "decision": "validated_decision_or_wait_for_data",
                    "supporting_inputs": "validated_source_references",
                    "annual_savings_eur": "validated_value_or_null",
                    "monthly_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "calculation_basis": "required_when_financial_value_exists",
                    "blocked_dependencies": "required_when_waiting",
                    "data_quality": "required"
                },
                "evidence_policy": {
                    "financial_value_requires_traceable_inputs": True,
                    "decision_requires_traceable_evaluation": True,
                    "source_values_must_be_validated": True,
                    "candidate_values_may_not_be_evidence": True,
                    "missing_values_may_not_be_assumed": True,
                    "automatic_refresh_after_new_data": True
                },
                "audit_policy": {
                    "preserve_source_type": True,
                    "preserve_measurement_window": True,
                    "preserve_contract_validation_state": True,
                    "preserve_external_gate_state": True,
                    "explain_why_blocked_or_actionable": True
                },
                "publication_policy": {
                    "publish_financial_decision_only_with_complete_evidence": True,
                    "blocked_decision": "wait_for_data",
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "zero_substitution_allowed": False
                },
                "status": "decision_evidence_runtime_active_guarded"
            },
            "v22_financial_decision_runtime": {
                "objective": "turn_the_completed_v21_financial_action_chain_into_a_guarded_runtime_decision_with_auditable_euro_impact",
                "source_completion_gate": "v21_completion_gate",
                "supported_decisions": ["switch_contract", "buy_battery", "replace_appliance", "shift_load", "keep_current", "wait_for_data"],
                "decision_inputs": {
                    "selected_action": "v21_financial_action_selection",
                    "annual_savings_eur": "validated_financial_evaluation",
                    "simple_payback_years": "validated_financial_evaluation_or_null",
                    "blocked_dependencies": "v21_blocked_dependency_runtime",
                    "data_quality": "validated_runtime_quality"
                },
                "activation_policy": {
                    "requires_v21_chain_ready_guarded": True,
                    "requires_complete_positive_financial_case_for_change_action": True,
                    "external_gates_must_be_open": True,
                    "automatic_re_evaluation_after_new_data": True,
                    "manual_override_allowed": False
                },
                "decision_contract": {
                    "decision": "validated_decision_or_wait_for_data",
                    "annual_savings_eur": "validated_value_or_null",
                    "monthly_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "reason": "required",
                    "blocked_dependencies": "required_when_waiting",
                    "data_quality": "required"
                },
                "safety_policy": {
                    "candidate_values_may_drive_decision": False,
                    "missing_values_may_be_assumed": False,
                    "zero_substitution_allowed": False,
                    "epex_supplier_all_in_allowed": False,
                    "negative_or_zero_savings_change_action_allowed": False
                },
                "status": "financial_decision_runtime_active_guarded"
            },
            "v21_completion_gate": {
                "objective": "close_v21_with_one_guarded_end_to_end_financial_action_chain_ready_for_v22",
                "runtime": "ready_guarded",
                "gate_resolution": "ready_guarded",
                "blocked_dependency_runtime": "ready_guarded",
                "action_readiness": "ready_guarded",
                "financial_evaluation_contract": "ready_guarded",
                "financial_action_selection": "ready_guarded",
                "supported_actions": ["switch_contract", "buy_battery", "replace_appliance", "shift_load"],
                "external_dependencies": {
                    "observation_gate": "minimum_7_observed_days",
                    "supplier_contract_gate": "official_contract_values_required",
                    "opportunity_inputs_gate": "complete_validated_inputs_required"
                },
                "safety_policy": {
                    "automatic_transition_after_external_gates": True,
                    "manual_override_allowed": False,
                    "candidate_values_may_drive_action": False,
                    "missing_values_may_be_assumed": False,
                    "zero_substitution_allowed": False,
                    "epex_supplier_all_in_allowed": False
                },
                "publication_policy": {
                    "publish_only_complete_positive_financial_action": True,
                    "blocked_action": "wait_for_data",
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar"
                },
                "roadmap_state": "v21_complete_guarded_financial_action_chain_ready_for_v22",
                "next_major_release": "23.5.0",
                "status": "v21_complete_external_data_gates_remain"
            },
            "v21_financial_action_selection": {
                "objective": "select_one_best_validated_cost_saving_action_from_completed_financial_evaluations",
                "source_evaluation": "v21_financial_evaluation_contract",
                "candidate_actions": ["switch_contract", "buy_battery", "replace_appliance", "shift_load"],
                "selection_order": [
                    "highest_validated_annual_savings_eur",
                    "shortest_validated_simple_payback_years",
                    "lowest_implementation_effort"
                ],
                "selection_policy": {
                    "completed_evaluations_only": True,
                    "positive_annual_savings_required": True,
                    "blocked_or_incomplete_actions_excluded": True,
                    "candidate_values_may_not_drive_selection": True,
                    "missing_values_may_not_be_assumed": True,
                    "automatic_reselection_after_new_data": True
                },
                "output_contract": {
                    "selected_action": "validated_action_or_wait_for_data",
                    "annual_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "reason": "required",
                    "alternatives_considered": "validated_complete_actions_only",
                    "blocked_dependencies": "required_when_no_action_selected",
                    "data_quality": "required"
                },
                "publication_policy": {
                    "publish_only_complete_selection": True,
                    "no_validated_action_result": "wait_for_data",
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "zero_substitution_allowed": False
                },
                "status": "financial_action_selection_active_guarded"
            },
            "v21_financial_evaluation_contract": {
                "objective": "define_a_single_guarded_financial_evaluation_contract_for_each_ready_savings_action",
                "source_readiness": "v21_financial_action_readiness",
                "evaluation_types": {
                    "switch_contract": {
                        "primary_metric": "validated_annual_savings_eur",
                        "secondary_metric": "validated_monthly_savings_eur",
                        "decision": "switch_keep_or_wait"
                    },
                    "buy_battery": {
                        "primary_metric": "validated_annual_savings_eur",
                        "secondary_metric": "simple_payback_years",
                        "decision": "buy_wait_or_reject"
                    },
                    "replace_appliance": {
                        "primary_metric": "validated_annual_savings_eur",
                        "secondary_metric": "simple_payback_years",
                        "decision": "replace_keep_or_wait"
                    },
                    "shift_load": {
                        "primary_metric": "validated_annual_savings_eur",
                        "secondary_metric": "shiftable_kwh",
                        "decision": "shift_keep_or_wait"
                    }
                },
                "evaluation_policy": {
                    "requires_ready_for_financial_evaluation": True,
                    "validated_inputs_only": True,
                    "positive_savings_required_for_cost_saving_action": True,
                    "payback_must_be_derived_from_validated_cost_and_savings": True,
                    "candidate_values_may_not_drive_evaluation": True,
                    "missing_values_may_not_be_assumed": True,
                    "automatic_re_evaluation_after_new_data": True
                },
                "result_contract": {
                    "action_type": "required",
                    "evaluation_status": "blocked_ready_or_complete",
                    "annual_savings_eur": "validated_value_or_null",
                    "monthly_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "decision": "validated_decision_or_wait_for_data",
                    "reason": "required",
                    "data_quality": "required"
                },
                "publication_policy": {
                    "complete_evaluation_required": True,
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "zero_substitution_allowed": False,
                    "negative_or_zero_savings_may_not_trigger_purchase_or_switch": True
                },
                "status": "financial_evaluation_contract_active_guarded"
            },
            "v21_financial_action_readiness": {
                "objective": "provide_one_auditable_readiness_state_for_each_cost_saving_action_without_bypassing_runtime_gates",
                "source_runtime": "v21_financial_action_runtime",
                "source_dependencies": "v21_blocked_dependency_runtime",
                "action_types": ["switch_contract", "buy_battery", "replace_appliance", "shift_load"],
                "readiness_states": ["blocked", "input_incomplete", "ready_for_financial_evaluation", "actionable"],
                "action_requirements": {
                    "switch_contract": ["observation_quality_gate", "official_current_supplier_all_in", "validated_alternative_supplier_all_in"],
                    "buy_battery": ["validated_import_profile", "validated_export_profile", "dynamic_price_profile", "battery_purchase_price", "usable_capacity_kwh", "roundtrip_efficiency", "power_limits"],
                    "replace_appliance": ["validated_device_measurement", "official_or_nameplate_consumption", "replacement_purchase_price", "replacement_expected_consumption"],
                    "shift_load": ["dynamic_price_profile", "measured_load_profile"]
                },
                "readiness_policy": {
                    "financial_evaluation_requires_complete_inputs": True,
                    "actionable_requires_positive_validated_financial_case": True,
                    "candidate_values_may_not_satisfy_required_inputs": True,
                    "missing_values_may_not_be_assumed": True,
                    "automatic_re_evaluation_after_new_data": True
                },
                "output_contract": {
                    "action_type": "required",
                    "readiness_state": "required",
                    "missing_inputs": "validated_list",
                    "estimated_annual_savings_eur": "validated_value_or_null",
                    "simple_payback_years": "validated_value_or_null",
                    "recommended_action": "validated_action_or_wait_for_data",
                    "reason": "required"
                },
                "publication_policy": {
                    "blocked_numeric_value": None,
                    "blocked_rendering": "Niet beschikbaar",
                    "zero_substitution_allowed": False,
                    "publish_action_only_when_actionable": True
                },
                "status": "financial_action_readiness_active_guarded"
            },
            "v21_blocked_dependency_runtime": {
                "objective": "make_the_current_blocking_financial_dependencies_explicit_and_actionable_without_bypassing_gates",
                "source_gate_resolution": "v21_runtime_gate_resolution",
                "dependency_groups": {
                    "observation": {
                        "source": "projection_eligibility",
                        "required_fields": [
                            "eligible",
                            "observed_days",
                            "minimum_observed_days",
                            "remaining_observation_days",
                            "reason"
                        ],
                        "user_message": "Wachten op voldoende meetdekking"
                    },
                    "supplier_contract": {
                        "source": "contract_validation",
                        "required_fields": [
                            "all_required_components_present",
                            "missing_components",
                            "validation_errors"
                        ],
                        "user_message": "Wachten op officiële leveranciercontractgegevens"
                    },
                    "opportunity_inputs": {
                        "source": "v20_savings_opportunity_engine",
                        "required_fields": [
                            "required_inputs",
                            "missing_inputs"
                        ],
                        "user_message": "Wachten op complete besparingsanalyse-inputs"
                    }
                },
                "resolution_policy": {
                    "show_only_real_blockers": True,
                    "preserve_gate_order": True,
                    "do_not_infer_missing_contract_values": True,
                    "do_not_promote_candidate_values": True,
                    "automatic_refresh_after_new_data": True
                },
                "report_contract": {
                    "current_state": "resolved_runtime_state",
                    "primary_blocker": "first_unresolved_dependency_or_null",
                    "blocked_dependencies": "all_unresolved_dependencies",
                    "remaining_observation_days": "validated_value_or_null",
                    "missing_contract_components": "validated_list_or_empty",
                    "missing_opportunity_inputs": "validated_list_or_empty",
                    "blocked_rendering": "Niet beschikbaar"
                },
                "status": "blocked_dependency_runtime_active_guarded"
            },
            "v21_runtime_gate_resolution": {
                "objective": "resolve_the_current_financial_action_runtime_state_from_external_and_opportunity_gates",
                "source_runtime": "v21_financial_action_runtime",
                "gate_order": [
                    "observation_quality_gate",
                    "supplier_contract_gate",
                    "opportunity_input_gate"
                ],
                "state_mapping": {
                    "observation_quality_gate_false": "waiting_for_observation",
                    "supplier_contract_gate_false": "waiting_for_contract_data",
                    "opportunity_input_gate_false": "waiting_for_opportunity_inputs",
                    "all_required_gates_true": "actionable"
                },
                "current_gate_contract": {
                    "observation_source": "projection_eligibility.eligible",
                    "supplier_contract_source": "contract_validation.all_required_components_present",
                    "opportunity_source": "v20_savings_action_handoff",
                    "blocked_dependencies_required": True,
                    "automatic_transition": True
                },
                "publication_policy": {
                    "actionable_requires_all_required_gates": True,
                    "partial_gate_pass_may_publish_action": False,
                    "candidate_values_may_drive_state": False,
                    "missing_values_render_as": "Niet beschikbaar",
                    "zero_substitution_allowed": False
                },
                "status": "runtime_gate_resolution_active_guarded"
            },
            "v21_financial_action_runtime": {
                "objective": "derive_one_runtime_savings_action_from_the_guarded_v20_savings_chain",
                "source_action_handoff": "v20_savings_action_handoff",
                "activation_policy": {"requires_complete_validated_opportunity": True, "requires_publishable_financial_values": True, "requires_required_external_gates": True, "automatic_re_evaluation": True, "manual_override_allowed": False},
                "runtime_states": ["waiting_for_observation", "waiting_for_contract_data", "waiting_for_opportunity_inputs", "actionable"],
                "action_contract": {"recommended_action": "validated_action_or_wait_for_data", "opportunity_type": "validated_type_or_null", "annual_savings_eur": "validated_value_or_null", "simple_payback_years": "validated_value_or_null", "reason": "required", "data_quality": "required", "blocked_dependencies": "required_when_not_actionable"},
                "safety_policy": {"candidate_values_may_drive_action": False, "missing_values_may_be_assumed": False, "zero_substitution_allowed": False, "blocked_rendering": "Niet beschikbaar", "epex_supplier_all_in_allowed": False},
                "status": "financial_action_runtime_active_guarded"
            },
            "v20_savings_action_handoff": {
                "objective": "convert_highest_ranked_complete_savings_opportunity_into_one_auditable_user_action",
                "source_priority_engine": "v20_savings_priority_engine",
                "allowed_actions": ["switch_contract", "buy_battery", "replace_appliance", "shift_load", "keep_current", "wait_for_data"],
                "selection_policy": {"complete_validated_opportunities_only": True, "prefer_highest_validated_annual_savings": True, "use_payback_as_secondary_priority": True, "use_implementation_effort_as_tiebreaker": True, "candidate_only_values_may_drive_action": False, "missing_values_may_be_assumed": False},
                "output_contract": {"recommended_action": "validated_action_or_wait_for_data", "opportunity_type": "validated_top_opportunity_or_null", "estimated_annual_savings_eur": "validated_value_or_null", "simple_payback_years": "validated_value_or_null", "reason": "required", "blocked_dependencies": "required_when_waiting", "data_quality": "required"},
                "publication_policy": {"publish_financial_action_only_when_complete": True, "blocked_action": "wait_for_data", "blocked_numeric_value": None, "blocked_rendering": "Niet beschikbaar", "zero_substitution_allowed": False, "automatic_re_evaluation_after_new_measurements": True},
                "roadmap_state": "v20_savings_chain_complete_guarded_ready_for_v21",
                "status": "savings_action_handoff_active_guarded"
            },
            "v20_completion_gate": {
              "savings_opportunity_engine": "ready_guarded",
              "savings_priority_engine": "ready_guarded",
              "savings_action_handoff": "ready_guarded",
              "savings_chain_status": "v20_savings_chain_complete_external_data_gates_remain",
                "financial_report_runtime_contract": "ready_guarded",
                "report_runtime_value_mapping": "ready_guarded",
                "report_publication_state": "ready_guarded",
                "observation_gate_dependency": "minimum_7_observed_days",
                "supplier_all_in_dependency": "official_contract_values_required",
                "decision_gate_dependency": "complete_publishable_recommendation",
                "automatic_transition_after_external_gates": True,
                "manual_override_allowed": False,
                "candidate_value_policy": "informational_only_never_primary_report_value",
                "missing_value_policy": "explicit_unavailable_never_zero",
                "epex_policy": "market_reference_only",
                "next_major_release": "23.5.0",
                "release_status": "v20_complete_external_data_gates_remain",
            },
            "v20_report_publication_state": {
                "objective": "derive_one_auditable_publication_state_for_all_official_financial_report_sections",
                "source_value_mapping": "v20_report_runtime_value_mapping",
                "source_observation_gate": "projection_eligibility",
                "source_supplier_gate": "contract_validation",
                "source_decision_gate": "v12_decision_support",
                "states": ["blocked_observation", "blocked_supplier_contract", "publishable"],
                "observation_publishable_when": "eligible_true",
                "supplier_publishable_when": "all_required_components_present_true",
                "decision_publishable_when": "recommendation_publishable_true",
                "page1_management_and_kpis_require_decision_gate": True,
                "page2_projection_requires_observation_gate": True,
                "page2_supplier_all_in_requires_supplier_gate": True,
                "page2_advance_control_requires_decision_gate": True,
                "pages3_13_financial_context_requires_field_gate": True,
                "blocked_value": None,
                "blocked_rendering": "Niet beschikbaar",
                "candidate_values_primary_output_allowed": False,
                "manual_override_allowed": False,
                "epex_supplier_all_in_allowed": False,
                "automatic_transition_after_external_gates": True,
                "status": "official_report_publication_state_active",
            },
            "v20_report_runtime_value_mapping": {
                "objective": "map_guarded_financial_runtime_values_to_official_report_sections",
                "source": "v20_financial_report_runtime_contract",
                "page1_management_summary": {
                    "decision": "v19_report_action_mapping",
                    "reason": "v18_financial_explanation_runtime",
                    "quality": "v19_report_action_quality_context"
                },
                "page1_financial_kpis": {
                    "difference_eur": "v12_decision_support.projected_monthly_difference_eur",
                    "recommended_advance_eur": "v12_decision_support.recommended_advance_eur",
                    "strength": "v12_decision_support.recommendation_strength"
                },
                "page2_projection": {
                    "projection": "financial_projection",
                    "detail": "projection_detail",
                    "supplier_all_in": "validated_contract_only"
                },
                "page2_advance_control": {
                    "reference_advance_eur": 150.0,
                    "recommendation": "v12_decision_support",
                    "publish_requires_complete_gate": True
                },
                "blocked_values_render_as": "Niet beschikbaar",
                "zero_substitution_allowed": False,
                "candidate_values_primary_output_allowed": False,
                "epex_supplier_all_in_allowed": False,
                "status": "official_report_value_mapping_active",
            },
            "v20_financial_report_runtime_contract": {
                "objective": "bind_guarded_financial_action_context_to_official_report_runtime_fields",
                "source_decision_presentation": "v19_financial_report_decision_presentation",
                "source_action_mapping": "v19_report_action_mapping",
                "source_quality_context": "v19_report_action_quality_context",
                "monthly_advance_reference_eur": 150.0,
                "page1_management_fields": ["decision_label", "reason", "data_quality_label"],
                "page1_financial_kpi_fields": ["projected_monthly_difference_eur", "recommended_advance_eur", "recommendation_strength"],
                "page2_financial_fields": ["projection_status", "projected_30d_variable_electricity_cost_eur", "supplier_all_in_projection_eur", "recommended_advance_eur", "reason"],
                "pages3_13_context_fields": ["data_quality_label", "blocked_dependencies"],
                "publish_requires_observation_quality_gate": True,
                "supplier_all_in_requires_validated_contract": True,
                "recommendation_requires_complete_publication_gate": True,
                "blocked_rendering": "Niet beschikbaar",
                "candidate_values_primary_output_allowed": False,
                "epex_role": "markt-/referentieprijs",
                "epex_supplier_all_in_allowed": False,
                "status": "official_report_runtime_contract_active",
            },
            "v19_completion_gate": {
                "financial_report_decision_presentation": "ready_guarded",
                "report_action_mapping": "ready_guarded",
                "report_action_quality_context": "ready_guarded",
                "observation_gate_dependency": "minimum_7_observed_days",
                "supplier_all_in_dependency": "official_contract_values_required",
                "blocked_action_policy": "explicit_reason_and_unavailable_values",
                "candidate_value_policy": "informational_only_never_primary_report_value",
                "missing_value_policy": "explicit_unavailable_never_zero",
                "epex_policy": "market_reference_only",
                "automatic_transition_after_external_gates": True,
                "manual_override_allowed": False,
                "next_major_release": "23.5.0",
                "release_status": "v19_complete_external_data_gates_remain",
            },
            "v19_report_action_quality_context": {
                "objective": "attach_quality_and_dependency_context_to_each_guarded_report_action",
                "source_action": "v19_report_action_mapping",
                "quality_labels": {
                    "blocked_observation": "Onvoldoende meetdekking",
                    "blocked_supplier": "Leverancier-all-in nog niet beschikbaar",
                    "blocked_contract": "Contractgegevens onvolledig",
                    "publishable": "Gevalideerd financieel advies"
                },
                "blocked_dependency_order": ["observation_quality_gate", "supplier_all_in_gate", "contract_components_gate"],
                "show_observed_progress_when_blocked": True,
                "show_remaining_observation_days_when_blocked": True,
                "show_missing_contract_components_when_blocked": True,
                "candidate_numbers_may_be_primary_report_values": False,
                "missing_values_render_as": "Niet beschikbaar",
                "status": "report_action_quality_context_active",
            },
            "v19_report_action_mapping": {
                "objective": "map_guarded_financial_decisions_to_consistent_dutch_report_actions",
                "source": "v19_financial_report_decision_presentation",
                "action_labels": {
                    "blocked": "Nog geen financieel advies",
                    "advance_can_be_lowered": "Maandvoorschot kan omlaag",
                    "advance_is_appropriate": "Maandvoorschot is passend",
                    "advance_should_be_raised": "Maandvoorschot verhogen"
                },
                "management_summary_requires_reason": True,
                "financial_kpi_requires_strength": True,
                "advance_control_requires_recommended_amount": True,
                "difference_requires_publishable_recommendation": True,
                "blocked_amount": None,
                "blocked_strength": None,
                "blocked_rendering": "Niet beschikbaar",
                "candidate_context_label": "Indicatief - nog niet publiceerbaar",
                "candidate_context_may_drive_action": False,
                "epex_role": "markt-/referentieprijs",
                "status": "report_action_mapping_active",
            },
            "v19_financial_report_decision_presentation": {
                "objective": "present_guarded_financial_decisions_as_clear_report_ready_user_actions",
                "source_decision": "v12_decision_support.decision",
                "source_explanation": "v18_financial_explanation_runtime",
                "monthly_advance_reference_eur": 150.0,
                "presentation_states": [
                    "blocked",
                    "advance_can_be_lowered",
                    "advance_is_appropriate",
                    "advance_should_be_raised"
                ],
                "required_report_fields": [
                    "decision_label",
                    "reason",
                    "projected_monthly_difference_eur",
                    "recommended_advance_eur",
                    "recommendation_strength",
                    "data_quality_label"
                ],
                "blocked_decision_label": "Nog geen financieel advies",
                "blocked_value_rendering": "Niet beschikbaar",
                "publish_requires_complete_v17_recommendation": True,
                "explanation_required": True,
                "candidate_context_allowed": True,
                "candidate_context_label": "Indicatief - nog niet publiceerbaar",
                "candidate_context_may_drive_decision": False,
                "epex_label": "Markt-/referentieprijs",
                "epex_may_drive_supplier_decision": False,
                "status": "financial_report_decision_presentation_active",
            },
            "v18_completion_gate": {
                "financial_explainability_contract": "ready_guarded",
                "financial_explanation_runtime": "ready_guarded",
                "report_explanation_handoff": "ready_guarded",
                "blocked_explanation_required": True,
                "publishable_explanation_required": True,
                "candidate_context_policy": "informational_only_never_decision_input",
                "missing_value_policy": "explicit_unavailable_never_zero",
                "epex_policy": "market_reference_only",
                "observation_gate_dependency": "minimum_7_observed_days",
                "supplier_all_in_dependency": "official_contract_values_required",
                "next_major_release": "23.5.0",
                "release_status": "v18_complete_external_data_gates_remain",
            },
            "v18_report_explanation_handoff": {
                "objective": "hand_off_guarded_financial_explanations_to_official_report_outputs",
                "source": "v18_financial_explanation_runtime",
                "page1_management_summary": "explanation_ready_guarded",
                "page1_financial_kpis": "explanation_ready_guarded",
                "page2_financial_simulation": "explanation_ready_guarded",
                "page2_year_projection": "explanation_ready_guarded",
                "page2_monthly_advance_control": "explanation_ready_guarded",
                "pages3_13_financial_context": "explanation_ready_guarded",
                "blocked_reason_required": True,
                "publishable_reason_required": True,
                "missing_value_rendering": "Niet beschikbaar",
                "candidate_context_label": "Indicatief - nog niet publiceerbaar",
                "candidate_context_may_drive_recommendation": False,
                "epex_label": "Markt-/referentieprijs",
                "epex_may_be_labeled_supplier_all_in": False,
                "status": "report_explanation_handoff_active",
            },
            "v18_financial_explanation_runtime": {
                "objective": "derive_a_single_human_readable_explanation_state_from_guarded_financial_runtime",
                "decision_source": "v12_decision_support.decision",
                "reason_source": "v12_decision_support.reason",
                "quality_gate_source": "v12_decision_support.quality_gate_passed",
                "supplier_all_in_source": "v12_decision_support.supplier_all_in_ready",
                "contract_gate_source": "v12_decision_support.contract_components_complete",
                "blocked_dependency_order": ["observation_quality_gate", "supplier_all_in_gate", "contract_components_gate"],
                "blocked_reason_mapping": {
                    "waiting_for_minimum_observation_quality": "Nog onvoldoende waarnemingsdagen voor een betrouwbare financiële prognose.",
                    "waiting_for_supplier_all_in": "Leverancier-all-in kosten zijn nog niet volledig gevalideerd.",
                    "waiting_for_contract_components": "Officiële contractcomponenten ontbreken nog."
                },
                "publishable_explanation_requires_complete_recommendation": True,
                "blocked_explanation_may_show_candidate_context": True,
                "candidate_context_may_drive_recommendation": False,
                "missing_values_render_as": "Niet beschikbaar",
                "status": "financial_explanation_runtime_active",
            },
            "v18_financial_explainability_contract": {
                "objective": "make_every_future_financial_recommendation_explainable_and_auditable",
                "recommendation_source": "v12_decision_support",
                "required_context": [
                    "monthly_advance_eur",
                    "projection_quality_gate",
                    "supplier_all_in_gate",
                    "contract_component_gate",
                    "projected_monthly_difference_eur",
                    "recommended_advance_eur",
                    "recommendation_strength"
                ],
                "explanation_fields": [
                    "decision",
                    "reason",
                    "basis",
                    "difference_eur",
                    "recommended_advance_eur",
                    "recommendation_strength",
                    "data_quality",
                    "blocked_dependencies"
                ],
                "blocked_state_must_explain_why": True,
                "publishable_state_must_explain_why": True,
                "candidate_values_may_be_explanation_only": True,
                "candidate_values_may_drive_decision": False,
                "epex_role": "market_reference_only",
                "missing_contract_values_may_be_assumed": False,
                "status": "financial_explainability_contract_active",
            },
            "v17_completion_gate": {
                "financial_decision_output": "ready_guarded",
                "savings_recommendation_contract": "ready_guarded",
                "recommendation_publication_gate": "ready_guarded",
                "monthly_advance_reference_eur": 150.0,
                "observation_gate_dependency": "minimum_7_observed_days",
                "supplier_all_in_dependency": "official_contract_values_required",
                "complete_recommendation_dependency": "decision_difference_advance_strength_all_required",
                "partial_recommendation_publication": "forbidden",
                "candidate_values_publication": "forbidden",
                "epex_policy": "reference_only",
                "blocked_value_policy": "explicit_unavailable_never_zero",
                "next_major_release": "23.5.0",
                "release_status": "v17_complete_external_data_gates_remain",
            },
            "v17_recommendation_publication_gate": {
                "objective": "publish_cost_saving_action_only_when_runtime_decision_is_complete_and_auditable",
                "publishable_source": "v12_decision_support.recommendation_publishable",
                "decision_source": "v12_decision_support.decision",
                "difference_source": "v12_decision_support.projected_monthly_difference_eur",
                "recommended_advance_source": "v12_decision_support.recommended_advance_eur",
                "strength_source": "v12_decision_support.recommendation_strength",
                "required_publishable_value": True,
                "required_non_null_fields": [
                    "decision",
                    "projected_monthly_difference_eur",
                    "recommended_advance_eur",
                    "recommendation_strength"
                ],
                "blocked_reason_source": "v12_decision_support.reason",
                "blocked_rendering": "Niet beschikbaar",
                "partial_recommendation_allowed": False,
                "automatic_publication_after_gate": True,
                "status": "recommendation_publication_gate_active",
            },
            "v17_savings_recommendation_contract": {
                "objective": "publish_actionable_savings_recommendation_only_after_full_financial_validation",
                "reference_monthly_advance_eur": 150.0,
                "recommendation_source": "v12_decision_support",
                "required_projection_state": "quality_gate_passed_true",
                "required_supplier_state": "supplier_all_in_ready_true",
                "required_contract_state": "contract_components_complete_true",
                "allowed_actions": [
                    "lower_monthly_advance",
                    "keep_monthly_advance",
                    "raise_monthly_advance"
                ],
                "savings_amount_source": "projected_monthly_difference_eur",
                "recommended_advance_source": "recommended_advance_eur",
                "recommendation_strength_source": "recommendation_strength",
                "blocked_action": None,
                "blocked_amount": None,
                "blocked_rendering": "Niet beschikbaar",
                "candidate_only_values_allowed": False,
                "epex_supplier_decision_allowed": False,
                "status": "savings_recommendation_contract_active",
            },
            "v17_financial_decision_output": {
                "objective": "convert_validated_financial_runtime_state_into_actionable_cost_saving_output",
                "monthly_advance_eur": 150.0,
                "projection_source": "financial_projection",
                "supplier_all_in_source": "validated_contract_only",
                "decision_source": "v12_decision_support",
                "recommendation_publishable_requires": [
                    "projection_quality_gate_passed",
                    "supplier_all_in_ready",
                    "contract_components_complete"
                ],
                "allowed_decisions": [
                    "advance_can_be_lowered",
                    "advance_is_appropriate",
                    "advance_should_be_raised"
                ],
                "blocked_decision": None,
                "blocked_rendering": "Niet beschikbaar",
                "candidate_values_may_drive_decision": False,
                "epex_may_drive_supplier_decision": False,
                "status": "financial_decision_output_guard_active",
            },
            "v16_completion_gate": {
                "official_output_contract": "ready_guarded",
                "runtime_activation_binding": "ready_guarded",
                "runtime_publication_validation": "ready_guarded",
                "projection_gate_dependency": "minimum_7_observed_days",
                "supplier_all_in_dependency": "official_contract_values_required",
                "decision_gate_dependency": "publishable_projection_and_supplier_all_in",
                "blocked_value_policy": "explicit_unavailable_never_zero",
                "manual_override_allowed": False,
                "epex_policy": "reference_only",
                "next_major_release": "23.5.0",
                "release_status": "v16_complete_external_data_gates_remain",
            },
            "v16_output_runtime_validation": {
                "objective": "make_runtime_gate_state_auditable_before_official_report_publication",
                "projection_gate": {
                    "required_source": "projection_eligibility",
                    "required_value": "eligible_true",
                    "blocked_reason_source": "projection_eligibility.reason",
                },
                "supplier_all_in_gate": {
                    "required_source": "contract_validation",
                    "required_value": "all_required_components_present_true",
                    "blocked_reason_source": "contract_validation.missing_components",
                },
                "decision_gate": {
                    "required_source": "v12_decision_support",
                    "required_value": "recommendation_publishable_true",
                    "blocked_reason_source": "v12_decision_support.reason",
                },
                "publication_state_values": ["blocked", "publishable"],
                "blocked_rendering": "Niet beschikbaar",
                "numeric_zero_for_blocked_allowed": False,
                "status": "runtime_validation_active",
            },
            "v16_output_activation_state": {
                "projection_gate_source": "projection_eligibility",
                "projection_publishable_when": "eligible_true",
                "supplier_all_in_gate_source": "contract_validation",
                "supplier_all_in_publishable_when": "all_required_components_present_true",
                "decision_gate_source": "v12_decision_support",
                "decision_publishable_when": "recommendation_publishable_true",
                "blocked_output": "Niet beschikbaar",
                "blocked_numeric_value": None,
                "automatic_transition": True,
                "manual_override_allowed": False,
                "status": "activation_state_bound_to_runtime_gates",
            },
            "v16_financial_report_output_contract": {
                "objective": "prepare_official_report_outputs_for_real_financial_values_after_external_gates",
                "page1_management_summary_output": "guarded_value_or_unavailable",
                "page1_financial_kpis_output": "guarded_value_or_unavailable",
                "page2_financial_simulation_output": "guarded_value_or_unavailable",
                "page2_year_projection_output": "guarded_value_or_unavailable",
                "page2_monthly_advance_output": "guarded_value_or_unavailable",
                "pages3_13_financial_output": "field_specific_guarded_value_or_unavailable",
                "projection_activation": "automatic_after_7_observed_days",
                "supplier_all_in_activation": "automatic_after_validated_contract_components",
                "manual_gate_override_allowed": False,
                "validation_candidate_as_report_value_allowed": False,
                "missing_value_numeric_fallback": False,
                "epex_supplier_all_in_allowed": False,
                "status": "official_output_contract_active",
            },
            "v15_completion_gate": {
                "official_report_production_context": "ready_guarded",
                "generator_field_contracts": "ready_guarded",
                "financial_render_safety": "ready_guarded",
                "page1_management_financials": "ready_guarded",
                "page2_financial_simulation": "ready_guarded",
                "page2_year_projection": "ready_guarded",
                "page2_monthly_advance_control": "ready_guarded",
                "pages3_13_financial_context": "ready_guarded",
                "observation_gate_dependency": "minimum_7_observed_days",
                "supplier_all_in_dependency": "official_contract_values_required",
                "validation_candidates_publication": "forbidden",
                "missing_financial_values_policy": "explicit_unavailable_never_zero",
                "epex_policy": "reference_only",
                "next_major_release": "23.5.0",
                "release_status": "v15_complete_external_data_gates_remain",
            },
            "v15_report_render_safety": {
                "objective": "prevent_unvalidated_financial_values_from_reaching_official_reports",
                "page1_decision_values": "publish_only_when_recommendation_publishable",
                "page2_projection_values": "publish_only_when_quality_gate_passed",
                "page2_supplier_all_in_values": "publish_only_when_contract_components_complete",
                "page2_advance_comparison": "publish_only_when_supplier_all_in_ready",
                "pages3_13_financial_values": "field_gate_required",
                "blocked_text": "Niet beschikbaar",
                "blocked_numeric_value": None,
                "zero_substitution_allowed": False,
                "validation_only_candidates_publishable": False,
                "epex_supplier_all_in_allowed": False,
                "status": "render_safety_active",
            },
            "v15_report_generator_field_contract": {
                "page1_management_summary_source": "v15_official_report_production_context",
                "page1_financial_kpis_source": "v12_guarded_decision_support",
                "page2_financial_projection_source": "financial_projection",
                "page2_projection_detail_source": "projection_detail",
                "page2_advance_recommendation_source": "v12_guarded_decision_support",
                "pages3_13_financial_context_source": "v15_official_report_production_context",
                "projection_requires_quality_gate": True,
                "supplier_all_in_requires_contract_gate": True,
                "advance_requires_publishable_recommendation": True,
                "missing_value_rendering": "Niet beschikbaar",
                "numeric_missing_value_fallback": False,
                "epex_supplier_all_in_allowed": False,
                "status": "generator_field_contract_active",
            },
            "v15_official_report_production_context": {
                "objective": "feed_official_generators_with_single_guarded_financial_context",
                "page1_management_summary": "production_context_active",
                "page1_financial_kpis": "production_context_active",
                "page2_financial_simulation": "production_context_active_guarded",
                "page2_year_projection": "production_context_active_guarded",
                "page2_monthly_advance_control": "production_context_active_guarded",
                "pages3_13_context": "production_context_active_guarded",
                "projection_source": "financial_projection_and_projection_detail",
                "decision_source": "v12_guarded_decision_support",
                "supplier_all_in_source": "validated_contract_only",
                "blocked_value_rendering": "Niet beschikbaar",
                "numeric_fallback_for_missing_values": False,
                "observation_gate_dependency": "minimum_7_observed_days",
                "epex_policy": "reference_only",
                "status": "official_report_production_context_active",
            },
            "v14_completion_gate": {
                "official_report_generation": "ready_guarded",
                "financial_source_mapping": "ready_guarded",
                "financial_publication_gate": "ready_guarded",
                "management_financial_kpis": "ready_guarded",
                "page2_financial_simulation": "ready_guarded",
                "page2_year_projection": "ready_guarded",
                "page2_monthly_advance_control": "ready_guarded",
                "pages3_13_financial_context": "ready_guarded",
                "ha_release_changelog_policy": "current_release_only",
                "observation_gate_dependency": "minimum_7_observed_days",
                "supplier_all_in_dependency": "official_contract_values_required",
                "missing_financial_values_policy": "explicit_unavailable_never_zero",
                "epex_policy": "reference_only",
                "release_status": "v14_complete_external_data_gates_remain",
            },
            "v14_report_publication_gate": {
                "management_financial_kpis_publishable": "decision_support_gate",
                "page2_projection_publishable": "observation_quality_gate",
                "page2_supplier_all_in_publishable": "official_contract_gate",
                "page2_advance_advice_publishable": "recommendation_publishable_gate",
                "pages3_13_financial_values_publishable": "field_specific_gate",
                "blocked_value_rendering": "Niet beschikbaar",
                "blocked_value_numeric_fallback_allowed": False,
                "epex_supplier_all_in_publication_allowed": False,
                "status": "publication_guard_active",
            },
            "v14_report_value_mapping": {
                "management_financial_kpi_source": "v12_guarded_decision_support",
                "page2_projection_source": "financial_projection",
                "page2_projection_detail_source": "projection_detail",
                "page2_advance_source": "v12_guarded_decision_support",
                "supplier_all_in_source": "validated_contract_only",
                "unavailable_label": "Niet beschikbaar",
                "zero_fallback_allowed": False,
                "quality_gate_required": True,
                "supplier_contract_gate_required": True,
                "epex_reference_only": True,
                "status": "mapped_guarded",
            },
            "v14_report_generation_activation": {
                "objective": "activate_official_reports_from_guarded_financial_context",
                "management_page_financial_kpis": "guarded_active",
                "page2_financial_simulation": "guarded_active",
                "page2_year_projection": "guarded_active",
                "page2_monthly_advance_control": "guarded_active",
                "pages3_13_financial_context": "guarded_active",
                "observation_quality_dependency": "minimum_7_observed_days",
                "supplier_all_in_dependency": "official_contract_values_required",
                "missing_financial_values_policy": "render_unavailable_never_zero",
                "epex_policy": "reference_only",
                "latest_release_display_policy": "latest_only",
                "status": "production_active_guarded",
            },
            "v13_completion_gate": {
                "official_financial_reporting": "ready_guarded",
                "financial_simulation": "ready_guarded",
                "year_projection": "ready_guarded",
                "monthly_advance_control": "ready_guarded",
                "latest_release_display_policy": "latest_only",
                "missing_financial_values_policy": "explicit_unavailable_never_zero",
                "supplier_all_in_dependency": "official_contract_values_required",
                "observation_gate_dependency": "minimum_7_observed_days",
                "epex_policy": "reference_only",
                "release_status": "v13_complete_external_data_gates_remain",
            },
            "v13_official_report_render_contract": {
                "management_financial_summary": "guarded",
                "financial_simulation": "guarded",
                "year_projection": "guarded",
                "monthly_advance_control": "guarded",
                "unavailable_value_label": "Niet beschikbaar",
                "missing_value_numeric_fallback_allowed": False,
                "supplier_all_in_label_requires_validated_contract": True,
                "projection_label_requires_quality_gate": True,
                "advance_advice_requires_publishable_decision": True,
                "epex_may_be_labeled_supplier_all_in": False,
                "status": "active",
            },
            "v13_report_field_policy": {
                "financial_projection": "quality_gate_required",
                "supplier_all_in_cost": "official_contract_validation_required",
                "advance_recommendation": "recommendation_publishable_required",
                "recommendation_strength": "recommendation_publishable_required",
                "unavailable_rendering": "explicit_unavailable",
                "zero_substitution_for_missing_financial_data": False,
                "epex_supplier_all_in_allowed": False,
                "status": "active_guarded",
            },
            "v13_reporting_financial_handoff": {
                "objective": "official_reports_use_validated_financial_decisions",
                "source_decision_layer": "v12_guarded_decision_support",
                "projection_fields_policy": "publish_only_after_observation_quality_gate",
                "supplier_all_in_fields_policy": "publish_only_after_official_contract_validation",
                "advance_recommendation_policy": "publish_only_when_recommendation_publishable",
                "missing_financial_values_policy": "render_unavailable_never_assume",
                "epex_policy": "reference_only_never_supplier_all_in",
                "generator_status": "ready_guarded",
                "release_status": "v13_reporting_handoff_active",
            },
            "v12_completion_gate": {
                "decision_support_engine": "ready_guarded",
                "advance_recommendation_logic": "ready_guarded",
                "recommendation_strength_logic": "ready_guarded",
                "safety_margin_pct": 5.0,
                "observation_quality_dependency": "minimum_7_observed_days",
                "supplier_all_in_dependency": "official_contract_values_required",
                "official_report_handoff": "ready_guarded",
                "release_status": "v12_complete_external_data_gates_remain",
            },
            "v12_decision_support": {
                **decision_support,
                "financial_chain_dependency": "guarded_production_baseline",
                "decision_status": (
                    "decision_ready"
                    if decision_support.get("recommendation_publishable")
                    else "waiting_for_projection_and_supplier_all_in_gates"
                ),
                "no_assumed_contract_values": True,
                "epex_reference_only": True,
            },
            "v11_completion_gate": {
                "analysis_chain": "ready",
                "forecast_engine": "ready_guarded",
                "official_report_generators": "ready_guarded",
                "automatic_forecast_activation": "ready",
                "supplier_all_in": "waiting_for_official_contract_values",
                "observation_gate": "waiting_until_7_days",
                "release_status": "v11_complete_external_data_gates_remain",
            },
            "report_readiness": {
                "official_generators_connected": True,
                "financial_projection_required_for_projection_fields": True,
                "supplier_all_in_required_for_all_in_fields": True,
                "missing_financial_values_render_as_unavailable": True,
                "status": "guarded_ready",
            },
            "forecast_activation": {
                "mode": "automatic_after_quality_gate",
                "minimum_observed_days": 7.0,
                "supplier_all_in_remains_contract_gated": True,
                "no_manual_override": True,
            },
        },
        "scope": {"year_filter": year, "month_count": len(months)},
        "history_span": {
            "first_month": months[0]["month"] if months else None,
            "last_month": months[-1]["month"] if months else None,
        },
        "summary": {
            "months": len(months),
            "quarters": len(quarters),
            "years": len(years),
            "warnings": warnings,
        },
        "definitions": {
            "grid_import_kwh": "Elektriciteit van het net volgens P1e.",
            "grid_export_kwh": "Teruglevering aan het net volgens P1e.",
            "net_grid_kwh": "grid_import_kwh minus grid_export_kwh.",
            "gas_m3": "Gasverbruik volgens P1g.",
            "solar_production_kwh": "Enphase-opwek; bij ontbrekende Enphase alleen expliciet gemarkeerde export_fallback.",
            "self_use_pct": "Direct eigen zonnegebruik gedeeld door zonneproductie; null als brondekking dit niet betrouwbaar toelaat.",
            "self_supply_pct": "Direct eigen zonnegebruik gedeeld door berekend huishoudelijk elektriciteitsgebruik; null als brondekking dit niet betrouwbaar toelaat.",
            "supplier_context": "Bekende NextEnergy-contractmetadata plus live en historische Home Assistant-prijstelemetrie. Over beschikbare kwartiersnapshots wordt ook een werkelijk verbruikgewogen afnameprijs berekend uit P1-importdelta × NextEnergy-prijs; dit blijft gedeeltelijke dekking en nog geen leverancier-all-in maandbedrag.",
            "price_context": "Historische EPEX-v6 prijscontext. De reader zoekt eerst in de feitelijke Home Assistant share `/share/Energie_NAS/05_Maanddata/EPEX` en ondersteunt daarnaast legacy projectpaden. De hoofdstatistiek gebruikt prijs_incl_btw_en_eb en is geen leverancier-all-in prijs.",
        },
        "months": months,
        "quarters": quarters,
        "years": years,
    }


def analysis_overview(context: dict[str, Any]) -> dict[str, Any]:
    summary = context.get("summary") or {}
    history = context.get("history_span") or {}
    latest = (context.get("months") or [])[-1] if context.get("months") else {}
    quality = latest.get("quality") or {}
    warnings = summary.get("warnings") or []
    return {
        "history": f"{history.get('first_month') or '—'} t/m {history.get('last_month') or '—'}",
        "months": summary.get("months", 0),
        "quarters": summary.get("quarters", 0),
        "years": summary.get("years", 0),
        "latest_month": latest.get("month") or "—",
        "latest_sources": ", ".join(quality.get("available_sources") or []) or "geen",
        "quality": "Waarschuwing" if warnings else "OK",
        "warning": warnings[0] if warnings else "Analysecontext beschikbaar",
    }

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




def required_month_input_files(options: Options, *, historical: bool = False) -> set[str]:
    """Return files that must exist for the selected workflow mode.

    A historical workflow must not fail because present-day device sources did not
    exist, were switched off, or were never archived for the requested month. Exact
    historical files are still reused when available. EPEX remains required only
    when its historical importer is explicitly enabled.
    """
    required: set[str] = set()
    if not historical and options.month_input_require_homewizard:
        required.update([
            "P1e.csv",
            "P1g.csv",
            "Airco Skt.csv",
            "Mobiel Skt.csv",
            "Heater kantoor Skt.csv",
            "Heater woonkamer Skt.csv",
            "Heater lounge Skt.csv",
        ])
    if not historical and options.month_input_require_enphase:
        required.add("Enphase.csv")
    if not historical and options.month_input_require_nordpool:
        required.add("Nordpool elektriciteit.csv")
    if options.epex_electricity_enabled:
        required.add("EPEX stroom.csv")
    if options.epex_gas_enabled:
        required.add("EPEX gas.csv")
    return required


def report_input_readiness(month_key: str, options: Options) -> dict[str, Any]:
    """Check whether the official report chain has its complete input contract."""
    folder = MONTH_INPUT_ROOT / month_key
    expected = expected_month_input_files(options)
    missing: list[str] = []
    empty: list[str] = []
    for filename in expected:
        path = folder / filename
        if not path.exists() or not path.is_file():
            missing.append(filename)
        elif path.stat().st_size == 0:
            empty.append(filename)
    return {
        "status": "ready" if not missing and not empty else "incomplete",
        "folder": str(folder),
        "expected": expected,
        "missing": sorted(missing),
        "empty": sorted(empty),
    }


def historical_month_input_candidates(month_key: str, options: "Options") -> dict[str, Any]:
    """Return read-only candidate locations for previously built historical month input.

    Historical processing must never manufacture old HomeWizard/HA snapshots from
    current live data. We therefore only reuse exact, already stored month files.
    """
    parse_month_key(month_key)
    transfer_root = TRANSFER_SHARE_ROOT / Path(options.transfer_share_folder)
    # De console-link “YYYY_MM als archief downloaden” bewaart geen fysieke ZIP:
    # zip_month() bouwt die download dynamisch uit OUTPUT_ROOT / month_key.
    # Daarom is die maandmap zelf een primaire historische bron.
    roots = [
        MONTH_INPUT_ROOT / month_key,
        OUTPUT_ROOT / month_key,
        transfer_root / month_key,
        transfer_root / "01_Input" / month_key,
        transfer_root / "02_Output" / month_key,
    ]
    zips = [
        MONTH_INPUT_ROOT / f"01_Input_{month_key}.zip",
        transfer_root / f"01_Input_{month_key}.zip",
    ]

    # Neem daarnaast reeds bewaarde maandarchieven mee. Alleen ZIP-bestanden
    # met de exacte maandcode in de naam worden bekeken; Recovery Updates en
    # andere maanden worden daarmee niet als historische invoer gebruikt.
    discovered_zips: list[Path] = []
    for search_root in (OUTPUT_ROOT, transfer_root):
        if not search_root.exists() or not search_root.is_dir():
            continue
        try:
            for candidate in search_root.rglob(f"*{month_key}*.zip"):
                if candidate.is_file() and candidate not in zips:
                    discovered_zips.append(candidate)
        except OSError:
            continue
    zips.extend(sorted(set(discovered_zips), key=lambda path: str(path)))

    return {
        "roots": roots,
        "zips": zips,
        "checked": [str(path) for path in [*roots, *zips]],
    }


def recover_historical_month_input(month_key: str, target: Path, options: "Options") -> dict[str, Any]:
    """Recover exact historical input files from existing folders/archives.

    Files are copied with their existing case-sensitive names. Existing target files
    are never overwritten. ZIP members are accepted only when their basename exactly
    matches an expected input filename, preventing path traversal and accidental
    renaming.
    """
    candidates = historical_month_input_candidates(month_key, options)
    expected = set(expected_month_input_files(options))
    recovered: list[dict[str, str]] = []

    for source_root in candidates["roots"]:
        if source_root == target or not source_root.exists() or not source_root.is_dir():
            continue
        for filename in sorted(expected):
            destination = target / filename
            if destination.exists():
                continue

            # Zoek recursief: de downloadbare maand-archive bevat precies de
            # boom onder OUTPUT_ROOT/YYYY_MM en historische bronbestanden kunnen
            # daarin in submappen staan. De basename moet case-sensitive exact
            # overeenkomen; er wordt dus nooit automatisch hernoemd.
            source = None
            try:
                matches = sorted(
                    (path for path in source_root.rglob(filename) if path.is_file()),
                    key=lambda path: (len(path.parts), str(path)),
                )
            except OSError:
                matches = []
            if matches:
                source = matches[0]
            if source is None:
                continue
            shutil.copy2(source, destination)
            item = {"file": filename, "source": str(source), "target": str(destination)}
            recovered.append(item)
            try:
                append_workflow_log(
                    month_key,
                    "info",
                    "Historisch bronbestand hersteld",
                    file=filename,
                    source=str(source),
                    target=str(destination),
                )
            except Exception:
                pass

    for archive_path in candidates["zips"]:
        if not archive_path.exists() or not archive_path.is_file():
            continue
        try:
            with zipfile.ZipFile(archive_path, "r") as archive:
                members_by_name: dict[str, str] = {}
                for member in archive.namelist():
                    path = Path(member)
                    if path.name in expected and not member.endswith("/"):
                        members_by_name.setdefault(path.name, member)
                for filename in sorted(expected):
                    destination = target / filename
                    member = members_by_name.get(filename)
                    if destination.exists() or not member:
                        continue
                    data = archive.read(member)
                    destination.write_bytes(data)
                    item = {"file": filename, "source": f"{archive_path}!/{member}", "target": str(destination)}
                    recovered.append(item)
                    try:
                        append_workflow_log(
                            month_key,
                            "info",
                            "Historisch bronbestand hersteld",
                            file=filename,
                            source=item["source"],
                            target=str(destination),
                        )
                    except Exception:
                        pass
        except (zipfile.BadZipFile, OSError):
            continue

    return {
        "status": "recovered" if recovered else "none",
        "recovered": recovered,
        "checked": candidates["checked"],
    }

def build_month_input(month_key: str | None = None, *, reuse_existing: bool = False) -> dict[str, Any]:
    options = Options.load()
    if not options.month_input_enabled:
        raise RuntimeError("Maandmap-opbouw is uitgeschakeld.")

    month_key = month_key or datetime.now(TZ).strftime("%Y_%m")
    parse_month_key(month_key)

    target = MONTH_INPUT_ROOT / month_key
    target.mkdir(parents=True, exist_ok=True)

    historical_recovery = {"status": "not_requested", "recovered": [], "checked": []}
    if reuse_existing:
        historical_recovery = recover_historical_month_input(month_key, target, options)

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
            if reuse_existing and destination.exists() and destination.is_file():
                size = destination.stat().st_size
                reused_result = {
                    "source": str(destination),
                    "target": str(destination),
                    "written_rows": 1 if size > 0 else 0,
                    "reused_existing": True,
                    "bytes": size,
                }
                results.append(reused_result)
                if size == 0:
                    empty.append(destination.name)
                continue
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

    required = required_month_input_files(options, historical=reuse_existing)

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
        "reuse_existing": reuse_existing,
        "historical_mode": reuse_existing,
        "required_files": sorted(required),
        "historical_recovery": historical_recovery,
        "source_paths_checked": historical_recovery.get("checked", []) if reuse_existing else [],
        "reused_existing_files": sorted(
            Path(item["target"]).name
            for item in results
            if item.get("reused_existing")
        ),
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
            else (
                f"Ontbrekend: {', '.join(missing_required)}; leeg: {', '.join(empty_required)}; "
                f"gecontroleerde historische bronnen: {', '.join(historical_recovery.get('checked', [])) if reuse_existing else 'n.v.t.'}"
            )
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
    send_notification: bool = True,
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
    if options.transfer_share_folder == "Energie_Overdracht":
        destination_root = NAS_DATA_ROOT / "01_Input"
    else:
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
    if options.transfer_notify_home_assistant and send_notification:
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



def append_automatic_run_history(record: dict[str, Any]) -> dict[str, Any]:
    row = {"recorded_at": datetime.now(TZ).isoformat(), "version": APP_VERSION, **record}
    AUTOMATIC_RUN_LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUTOMATIC_RUN_LEDGER_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    return row


def read_automatic_run_history(limit: int = 20) -> list[dict[str, Any]]:
    if not AUTOMATIC_RUN_LEDGER_PATH.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in AUTOMATIC_RUN_LEDGER_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return list(reversed(rows[-max(1, min(limit, 100)):]))



RETRY_DEBUG_LAST_SIGNATURE: str | None = None


def append_finalization_debug(event: str, **data: Any) -> None:
    """Append-only trace van de laatste workflow/finalization-fase."""
    record = {
        "timestamp": datetime.now(TZ).isoformat(),
        "version": APP_VERSION,
        "event": event,
        **data,
    }
    try:
        FINALIZATION_DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with FINALIZATION_DEBUG_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError:
        LOGGER.exception("Finalization debuglog kon niet worden geschreven.")


def finalization_debug_tail(limit: int = 30) -> list[dict[str, Any]]:
    if not FINALIZATION_DEBUG_LOG_PATH.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in FINALIZATION_DEBUG_LOG_PATH.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines()[-max(1, min(limit, 100)):]:
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def append_retry_debug(event: str, **data: Any) -> None:
    """Append-only diagnose; identieke opeenvolgende regels worden onderdrukt."""
    global RETRY_DEBUG_LAST_SIGNATURE
    record = {
        "timestamp": datetime.now(TZ).isoformat(),
        "version": APP_VERSION,
        "event": event,
        **data,
    }
    signature = json.dumps({"event": event, **data}, ensure_ascii=False, sort_keys=True, default=str)
    if signature == RETRY_DEBUG_LAST_SIGNATURE:
        return
    RETRY_DEBUG_LAST_SIGNATURE = signature
    try:
        RETRY_DEBUG_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with RETRY_DEBUG_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    except OSError:
        LOGGER.exception("Retry debuglog kon niet worden geschreven.")


def workflow_history_debug(month_key: str) -> dict[str, Any]:
    path = OUTPUT_ROOT / "workflow_results" / month_key / "workflow_result.json"
    detail: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "readable": False,
        "proves_completed": False,
        "status": None,
        "trigger": None,
        "failed_step": None,
        "error_count": None,
        "steps_completed": None,
        "steps_total": None,
        "checks": {},
    }
    if not path.is_file():
        detail["decision"] = "workflow_result ontbreekt"
        return detail
    try:
        item = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        detail["decision"] = f"workflow_result onleesbaar: {exc}"
        return detail
    if not isinstance(item, dict):
        detail["decision"] = "workflow_result is geen object"
        return detail

    completed = int(item.get("steps_completed") or 0)
    total = int(item.get("steps_total") or 0)
    persisted_steps = item.get("steps") if isinstance(item.get("steps"), list) else []
    accepted_terminal_statuses = {"ok", "info", "warning", "skipped"}
    if persisted_steps:
        recomputed_completed = sum(
            1 for step in persisted_steps
            if isinstance(step, dict) and step.get("status") in accepted_terminal_statuses
        )
        recomputed_total = len(persisted_steps)
        all_steps_completed = (
            recomputed_total > 0 and recomputed_completed == recomputed_total
        )
    else:
        recomputed_completed = completed
        recomputed_total = total
        all_steps_completed = total > 0 and completed >= total
    checks = {
        "status_ok": str(item.get("status") or "") in {"completed", "completed_warning"},
        "trigger_automatic": str(item.get("trigger") or "") == "automatic",
        "no_failed_step": not item.get("failed_step"),
        "no_errors": not list(item.get("errors") or []),
        "all_steps_completed": all_steps_completed,
    }
    detail.update({
        "readable": True,
        "status": item.get("status"),
        "trigger": item.get("trigger"),
        "failed_step": item.get("failed_step"),
        "error_count": len(list(item.get("errors") or [])),
        "steps_completed": completed,
        "steps_total": total,
        "recomputed_steps_completed": recomputed_completed,
        "recomputed_steps_total": recomputed_total,
        "completion_source": "steps" if persisted_steps else "stored_counters",
        "checks": checks,
        "proves_completed": all(checks.values()),
    })
    failed = [name for name, ok in checks.items() if not ok]
    detail["decision"] = "bewijs geldig" if not failed else "afgewezen: " + ", ".join(failed)
    return detail


def retry_debug_snapshot(state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Niet-muteren­de diagnose van alle bronnen die de retrybeslissing beïnvloeden."""
    state = state or load_state()
    retry = read_automatic_retry_state()
    month = str(
        retry.get("month")
        or state.get("automatic_month_close_retry_month")
        or state.get("automatic_month_close_last_month")
        or ""
    )
    ledger_matches = []
    if month:
        for item in read_automatic_run_history(limit=100):
            if str(item.get("month") or "") == month:
                ledger_matches.append({
                    "type": item.get("type"),
                    "status": item.get("status"),
                    "finalization_status": item.get("finalization_status"),
                    "version": item.get("version"),
                    "finished_at": item.get("finished_at") or item.get("recorded_at"),
                })
    ledger_proof = automatic_history_proves_completed(month) if month else None
    workflow_debug = workflow_history_debug(month) if month else {
        "exists": False, "proves_completed": False, "decision": "geen retry-maand"
    }
    marker = (read_automatic_completion_markers().get(month) or {}) if month else {}
    marker_ok = automatic_month_is_completed(month) if month else False

    return {
        "checked_at": datetime.now(TZ).isoformat(),
        "retry_state_path": str(AUTOMATIC_RETRY_STATE_PATH),
        "retry_state_file_exists": AUTOMATIC_RETRY_STATE_PATH.is_file(),
        "retry_state_loaded": retry,
        "legacy_state": {
            "last_month": state.get("automatic_month_close_last_month"),
            "last_status": state.get("automatic_month_close_last_status"),
            "next_retry": state.get("automatic_month_close_next_retry"),
            "retry_month": state.get("automatic_month_close_retry_month"),
            "retry_reason": state.get("automatic_month_close_retry_reason"),
            "retry_origin": state.get("automatic_month_close_retry_origin"),
        },
        "month_checked": month,
        "completion_marker": {
            "found": bool(marker),
            "proves_completed": marker_ok,
            "value": marker,
        },
        "append_history": {
            "matching_records": ledger_matches,
            "proves_completed": bool(ledger_proof),
            "proof": ledger_proof,
        },
        "workflow_history": workflow_debug,
        "current_decision": {
            "state": retry.get("state") or "GEEN",
            "reason": retry.get("reason"),
            "origin": retry.get("origin"),
            "evidence": retry.get("evidence"),
            "next_retry": retry.get("next_retry"),
        },
        "debug_log_path": str(RETRY_DEBUG_LOG_PATH),
    }


RETRY_STATES = {"OPEN", "RUNNING", "COMPLETED", "CANCELLED", "EXPIRED"}


def read_automatic_retry_state() -> dict[str, Any]:
    if not AUTOMATIC_RETRY_STATE_PATH.is_file():
        return {}
    try:
        value = json.loads(AUTOMATIC_RETRY_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict):
        return {}
    if str(value.get("state") or "") not in RETRY_STATES:
        return {}
    return value


def write_automatic_retry_state(
    *,
    state: str,
    month: str | None,
    reason: str | None = None,
    origin: str | None = None,
    next_retry: str | None = None,
    evidence: str | None = None,
) -> dict[str, Any]:
    if state not in RETRY_STATES:
        raise ValueError(f"Ongeldige retry-state: {state}")
    current = read_automatic_retry_state()
    now = datetime.now(TZ).isoformat()
    row = {
        "state": state,
        "month": month,
        "reason": reason,
        "origin": origin,
        "next_retry": next_retry,
        "evidence": evidence,
        "updated_at": now,
        "version": APP_VERSION,
        "created_at": current.get("created_at") or now,
    }
    AUTOMATIC_RETRY_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = AUTOMATIC_RETRY_STATE_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(row, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(AUTOMATIC_RETRY_STATE_PATH)
    return row


def automatic_history_proves_completed(month_key: str) -> dict[str, Any] | None:
    if not AUTOMATIC_RUN_LEDGER_PATH.is_file():
        return None
    for item in read_automatic_run_history(limit=100):
        if (
            str(item.get("month") or "") == month_key
            and str(item.get("type") or "") == "Automatisch"
            and str(item.get("status") or "") in {"completed", "completed_warning"}
            and str(item.get("finalization_status") or "") == "ok"
        ):
            return item
    return None


def workflow_history_proves_completed(month_key: str) -> dict[str, Any] | None:
    """Hard auditbewijs met dezelfde semantiek als Retry Debug."""
    path = OUTPUT_ROOT / "workflow_results" / month_key / "workflow_result.json"
    if not path.is_file():
        return None
    try:
        item = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(item, dict):
        return None

    status_ok = str(item.get("status") or "") in {"completed", "completed_warning"}
    trigger_ok = str(item.get("trigger") or "") == "automatic"
    failed_step_ok = not item.get("failed_step")
    errors_ok = not list(item.get("errors") or [])

    accepted_terminal_statuses = {"ok", "info", "warning", "skipped"}
    persisted_steps = item.get("steps") if isinstance(item.get("steps"), list) else []
    explicit_flag = item.get("all_steps_completed")

    if isinstance(explicit_flag, bool):
        steps_ok = explicit_flag
    elif persisted_steps:
        steps_ok = all(
            isinstance(step, dict) and step.get("status") in accepted_terminal_statuses
            for step in persisted_steps
        )
    else:
        completed = int(item.get("steps_completed") or 0)
        total = int(item.get("steps_total") or 0)
        steps_ok = total > 0 and completed >= total

    if status_ok and trigger_ok and failed_step_ok and errors_ok and steps_ok:
        return item
    return None


def migrate_legacy_retry_state(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    retry = read_automatic_retry_state()
    append_retry_debug(
        "migration_enter",
        retry_file_exists=AUTOMATIC_RETRY_STATE_PATH.is_file(),
        loaded_retry=retry,
        legacy_last_month=state.get("automatic_month_close_last_month"),
        legacy_last_status=state.get("automatic_month_close_last_status"),
        legacy_next_retry=state.get("automatic_month_close_next_retry"),
    )
    if retry:
        append_retry_debug(
            "migration_existing_retry_returned",
            state=retry.get("state"),
            month=retry.get("month"),
            reason=retry.get("reason"),
            evidence=retry.get("evidence"),
        )
        return state, retry

    next_retry = state.get("automatic_month_close_next_retry")
    last_month = str(state.get("automatic_month_close_retry_month") or state.get("automatic_month_close_last_month") or "")
    last_status = str(state.get("automatic_month_close_last_status") or "")
    origin = str(state.get("automatic_month_close_retry_origin") or "automatic")
    reason = str(state.get("automatic_month_close_retry_reason") or "legacy_retry")

    if not next_retry or not last_month:
        retry = write_automatic_retry_state(
            state="COMPLETED", month=None, reason=None, origin=None, next_retry=None,
            evidence="Geen open legacy retry aanwezig bij migratie.",
        )
        return state, retry

    ledger_proof = automatic_history_proves_completed(last_month)
    workflow_proof = workflow_history_proves_completed(last_month)
    completion_marker = automatic_month_is_completed(last_month)
    append_retry_debug(
        "migration_legacy_evidence",
        month=last_month,
        ledger_proof=bool(ledger_proof),
        workflow_proof=bool(workflow_proof),
        workflow_debug=workflow_history_debug(last_month),
        completion_marker=completion_marker,
        legacy_last_status=last_status,
    )
    if ledger_proof or workflow_proof or completion_marker or last_status in {"completed", "completed_warning"}:
        if ledger_proof:
            evidence = "Append-only historie bevat een geslaagde echte Automatisch-run."
        elif workflow_proof:
            evidence = "Historisch workflow_result bewijst een volledig geslaagde automatische run."
        else:
            evidence = "Duurzame completion-marker of completed-state aanwezig."
        return finalize_proven_retry_state(
            state,
            {"state": "OPEN", "month": last_month, "reason": reason, "origin": origin, "next_retry": str(next_retry)},
            month=last_month,
            evidence=evidence,
        )

    retry = write_automatic_retry_state(
        state="OPEN",
        month=last_month,
        reason=reason,
        origin=origin,
        next_retry=str(next_retry),
        evidence="Legacy retry zonder bewijs van definitieve voltooiing.",
    )
    return state, retry




def read_automatic_completion_markers() -> dict[str, Any]:
    if not AUTOMATIC_COMPLETION_MARKERS_PATH.is_file():
        return {}
    try:
        value = json.loads(AUTOMATIC_COMPLETION_MARKERS_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def automatic_month_is_completed(month_key: str) -> bool:
    marker = read_automatic_completion_markers().get(month_key) or {}
    return bool(
        isinstance(marker, dict)
        and marker.get("status") in {"completed", "completed_warning"}
        and marker.get("finalization_status") == "ok"
    )


def mark_automatic_month_completed(
    month_key: str,
    *,
    status: str,
    finalization_status: str,
    finished_at: str | None,
) -> dict[str, Any]:
    """Schrijf een duurzame, atomische productie-completion marker."""
    markers = read_automatic_completion_markers()
    marker = {
        "month": month_key,
        "status": status,
        "finalization_status": finalization_status,
        "finished_at": finished_at or datetime.now(TZ).isoformat(),
        "version": APP_VERSION,
        "recorded_at": datetime.now(TZ).isoformat(),
    }
    markers[month_key] = marker
    AUTOMATIC_COMPLETION_MARKERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = AUTOMATIC_COMPLETION_MARKERS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(markers, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(AUTOMATIC_COMPLETION_MARKERS_PATH)
    return marker


FULL_WORKFLOW_RESULT_NAME = "workflow_result.json"
WORKFLOW_LOG_NAME = "workflow.log"


def workflow_result_dir(month_key: str) -> Path:
    return OUTPUT_ROOT / "workflow_results" / month_key


def append_workflow_log(month_key: str, level: str, message: str, **extra: Any) -> None:
    root = workflow_result_dir(month_key)
    root.mkdir(parents=True, exist_ok=True)
    record = {
        "timestamp": datetime.now(TZ).isoformat(),
        "level": level,
        "message": message,
        **extra,
    }
    path = root / WORKFLOW_LOG_NAME
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def record_workflow_failure(
    month_key: str,
    *,
    step: str,
    exc: BaseException,
    started_at: str | None = None,
    duration_seconds: float | None = None,
) -> dict[str, Any]:
    """Sla de volledige diagnose van een workflowfout persistent op."""
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
    details = {
        "timestamp": datetime.now(TZ).isoformat(),
        "month": month_key,
        "step": step,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "started_at": started_at,
        "duration_seconds": duration_seconds,
        "traceback": tb,
    }
    update_state(
        full_workflow_last_error=str(exc),
        full_workflow_last_error_type=type(exc).__name__,
        full_workflow_last_error_step=step,
        full_workflow_last_error_at=details["timestamp"],
        full_workflow_last_traceback=tb,
    )
    append_workflow_log(
        month_key, "error", "Stap mislukt", step=step, error=str(exc),
        error_type=type(exc).__name__, duration_seconds=duration_seconds, traceback=tb,
    )
    return details


def workflow_log_file(month_key: str) -> Path:
    parse_month_key(month_key)
    return workflow_result_dir(month_key) / WORKFLOW_LOG_NAME


def workflow_log_tail(month_key: str, limit: int = 120) -> list[dict[str, Any]]:
    parse_month_key(month_key)
    path = workflow_result_dir(month_key) / WORKFLOW_LOG_NAME
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-max(1, min(limit, 500)):]:
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            rows.append({"timestamp": None, "level": "info", "message": line})
    return rows


def previous_workflow_result(month_key: str) -> dict[str, Any] | None:
    path = workflow_result_dir(month_key) / FULL_WORKFLOW_RESULT_NAME
    if not path.is_file():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def resumable_step_names(month_key: str) -> set[str]:
    previous = previous_workflow_result(month_key) or {}
    if previous.get("status") in {"completed", "completed_warning"}:
        return set()
    completed: set[str] = set()
    for step in previous.get("steps") or []:
        if step.get("status") in {"ok", "info", "warning", "skipped"}:
            name = str(step.get("name") or "")
            if name:
                completed.add(name)
    return completed


def resumable_step_results(month_key: str) -> dict[str, Any]:
    previous = previous_workflow_result(month_key) or {}
    results: dict[str, Any] = {}
    for step in previous.get("steps") or []:
        if step.get("status") in {"ok", "info", "warning", "skipped"}:
            name = str(step.get("name") or "")
            if name:
                results[name] = step.get("result")
    return results


def start_workflow_background(
    month_key: str,
    *,
    collect_live_snapshots: bool,
    resume: bool = False,
    trigger: str | None = None,
) -> dict[str, Any]:
    parse_month_key(month_key)
    if WORKFLOW_LOCK.locked():
        return {"status": "busy", "active": workflow_lock_snapshot(), "message": "Er draait al een maandworkflow."}
    resolved_trigger = trigger or ("resume" if resume else "manual")
    if resolved_trigger not in {"manual", "historical", "automatic", "resume"}:
        raise ValueError(f"Onbekende workflowtrigger: {resolved_trigger}")

    def worker() -> None:
        try:
            run_full_month_workflow(
                month_key,
                collect_live_snapshots=collect_live_snapshots,
                resume=resume,
                trigger=resolved_trigger,
            )
        except Exception as exc:
            LOGGER.exception("Achtergrondworkflow mislukt: %s", exc)
        finally:
            # Failsafe: een onverwachte fout na de normale workflow-afhandeling
            # mag nooit een permanente workflow-lock achterlaten.
            if WORKFLOW_LOCK.locked():
                try:
                    append_workflow_log(month_key, "error", "Failsafe heeft achtergebleven workflow-lock vrijgegeven")
                    set_workflow_lock_state(
                        status="idle",
                        month=month_key,
                        step="Failsafe",
                        message="Workflow is onverwacht gestopt; lock is veilig vrijgegeven.",
                    )
                finally:
                    try:
                        WORKFLOW_LOCK.release()
                    except RuntimeError:
                        pass

    threading.Thread(target=worker, daemon=True, name=f"workflow-{month_key}").start()
    # Geef de worker kort gelegenheid om het lock te nemen zodat dubbelklikken wordt afgevangen.
    for _ in range(20):
        if WORKFLOW_LOCK.locked():
            break
        time.sleep(0.01)
    return {"status": "started", "month": month_key, "resume": resume, "trigger": resolved_trigger}


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


def workflow_heartbeat(month_key: str, step: str, message: str, **extra: Any) -> None:
    """Werk UI en workflowlog bij zonder de starttijd van de lock te resetten."""
    now = datetime.now(TZ).isoformat()
    with WORKFLOW_LOCK_META:
        if WORKFLOW_ACTIVE:
            WORKFLOW_ACTIVE["step"] = step
            WORKFLOW_ACTIVE["message"] = message
            WORKFLOW_ACTIVE["heartbeat_at"] = now
    update_state(
        workflow_lock_step=step,
        workflow_lock_message=message,
        workflow_heartbeat_at=now,
    )
    append_workflow_log(month_key, "info", "Heartbeat", step=step, heartbeat_message=message, **extra)


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

    heartbeat_stop = threading.Event()
    import_started = time.monotonic()

    def import_heartbeat_worker() -> None:
        timeout_requested = False
        while not heartbeat_stop.wait(options.workflow_heartbeat_seconds):
            state = load_state()
            elapsed = round(time.monotonic() - import_started, 1)
            message = str(state.get("progress_message") or "SlimmeMeterPortal maandimport actief")
            workflow_heartbeat(
                f"{year:04d}_{month:02d}",
                "SlimmeMeterPortal maandimport",
                message,
                elapsed_seconds=elapsed,
                progress_current=int(state.get("progress_current") or 0),
                progress_total=int(state.get("progress_total") or 0),
            )
            if elapsed >= options.workflow_step_timeout_seconds and not timeout_requested:
                timeout_requested = True
                update_state(
                    cancel_requested=True,
                    workflow_cancel_reason="workflow_timeout",
                )
                append_workflow_log(
                    f"{year:04d}_{month:02d}",
                    "error",
                    "Workflow-timeout bereikt; import wordt gecontroleerd gestopt",
                    step="SlimmeMeterPortal maandimport",
                    timeout_seconds=options.workflow_step_timeout_seconds,
                    elapsed_seconds=elapsed,
                )

    heartbeat_thread = threading.Thread(
        target=import_heartbeat_worker,
        daemon=True,
        name=f"smp-heartbeat-{year:04d}-{month:02d}",
    )
    heartbeat_thread.start()
    try:
        run_import(year, month)
    finally:
        heartbeat_stop.set()
        heartbeat_thread.join(timeout=max(1, options.workflow_heartbeat_seconds + 1))

    import_state = load_state()
    if import_state.get("status") == "cancelled":
        reason = str(import_state.get("last_cancel_reason") or "unknown")
        if reason == "workflow_timeout":
            raise RuntimeError(
                "SlimmeMeterPortal maandimport overschreed de workflow-timeout van "
                f"{options.workflow_step_timeout_seconds} seconden."
            )
        raise ImportCancelled(reason)
    if import_state.get("status") == "error":
        raise RuntimeError(str(import_state.get("last_error") or "Maandimport mislukt."))
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
    resume: bool = False,
    trigger: str = "manual",
) -> dict[str, Any]:
    options = Options.load()
    if trigger not in {"manual", "historical", "automatic", "automatic_test", "resume"}:
    # v7.9: automatic_test gebruikt exact dezelfde workflow als automatic,
    # maar mag de schedulerstaat niet als afgehandeld markeren.
        raise ValueError("Ongeldige workflow-trigger.")
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
    # Een nieuwe run mag geen foutdiagnose of voortgang van een vorige run tonen.
    # Dit voorkomt dat een opgeloste fout tijdens een actieve run als actuele fout
    # zichtbaar blijft in de operationele console.
    update_state(
        full_workflow_last_month=month_key,
        full_workflow_last_trigger=trigger,
        full_workflow_last_status="running",
        full_workflow_last_step="Initialiseren",
        full_workflow_last_error=None,
        full_workflow_last_error_type=None,
        full_workflow_last_error_step=None,
        full_workflow_last_error_at=None,
        full_workflow_last_traceback=None,
        progress_current=0,
        progress_total=0,
        progress_message="Workflow gestart",
    )
    current_month_key = datetime.now(TZ).strftime("%Y_%m")
    target_is_current_month = month_key == current_month_key
    if collect_live_snapshots is None:
        collect_live_snapshots = target_is_current_month

    resume_completed = resumable_step_names(month_key) if resume else set()
    resume_results = resumable_step_results(month_key) if resume else {}
    append_workflow_log(
        month_key,
        "info",
        "Workflow gestart" if not resume else "Workflow hervat",
        resume=resume,
        trigger=trigger,
        skipped_previous=sorted(resume_completed),
    )

    if options.workflow_notify_home_assistant and options.workflow_notify_on_start:
        try:
            title = "Automatische energie-maandafsluiting gestart" if trigger in {"automatic", "automatic_test"} else "Energie maandworkflow gestart"
            notify_home_assistant(
                title,
                f"Maand {month_key} wordt verwerkt. Trigger: {trigger}.",
            )
        except Exception as exc:
            append_workflow_log(month_key, "warning", "Startnotificatie mislukt", error=str(exc))

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
        if resume and name in resume_completed:
            previous_result = resume_results.get(name)
            result = previous_result if previous_result is not None else {
                "status": "completed_info", "resume": True,
                "message": "Eerder succesvol; stap hergebruikt.",
            }
            append_workflow_step(
                steps, name=name, status="info", started_at=step_started,
                finished_at=datetime.now(TZ).isoformat(), result=result,
            )
            infos.append(f"{name}: hergebruikt bij hervatten")
            append_workflow_log(month_key, "info", "Stap hergebruikt", step=name, status="info")
            return result
        append_workflow_log(
            month_key, "info", "Stap gestart", step=name,
            timeout_seconds=options.workflow_step_timeout_seconds,
        )
        step_started_monotonic = time.monotonic()
        try:
            result = function()
            step_duration = round(time.monotonic() - step_started_monotonic, 3)
            if step_duration > options.workflow_step_timeout_seconds:
                raise RuntimeError(
                    f"{name} overschreed de workflow-timeout van "
                    f"{options.workflow_step_timeout_seconds} seconden."
                )
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
            append_workflow_log(
                month_key, "warning" if status == "warning" else "info",
                "Stap afgerond", step=name, status=status, duration_seconds=step_duration,
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
        except ImportCancelled as exc:
            step_finished = datetime.now(TZ).isoformat()
            append_workflow_step(
                steps, name=name, status="cancelled", started_at=step_started,
                finished_at=step_finished, error=exc.reason,
            )
            failed_step = name
            append_workflow_log(month_key, "info", "Stap geannuleerd", step=name, reason=exc.reason)
            raise
        except Exception as exc:
            step_finished = datetime.now(TZ).isoformat()
            step_duration = round(time.monotonic() - step_started_monotonic, 3)
            details = record_workflow_failure(
                month_key, step=name, exc=exc, started_at=step_started,
                duration_seconds=step_duration,
            )
            already_recorded = bool(
                steps
                and steps[-1].get("name") == name
                and steps[-1].get("status") == "error"
            )
            if not already_recorded:
                append_workflow_step(
                    steps, name=name, status="error", started_at=step_started,
                    finished_at=step_finished, error=str(exc),
                )
                steps[-1]["diagnostics"] = details
            failed_step = name
            error_text = f"{name}: {type(exc).__name__}: {exc}"
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
            infos.append(
                "Historische maand: live snapshots bewust niet aan doelmaand toegevoegd."
            )

        if options.enphase_enabled:
            if collect_live_snapshots and target_is_current_month:
                execute_step(
                    "Enphase bronimport",
                    run_enphase_import,
                    required=True,
                )
            else:
                now_iso = datetime.now(TZ).isoformat()
                append_workflow_step(
                    steps,
                    name="Enphase bronimport",
                    status="info",
                    started_at=now_iso,
                    finished_at=now_iso,
                    result={
                        "status": "info",
                        "reason": "Historische run gebruikt uitsluitend reeds beschikbare Enphase-maanddata.",
                    },
                )
                infos.append("Historische Enphase live-import bewust niet uitgevoerd.")
                append_workflow_log(month_key, "info", "Stap afgerond", step="Enphase bronimport", status="info", duration_seconds=0.0)
        else:
            now_iso = datetime.now(TZ).isoformat()
            append_workflow_step(
                steps,
                name="Enphase bronimport",
                status="info",
                started_at=now_iso,
                finished_at=now_iso,
                result={"status": "info", "reason": "Enphase externe bron is niet geconfigureerd."},
            )
            infos.append("Enphase externe bron is niet geconfigureerd.")
            append_workflow_log(month_key, "info", "Stap afgerond", step="Enphase bronimport", status="info", duration_seconds=0.0)

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
                append_workflow_log(month_key, "info", "Stap afgerond", step="EPEX import en validatie", status="info", duration_seconds=0.0)
        else:
            now_iso = datetime.now(TZ).isoformat()
            append_workflow_step(
                steps,
                name="EPEX import en validatie",
                status="info",
                started_at=now_iso,
                finished_at=now_iso,
                result={"status": "info", "reason": "EPEX workflowcoördinatie is uitgeschakeld."},
            )
            infos.append("EPEX workflowcoördinatie is uitgeschakeld.")
            append_workflow_log(month_key, "info", "Stap afgerond", step="EPEX import en validatie", status="info", duration_seconds=0.0)

        month_result = execute_step(
            "Maandmap bouwen",
            lambda: build_month_input(
                month_key,
                reuse_existing=(not collect_live_snapshots),
            ),
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

        pre_report_validation = execute_step(
            "Eindvalidatie vóór rapportage",
            lambda: validate_pre_report_workflow(
                options,
                month_key,
                historical_mode=(not collect_live_snapshots),
            ),
            required=True,
        )
        if isinstance(pre_report_validation, dict) and pre_report_validation.get("status") == "error":
            failed_step = "Eindvalidatie vóór rapportage"
            raise RuntimeError(
                "Eindvalidatie vóór rapportage bevat fouten: "
                + "; ".join(pre_report_validation.get("errors") or [])
            )

        transfer_result = execute_step(
            "Overdrachtspakket maken",
            lambda: create_transfer_package(month_key, replace_existing=True, send_notification=False),
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
                readiness = report_input_readiness(month_key, options)
                historical_mode = not collect_live_snapshots
                if historical_mode and readiness.get("status") != "ready":
                    now_iso = datetime.now(TZ).isoformat()
                    append_workflow_step(
                        steps,
                        name="Rapportgenerator koppelen",
                        status="skipped",
                        started_at=now_iso,
                        finished_at=now_iso,
                        result={
                            "status": "skipped",
                            "reason": "Historische detailbronnen zijn niet volledig beschikbaar.",
                            "report_input": readiness,
                        },
                    )
                    info = (
                        "Historische maand verwerkt; rapportgeneratie informatief overgeslagen omdat "
                        "historische detailbronnen niet volledig beschikbaar zijn: "
                        + ", ".join(readiness.get("missing") or readiness.get("empty") or [])
                    )
                    infos.append(info)
                    append_workflow_log(
                        month_key,
                        "info",
                        "Historisch rapport informatief overgeslagen",
                        missing=readiness.get("missing", []),
                        empty=readiness.get("empty", []),
                    )
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
    except ImportCancelled as exc:
        status = "cancelled"
        infos.append(f"Workflow gecontroleerd geannuleerd: {exc.reason}")
    except Exception as exc:
        if not errors:
            errors.append(f"{type(exc).__name__}: {exc}")
        state_now = load_state()
        if not state_now.get("full_workflow_last_traceback") or state_now.get("full_workflow_last_error_step") != failed_step:
            record_workflow_failure(
                month_key, step=failed_step or "Workflow", exc=exc,
                duration_seconds=round(time.monotonic() - started_monotonic, 3),
            )
        status = "error"

    finished_at = datetime.now(TZ).isoformat()
    duration_seconds = round(time.monotonic() - started_monotonic, 3)
    result = {
        "version": APP_VERSION,
        "workflow": "full_month_workflow",
        "trigger": trigger,
        "status": status,
        "month": month_key,
        "target_is_current_month": target_is_current_month,
        "live_snapshots_collected": bool(collect_live_snapshots and target_is_current_month),
        "resumed": resume,
        "started_at": started_at,
        "finished_at": finished_at,
        "duration_seconds": duration_seconds,
        "steps_completed": sum(
            1 for step in steps if step.get("status") in {"ok", "info", "warning", "skipped"}
        ),
        "steps_total": len(steps),
        "all_steps_completed": all(
            step.get("status") in {"ok", "info", "warning", "skipped"}
            for step in steps
        ),
        "failed_step": failed_step,
        "infos": infos,
        "warnings": warnings,
        "errors": errors,
        "steps": steps,
    }

    result_root = workflow_result_dir(month_key)
    result_root.mkdir(parents=True, exist_ok=True)
    result_path = result_root / FULL_WORKFLOW_RESULT_NAME
    append_finalization_debug(
        "workflow_result_pre_write",
        month=month_key,
        trigger=trigger,
        status=status,
        steps_total=len(steps),
        steps_completed_field=result.get("steps_completed"),
        steps_accepted_including_skipped=sum(
            1 for step in steps
            if step.get("status") in {"ok", "info", "warning", "skipped"}
        ),
        step_statuses=[
            {"name": step.get("name"), "status": step.get("status")}
            for step in steps
        ],
        failed_step=failed_step,
        errors=errors,
        path=str(result_path),
    )
    write_atomic_json(result_path, result)
    persisted_result = previous_workflow_result(month_key) or {}
    append_finalization_debug(
        "workflow_result_post_write",
        month=month_key,
        exists=result_path.is_file(),
        persisted_status=persisted_result.get("status"),
        persisted_trigger=persisted_result.get("trigger"),
        persisted_steps_completed=persisted_result.get("steps_completed"),
        persisted_steps_total=persisted_result.get("steps_total"),
        persisted_failed_step=persisted_result.get("failed_step"),
        persisted_errors=persisted_result.get("errors"),
        path=str(result_path),
    )

    state_updates = dict(
        full_workflow_last_run=finished_at, full_workflow_last_month=month_key,
        full_workflow_last_status=status, full_workflow_last_step=failed_step or "Gereed",
        full_workflow_last_result=str(result_path),
        full_workflow_last_error=None if status in {"completed", "completed_warning", "cancelled"} else "; ".join(errors),
    )
    if status in {"completed", "completed_warning", "cancelled"}:
        state_updates.update(
            full_workflow_last_error_type=None, full_workflow_last_error_step=None,
            full_workflow_last_error_at=None, full_workflow_last_traceback=None,
        )
    update_state(**state_updates)
    persist_normalized_status(options)

    # v10.1 sidecar: een QNAP-back-up mag de bewezen maandworkflow nooit laten falen.
    # Wanneer de QNAP-share nog niet is gekoppeld wordt dit expliciet als setup_required
    # gerapporteerd, maar de maandworkflow blijft inhoudelijk ongewijzigd.
    if status in {"completed", "completed_warning"}:
        backup_result = create_project_backup(month_key, trigger=trigger)
        update_state(last_project_backup=backup_result)

    try:
        if options.workflow_notify_home_assistant:
            if status in {"completed", "completed_warning"}:
                title = "Automatische energie-maandafsluiting gereed" if trigger == "automatic" else "Energie maandworkflow gereed"
                notify_home_assistant(
                    title,
                    (
                        f"Maand {month_key} is volledig verwerkt in {duration_seconds:.1f} s. "
                        f"Status: {status}. Resultaat: {result_path}"
                    ),
                )
            elif status == "cancelled":
                notify_home_assistant(
                    "Automatische energie-maandafsluiting geannuleerd" if trigger == "automatic" else "Energie maandworkflow geannuleerd",
                    f"Maand {month_key} is gecontroleerd geannuleerd.",
                )
            else:
                notify_home_assistant(
                    "Automatische energie-maandafsluiting mislukt" if trigger == "automatic" else "Energie maandworkflow mislukt",
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

    append_finalization_debug(
        "workflow_close_enter",
        month=month_key,
        status=status,
        failed_step=failed_step,
        duration_seconds=duration_seconds,
    )
    append_workflow_log(month_key, "info" if status in {"completed", "completed_warning", "cancelled"} else "error", "Workflow afgerond", status=status, failed_step=failed_step, duration_seconds=duration_seconds)
    append_finalization_debug("workflow_log_final_written", month=month_key)
    set_workflow_lock_state(
        status="idle",
        month=month_key,
        step=failed_step or "Gereed",
        message=(
            "Volledige maandworkflow is afgerond."
            if status in {"completed", "completed_warning"}
            else ("Volledige maandworkflow is gecontroleerd geannuleerd." if status == "cancelled" else "; ".join(errors))
        ),
    )
    append_finalization_debug(
        "workflow_lock_state_set_idle",
        month=month_key,
        lock_status=load_state().get("workflow_lock_status"),
    )
    if WORKFLOW_LOCK.locked():
        try:
            WORKFLOW_LOCK.release()
            append_finalization_debug("workflow_lock_released", month=month_key, released=True)
        except RuntimeError as exc:
            append_finalization_debug("workflow_lock_release_failed", month=month_key, error=str(exc))
    else:
        append_finalization_debug("workflow_lock_released", month=month_key, released=False, reason="lock_was_not_locked")
    append_finalization_debug(
        "workflow_return",
        month=month_key,
        status=result.get("status"),
        steps_completed=result.get("steps_completed"),
        steps_total=result.get("steps_total"),
    )
    append_audit_event(
        "month_workflow", action="completed", status=str(result.get("status") or "unknown"), month=month_key,
        details={"trigger": trigger, "steps_completed": result.get("steps_completed"), "steps_total": result.get("steps_total"), "failed_step": result.get("failed_step"), "duration_seconds": result.get("duration_seconds")},
    )
    return result




def infrastructure_snapshot() -> dict[str, Any]:
    """Controleer de 24/7 opslagketen zonder brondata te wijzigen."""
    share_root = Path("/share")
    result: dict[str, Any] = {
        "version": APP_VERSION,
        "checked_at": datetime.now(TZ).isoformat(),
        "share_root": str(share_root),
        "nas_share_root": str(NAS_SHARE_ROOT),
        "backup_root": str(PROJECT_BACKUP_ROOT),
        "share_available": share_root.is_dir(),
        "nas_share_available": NAS_SHARE_ROOT.is_dir(),
        "nas_writable": False,
        "backup_ready": False,
        "last_backup": load_state().get("last_project_backup"),
        "message": "",
    }
    if not result["share_available"]:
        result["message"] = "Home Assistant /share is niet beschikbaar."
        result["status"] = "error"
        return result
    if not result["nas_share_available"]:
        result["message"] = (
            "QNAP-share Energie_NAS is nog niet gekoppeld als Home Assistant netwerklocatie type Share."
        )
        result["status"] = "setup_required"
        return result
    try:
        PROJECT_BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
        probe = PROJECT_BACKUP_ROOT / ".energieproject_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        result["nas_writable"] = True
        result["backup_ready"] = True
        result["status"] = "ok"
        result["message"] = "QNAP-opslag is 24/7 bereikbaar en schrijfbaar."
    except OSError as exc:
        result["status"] = "error"
        result["message"] = f"QNAP-opslag is gevonden maar niet schrijfbaar: {exc}"
    return result


def _release_version_from_zip(path: Path) -> str | None:
    """Lees uitsluitend de versie uit een release-ZIP; pak niets uit en schrijf niets."""
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = set(archive.namelist())
            candidates = [name for name in names if name == "VERSIE.txt" or name.endswith("/VERSIE.txt")]
            if not candidates:
                return None
            value = archive.read(sorted(candidates, key=len)[0]).decode("utf-8", errors="replace").strip()
            return value or None
    except (OSError, zipfile.BadZipFile):
        return None


def release_inbox_snapshot() -> dict[str, Any]:
    """Inventariseer en valideer de release-inbox zonder een release te installeren."""
    result: dict[str, Any] = {
        "checked_at": datetime.now(TZ).isoformat(),
        "path": str(NAS_RELEASE_INBOX),
        "available": NAS_RELEASE_INBOX.is_dir(),
        "zip_count": 0,
        "latest": None,
        "releases": [],
        "status": "not_ready",
        "message": "Release-inbox bestaat nog niet.",
    }
    if not NAS_RELEASE_INBOX.is_dir():
        return result
    releases: list[dict[str, Any]] = []
    try:
        zips = sorted(NAS_RELEASE_INBOX.glob("*.zip"), key=lambda item: item.stat().st_mtime, reverse=True)
    except OSError as exc:
        result["status"] = "error"
        result["message"] = f"Release-inbox kon niet worden gelezen: {exc}"
        return result
    for path in zips[:20]:
        item: dict[str, Any] = {
            "name": path.name,
            "bytes": path.stat().st_size,
            "version": _release_version_from_zip(path),
            "zip_valid": False,
        }
        try:
            with zipfile.ZipFile(path, "r") as archive:
                item["zip_valid"] = archive.testzip() is None
        except (OSError, zipfile.BadZipFile):
            item["zip_valid"] = False
        item["candidate_valid"] = bool(item["zip_valid"] and item["version"])
        releases.append(item)
    result["releases"] = releases
    result["zip_count"] = len(zips)
    result["latest"] = releases[0] if releases else None
    if not releases:
        result["status"] = "empty"
        result["message"] = "Release-inbox is beschikbaar en leeg; er hoeft niets verwerkt te worden."
    elif releases[0].get("candidate_valid"):
        result["status"] = "candidate_ready"
        result["message"] = f"Nieuwste ZIP is technisch leesbaar: {releases[0].get('name')}. Release is technisch klaar voor verwerking door de v10.3-installer."
    else:
        result["status"] = "warning"
        result["message"] = "De nieuwste ZIP in de release-inbox is geen geldige EnergieProject-release."
    return result


def nas_migration_snapshot() -> dict[str, Any]:
    """Maak een read-only migratie-inventaris van oud NAS-project naar v10-layout."""
    infra = infrastructure_snapshot()
    legacy = {name: (NAS_SHARE_ROOT / name).is_dir() for name in LEGACY_NAS_DIRECTORIES}
    proposed = {name: path.is_dir() for name, path in NAS_V10_LAYOUT.items()}
    inbox = release_inbox_snapshot()
    found_legacy = [name for name, exists in legacy.items() if exists]
    existing_v10 = [name for name, exists in proposed.items() if exists]
    status = "setup_required"
    message = infra.get("message") or "QNAP-share nog niet beschikbaar."
    if infra.get("status") == "ok":
        if found_legacy and not existing_v10:
            status = "legacy_detected"
            message = "Legacy-structuur gevonden naast de nieuwe projectlocatie; v10.3 gebruikt uitsluitend de nieuwe EnergieProject-root."
        elif found_legacy and existing_v10:
            status = "transition"
            message = "Nieuwe EnergieProject-layout is aanwezig; legacy-mappen worden genegeerd."
        elif existing_v10:
            status = "v10_layout_detected"
            message = "Nieuwe EnergieProject-layout is aanwezig en gereed voor releaseverwerking."
        else:
            status = "share_ready"
            message = "QNAP-share is schrijfbaar; EnergieProject-layout moet nog worden voorbereid."
    return {
        "version": APP_VERSION,
        "checked_at": datetime.now(TZ).isoformat(),
        "status": status,
        "message": message,
        "source_root": str(NAS_SHARE_ROOT),
        "legacy_directories": legacy,
        "legacy_found": found_legacy,
        "proposed_layout": {name: {"path": str(NAS_V10_LAYOUT[name]), "exists": exists} for name, exists in proposed.items()},
        "v10_directories_found": existing_v10,
        "release_inbox": inbox,
        "safety": {
            "read_only_inventory": False,
            "release_processing_supported": True,
            "imac_required": False,
        },
        "next_step": "Plaats een release-ZIP in EnergieProject/Inbox/incoming; de release-installer valideert eerst en houdt rollback beschikbaar.",
    }


def _backup_runtime_paths(month_key: str) -> list[tuple[Path, str]]:
    """Selecteer herstelrelevante runtime-data; options.json/geheimen worden nooit opgenomen."""
    paths: list[tuple[Path, str]] = []
    month_dir = OUTPUT_ROOT / month_key
    if month_dir.is_dir():
        paths.append((month_dir, f"output/{month_key}"))
    workflow_dir = workflow_result_dir(month_key)
    if workflow_dir.is_dir():
        paths.append((workflow_dir, f"output/workflow_results/{month_key}"))
    for src, arcname in [
        (STATE_PATH, "runtime/state.json"),
        (AUTO_CLOSE_UI_OPTIONS_PATH, "runtime/automatic_month_close.json"),
        (PRODUCTION_CERTIFICATE_PATH, "runtime/production_certificate.json"),
        (PRODUCTION_CERTIFICATE_HISTORY_PATH, "runtime/production_certificate_history.jsonl"),
        (AUDIT_TRAIL_PATH, "runtime/audit_trail.jsonl"),
        (RECOVERY_STATE_PATH, "runtime/recovery_state.json"),
        (RECOVERY_HISTORY_PATH, "runtime/recovery_history.jsonl"),
        (MONITORING_STATE_PATH, "runtime/monitoring_state.json"),
        (MONITORING_HISTORY_PATH, "runtime/monitoring_history.jsonl"),
        (AUTOMATIC_RUN_LEDGER_PATH, "runtime/automatic_run_history.jsonl"),
        (AUTOMATIC_COMPLETION_MARKERS_PATH, "runtime/automatic_completed_months.json"),
        (AUTOMATIC_RETRY_STATE_PATH, "runtime/automatic_retry_state.json"),
    ]:
        if src.is_file():
            paths.append((src, arcname))
    return paths


def _write_path_to_archive(archive: zipfile.ZipFile, src: Path, arcname: str) -> None:
    if src.is_file():
        archive.write(src, arcname=arcname)
        return
    if src.is_dir():
        for child in sorted(src.rglob("*")):
            if child.is_file():
                archive.write(child, arcname=str(Path(arcname) / child.relative_to(src)))


def _prune_project_backups() -> list[str]:
    if not PROJECT_BACKUP_ROOT.is_dir():
        return []
    backups = sorted(
        PROJECT_BACKUP_ROOT.glob(f"{PROJECT_BACKUP_PREFIX}_*.zip"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    removed: list[str] = []
    for old in backups[PROJECT_BACKUP_RETENTION:]:
        try:
            old.unlink()
            removed.append(old.name)
        except OSError:
            LOGGER.warning("Oude projectback-up kon niet worden verwijderd: %s", old)
    return removed


def create_project_backup(month_key: str, *, trigger: str) -> dict[str, Any]:
    """Maak na een geslaagde maandworkflow een gecontroleerde QNAP-sidecarback-up."""
    infra = infrastructure_snapshot()
    if not infra.get("backup_ready"):
        result = {
            "status": "skipped",
            "created_at": datetime.now(TZ).isoformat(),
            "month": month_key,
            "trigger": trigger,
            "reason": infra.get("message"),
            "backup_root": str(PROJECT_BACKUP_ROOT),
        }
        update_state(last_project_backup=result)
        return result
    created = datetime.now(TZ)
    filename = f"{PROJECT_BACKUP_PREFIX}_{month_key}_v{APP_VERSION}_{created:%Y%m%dT%H%M%S}.zip"
    target = PROJECT_BACKUP_ROOT / filename
    temp = target.with_suffix(".zip.tmp")
    info = {
        "schema": 1,
        "release_version": APP_VERSION,
        "production_core_revision": PRODUCTION_CORE_REVISION,
        "month": month_key,
        "trigger": trigger,
        "created_at": created.isoformat(),
        "restore_note": "Broncode komt uit GitHub; deze back-up bevat herstelrelevante runtime- en maanddata, nooit options.json/API-sleutels.",
    }
    emergency = build_emergency_recovery_guide().encode("utf-8")
    try:
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("BACKUP_INFO.json", json.dumps(info, ensure_ascii=False, indent=2))
            archive.writestr("NOODHERSTEL.md", emergency)
            for src, arcname in _backup_runtime_paths(month_key):
                _write_path_to_archive(archive, src, arcname)
        temp.replace(target)
        digest = sha256_file(target)
        removed = _prune_project_backups()
        result = {
            "status": "ok",
            "created_at": created.isoformat(),
            "month": month_key,
            "trigger": trigger,
            "path": str(target),
            "bytes": target.stat().st_size,
            "sha256": digest,
            "retention": PROJECT_BACKUP_RETENTION,
            "removed": removed,
        }
        update_state(last_project_backup=result)
        append_workflow_log(month_key, "info", "Projectback-up naar QNAP opgeslagen", path=str(target), sha256=digest)
        return result
    except Exception as exc:
        temp.unlink(missing_ok=True)
        result = {
            "status": "error",
            "created_at": datetime.now(TZ).isoformat(),
            "month": month_key,
            "trigger": trigger,
            "error": str(exc),
            "backup_root": str(PROJECT_BACKUP_ROOT),
        }
        update_state(last_project_backup=result)
        append_workflow_log(month_key, "warning", "Projectback-up naar QNAP mislukt", error=str(exc))
        return result


def build_emergency_recovery_guide() -> str:
    return f"""# Energieproject - noodherstel\n\nVersie: {APP_VERSION}\n\n## Doel\nDeze handleiding is uitsluitend voor een echte crash of vervanging van Home Assistant. Normaal dagelijks beheer gebeurt automatisch.\n\n## Herstel in het kort\n1. Herstel Home Assistant eerst met de normale Home Assistant back-up vanaf de externe QNAP-back-uplocatie.\n2. Voeg daarna de GitHub-repository `https://github.com/kgnfn65498-droid/EnergieProject` toe en installeer SlimmeMeterPortal Import.\n3. Controleer in Home Assistant bij Instellingen > Systeem > Opslag dat de QNAP-share met naam `Energie_NAS` gekoppeld is als type Share.\n4. Start de app en download het diagnosepakket. GO + health 100% betekent dat de operationele keten hersteld is.\n5. Alleen wanneer maanddata ontbreken, gebruik je de nieuwste `EnergieProject_maandbackup_*.zip` uit `EnergieProject/Backups` om de ontbrekende runtime-/maanddata terug te zetten.\n\n## Belangrijk\n- API-sleutels staan bewust niet in projectback-ups. Home Assistant/appconfiguratie hoort via de normale Home Assistant back-up terug te komen.\n- Broncode staat in GitHub; maand- en runtimegegevens staan in de QNAP-sidecarback-ups.\n- Voer geen terminalcommando's uit zolang bovenstaande UI-route beschikbaar is.\n"""


def build_chat_transfer_package() -> bytes:
    """Maak een compacte nieuwe-chat overdracht met afspraken, roadmap en actuele status."""
    options = Options.load()
    op = operation_status(options)
    health = health_dashboard(options)
    infra = infrastructure_snapshot()
    certificate = validate_production_certificate()
    agreements = f"""# Vaste ontwikkelafspraken Energieproject\n\n- Actieve release: {APP_VERSION}; productiekern: {PRODUCTION_CORE_REVISION}.\n- Als de gebruiker zegt `bouw X.Y`, bouw dan daadwerkelijk de volgende complete productieversie op de vorige geteste versie.\n- Lever bij iedere build: ZIP, changelog, kopieerbare committekst en testinstructies onderaan.\n- Wacht na iedere versie op de Home Assistant-testresultaten voordat je verder bouwt.\n- Vermijd herhaalde handmatige teststappen: terugkerende controles automatiseren en in het diagnosepakket opnemen.\n- Normaal testen via één diagnosepakket; screenshots alleen bij visuele of interactieve problemen.\n- De iMac mag weken uitstaan en mag geen noodzakelijke schakel in de productieketen zijn.\n- Productiedata, maandverwerking en back-ups moeten 24/7 via Home Assistant/QNAP kunnen doorlopen.\n- Recovery Manager blijft primair bedoeld voor calamiteiten/crash recovery; noodherstel moet met een korte actuele handleiding kunnen.\n- Bij een trage/volle chat: maak een nieuwe-chat overdracht met status, roadmap, afspraken en open acties.\n- Bespreek grote architectuurkeuzes bij voorkeur in een korte spraaksessie voordat ze worden gebouwd.\n- Einddoel: de gebruiker stelt in gewone taal analysevragen; data-inname, opslag, validatie, back-up en voorbereiding verlopen automatisch.\n- Financiële analyse moet termijnbedrag, werkelijke kosten, historische data, terugverdientijd en marktopties kritisch bewaken; geen ongefundeerde gok.\n- Toekomstige analyse omvat weersverwachting, dynamische energieprijzen en proactieve energiebesparings-/investeringssignalen.\n"""
    roadmap = """# Roadmap vanaf v10.1\n\n## v10.1 - 24/7 infrastructuurfundament\nQNAP-opslagcontrole, automatische maandback-up, noodherstelhandleiding en chat-overdracht.\n\n## v10.2 - Voorspellende context\nWeerdata/verwachting en prijsdata automatisch verzamelen en historiseren.\n\n## v10.3 - Dynamisch dashboard\nEén mobiele dashboardpagina die zelf de relevante inzichten prioriteert.\n\n## v10.4 - Financiële regie\nTermijnbedrag, jaarprognose, werkelijke kosten, bandbreedte/betrouwbaarheid en investeringsscenario's.\n\n## v10.5 - Conversatie-/analysebasis\nGestandaardiseerde analysecontext zodat vragen over kwartalen/jaren direct uit historische data beantwoord kunnen worden.\n\n## v11 - Proactieve energieassistent\nZelf relevante markt-, prijs-, weer- en besparingsontwikkelingen signaleren en onderbouwde acties voorstellen.\n"""
    start = f"""# Start nieuwe chat - Energieproject\n\nLees eerst alle bestanden in dit overdrachtspakket.\n\nActuele softwareversie: {APP_VERSION}\nProductiekern: {PRODUCTION_CORE_REVISION}\nHealthscore: {health.get('score')}\nProductiecertificaat geldig: {bool(certificate.get('valid'))}\nInfrastructuurstatus: {infra.get('status')} - {infra.get('message')}\n\nGa daarna verder vanaf de openstaande roadmap. Vraag niet opnieuw naar afspraken die in PROJECT_AFSPRAKEN.md staan.\n"""
    status = {
        "version": APP_VERSION,
        "production_core_revision": PRODUCTION_CORE_REVISION,
        "generated_at": datetime.now(TZ).isoformat(),
        "operation_status": op,
        "health": health,
        "infrastructure": infra,
        "certificate": certificate,
    }
    entries = {
        "NIEUWE_CHAT_START.md": start.encode("utf-8"),
        "PROJECT_AFSPRAKEN.md": agreements.encode("utf-8"),
        "ROADMAP_V10.md": roadmap.encode("utf-8"),
        "NOODHERSTEL.md": build_emergency_recovery_guide().encode("utf-8"),
        "PROJECT_STATUS.json": json.dumps(status, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
    }
    sha = "\n".join(f"{hashlib.sha256(entries[name]).hexdigest()}  {name}" for name in sorted(entries)) + "\n"
    entries["SHA256SUMS.txt"] = sha.encode("utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            archive.writestr(name, entries[name])
    return buffer.getvalue()

def historical_month_allowed(month_key: str) -> str:
    """Validate and normalize a YYYY_MM month selected by the operator."""
    year, month = parse_month_key(month_key)
    selected = date(year, month, 1)
    current = datetime.now(TZ).date().replace(day=1)
    if selected > current:
        raise ValueError("Een toekomstige maand kan niet worden afgesloten.")
    return f"{year:04d}_{month:02d}"


def read_monitoring_status() -> dict[str, Any]:
    """Lees de laatst vastgelegde monitoringstatus zonder runtime-acties te starten."""
    try:
        if MONITORING_STATE_PATH.is_file():
            data = json.loads(MONITORING_STATE_PATH.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        LOGGER.exception("Monitoringstatus kon niet worden gelezen.")
    return {}


def read_monitoring_history(limit: int = 20) -> list[dict[str, Any]]:
    if not MONITORING_HISTORY_PATH.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        for line in MONITORING_HISTORY_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                rows.append(item)
    except OSError:
        LOGGER.exception("Monitoringhistorie kon niet worden gelezen.")
        return []
    return list(reversed(rows[-max(1, limit):]))


def monitoring_snapshot(options: Options | None = None, *, force: bool = False, trigger: str = "status") -> dict[str, Any]:
    """Productiemonitoring; alleen statuswisselingen worden append-only opgeslagen."""
    options = options or Options.load()
    with MONITORING_LOCK:
        previous = read_monitoring_status()
        if not force and previous.get("checked_at"):
            try:
                checked = datetime.fromisoformat(str(previous.get("checked_at")))
                if checked.tzinfo is None:
                    checked = checked.replace(tzinfo=TZ)
                if (datetime.now(TZ) - checked).total_seconds() < 30:
                    return previous
            except (TypeError, ValueError):
                pass

        state = load_state()
        certificate = validate_production_certificate()
        audit = validate_audit_trail()
        recovery = read_recovery_status()
        checks: list[dict[str, Any]] = []

        def add(name: str, status: str, detail: str) -> None:
            checks.append({"name": name, "status": status, "detail": detail})

        api_ok = (state.get("api_test") or {}).get("status") == "ok"
        add("API", "ok" if api_ok else "warning", "verbonden" if api_ok else "API-test niet ok")

        last_status = str(state.get("full_workflow_last_status") or "")
        workflow_ok = last_status in {"completed", "completed_warning", "running"}
        add("Workflow", "ok" if workflow_ok else "warning", last_status or "nog geen run")

        cert_current = str(certificate.get("production_core_revision") or "") == PRODUCTION_CORE_REVISION
        cert_integrity_ok = certificate.get("integrity") in {"ok", "not_checked"}
        cert_status = "ok" if certificate.get("valid") else ("pending" if cert_integrity_ok and not cert_current else "warning")
        cert_detail = (
            "geldig" if certificate.get("valid")
            else (f"productiekern {PRODUCTION_CORE_REVISION} nog niet gecertificeerd" if cert_integrity_ok and not cert_current else str(certificate.get("status") or "ongeldig"))
        )
        add("Productiecertificaat", cert_status, cert_detail)
        add("Audittrail", "ok" if audit.get("valid") else "warning", str(audit.get("status") or "unknown"))

        recovery_status = str(recovery.get("status") or "unknown")
        add("Recovery", "ok" if recovery_status == "ok" else "warning", recovery_status)

        if options.automatic_month_close_enabled:
            scheduler_ok = bool(certificate.get("valid"))
            add("Scheduler", "ok" if scheduler_ok else "pending",
                "actief" if scheduler_ok else f"wacht op certificaat productiekern {PRODUCTION_CORE_REVISION}")
        else:
            add("Scheduler", "ok", "uitgeschakeld")

        source_values = list((state.get("workflow_sources") or {}).values())
        sources_ok = bool(source_values) and all(str(v).lower() in {"ready", "ok", "completed"} for v in source_values)
        add("Bronnen", "ok" if sources_ok else "warning", ", ".join(map(str, source_values)) or "nog onbekend")

        active = [item for item in checks if item["status"] != "ok"]
        errors = [item for item in active if item["status"] == "warning"]
        pending_points = [item for item in active if item["status"] in {"pending", "attention"}]
        overall = "warning" if errors else ("pending" if pending_points else "ok")
        fingerprint = hashlib.sha256(json.dumps(
            [(item["name"], item["status"], item["detail"]) for item in checks],
            ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")).hexdigest()
        now = datetime.now(TZ).isoformat()
        result = {
            "version": APP_VERSION,
            "checked_at": now,
            "trigger": trigger,
            "status": overall,
            "active_alerts": len(active),
            "active_errors": len(errors),
            "pending_points": len(pending_points),
            "attention_points": len(pending_points),  # compatibiliteit met v9.1-statusclients
            "checks": checks,
            "fingerprint": fingerprint,
            "history_path": str(MONITORING_HISTORY_PATH),
        }
        MONITORING_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        write_atomic_json(MONITORING_STATE_PATH, result)

        if str(previous.get("fingerprint") or "") != fingerprint:
            record = {"recorded_at": now, **result}
            with MONITORING_HISTORY_PATH.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, separators=(",", ":"), default=str) + "\n")
            try:
                if validate_audit_trail().get("valid"):
                    append_audit_event(
                        "monitoring", action="status_changed", status=("info" if overall == "pending" else overall),
                        details={
                            "active_alerts": len(active),
                            "active_errors": len(errors),
                            "pending_points": len(pending_points),
                            "attention_points": len(pending_points),
                            "checks": checks,
                            "trigger": trigger,
                            "lifecycle_status": overall,
                        },
                    )
            except Exception as exc:
                LOGGER.warning("Monitoringstatus kon niet aan audittrail worden toegevoegd: %s", exc)
        return result


def health_dashboard(options: Options | None = None) -> dict[str, Any]:
    options = options or Options.load()
    state = load_state()
    checks: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str, *, status_if_not_ok: str = "warning") -> None:
        checks.append({"name": name, "status": "ok" if ok else status_if_not_ok, "detail": detail})

    add("SlimmeMeterPortal", (state.get("api_test") or {}).get("status") == "ok", "API-verbinding")
    add("Rapportgeneratoren", BUNDLED_REPORT_GENERATORS.is_dir(), "Officiële generatoren aanwezig")
    add("Outputopslag", OUTPUT_ROOT.exists() or OUTPUT_ROOT.parent.exists(), str(OUTPUT_ROOT))
    workflow_running = WORKFLOW_LOCK.locked() and str(state.get("workflow_lock_status") or "") == "running"
    add(
        "Workflow-lock",
        (not WORKFLOW_LOCK.locked()) or workflow_running,
        "actieve verwerking" if workflow_running else ("vrij" if not WORKFLOW_LOCK.locked() else "onverwacht bezet"),
    )
    last_status = state.get("full_workflow_last_status")
    add(
        "Laatste workflow",
        last_status in {"running", "completed", "completed_warning"},
        str(last_status or "nog geen run"),
    )
    source_values = list((state.get("workflow_sources") or {}).values())
    add("Bronstatus", bool(source_values) and all(str(v).lower() in {"ready", "ok", "completed"} for v in source_values), ", ".join(map(str, source_values)) or "nog onbekend")

    certificate_validation = validate_production_certificate()
    certificate_current = str(certificate_validation.get("production_core_revision") or "") == PRODUCTION_CORE_REVISION
    certificate_integrity = str(certificate_validation.get("integrity") or "not_checked")
    certificate_gate_expected = (not certificate_validation.get("valid")) and certificate_integrity in {"ok", "not_checked"} and not certificate_current
    add(
        "Productiecertificaat", bool(certificate_validation.get("valid")),
        "geldig" if certificate_validation.get("valid") else f"productiekern {PRODUCTION_CORE_REVISION} nog niet gecertificeerd",
        status_if_not_ok="pending" if certificate_gate_expected else "warning",
    )
    add("Certificaatintegriteit", certificate_integrity in {"ok", "not_checked"}, certificate_integrity)
    add(
        "Certificaatversie", certificate_current,
        (
            f"kern {certificate_validation.get('production_core_revision') or 'geen'} · doel {PRODUCTION_CORE_REVISION}"
            + (f" · afgegeven met v{certificate_validation.get('version')}" if certificate_validation.get('version') else "")
        ),
        status_if_not_ok="pending" if certificate_gate_expected else "warning",
    )
    audit_validation = validate_audit_trail()
    add("Audittrail", bool(audit_validation.get("valid")), f"{audit_validation.get('records', 0)} record(s)")
    add("Auditintegriteit", bool(audit_validation.get("valid")), str(audit_validation.get("status") or "unknown"))
    monitoring = monitoring_snapshot(options)
    monitoring_errors = int(monitoring.get("active_errors") or 0)
    monitoring_pending = int(monitoring.get("pending_points") if monitoring.get("pending_points") is not None else (monitoring.get("attention_points") or 0))
    monitoring_ok = monitoring_errors == 0 and monitoring_pending == 0
    monitoring_detail = f"{monitoring_errors} fout(en) · {monitoring_pending} wachtstatus(sen)"
    add(
        "Monitoring", monitoring_ok, monitoring_detail,
        status_if_not_ok="pending" if monitoring_errors == 0 else "warning",
    )

    weights = {"ok": 1.0, "pending": 0.9, "attention": 0.8, "warning": 0.0}
    score = round((sum(weights.get(c["status"], 0.0) for c in checks) / len(checks)) * 100) if checks else 0
    return {
        "version": APP_VERSION,
        "generated_at": datetime.now(TZ).isoformat(),
        "score": score,
        "status": "ok" if score == 100 else ("pending" if score >= 90 else "warning"),
        "checks": checks,
    }



def visual_step_counts_from_result(result: dict[str, Any]) -> tuple[int, int]:
    """Normaliseer workflowhistorie naar de v7.4 visuele fasen."""
    phase_names = {name for name, _weight, _seconds in WORKFLOW_VISUAL_PHASES}
    completed = 0
    seen: set[str] = set()
    for step in result.get("steps") or []:
        name = str(step.get("name") or "")
        if name in phase_names and name not in seen and step.get("status") in {"ok", "info", "warning", "skipped"}:
            seen.add(name)
            completed += 1
    # Report handoff is intentionally not a separate visual phase.
    return completed, WORKFLOW_VISUAL_TOTAL_STEPS


def workflow_visualization(state: dict[str, Any], log_lines: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a stable, weighted UX progress model without changing workflow execution."""
    status = str(state.get("workflow_lock_status") or "idle").lower()
    last_status = str(state.get("full_workflow_last_status") or "").lower()
    phase_names = [name for name, _weight, _seconds in WORKFLOW_VISUAL_PHASES]
    weights = {name: weight for name, weight, _seconds in WORKFLOW_VISUAL_PHASES}
    expected = {name: seconds for name, _weight, seconds in WORKFLOW_VISUAL_PHASES}

    # Alleen de regels van de meest recente run gebruiken.
    start_index = 0
    for idx, line in enumerate(log_lines):
        if line.get("message") in {"Workflow gestart", "Workflow hervat"}:
            start_index = idx
    recent = log_lines[start_index:]

    completed: set[str] = set()
    active_step = str(state.get("workflow_lock_step") or "")
    active_started_at: datetime | None = None
    detail = str(state.get("progress_message") or "")
    for line in recent:
        step = str(line.get("step") or "")
        if line.get("message") == "Stap afgerond" and step in weights:
            completed.add(step)
        if line.get("message") == "Stap gestart" and step in weights:
            active_step = step
            try:
                active_started_at = datetime.fromisoformat(str(line.get("timestamp")))
            except (TypeError, ValueError):
                active_started_at = None
        if line.get("message") == "Heartbeat" and step == active_step:
            detail = str(line.get("heartbeat_message") or detail)

    if status != "running":
        if last_status in {"completed", "completed_warning"}:
            return {
                "percent": 100.0, "step_index": WORKFLOW_VISUAL_TOTAL_STEPS,
                "steps_total": WORKFLOW_VISUAL_TOTAL_STEPS, "step": "Gereed",
                "detail": "Workflow voltooid", "elapsed_seconds": state.get("workflow_lock_last_duration_seconds"),
                "eta_seconds": 0, "running": False,
            }
        return {
            "percent": 0.0, "step_index": 0, "steps_total": WORKFLOW_VISUAL_TOTAL_STEPS,
            "step": "Geen actieve workflow", "detail": "Klaar om te starten",
            "elapsed_seconds": None, "eta_seconds": None, "running": False,
        }

    completed_weight = sum(weights[name] for name in completed)
    if active_step not in weights:
        # Initialiseren: toon bewust 0% in plaats van de vorige run.
        return {
            "percent": 0.0, "step_index": 0, "steps_total": WORKFLOW_VISUAL_TOTAL_STEPS,
            "step": active_step or "Initialiseren", "detail": detail or "Workflow gestart",
            "elapsed_seconds": 0, "eta_seconds": round(sum(x[2] for x in WORKFLOW_VISUAL_PHASES), 1),
            "running": True,
        }

    phase_index = phase_names.index(active_step)
    phase_weight = weights[active_step]
    phase_fraction = 0.08
    elapsed_phase = 0.0
    if active_step == "SlimmeMeterPortal maandimport":
        cur = int(state.get("progress_current") or 0)
        total = int(state.get("progress_total") or 0)
        if total > 0:
            phase_fraction = min(0.95, max(0.08, cur / total))
    elif active_started_at is not None:
        now = datetime.now(TZ)
        if active_started_at.tzinfo is None:
            active_started_at = active_started_at.replace(tzinfo=TZ)
        elapsed_phase = max(0.0, (now - active_started_at).total_seconds())
        phase_fraction = min(0.92, max(0.08, elapsed_phase / max(expected[active_step], 0.1)))

    percent = min(99.0, completed_weight + phase_weight * phase_fraction)
    remaining = max(0.0, expected[active_step] - elapsed_phase)
    for name in phase_names[phase_index + 1:]:
        if name not in completed:
            remaining += expected[name]
    return {
        "percent": round(percent, 1),
        "step_index": phase_index + 1,
        "steps_total": WORKFLOW_VISUAL_TOTAL_STEPS,
        "step": active_step,
        "detail": detail or active_step,
        "elapsed_seconds": round(elapsed_phase, 1),
        "eta_seconds": round(remaining, 1),
        "running": True,
    }


def finalize_proven_retry_state(
    state: dict[str, Any],
    retry: dict[str, Any],
    *,
    month: str,
    evidence: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Sluit een aantoonbaar afgeronde productie-retry definitief af."""
    closed = write_automatic_retry_state(
        state="COMPLETED",
        month=month,
        reason=None,
        origin=str(retry.get("origin") or "automatic"),
        next_retry=None,
        evidence=evidence,
    )
    update_state(
        automatic_month_close_next_retry=None,
        automatic_month_close_retry_month=None,
        automatic_month_close_retry_reason=None,
        automatic_month_close_retry_origin=None,
    )
    refreshed = load_state()
    append_retry_debug(
        "retry_finalized",
        month=month,
        resulting_state=closed.get("state"),
        evidence=evidence,
    )
    return refreshed, closed


def reconcile_automatic_retry_state(state: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    state, retry = migrate_legacy_retry_state(state)
    retry_state = str(retry.get("state") or "")
    month = str(retry.get("month") or "")
    append_retry_debug(
        "reconcile_enter",
        retry_state=retry_state,
        month=month,
        reason=retry.get("reason"),
        evidence=retry.get("evidence"),
    )

    if retry_state in {"OPEN", "RUNNING"} and month:
        ledger_proof = automatic_history_proves_completed(month)
        workflow_proof = workflow_history_proves_completed(month)
        marker = automatic_month_is_completed(month)
        append_retry_debug(
            "reconcile_evidence",
            month=month,
            ledger_proof=bool(ledger_proof),
            workflow_proof=bool(workflow_proof),
            workflow_debug=workflow_history_debug(month),
            completion_marker=marker,
        )
        if ledger_proof or workflow_proof or marker:
            if ledger_proof:
                evidence = "Geslaagde echte Automatisch-run aangetroffen in append-only historie."
            elif workflow_proof:
                evidence = "Historisch workflow_result bewijst een volledig geslaagde automatische run."
            else:
                evidence = "Duurzame completion-marker aangetroffen."
            state, retry = finalize_proven_retry_state(
                state, retry, month=month, evidence=evidence
            )
            append_retry_debug(
                "reconcile_closed",
                month=month,
                resulting_state=retry.get("state"),
                evidence=retry.get("evidence"),
            )
    append_retry_debug(
        "reconcile_result",
        month=month,
        resulting_state=retry.get("state"),
        reason=retry.get("reason"),
        evidence=retry.get("evidence"),
        next_retry=retry.get("next_retry"),
    )
    return state, retry


def append_recovery_history(result: dict[str, Any]) -> None:
    RECOVERY_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with RECOVERY_HISTORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, default=str) + "\n")


def run_recovery_controller(*, trigger: str = "manual") -> dict[str, Any]:
    """Conservatieve v8.17-herstelcontrole op duurzame productiestatus.

    Herstelt alleen afleidbare status uit bestaand hard bewijs. Er wordt nooit
    automatisch een maandworkflow gestart en een ongeldige auditketen wordt
    nooit overschreven.
    """
    checked_at = datetime.now(TZ).isoformat()
    repairs: list[dict[str, Any]] = []
    warnings: list[str] = []
    state = load_state()

    # Een procesherstart kan een persistente 'running'-status achterlaten terwijl
    # de in-memory lock per definitie vrij is. Alleen die administratieve status
    # mag veilig worden genormaliseerd.
    if str(state.get("workflow_lock_status") or "").lower() == "running" and not WORKFLOW_LOCK.locked():
        previous = {
            "month": state.get("workflow_lock_month"),
            "step": state.get("workflow_lock_step"),
            "started_at": state.get("workflow_lock_started_at"),
        }
        update_state(
            workflow_lock_status="idle",
            workflow_lock_started_at=None,
            workflow_lock_month=None,
            workflow_lock_step=None,
            workflow_lock_message="Recovery v8.17 normaliseerde achtergebleven workflowstatus na herstart.",
            workflow_lock_last_released=checked_at,
        )
        repairs.append({"type": "workflow_lock_state", "action": "normalized", "before": previous})
        state = load_state()

    # Retry-state wordt uitsluitend gesloten als de bestaande append-only historie,
    # workflow_result of completion-marker hard bewijs levert.
    retry_before = read_automatic_retry_state()
    retry_before_state = str(retry_before.get("state") or "")
    state, retry_after = reconcile_automatic_retry_state(state)
    retry_after_state = str(retry_after.get("state") or "")
    if retry_before_state != retry_after_state:
        repairs.append({
            "type": "automatic_retry",
            "action": "reconciled",
            "before": retry_before_state,
            "after": retry_after_state,
            "month": retry_after.get("month") or retry_before.get("month"),
            "evidence": retry_after.get("evidence"),
        })

    # Productiecertificaat mag alleen uit een geslaagde productietest van exact
    # deze versie worden hersteld.
    certificate_before = validate_production_certificate()
    certificate_after = certificate_before
    if not certificate_before.get("valid"):
        try:
            managed = manage_production_certificate(allow_repair=True)
            certificate_after = validate_production_certificate()
            if managed.get("repaired") and certificate_after.get("valid"):
                repairs.append({
                    "type": "production_certificate",
                    "action": "repaired",
                    "certificate_id": managed.get("certificate_id"),
                    "source_test_month": managed.get("source_test_month"),
                })
        except Exception as exc:
            warnings.append("Productiecertificaat niet automatisch hersteld: " + str(exc))

    audit = validate_audit_trail()
    if not audit.get("valid"):
        warnings.append("Audittrail-integriteit vereist handmatige controle; recovery wijzigt de audittrail niet.")

    status = "ok" if not warnings else "attention"
    result = {
        "version": APP_VERSION,
        "checked_at": checked_at,
        "trigger": trigger,
        "status": status,
        "repairs": repairs,
        "repair_count": len(repairs),
        "warnings": warnings,
        "retry_state": retry_after,
        "certificate": certificate_after,
        "audit": audit,
        "workflow_lock_active": WORKFLOW_LOCK.locked(),
    }
    write_atomic_json(RECOVERY_STATE_PATH, result)
    append_recovery_history(result)
    update_state(recovery_last_result=result)
    if audit.get("valid"):
        try:
            append_audit_event(
                "recovery_controller",
                action="repaired" if repairs else "validated",
                status=status,
                details={"trigger": trigger, "repair_count": len(repairs), "repairs": repairs, "warnings": warnings},
            )
        except Exception as exc:
            LOGGER.warning("Recovery-auditrecord kon niet worden toegevoegd: %s", exc)
    return result


def read_recovery_status() -> dict[str, Any]:
    state = load_state()
    result = state.get("recovery_last_result") or {}
    if not isinstance(result, dict):
        result = {}
    return {
        "status": result.get("status") or "not_checked",
        "checked_at": result.get("checked_at"),
        "trigger": result.get("trigger"),
        "repair_count": int(result.get("repair_count") or 0),
        "repairs": result.get("repairs") or [],
        "warnings": result.get("warnings") or [],
        "state_path": str(RECOVERY_STATE_PATH),
        "history_path": str(RECOVERY_HISTORY_PATH),
    }


def automatic_recovery_status(
    state: dict[str, Any],
    options: Options,
    retry: dict[str, Any] | None = None,
) -> dict[str, Any]:
    retry = retry or read_automatic_retry_state()
    retry_state = str(retry.get("state") or "")
    month = str(retry.get("month") or "")
    next_retry = retry.get("next_retry")
    reason = str(retry.get("reason") or "")
    evidence = str(retry.get("evidence") or "")

    if retry_state == "OPEN":
        return {
            "status": "retry_scheduled" if next_retry else "attention",
            "label": "Retry gepland" if next_retry else "Herstel vereist",
            "detail": (
                f"{month or 'Onbekende maand'} wordt opnieuw geprobeerd op {format_local_datetime(next_retry)}. Reden: {reason or 'onbekend'}."
                if next_retry
                else f"{month or 'Onbekende maand'} heeft een open productie-retry. Reden: {reason or 'onbekend'}."
            ),
            "next_retry": next_retry,
            "retry_required": True,
            "retry_state": retry_state,
        }
    if retry_state == "RUNNING":
        return {
            "status": "running",
            "label": "Herstel loopt",
            "detail": f"Automatische herstelpoging voor {month or 'onbekende maand'} wordt uitgevoerd.",
            "next_retry": None,
            "retry_required": True,
            "retry_state": retry_state,
        }
    if retry_state == "COMPLETED":
        return {
            "status": "ready",
            "label": "Geen herstelactie nodig",
            "detail": evidence or "Er staat geen openstaande productie-retry.",
            "next_retry": None,
            "retry_required": False,
            "retry_state": retry_state,
        }
    if retry_state == "CANCELLED":
        return {
            "status": "ready",
            "label": "Retry geannuleerd",
            "detail": evidence or "De retry is gecontroleerd afgesloten.",
            "next_retry": None,
            "retry_required": False,
            "retry_state": retry_state,
        }
    if retry_state == "EXPIRED":
        return {
            "status": "attention",
            "label": "Retry verlopen",
            "detail": evidence or "De retry is verlopen en vereist controle.",
            "next_retry": None,
            "retry_required": True,
            "retry_state": retry_state,
        }
    return {
        "status": "ready",
        "label": "Geen herstelactie nodig",
        "detail": "Er staat geen openstaande productie-retry.",
        "next_retry": None,
        "retry_required": False,
        "retry_state": "COMPLETED",
    }


def operation_status(options: Options | None = None) -> dict[str, Any]:
    """Return one compact operational view without changing workflow state."""
    options = options or Options.load()
    state = persist_normalized_status(options)
    state, retry_state_machine = reconcile_automatic_retry_state(state)
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
                        "version": result.get("version"),
                        "status": result.get("status", "unknown"),
                        "trigger": result.get("trigger", "manual"),
                        "finished_at": result.get("finished_at"),
                        "duration_seconds": result.get("duration_seconds"),
                        "failed_step": result.get("failed_step"),
                        "steps_completed": visual_step_counts_from_result(result)[0],
                        "steps_total": visual_step_counts_from_result(result)[1],
                    })
                except (OSError, json.JSONDecodeError) as exc:
                    item.update({"status": "unreadable", "error": str(exc)})
            history.append(item)
    live_log = workflow_log_tail(
        str(state.get("workflow_lock_month") or state.get("full_workflow_last_month") or ""),
        limit=80,
    )
    visual = workflow_visualization(state, live_log)
    ledger_history = read_automatic_run_history(limit=12)
    if ledger_history:
        automatic_history = [{
            "month": item.get("month"),
            "version": item.get("version"),
            "trigger": None,
            "run_type": item.get("type") or "Automatisch",
            "status": item.get("status"),
            "finalization_status": item.get("finalization_status"),
            "finished_at": item.get("finished_at") or item.get("recorded_at"),
            "duration_seconds": item.get("duration_seconds"),
            "scheduler_enabled_unchanged": item.get("scheduler_enabled_unchanged"),
        } for item in ledger_history[:6]]
        automatic_history_source = "append_only_ledger"
    else:
        acceptance = state.get("automatic_scheduler_acceptance_last_result") or {}
        acceptance_execution = acceptance.get("execution") or {}
        acceptance_workflow = acceptance_execution.get("workflow") or {}
        acceptance_finished_at = acceptance_workflow.get("finished_at")
        product_test = state.get("automatic_month_close_test_last_result") or {}
        product_test_workflow = product_test.get("workflow") or {}
        product_test_finished_at = product_test_workflow.get("finished_at")
        last_finalization = state.get("automatic_month_close_last_finalization") or {}

        automatic_history: list[dict[str, Any]] = []
        for item in history:
            if item.get("trigger") not in {"automatic", "automatic_test"}:
                continue
            run_type = "Automatisch"
            finalization_status: str | None = None
            if (
                item.get("trigger") == "automatic"
                and acceptance_finished_at
                and item.get("finished_at") == acceptance_finished_at
                and item.get("month") == acceptance.get("month")
            ):
                run_type = "Scheduler-test"
                finalization_status = str(
                    (acceptance_execution.get("finalization") or {}).get("status") or ""
                ) or None
            elif (
                item.get("trigger") == "automatic_test"
                and product_test_finished_at
                and item.get("finished_at") == product_test_finished_at
                and item.get("month") == product_test.get("month")
            ):
                run_type = "Test"
                finalization_status = str(
                    (product_test.get("finalization") or {}).get("status") or ""
                ) or None
            elif (
                item.get("trigger") == "automatic"
                and item.get("month") == last_finalization.get("month")
            ):
                finalization_status = str(last_finalization.get("status") or "") or None

            automatic_history.append({
                "month": item.get("month"),
                "version": item.get("version"),
                "trigger": item.get("trigger"),
                "run_type": run_type,
                "status": item.get("status"),
                "finalization_status": finalization_status,
                "finished_at": item.get("finished_at"),
                "duration_seconds": item.get("duration_seconds"),
            })
        automatic_history = automatic_history[:6]
        automatic_history_source = "legacy_workflow_results"
    return {
        "version": APP_VERSION,
        "generated_at": datetime.now(TZ).isoformat(),
        "infrastructure": infrastructure_snapshot(),
        "nas_migration": nas_migration_snapshot(),
        "workflow": {
            "status": state.get("workflow_lock_status"),
            "month": state.get("workflow_lock_month"),
            "step": state.get("workflow_lock_step"),
            "message": state.get("workflow_lock_message"),
        },
        "last_run": {
            "month": state.get("full_workflow_last_month"),
            "trigger": state.get("full_workflow_last_trigger") or "manual",
            "status": state.get("full_workflow_last_status"),
            "step": state.get("full_workflow_last_step"),
            "error": state.get("full_workflow_last_error"),
            "error_type": state.get("full_workflow_last_error_type"),
            "error_step": state.get("full_workflow_last_error_step"),
            "error_at": state.get("full_workflow_last_error_at"),
            "traceback": state.get("full_workflow_last_traceback"),
        },
        "live_log": live_log,
        "visual_progress": visual,
        "automatic_month_close": {
            "enabled": options.automatic_month_close_enabled,
            "day": options.automatic_month_close_day,
            "hour": options.automatic_month_close_hour,
            "retry_hours": options.automatic_month_close_retry_hours,
            "last_month": state.get("automatic_month_close_last_month"),
            "last_status": state.get("automatic_month_close_last_status"),
            "last_run": state.get("automatic_month_close_last_run"),
            "last_attempt": state.get("automatic_month_close_last_attempt"),
            "next_retry": state.get("automatic_month_close_next_retry"),
            "last_preflight": state.get("automatic_month_close_last_preflight"),
            "last_finalization": state.get("automatic_month_close_last_finalization"),
            "test_last_result": state.get("automatic_month_close_test_last_result"),
            "scheduler_acceptance_last_result": state.get("automatic_scheduler_acceptance_last_result"),
            "production_readiness": automatic_production_readiness(state),
            "scheduler_effective": bool(
                options.automatic_month_close_enabled
                and automatic_production_readiness(state).get("ready")
            ),
            "next_scheduled_run": (
                next_automatic_month_close_run(options)
                if automatic_production_readiness(state).get("ready")
                else None
            ),
            "history": automatic_history,
            "history_source": automatic_history_source,
            "history_path": str(AUTOMATIC_RUN_LEDGER_PATH),
            "completion_markers_path": str(AUTOMATIC_COMPLETION_MARKERS_PATH),
            "completed_months": sorted(read_automatic_completion_markers().keys(), reverse=True),
            "idempotency_protection": "active",
            "recovery": automatic_recovery_status(state, options, retry_state_machine),
            "retry_state_machine": retry_state_machine,
            "retry_state_path": str(AUTOMATIC_RETRY_STATE_PATH),
            "retry_debug": retry_debug_snapshot(state),
            "finalization_debug": finalization_debug_tail(limit=20),
            "finalization_debug_log_path": str(FINALIZATION_DEBUG_LOG_PATH),
            "production_certificate": validate_production_certificate(),
            "production_certificate_history": read_production_certificate_history(limit=10),
            "production_certificate_management": state.get("production_certificate_management") or {},
        },
        "audit_trail": {"validation": validate_audit_trail(), "events": read_audit_trail(limit=12), "path": str(AUDIT_TRAIL_PATH)},
        "recovery_controller": read_recovery_status(),
        "monitoring": monitoring_snapshot(options),
        "history": history,
        "can_resume": bool(
            state.get("full_workflow_last_month")
            and state.get("full_workflow_last_status") not in {"completed", "completed_warning"}
        ),
        "health": health_dashboard(options),
        "queue": {
            "active": WORKFLOW_LOCK.locked(),
            "rejected_count": state.get("workflow_lock_rejected_count") or 0,
        },
    }



def audit_event_payload_hash(event: dict[str, Any]) -> str:
    """SHA-256 over één auditrecord zonder het eigen hashveld."""
    canonical = {key: value for key, value in event.items() if key != "integrity_sha256"}
    raw = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_audit_trail() -> dict[str, Any]:
    """Valideer hashes en de volledige hashketen van de append-only audittrail."""
    if not AUDIT_TRAIL_PATH.is_file():
        return {"status": "empty", "valid": True, "records": 0, "last_event_id": None, "last_hash": None, "checked_at": datetime.now(TZ).isoformat(), "path": str(AUDIT_TRAIL_PATH), "errors": []}
    errors: list[str] = []
    previous_hash: str | None = None
    records = 0
    last_event_id: str | None = None
    last_hash: str | None = None
    for line_number, line in enumerate(AUDIT_TRAIL_PATH.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"regel {line_number}: onleesbaar ({exc})")
            continue
        if not isinstance(event, dict):
            errors.append(f"regel {line_number}: geen object")
            continue
        records += 1
        stored = str(event.get("integrity_sha256") or "")
        calculated = audit_event_payload_hash(event)
        if not stored or stored != calculated:
            errors.append(f"regel {line_number}: hash ongeldig")
        if event.get("previous_hash") != previous_hash:
            errors.append(f"regel {line_number}: hashketen onderbroken")
        previous_hash = stored or calculated
        last_hash = stored or None
        last_event_id = str(event.get("event_id") or "") or None
    return {"status": "ok" if not errors else "invalid", "valid": not errors, "records": records, "last_event_id": last_event_id, "last_hash": last_hash, "checked_at": datetime.now(TZ).isoformat(), "path": str(AUDIT_TRAIL_PATH), "errors": errors}


def read_audit_trail(limit: int = 50) -> list[dict[str, Any]]:
    if not AUDIT_TRAIL_PATH.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(AUDIT_TRAIL_PATH.read_text(encoding="utf-8", errors="replace").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            rows.append({"line": line_number, "status": "unreadable", "integrity": "error", "error": str(exc)})
            continue
        if isinstance(item, dict):
            item = dict(item)
            item["line"] = line_number
            rows.append(item)
    return rows[-max(1, min(int(limit), 500)):][::-1]


def append_audit_event(event_type: str, *, status: str = "ok", month: str | None = None, action: str | None = None, details: dict[str, Any] | None = None) -> dict[str, Any]:
    """Voeg een hash-gekoppeld record toe; schrijven stopt als bestaande integriteit niet klopt."""
    AUDIT_TRAIL_PATH.parent.mkdir(parents=True, exist_ok=True)
    with AUDIT_LOCK:
        before = validate_audit_trail()
        if not before.get("valid"):
            raise RuntimeError("Audittrail-integriteit is ongeldig; nieuw auditrecord geblokkeerd: " + "; ".join(before.get("errors") or []))
        now = datetime.now(TZ)
        event = {
            "schema": 1,
            "event_id": f"{APP_VERSION}-{now.strftime('%Y%m%dT%H%M%S%f%z')}",
            "recorded_at": now.isoformat(),
            "version": APP_VERSION,
            "event_type": str(event_type),
            "action": action,
            "status": str(status),
            "month": month,
            "details": details or {},
            "previous_hash": before.get("last_hash"),
        }
        event["integrity_sha256"] = audit_event_payload_hash(event)
        with AUDIT_TRAIL_PATH.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, default=str) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        after = validate_audit_trail()
        if not after.get("valid"):
            raise RuntimeError("Audittrail faalde directe integriteitscontrole na schrijven.")
        update_state(audit_trail_last_event=event, audit_trail_last_checked=after.get("checked_at"), audit_trail_last_status=after.get("status"))
        return event


def production_certificate_payload_hash(certificate: dict[str, Any]) -> str:
    """SHA-256 over de certificaatinhoud zonder het hashveld zelf."""
    canonical = {
        key: value
        for key, value in certificate.items()
        if key not in {"integrity_sha256", "validated_at"}
    }
    raw = json.dumps(
        canonical,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def read_production_certificate() -> dict[str, Any]:
    if not PRODUCTION_CERTIFICATE_PATH.is_file():
        return {}
    try:
        value = json.loads(PRODUCTION_CERTIFICATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def validate_production_certificate(
    certificate: dict[str, Any] | None = None,
) -> dict[str, Any]:
    certificate = certificate if certificate is not None else read_production_certificate()
    exists = PRODUCTION_CERTIFICATE_PATH.is_file()
    if not certificate:
        return {
            "status": "missing",
            "valid": False,
            "exists": exists,
            "version": None,
            "accepted_at": None,
            "reason": "Productiecertificaat ontbreekt.",
            "path": str(PRODUCTION_CERTIFICATE_PATH),
            "history_path": str(PRODUCTION_CERTIFICATE_HISTORY_PATH),
            "integrity": "not_checked",
            "checks": {},
            "certificate": None,
        }

    stored_hash = str(certificate.get("integrity_sha256") or "")
    calculated_hash = production_certificate_payload_hash(certificate)
    certificate_core_revision = str(certificate.get("production_core_revision") or "")
    checks = {
        "status_accepted": str(certificate.get("status") or "") == "accepted",
        "core_revision_current": certificate_core_revision == PRODUCTION_CORE_REVISION,
        "scheduler_unchanged": certificate.get("scheduler_state_unchanged") is True,
        "preflight_ok": str(certificate.get("preflight_status") or "") == "ok",
        "workflow_ok": str(certificate.get("workflow_status") or "") in {"completed", "completed_warning"},
        "finalization_ok": str(certificate.get("finalization_status") or "") == "ok",
        "integrity_ok": bool(stored_hash) and stored_hash == calculated_hash,
    }
    valid = all(checks.values())
    failed = [name for name, ok in checks.items() if not ok]
    return {
        "status": "valid" if valid else "invalid",
        "valid": valid,
        "exists": exists,
        "version": certificate.get("version"),
        "production_core_revision": certificate.get("production_core_revision"),
        "release_version_current": str(certificate.get("version") or "") == APP_VERSION,
        "accepted_at": certificate.get("accepted_at"),
        "month": certificate.get("month"),
        "reason": None if valid else "Afgekeurd: " + ", ".join(failed),
        "path": str(PRODUCTION_CERTIFICATE_PATH),
        "history_path": str(PRODUCTION_CERTIFICATE_HISTORY_PATH),
        "integrity": "ok" if checks["integrity_ok"] else "error",
        "integrity_sha256": stored_hash or None,
        "checks": checks,
        "certificate": certificate,
    }


def append_production_certificate_history(certificate: dict[str, Any]) -> None:
    row = {
        "recorded_at": datetime.now(TZ).isoformat(),
        "certificate_id": certificate.get("certificate_id"),
        "version": certificate.get("version"),
        "production_core_revision": certificate.get("production_core_revision"),
        "status": certificate.get("status"),
        "accepted_at": certificate.get("accepted_at"),
        "month": certificate.get("month"),
        "issued_by": certificate.get("issued_by"),
        "integrity_sha256": certificate.get("integrity_sha256"),
    }
    PRODUCTION_CERTIFICATE_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    with PRODUCTION_CERTIFICATE_HISTORY_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def read_production_certificate_history(limit: int = 10) -> list[dict[str, Any]]:
    if not PRODUCTION_CERTIFICATE_HISTORY_PATH.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in PRODUCTION_CERTIFICATE_HISTORY_PATH.read_text(
        encoding="utf-8", errors="replace"
    ).splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows[-max(1, min(limit, 100)):][::-1]


def write_production_acceptance(test_result: dict[str, Any]) -> dict[str, Any]:
    """Schrijf na een geslaagde productietest een persistent certificaat."""
    workflow = test_result.get("workflow") or {}
    preflight = test_result.get("preflight") or {}
    finalization = test_result.get("finalization") or {}
    valid = bool(
        str(test_result.get("production_core_revision") or "") == PRODUCTION_CORE_REVISION
        and str(test_result.get("status") or "") in {"completed", "completed_warning"}
        and str(preflight.get("status") or "") == "ok"
        and str(workflow.get("status") or "") in {"completed", "completed_warning"}
        and str(finalization.get("status") or "") == "ok"
        and test_result.get("scheduler_state_changed") is False
    )
    certificate = {
        "schema": 3,
        "certificate_id": f"{APP_VERSION}-{datetime.now(TZ).strftime('%Y%m%dT%H%M%S%z')}",
        "version": APP_VERSION,
        "production_core_revision": PRODUCTION_CORE_REVISION,
        "status": "accepted" if valid else "rejected",
        "accepted_at": datetime.now(TZ).isoformat() if valid else None,
        "month": test_result.get("month"),
        "test_type": "production",
        "tested_at": test_result.get("tested_at"),
        "test_status": test_result.get("status"),
        "preflight_status": preflight.get("status"),
        "workflow_status": workflow.get("status"),
        "finalization_status": finalization.get("status"),
        "scheduler_state_unchanged": test_result.get("scheduler_state_changed") is False,
        "issued_by": "automatic_production_test",
        "evidence": {
            "test_version": test_result.get("version"),
            "production_core_revision": test_result.get("production_core_revision"),
            "test_month": test_result.get("month"),
            "test_status": test_result.get("status"),
        },
    }
    certificate["integrity_sha256"] = production_certificate_payload_hash(certificate)

    PRODUCTION_CERTIFICATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = PRODUCTION_CERTIFICATE_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(certificate, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(PRODUCTION_CERTIFICATE_PATH)
    append_production_certificate_history(certificate)
    append_audit_event(
        "production_certificate", action="issued" if valid else "rejected", status="ok" if valid else "rejected",
        month=str(test_result.get("month") or "") or None,
        details={"certificate_id": certificate.get("certificate_id"), "production_core_revision": PRODUCTION_CORE_REVISION, "test_status": test_result.get("status"), "issued_by": certificate.get("issued_by")},
    )
    update_state(production_acceptance=certificate)

    validation = validate_production_certificate(certificate)
    if valid and not validation.get("valid"):
        raise RuntimeError(
            "Productiecertificaat faalde directe validatie: "
            + str(validation.get("reason") or "onbekend")
        )
    return certificate


def manage_production_certificate(*, allow_repair: bool = True) -> dict[str, Any]:
    """Controleer het certificaat en herstel uitsluitend uit hard testbewijs van dezelfde productiekern."""
    before = validate_production_certificate()
    action = "validated"
    repaired = False
    source_test: dict[str, Any] | None = None
    if allow_repair and not before.get("valid"):
        candidate = load_state().get("automatic_month_close_test_last_result") or {}
        source_test = candidate if isinstance(candidate, dict) else {}
        candidate_valid = bool(
            str(source_test.get("production_core_revision") or "") == PRODUCTION_CORE_REVISION
            and str(source_test.get("status") or "") in {"completed", "completed_warning"}
            and str((source_test.get("preflight") or {}).get("status") or "") == "ok"
            and str((source_test.get("workflow") or {}).get("status") or "") in {"completed", "completed_warning"}
            and str((source_test.get("finalization") or {}).get("status") or "") == "ok"
            and source_test.get("scheduler_state_changed") is False
        )
        if candidate_valid:
            write_production_acceptance(source_test)
            repaired = True
            action = "generated_from_compatible_core_test"
        else:
            action = "test_required"
    after = validate_production_certificate()
    result = {
        "version": APP_VERSION,
        "production_core_revision": PRODUCTION_CORE_REVISION,
        "checked_at": datetime.now(TZ).isoformat(),
        "action": action,
        "repaired": repaired,
        "valid": bool(after.get("valid")),
        "status": after.get("status"),
        "reason": after.get("reason"),
        "certificate_id": (after.get("certificate") or {}).get("certificate_id"),
        "certificate_path": str(PRODUCTION_CERTIFICATE_PATH),
        "history_path": str(PRODUCTION_CERTIFICATE_HISTORY_PATH),
        "source_test_month": source_test.get("month") if source_test else None,
    }
    write_atomic_json(PRODUCTION_CERTIFICATE_MANAGEMENT_PATH, result)
    update_state(production_certificate_management=result)
    return result


def automatic_production_readiness(state: dict[str, Any] | None = None) -> dict[str, Any]:
    """Een geldig certificaat van de actuele productiekern geeft productie vrij.

    Daardoor hoeft een release die uitsluitend UI/diagnostiek/documentatie wijzigt niet
    opnieuw de echte maandafsluitingsroute te certificeren.
    """
    manage_production_certificate(allow_repair=True)
    validation = validate_production_certificate()
    certificate = validation.get("certificate") or {}
    return {
        "version": APP_VERSION,
        "production_core_revision": PRODUCTION_CORE_REVISION,
        "ready": bool(validation.get("valid")),
        "status": "accepted" if validation.get("valid") else "test_required",
        "tested_version": certificate.get("version"),
        "tested_at": certificate.get("tested_at"),
        "accepted_at": certificate.get("accepted_at"),
        "month": certificate.get("month"),
        "reason": validation.get("reason"),
        "certificate": certificate or None,
        "certificate_validation": validation,
    }


def format_local_datetime(value: Any) -> str:
    """Toon een ISO-datum compact in lokale Nederlandse productieweergave."""
    if not value:
        return "Niet gepland"
    try:
        dt = datetime.fromisoformat(str(value))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ)
        dt = dt.astimezone(TZ)
        return dt.strftime("%d-%m-%Y %H:%M")
    except (TypeError, ValueError):
        return str(value)


def next_automatic_month_close_run(options: Options, now: datetime | None = None) -> str | None:
    """Bereken de eerstvolgende geplande automatische maandafsluiting."""
    if not options.automatic_month_close_enabled:
        return None
    now = now or datetime.now(TZ)
    candidate = now.replace(
        day=options.automatic_month_close_day,
        hour=options.automatic_month_close_hour,
        minute=0,
        second=0,
        microsecond=0,
    )
    if candidate <= now:
        year = candidate.year + (1 if candidate.month == 12 else 0)
        month = 1 if candidate.month == 12 else candidate.month + 1
        candidate = candidate.replace(year=year, month=month, day=options.automatic_month_close_day)
    return candidate.isoformat()


def set_automatic_month_close_enabled(enabled: bool) -> dict[str, Any]:
    """Bewaar alleen Aan/Uit direct; behoud dag, uur en retry exact."""
    options = Options.load()
    return save_automatic_month_close_settings(
        enabled=bool(enabled),
        day=options.automatic_month_close_day,
        hour=options.automatic_month_close_hour,
        retry_hours=options.automatic_month_close_retry_hours,
    )


def save_automatic_month_close_settings(*, enabled: bool, day: int, hour: int, retry_hours: int) -> dict[str, Any]:
    """Bewaar UI-instellingen; inschakelen vereist een actuele productietest."""
    previous_options = Options.load()
    previous_settings = {
        "enabled": bool(previous_options.automatic_month_close_enabled),
        "day": int(previous_options.automatic_month_close_day),
        "hour": int(previous_options.automatic_month_close_hour),
        "retry_hours": int(previous_options.automatic_month_close_retry_hours),
    }
    if enabled and not automatic_production_readiness().get("ready"):
        raise ValueError(
            "Automatische maandafsluiting kan pas AAN na certificering van productiekern "
            + PRODUCTION_CORE_REVISION
            + "."
        )
    if not 1 <= day <= 28:
        raise ValueError("Dag moet 1 t/m 28 zijn.")
    if not 0 <= hour <= 23:
        raise ValueError("Uur moet 0 t/m 23 zijn.")
    if not 1 <= retry_hours <= 48:
        raise ValueError("Retry moet 1 t/m 48 uur zijn.")
    payload = {
        "version": APP_VERSION,
        "saved_at": datetime.now(TZ).isoformat(),
        "automatic_month_close_enabled": bool(enabled),
        "automatic_month_close_day": int(day),
        "automatic_month_close_hour": int(hour),
        "automatic_month_close_retry_hours": int(retry_hours),
    }
    AUTO_CLOSE_UI_OPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = AUTO_CLOSE_UI_OPTIONS_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(AUTO_CLOSE_UI_OPTIONS_PATH)
    current_settings = {"enabled": bool(enabled), "day": int(day), "hour": int(hour), "retry_hours": int(retry_hours)}
    if current_settings != previous_settings:
        append_audit_event("scheduler_settings", action="changed", status="ok", details={"before": previous_settings, "after": current_settings})
    return payload


def run_automatic_month_close_test(month_key: str) -> dict[str, Any]:
    """Voer de automatische keten uit zonder enige wijziging aan de planning."""
    month_key = historical_month_allowed(month_key)
    scheduler_config_before = (
        AUTO_CLOSE_UI_OPTIONS_PATH.read_bytes()
        if AUTO_CLOSE_UI_OPTIONS_PATH.exists()
        else None
    )
    if WORKFLOW_LOCK.locked():
        raise RuntimeError("Er draait al een maandworkflow.")
    options = Options.load()
    preflight = automatic_month_close_preflight(options, month_key)
    if preflight.get("status") != "ok":
        previous_test = (load_state().get("automatic_month_close_test_last_result") or {})
        result = {
            "version": APP_VERSION,
            "production_core_revision": PRODUCTION_CORE_REVISION,
            "started_at": previous_test.get("started_at"),
            "tested_at": datetime.now(TZ).isoformat(),
            "month": month_key,
            "status": "blocked",
            "preflight": preflight,
            "workflow": None,
            "finalization": None,
            "error": "Preflight blokkeerde de productietest.",
            "scheduler_state_changed": False,
        }
        scheduler_config_after = (
            AUTO_CLOSE_UI_OPTIONS_PATH.read_bytes()
            if AUTO_CLOSE_UI_OPTIONS_PATH.exists()
            else None
        )
        if scheduler_config_after != scheduler_config_before:
            if scheduler_config_before is None:
                AUTO_CLOSE_UI_OPTIONS_PATH.unlink(missing_ok=True)
            else:
                AUTO_CLOSE_UI_OPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
                tmp_restore = AUTO_CLOSE_UI_OPTIONS_PATH.with_suffix(".restore.tmp")
                tmp_restore.write_bytes(scheduler_config_before)
                tmp_restore.replace(AUTO_CLOSE_UI_OPTIONS_PATH)
            result["scheduler_state_changed"] = True
            result["error"] = "Preflight/test wijzigde schedulerinstellingen; oorspronkelijke planning is hersteld."
        update_state(automatic_month_close_test_last_result=result)
        append_automatic_run_history({
            "type": "Test", "month": month_key, "status": result.get("status"),
            "finalization_status": None, "started_at": result.get("started_at"),
            "finished_at": result.get("tested_at"), "duration_seconds": None,
            "scheduler_enabled_before": None, "scheduler_enabled_after": None,
            "scheduler_enabled_unchanged": True,
        })
        append_audit_event("production_test", action="completed", status=str(result.get("status") or "blocked"), month=month_key, details={"preflight": (result.get("preflight") or {}).get("status"), "error": result.get("error")})
        return result

    current_key = datetime.now(TZ).strftime("%Y_%m")
    workflow = run_full_month_workflow(
        month_key,
        collect_live_snapshots=(month_key == current_key),
        trigger="automatic_test",
    )
    finalization = automatic_month_close_finalize(options, month_key, workflow)
    status = str(workflow.get("status") or "error")
    if status in {"completed", "completed_warning"} and finalization.get("status") != "ok":
        status = "error"
    previous_test = (load_state().get("automatic_month_close_test_last_result") or {})
    result = {
        "version": APP_VERSION,
        "production_core_revision": PRODUCTION_CORE_REVISION,
        "started_at": previous_test.get("started_at"),
        "tested_at": datetime.now(TZ).isoformat(),
        "month": month_key,
        "status": status,
        "preflight": preflight,
        "workflow": workflow,
        "finalization": finalization,
        "error": None if status in {"completed", "completed_warning"} else "Productieketen niet volledig gereed.",
        "scheduler_state_changed": False,
    }
    scheduler_config_after = (
        AUTO_CLOSE_UI_OPTIONS_PATH.read_bytes()
        if AUTO_CLOSE_UI_OPTIONS_PATH.exists()
        else None
    )
    if scheduler_config_after != scheduler_config_before:
        # Productietest mag de productieplanning nooit wijzigen.
        if scheduler_config_before is None:
            AUTO_CLOSE_UI_OPTIONS_PATH.unlink(missing_ok=True)
        else:
            AUTO_CLOSE_UI_OPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp_restore = AUTO_CLOSE_UI_OPTIONS_PATH.with_suffix(".restore.tmp")
            tmp_restore.write_bytes(scheduler_config_before)
            tmp_restore.replace(AUTO_CLOSE_UI_OPTIONS_PATH)
        result["status"] = "error"
        result["error"] = "Productietest probeerde schedulerinstellingen te wijzigen; oorspronkelijke planning is hersteld."
        result["scheduler_state_changed"] = True
    else:
        result["scheduler_state_changed"] = False

    update_state(automatic_month_close_test_last_result=result)
    if (
        str(result.get("status") or "") in {"completed", "completed_warning"}
        and str((result.get("preflight") or {}).get("status") or "") == "ok"
        and str((result.get("workflow") or {}).get("status") or "") in {"completed", "completed_warning"}
        and str((result.get("finalization") or {}).get("status") or "") == "ok"
        and result.get("scheduler_state_changed") is False
    ):
        result["production_acceptance"] = write_production_acceptance(result)
        update_state(automatic_month_close_test_last_result=result)
    append_automatic_run_history({
        "type": "Test", "month": month_key, "status": result.get("status"),
        "finalization_status": (result.get("finalization") or {}).get("status"),
        "started_at": result.get("started_at"), "finished_at": result.get("tested_at"),
        "duration_seconds": (result.get("workflow") or {}).get("duration_seconds"),
        "scheduler_enabled_before": None, "scheduler_enabled_after": None,
        "scheduler_enabled_unchanged": True,
    })
    append_audit_event(
        "production_test", action="completed", status=str(result.get("status") or "unknown"), month=month_key,
        details={"preflight": (result.get("preflight") or {}).get("status"), "workflow": (result.get("workflow") or {}).get("status"), "finalization": (result.get("finalization") or {}).get("status"), "scheduler_state_changed": result.get("scheduler_state_changed")},
    )
    return result


def automatic_month_close_preflight(options: Options, month_key: str) -> dict[str, Any]:
    """Controleer of een onbemande maandafsluiting veilig kan starten."""
    errors: list[str] = []
    checks: list[dict[str, Any]] = []
    def add(name: str, status: str, detail: str = "") -> None:
        checks.append({"name": name, "status": status, "detail": detail})
        if status == "error": errors.append(f"{name}: {detail}")
    add("config", "ok", "Configuratie geldig.")
    try:
        OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
        probe = OUTPUT_ROOT / ".automatic_close_write_test"
        probe.write_text("ok", encoding="utf-8"); probe.unlink(missing_ok=True)
        add("storage", "ok", str(OUTPUT_ROOT))
    except Exception as exc: add("storage", "error", str(exc))
    if options.transfer_enabled:
        try:
            transfer_root = TRANSFER_SHARE_ROOT / Path(options.transfer_share_folder)
            transfer_root.mkdir(parents=True, exist_ok=True)
            probe = transfer_root / ".automatic_close_write_test"
            probe.write_text("ok", encoding="utf-8"); probe.unlink(missing_ok=True)
            add("transfer_storage", "ok", str(transfer_root))
        except Exception as exc: add("transfer_storage", "error", str(exc))
    else: add("transfer_storage", "ok", "Overdracht bewust uitgeschakeld.")
    if options.report_service_enabled:
        runtime = check_report_runtime()
        add("report_runtime", "ok" if runtime.get("status") == "ok" else "error", json.dumps(runtime, ensure_ascii=False))
    else: add("report_runtime", "ok", "Rapportservice bewust uitgeschakeld.")
    result={"version":APP_VERSION,"checked_at":datetime.now(TZ).isoformat(),"month":month_key,"status":"ok" if not errors else "error","checks":checks,"errors":errors}
    update_state(automatic_month_close_last_preflight=result)
    return result


def automatic_month_close_finalize(options: Options, month_key: str, workflow_result: dict[str, Any]) -> dict[str, Any]:
    """Controleer of de volledige automatische productieketen gereed is."""
    errors: list[str] = []; checks: list[dict[str, Any]] = []; state=load_state()
    def add(name: str, status: str, detail: Any = "") -> None:
        checks.append({"name":name,"status":status,"detail":detail})
        if status == "error": errors.append(f"{name}: {detail}")
    ws=str(workflow_result.get("status") or "")
    add("workflow", "ok" if ws in {"completed","completed_warning"} else "error", ws or "onbekend")
    pre=state.get("last_pre_report_validation") or {}
    pre_ok=str(pre.get("month") or "")==month_key and pre.get("status")=="ok"
    add("pre_report_validation","ok" if pre_ok else "error",pre.get("status") or "ontbreekt")
    if options.report_service_enabled:
        gen_ok=state.get("report_generation_last_month")==month_key and state.get("report_generation_last_status")=="completed"
        add("report_generation","ok" if gen_ok else "error",state.get("report_generation_last_status") or "ontbreekt")
        published=list(state.get("report_output_last_files") or [])
        expected={f"Energierapport_{month_key}.pdf",f"Recovery_Update_{month_key}.zip"}
        names={Path(x).name for x in published}
        files_exist=all(Path(x).is_file() for x in published)
        pub_ok=(
            state.get("report_output_last_month")==month_key
            and state.get("report_output_last_status")=="completed"
            and names==expected
            and len(published)==2
            and files_exist
        )
        add("publication","ok" if pub_ok else "error",{"status":state.get("report_output_last_status"),"files":published,"expected":sorted(expected)})

        pdf_path = next((Path(x) for x in published if Path(x).name == f"Energierapport_{month_key}.pdf"), None)
        pdf_ok = bool(pdf_path and pdf_path.is_file() and pdf_path.stat().st_size > 4 and pdf_path.read_bytes()[:4] == b"%PDF")
        add("report_pdf_integrity", "ok" if pdf_ok else "error", str(pdf_path or "ontbreekt"))

        recovery_path = next((Path(x) for x in published if Path(x).name == f"Recovery_Update_{month_key}.zip"), None)
        recovery_ok = False
        recovery_detail: Any = str(recovery_path or "ontbreekt")
        if recovery_path and recovery_path.is_file():
            try:
                with zipfile.ZipFile(recovery_path) as recovery_zip:
                    bad_member = recovery_zip.testzip()
                    recovery_ok = bad_member is None and bool(recovery_zip.namelist())
                    recovery_detail = {
                        "path": str(recovery_path),
                        "files": len(recovery_zip.namelist()),
                        "bad_member": bad_member,
                    }
            except Exception as exc:
                recovery_detail = str(exc)
        add("recovery_zip_integrity", "ok" if recovery_ok else "error", recovery_detail)
    else:
        add("report_generation","ok","Rapportservice bewust uitgeschakeld."); add("publication","ok","Rapportservice bewust uitgeschakeld.")
    result={"version":APP_VERSION,"checked_at":datetime.now(TZ).isoformat(),"month":month_key,"status":"ok" if not errors else "error","checks":checks,"errors":errors}
    update_state(automatic_month_close_last_finalization=result)
    return result

def execute_automatic_month_close(
    options: Options,
    month_key: str,
    *,
    trigger: str = "automatic",
    record_as_real_automatic: bool = True,
) -> dict[str, Any]:
    """Gedeelde productie-executor voor scheduler en acceptatietest."""
    attempt_at = datetime.now(TZ)
    if record_as_real_automatic:
        write_automatic_retry_state(
            state="RUNNING",
            month=month_key,
            reason="scheduled_or_retry_execution",
            origin="automatic",
            next_retry=None,
            evidence="Echte automatische maandafsluiting gestart.",
        )
    update_state(
        automatic_month_close_last_month=month_key,
        automatic_month_close_last_status="preflight",
        automatic_month_close_last_attempt=attempt_at.isoformat(),
        automatic_month_close_last_run=attempt_at.isoformat(),
        automatic_month_close_next_retry=None,
        automatic_month_close_retry_month=None,
        automatic_month_close_retry_reason=None,
        automatic_month_close_retry_origin=None,
    )
    preflight = automatic_month_close_preflight(options, month_key)
    if preflight.get("status") != "ok":
        retry_at = (datetime.now(TZ) + timedelta(hours=options.automatic_month_close_retry_hours)).isoformat()
        update_state(
            automatic_month_close_last_month=month_key,
            automatic_month_close_last_status="blocked",
            automatic_month_close_last_run=datetime.now(TZ).isoformat(),
            automatic_month_close_next_retry=retry_at,
            automatic_month_close_retry_month=month_key,
            automatic_month_close_retry_reason="preflight_blocked",
            automatic_month_close_retry_origin="automatic" if record_as_real_automatic else "scheduler_test",
        )
        result = {"month": month_key, "status": "blocked", "preflight": preflight, "workflow": None, "finalization": None, "retry_at": retry_at}
        if record_as_real_automatic:
            write_automatic_retry_state(
                state="OPEN",
                month=month_key,
                reason="preflight_blocked",
                origin="automatic",
                next_retry=retry_at,
                evidence="Preflight blokkeerde de echte automatische maandafsluiting.",
            )
            options_after = Options.load()
            append_automatic_run_history({
                "type": "Automatisch", "month": month_key, "status": "blocked",
                "finalization_status": None, "started_at": attempt_at.isoformat(),
                "finished_at": datetime.now(TZ).isoformat(), "duration_seconds": None,
                "scheduler_enabled_before": bool(options.automatic_month_close_enabled),
                "scheduler_enabled_after": bool(options_after.automatic_month_close_enabled),
                "scheduler_enabled_unchanged": (
                    bool(options_after.automatic_month_close_enabled)
                    == bool(options.automatic_month_close_enabled)
                ),
            })
        return result

    update_state(automatic_month_close_last_status="running")
    append_finalization_debug(
        "automatic_executor_workflow_start",
        month=month_key,
        trigger=trigger,
        record_as_real_automatic=record_as_real_automatic,
    )
    workflow = run_full_month_workflow(month_key, collect_live_snapshots=False, trigger=trigger)
    append_finalization_debug(
        "automatic_executor_workflow_returned",
        month=month_key,
        workflow_status=workflow.get("status"),
        workflow_steps_completed=workflow.get("steps_completed"),
        workflow_steps_total=workflow.get("steps_total"),
        workflow_failed_step=workflow.get("failed_step"),
        workflow_errors=workflow.get("errors"),
    )
    finalization = automatic_month_close_finalize(options, month_key, workflow)
    append_finalization_debug(
        "automatic_executor_finalization_returned",
        month=month_key,
        finalization_status=finalization.get("status"),
        finalization_errors=finalization.get("errors"),
        finalization_checks=finalization.get("checks"),
    )
    final_status = str(workflow.get("status") or "error")
    if final_status in {"completed", "completed_warning"} and finalization.get("status") != "ok":
        final_status = "error"
    retry_at = None
    if final_status not in {"completed", "completed_warning"}:
        retry_at = (datetime.now(TZ) + timedelta(hours=options.automatic_month_close_retry_hours)).isoformat()
    retry_needed = final_status not in {"completed", "completed_warning"}
    update_state(
        automatic_month_close_last_month=month_key,
        automatic_month_close_last_status=final_status,
        automatic_month_close_last_run=datetime.now(TZ).isoformat(),
        automatic_month_close_next_retry=retry_at if retry_needed else None,
        automatic_month_close_retry_month=month_key if retry_needed else None,
        automatic_month_close_retry_reason="workflow_or_finalization_failed" if retry_needed else None,
        automatic_month_close_retry_origin=(
            ("automatic" if record_as_real_automatic else "scheduler_test")
            if retry_needed else None
        ),
    )
    result = {"month": month_key, "status": final_status, "preflight": preflight, "workflow": workflow, "finalization": finalization, "retry_at": retry_at}
    if record_as_real_automatic:
        append_finalization_debug(
            "production_finalize_enter",
            month=month_key,
            final_status=final_status,
            retry_needed=retry_needed,
            finalization_status=finalization.get("status"),
        )
        write_automatic_retry_state(
            state="COMPLETED" if not retry_needed else "OPEN",
            month=month_key,
            reason=None if not retry_needed else "workflow_or_finalization_failed",
            origin="automatic",
            next_retry=None if not retry_needed else retry_at,
            evidence=(
                "Echte automatische maandafsluiting en finalization volledig geslaagd."
                if not retry_needed
                else "Automatische maandafsluiting vereist een nieuwe herstelpoging."
            ),
        )
        append_finalization_debug(
            "retry_state_written",
            month=month_key,
            retry_state=read_automatic_retry_state(),
        )
        options_after = Options.load()
        if final_status in {"completed", "completed_warning"} and finalization.get("status") == "ok":
            append_finalization_debug("completion_marker_write_start", month=month_key)
            marker_result = mark_automatic_month_completed(
                month_key,
                status=final_status,
                finalization_status="ok",
                finished_at=workflow.get("finished_at"),
            )
            append_finalization_debug(
                "completion_marker_write_done",
                month=month_key,
                marker=marker_result,
                marker_file_exists=AUTOMATIC_COMPLETION_MARKERS_PATH.is_file(),
                marker_proves_completed=automatic_month_is_completed(month_key),
            )
        else:
            append_finalization_debug(
                "completion_marker_skipped",
                month=month_key,
                final_status=final_status,
                finalization_status=finalization.get("status"),
            )
        append_finalization_debug("automatic_history_write_start", month=month_key)
        history_row = append_automatic_run_history({
            "type": "Automatisch", "month": month_key, "status": final_status,
            "finalization_status": finalization.get("status"),
            "started_at": workflow.get("started_at"), "finished_at": workflow.get("finished_at"),
            "duration_seconds": workflow.get("duration_seconds"),
            "scheduler_enabled_before": bool(options.automatic_month_close_enabled),
            "scheduler_enabled_after": bool(options_after.automatic_month_close_enabled),
            "scheduler_enabled_unchanged": (
                bool(options_after.automatic_month_close_enabled)
                == bool(options.automatic_month_close_enabled)
            ),
        })
        append_finalization_debug(
            "automatic_history_write_done",
            month=month_key,
            row=history_row,
            ledger_file_exists=AUTOMATIC_RUN_LEDGER_PATH.is_file(),
            history_proves_completed=bool(automatic_history_proves_completed(month_key)),
        )
        append_finalization_debug(
            "production_finalize_done",
            month=month_key,
            completion_marker=automatic_month_is_completed(month_key),
            retry_state=read_automatic_retry_state(),
        )
    append_finalization_debug(
        "automatic_executor_return",
        month=month_key,
        status=result.get("status"),
        record_as_real_automatic=record_as_real_automatic,
    )
    return result


def automatic_scheduler_acceptance_test() -> dict[str, Any]:
    """Simuleer de eerstvolgende geplande run via exact de productie-schedulerroute."""
    if WORKFLOW_LOCK.locked():
        raise RuntimeError("Er draait al een maandworkflow.")
    options = Options.load()
    prerequisite_product_test: dict[str, Any] | None = None
    if not automatic_production_readiness().get("ready"):
        # v8.5.1: de acceptatietest is zelfstandig bruikbaar na een upgrade.
        # Eerst wordt exact dezelfde veilige productietest uitgevoerd; alleen bij
        # succes mag de echte schedulerroute worden gesimuleerd.
        prerequisite_month = datetime.now(TZ).strftime("%Y_%m")
        prerequisite_product_test = run_automatic_month_close_test(prerequisite_month)
        if str(prerequisite_product_test.get("status") or "") not in {
            "completed",
            "completed_warning",
        } or not automatic_production_readiness().get("ready"):
            detail = prerequisite_product_test.get("error") or "onbekende fout"
            raise RuntimeError(
                "Automatische voorbereidende productietest voor "
                + APP_VERSION
                + " is mislukt: "
                + str(detail)
            )
        # De productietest mag de planning niet wijzigen. Herlaad daarom pas nu
        # de scheduleropties die de simulatie daadwerkelijk gaat gebruiken.
        options = Options.load()

    if not options.automatic_month_close_enabled:
        raise RuntimeError("Zet automatische maandafsluiting eerst AAN.")

    now = datetime.now(TZ)
    simulated_at = now.replace(
        day=options.automatic_month_close_day,
        hour=options.automatic_month_close_hour,
        minute=0, second=0, microsecond=0,
    )
    if simulated_at <= now:
        year = simulated_at.year + (1 if simulated_at.month == 12 else 0)
        month = 1 if simulated_at.month == 12 else simulated_at.month + 1
        simulated_at = simulated_at.replace(year=year, month=month, day=options.automatic_month_close_day)

    month_key = automatic_month_close_due(options, simulated_at)
    if not month_key:
        raise RuntimeError("De gesimuleerde scheduler vond geen verschuldigde maand.")

    scheduler_enabled_before = bool(options.automatic_month_close_enabled)
    scheduler_keys = (
        "automatic_month_close_last_month",
        "automatic_month_close_last_status",
        "automatic_month_close_last_attempt",
        "automatic_month_close_last_run",
        "automatic_month_close_next_retry",
        "automatic_month_close_retry_month",
        "automatic_month_close_retry_reason",
        "automatic_month_close_retry_origin",
    )
    before = load_state()
    scheduler_before = {key: before.get(key) for key in scheduler_keys}
    config_before = AUTO_CLOSE_UI_OPTIONS_PATH.read_bytes() if AUTO_CLOSE_UI_OPTIONS_PATH.exists() else None
    started_at = datetime.now(TZ)

    try:
        execution = execute_automatic_month_close(
            options,
            month_key,
            trigger="automatic",
            record_as_real_automatic=False,
        )
        result = {
            "version": APP_VERSION,
            "production_core_revision": PRODUCTION_CORE_REVISION,
            "started_at": started_at.isoformat(),
            "tested_at": datetime.now(TZ).isoformat(),
            "simulated_at": simulated_at.isoformat(),
            "month": month_key,
            "status": execution.get("status"),
            "execution": execution,
            "prerequisite_product_test": prerequisite_product_test,
            "prerequisite_product_test_ran": prerequisite_product_test is not None,
            "scheduler_bookkeeping_restored": False,
            "scheduler_config_unchanged": None,
            "scheduler_enabled_before": scheduler_enabled_before,
            "scheduler_enabled_after": None,
            "scheduler_enabled_unchanged": None,
            "error": None,
        }
    except Exception as exc:
        result = {
            "version": APP_VERSION,
            "production_core_revision": PRODUCTION_CORE_REVISION,
            "started_at": started_at.isoformat(),
            "tested_at": datetime.now(TZ).isoformat(),
            "simulated_at": simulated_at.isoformat(),
            "month": month_key,
            "status": "error",
            "execution": None,
            "prerequisite_product_test": prerequisite_product_test,
            "prerequisite_product_test_ran": prerequisite_product_test is not None,
            "scheduler_bookkeeping_restored": False,
            "scheduler_config_unchanged": None,
            "scheduler_enabled_before": scheduler_enabled_before,
            "scheduler_enabled_after": None,
            "scheduler_enabled_unchanged": None,
            "error": str(exc),
        }
    finally:
        update_state(**scheduler_before)
        config_after = AUTO_CLOSE_UI_OPTIONS_PATH.read_bytes() if AUTO_CLOSE_UI_OPTIONS_PATH.exists() else None
        if config_after != config_before:
            if config_before is None:
                AUTO_CLOSE_UI_OPTIONS_PATH.unlink(missing_ok=True)
            else:
                AUTO_CLOSE_UI_OPTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
                tmp = AUTO_CLOSE_UI_OPTIONS_PATH.with_suffix(".acceptance.restore.tmp")
                tmp.write_bytes(config_before)
                tmp.replace(AUTO_CLOSE_UI_OPTIONS_PATH)
            config_after = config_before

    result["scheduler_bookkeeping_restored"] = True
    result["scheduler_config_unchanged"] = config_after == config_before
    options_after = Options.load()
    result["scheduler_enabled_after"] = bool(options_after.automatic_month_close_enabled)
    result["scheduler_enabled_unchanged"] = (
        result["scheduler_enabled_after"] == result["scheduler_enabled_before"]
    )
    if not result["scheduler_enabled_unchanged"]:
        result["status"] = "error"
        result["error"] = "Scheduler Aan/Uit is tijdens de acceptatietest gewijzigd."
    execution = result.get("execution") or {}
    finalization = execution.get("finalization") or {}
    if result.get("status") in {"completed", "completed_warning"} and finalization.get("status") != "ok":
        result["status"] = "error"
        result["error"] = "Finalization van gesimuleerde scheduler-run is niet OK."
    update_state(automatic_scheduler_acceptance_last_result=result)
    execution = result.get("execution") or {}
    workflow_result = execution.get("workflow") or {}
    finalization_result = execution.get("finalization") or {}
    append_automatic_run_history({
        "type": "Scheduler-test", "month": result.get("month"),
        "status": result.get("status"),
        "finalization_status": finalization_result.get("status"),
        "started_at": result.get("started_at"), "finished_at": result.get("tested_at"),
        "duration_seconds": workflow_result.get("duration_seconds"),
        "scheduler_enabled_before": result.get("scheduler_enabled_before"),
        "scheduler_enabled_after": result.get("scheduler_enabled_after"),
        "scheduler_enabled_unchanged": result.get("scheduler_enabled_unchanged"),
        "simulated_at": result.get("simulated_at"),
        "scheduler_bookkeeping_restored": result.get("scheduler_bookkeeping_restored"),
        "scheduler_config_unchanged": result.get("scheduler_config_unchanged"),
        "prerequisite_product_test_ran": result.get("prerequisite_product_test_ran"),
        "prerequisite_product_test_status": (
            (result.get("prerequisite_product_test") or {}).get("status")
        ),
    })
    append_audit_event(
        "scheduler_acceptance_test", action="completed", status=str(result.get("status") or "unknown"),
        month=str(result.get("month") or "") or None,
        details={"scheduler_enabled_unchanged": result.get("scheduler_enabled_unchanged"), "scheduler_config_unchanged": result.get("scheduler_config_unchanged"), "scheduler_bookkeeping_restored": result.get("scheduler_bookkeeping_restored"), "prerequisite_product_test_ran": result.get("prerequisite_product_test_ran")},
    )
    return result


def automatic_month_close_due(options: Options, now: datetime) -> str | None:
    if not options.automatic_month_close_enabled:
        return None
    # v8.1: een bewaarde AAN-stand na een upgrade is pas uitvoerbaar nadat
    # de actuele productiekern aantoonbaar is gecertificeerd.
    if not automatic_production_readiness().get("ready"):
        return None
    if now.day < options.automatic_month_close_day or now.hour < options.automatic_month_close_hour:
        return None
    year, month = previous_month(now.date())
    month_key = f"{year:04d}_{month:02d}"
    state = load_state()
    if automatic_month_is_completed(month_key):
        # v8.6: duurzame idempotency-marker is leidend, ook na Home Assistant restart.
        return None
    if state.get("automatic_month_close_last_month") == month_key and state.get("automatic_month_close_last_status") in {"completed", "completed_warning"}:
        return None

    last_attempt = state.get("automatic_month_close_last_attempt")
    if state.get("automatic_month_close_last_month") == month_key and last_attempt:
        try:
            attempted_at = datetime.fromisoformat(str(last_attempt))
            if attempted_at.tzinfo is None:
                attempted_at = attempted_at.replace(tzinfo=TZ)
            retry_at = attempted_at + timedelta(hours=options.automatic_month_close_retry_hours)
            if now < retry_at:
                update_state(automatic_month_close_next_retry=retry_at.isoformat())
                return None
        except ValueError:
            pass
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
                execute_automatic_month_close(options, close_month, trigger="automatic")

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



def _tail_text_file(path: Path, max_lines: int = 250, max_bytes: int = 256_000) -> list[str]:
    """Lees alleen het einde van een tekstlog; geen brondata of geheimen."""
    try:
        if not path.is_file():
            return []
        data = path.read_bytes()
        if len(data) > max_bytes:
            data = data[-max_bytes:]
        return data.decode("utf-8", errors="replace").splitlines()[-max_lines:]
    except OSError:
        return []


def _release_versions_on_nas(limit: int = 12) -> list[dict[str, Any]]:
    """Inventariseer recente releases in incoming/processing/processed/failed."""
    items: list[dict[str, Any]] = []
    for bucket in ("incoming", "processing", "processed", "failed"):
        folder = NAS_RELEASE_ROOT / bucket
        if not folder.is_dir():
            continue
        try:
            paths = sorted(folder.glob("EnergieProject_v*.zip"), key=lambda p: p.stat().st_mtime, reverse=True)
        except OSError:
            continue
        for path in paths[:limit]:
            name = path.name
            version = name.removeprefix("EnergieProject_v").removesuffix(".zip")
            try:
                mtime = datetime.fromtimestamp(path.stat().st_mtime, TZ).isoformat()
                size = path.stat().st_size
            except OSError:
                mtime, size = None, None
            items.append({
                "version": version,
                "bucket": bucket,
                "name": name,
                "modified_at": mtime,
                "bytes": size,
            })
    items.sort(key=lambda item: item.get("modified_at") or "", reverse=True)
    return items[:limit]


def runtime_diagnostics_snapshot() -> dict[str, Any]:
    """Kleine runtime-health snapshot; bedoeld om 'draait maar doet niets' te beoordelen."""
    now = datetime.now(TZ)
    threads = []
    for thread in threading.enumerate():
        threads.append({
            "name": thread.name,
            "alive": thread.is_alive(),
            "daemon": thread.daemon,
        })
    uptime_seconds = max(0, int((now - APP_PROCESS_STARTED_AT).total_seconds()))
    state = load_state()
    return {
        "schema": "energie_runtime_diagnostics_v1",
        "version": APP_VERSION,
        "generated_at": now.isoformat(),
        "process_started_at": APP_PROCESS_STARTED_AT.isoformat(),
        "uptime_seconds": uptime_seconds,
        "pid": os.getpid(),
        "thread_count": len(threads),
        "threads": threads,
        "workflow_status": state.get("workflow_status") or state.get("status"),
        "last_month": state.get("workflow_last_month") or state.get("last_month"),
        "last_validation_status": state.get("last_validation_status"),
        "last_integrity_status": state.get("last_integrity_status"),
        "nas_share_available": NAS_SHARE_ROOT.is_dir(),
        "release_root_available": NAS_RELEASE_ROOT.is_dir(),
        "backend_alive": True,
    }


def release_diagnostics_snapshot(version: str | None = None) -> dict[str, Any]:
    """Gerichte release-diagnose zonder energie-/maanddata."""
    requested = (version or "").strip().lstrip("v")
    project_version = ""
    try:
        project_version = (NAS_PROJECT_ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip()
    except OSError:
        pass

    releases = _release_versions_on_nas(limit=20)
    if not requested:
        requested = project_version or APP_VERSION

    locations = [item for item in releases if item.get("version") == requested]
    latest_status_path = NAS_RELEASE_ROOT / "latest_release_status.txt"
    watcher_log_path = NAS_RELEASE_ROOT / "logs" / "release_watcher.log"
    publish_state: dict[str, Any] = {}
    try:
        if GITHUB_PUBLISH_STATE.is_file():
            loaded = json.loads(GITHUB_PUBLISH_STATE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                publish_state = loaded
    except Exception:
        publish_state = {"error": "publisher_state_unreadable"}

    git_lock = NAS_PROJECT_ROOT / ".git" / "index.lock"
    lock_info: dict[str, Any] = {"exists": git_lock.exists(), "path": str(git_lock)}
    if git_lock.exists():
        try:
            stat = git_lock.stat()
            lock_info.update({
                "bytes": stat.st_size,
                "modified_at": datetime.fromtimestamp(stat.st_mtime, TZ).isoformat(),
                "age_seconds": max(0, int(datetime.now(TZ).timestamp() - stat.st_mtime)),
            })
        except OSError:
            pass

    watcher_lines = _tail_text_file(watcher_log_path, max_lines=400)
    matching_watcher_lines = [line for line in watcher_lines if requested in line]
    return {
        "schema": "energie_release_diagnostics_v1",
        "version": APP_VERSION,
        "generated_at": datetime.now(TZ).isoformat(),
        "requested_release": requested,
        "installed_project_version": project_version or None,
        "home_assistant_app_version": APP_VERSION,
        "locations": locations,
        "recent_releases": releases,
        "latest_release_status": "\n".join(_tail_text_file(latest_status_path, max_lines=80)),
        "watcher_log_available": watcher_log_path.is_file(),
        "watcher_log_path": str(watcher_log_path),
        "watcher_matching_lines": matching_watcher_lines[-150:],
        "watcher_tail": watcher_lines[-200:],
        "publisher_state": publish_state,
        "git_index_lock": lock_info,
        "runtime": runtime_diagnostics_snapshot(),
    }


def build_release_diagnostic_package(version: str | None = None) -> bytes:
    """Kleine ZIP voor releaseproblemen; bevat bewust geen energiedata of secrets."""
    snapshot = release_diagnostics_snapshot(version)
    requested = snapshot.get("requested_release") or APP_VERSION
    entries: dict[str, bytes] = {
        "release_diagnostics.json": json.dumps(snapshot, ensure_ascii=False, indent=2, default=str).encode("utf-8"),
        "runtime_diagnostics.json": json.dumps(snapshot["runtime"], ensure_ascii=False, indent=2, default=str).encode("utf-8"),
        "watcher_relevant.log": ("\n".join(snapshot.get("watcher_matching_lines") or []) + "\n").encode("utf-8"),
        "watcher_tail.log": ("\n".join(snapshot.get("watcher_tail") or []) + "\n").encode("utf-8"),
    }
    readme = (
        "EnergieProject release-diagnose\n"
        "================================\n"
        f"Appversie: {APP_VERSION}\n"
        f"Gevraagde release: {requested}\n"
        "Doel: verklaren waarom een release in incoming/processing/failed/processed blijft "
        "of niet bij Home Assistant aankomt.\n"
        "Bevat geen P1-, Enphase-, EPEX-, maandrapport-, token- of wachtwoorddata.\n"
    ).encode("utf-8")
    entries["README.txt"] = readme

    manifest = {
        "schema": 1,
        "generated_at": snapshot["generated_at"],
        "requested_release": requested,
        "files": [],
    }
    for name, data in entries.items():
        manifest["files"].append({
            "path": name,
            "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        })
    entries["MANIFEST.json"] = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in entries.items():
            archive.writestr(name, data)
    return buffer.getvalue()


def build_test_package() -> bytes:
    """Bouw één diagnosepakket voor goed-/afkeuring zonder geheimen uit options.json."""
    options = Options.load()
    state = persist_normalized_status(options)
    op = operation_status(options)
    health = health_dashboard(options)
    certificate = validate_production_certificate()
    monitoring = op.get("monitoring") or (
        monitoring_snapshot(options) if options is not None else read_monitoring_status()
    )
    if not monitoring:
        monitoring = {
            "status": "not_configured",
            "checks": [],
            "active_alerts": 0,
            "active_errors": 0,
            "pending_points": 0,
        }
    recovery = op.get("recovery_controller") or read_recovery_status()
    audit = op.get("audit_trail") or {"validation": validate_audit_trail(), "events": read_audit_trail(limit=12), "path": str(AUDIT_TRAIL_PATH)}

    month_key = str(
        (op.get("workflow") or {}).get("month")
        or (op.get("last_run") or {}).get("month")
        or state.get("workflow_last_month")
        or state.get("last_month")
        or ""
    ).strip().replace("-", "_")

    production_ready = bool(automatic_production_readiness(state).get("ready"))
    certificate_valid = bool(certificate.get("valid"))
    certificate_core = str(certificate.get("production_core_revision") or "")
    health_score = int(health.get("score") or 0)
    monitoring_errors = int(monitoring.get("active_errors", 0) or 0)
    monitoring_pending = int(monitoring.get("pending_points", monitoring.get("attention_points", 0)) or 0)
    recovery_status = str(recovery.get("status") or "unknown")
    audit_integrity = str((audit.get("validation") or {}).get("status") or "unknown")
    infrastructure = op.get("infrastructure") or infrastructure_snapshot()
    migration = nas_migration_snapshot()
    scheduler_enabled = bool((op.get("automatic_month_close") or {}).get("enabled"))
    scheduler_effective = bool((op.get("automatic_month_close") or {}).get("scheduler_effective"))

    criteria = {
        "production_ready": production_ready,
        "certificate_valid": certificate_valid,
        "certificate_core_matches": certificate_core == PRODUCTION_CORE_REVISION,
        "health_score_100": health_score == 100,
        "monitoring_no_errors": monitoring_errors == 0,
        "recovery_ok": recovery_status == "ok",
        "audit_integrity_ok": audit_integrity == "ok",
        "scheduler_effective": scheduler_effective,
    }
    failed_criteria = [name for name, ok in criteria.items() if not ok]
    verdict = "GO" if not failed_criteria else "NO-GO"
    assessment = {
        "schema": 3,
        "release_version": APP_VERSION,
        "production_core_revision": PRODUCTION_CORE_REVISION,
        "generated_at": datetime.now(TZ).isoformat(),
        "verdict": verdict,
        "criteria": criteria,
        "failed_criteria": failed_criteria,
        "manual_review_required": False if verdict == "GO" else True,
        "scope": "technische releasecriteria uit diagnosepakket; geen vervanging voor inhoudelijke rapportbeoordeling",
        "core_certificate_origin_release": certificate.get("version"),
        "core_certificate_reused": bool(certificate_valid and certificate_core == PRODUCTION_CORE_REVISION and str(certificate.get("version") or "") != APP_VERSION),
        "release_stage": "stable",
        "target_stable_release": "10.5.37",
    }

    summary = {
        "schema": 3,
        "release_version": APP_VERSION,
        "production_core_revision": PRODUCTION_CORE_REVISION,
        "generated_at": assessment["generated_at"],
        "test_month": month_key or None,
        "production_ready": production_ready,
        "production_certificate_valid": certificate_valid,
        "certificate_origin_release": certificate.get("version"),
        "certificate_core_revision": certificate.get("production_core_revision"),
        "core_certificate_reused": bool(certificate_valid and certificate_core == PRODUCTION_CORE_REVISION and str(certificate.get("version") or "") != APP_VERSION),
        "health_score": health_score,
        "monitoring_status": monitoring.get("status"),
        "monitoring_errors": monitoring_errors,
        "monitoring_pending": monitoring_pending,
        "recovery_status": recovery_status,
        "recovery_actions": recovery.get("repair_actions", recovery.get("repaired_count", 0)),
        "audit_integrity": audit_integrity,
        "audit_records": (audit.get("validation") or {}).get("records", 0),
        "scheduler_enabled": scheduler_enabled,
        "scheduler_effective": scheduler_effective,
        "source_status": state.get("workflow_sources") or {},
        "infrastructure": infrastructure,
        "nas_migration": migration,
        "release_inbox": migration.get("release_inbox"),
        "last_project_backup": state.get("last_project_backup"),
        "automatic_verdict": verdict,
        "failed_criteria": failed_criteria,
        "release_stage": "stable",
        "target_stable_release": "10.5.37",
        "note": "v10.5.6 voegt uitsluitend een read-only analysecontext toe bovenop bestaande maanddata; release-inbox, workflow, scheduler en productiekern 9.4-core1 blijven ongewijzigd.",
    }

    generated = {
        "beoordeling.json": assessment,
        "test_summary.json": summary,
        "operation_status.json": op,
        "health_dashboard.json": health,
        "production_certificate_validation.json": certificate,
        "monitoring_snapshot.json": monitoring,
        "recovery_snapshot.json": recovery,
        "audit_validation.json": audit.get("validation") or {},
        "infrastructure_status.json": infrastructure,
        "nas_migration_status.json": migration,
        "release_inbox_status.json": migration.get("release_inbox") or {},
    }

    files = [
        (PRODUCTION_CERTIFICATE_PATH, "evidence/production_certificate.json"),
        (PRODUCTION_CERTIFICATE_HISTORY_PATH, "evidence/production_certificate_history.jsonl"),
        (PRODUCTION_CERTIFICATE_MANAGEMENT_PATH, "evidence/production_certificate_management.json"),
        (RECOVERY_STATE_PATH, "evidence/recovery_state.json"),
        (RECOVERY_HISTORY_PATH, "evidence/recovery_history.jsonl"),
        (MONITORING_STATE_PATH, "evidence/monitoring_state.json"),
        (MONITORING_HISTORY_PATH, "evidence/monitoring_history.jsonl"),
        (AUDIT_TRAIL_PATH, "evidence/audit_trail.jsonl"),
        (AUTOMATIC_RUN_LEDGER_PATH, "evidence/automatic_run_history.jsonl"),
        (AUTOMATIC_COMPLETION_MARKERS_PATH, "evidence/automatic_completed_months.json"),
        (AUTOMATIC_RETRY_STATE_PATH, "evidence/automatic_retry_state.json"),
        (RETRY_DEBUG_LOG_PATH, "logs/retry_debug.log"),
        (FINALIZATION_DEBUG_LOG_PATH, "logs/finalization_debug.log"),
    ]
    if month_key:
        files.extend([
            (workflow_result_dir(month_key) / FULL_WORKFLOW_RESULT_NAME, f"workflow/{month_key}/workflow_result.json"),
            (workflow_log_file(month_key), f"workflow/{month_key}/workflow.log"),
        ])

    entries: dict[str, bytes] = {}
    manifest = []
    for name, payload in generated.items():
        data = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        entries[name] = data
        manifest.append({"path": name, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})

    for src, arcname in files:
        try:
            if src.is_file():
                data = src.read_bytes()
                entries[arcname] = data
                manifest.append({"path": arcname, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
        except OSError as exc:
            manifest.append({"path": arcname, "error": str(exc)})

    manifest_bytes = json.dumps(
        {"generated_at": summary["generated_at"], "release_version": APP_VERSION, "files": manifest},
        ensure_ascii=False, indent=2,
    ).encode("utf-8")
    entries["MANIFEST.json"] = manifest_bytes

    summary_lines = [
        "Energieproject diagnosepakket",
        "============================",
        f"Automatische technische beoordeling: {verdict}",
        f"Softwareversie: {APP_VERSION}",
        "Releasefase: Stable",
        "Doelrelease: 10.5.37",
        f"Gecertificeerde productiekern: {PRODUCTION_CORE_REVISION}",
        f"Gebruikte productiekern: {summary.get('certificate_core_revision') or PRODUCTION_CORE_REVISION}",
        f"Kerncertificaat geldig: {'JA' if summary.get('production_certificate_valid') else 'NEE'}",
        f"Kern oorspronkelijk gecertificeerd in: {summary.get('certificate_origin_release') or '—'}",
        f"Kerncertificaat hergebruikt voor deze release: {'JA' if summary.get('core_certificate_reused') else 'NEE'}",
        f"Gegenereerd: {summary['generated_at']}",
        f"Testmaand: {summary.get('test_month') or '—'}",
        f"Productieklaar: {'JA' if summary.get('production_ready') else 'NEE'}",
        f"Healthscore: {summary.get('health_score')}",
        f"Productiecertificaat geldig: {'JA' if summary.get('production_certificate_valid') else 'NEE'}",
        f"Monitoring: {summary.get('monitoring_status') or '—'}; fouten={summary.get('monitoring_errors', 0)}; wachtstatussen={summary.get('monitoring_pending', 0)}",
        f"Recovery: {summary.get('recovery_status') or '—'}; herstelacties={summary.get('recovery_actions', 0)}",
        f"Audittrail: {summary.get('audit_integrity') or '—'}; records={summary.get('audit_records', 0)}",
        f"Scheduler actief: {'JA' if summary.get('scheduler_effective') else 'NEE'}",
        f"QNAP infrastructuur: {infrastructure.get('status')} - {infrastructure.get('message')}",
        f"NAS migratiestatus: {migration.get('status')} - {migration.get('message')}",
        f"Release-inbox: {(migration.get('release_inbox') or {}).get('status')} - {(migration.get('release_inbox') or {}).get('message')}",
        f"Laatste projectback-up: {(summary.get('last_project_backup') or {}).get('status') or 'nog geen'}",
        f"Niet geslaagde technische criteria: {', '.join(failed_criteria) if failed_criteria else 'geen'}",
        "",
        "Beoordeling",
        "-----------",
        "Zie beoordeling.json voor de machineleesbare GO/NO-GO en alle afzonderlijke criteria.",
        "De beoordeling geldt voor de technische releasecriteria van dit diagnosepakket.",
        "",
        "SHA-256 controle",
        "---------------",
        "Zie SHA256SUMS.txt voor de SHA-256 van ieder bestand in dit diagnosepakket.",
        "Een SHA-256 van het ZIP-bestand zelf kan niet betrouwbaar in datzelfde ZIP-bestand worden opgenomen",
        "zonder een zelf-referentiële hash te veroorzaken.",
    ]
    entries["samenvatting.txt"] = ("\n".join(summary_lines) + "\n").encode("utf-8")

    sha_lines = []
    for name in sorted(entries):
        sha_lines.append(f"{hashlib.sha256(entries[name]).hexdigest()}  {name}")
    entries["SHA256SUMS.txt"] = ("\n".join(sha_lines) + "\n").encode("utf-8")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(entries):
            archive.writestr(name, entries[name])
    return buffer.getvalue()



def github_publication_ui_snapshot() -> dict[str, Any]:
    # Server-side UI snapshot: uitsluitend lokale publisher-state, geen browser/API-fetch.
    options = _publisher_options()
    enabled = bool(options.get("github_publication_enabled", False))
    saved: dict[str, Any] = {}
    try:
        if GITHUB_PUBLISH_STATE.is_file():
            loaded = json.loads(GITHUB_PUBLISH_STATE.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                saved = loaded
    except Exception as exc:
        saved = {"message": f"Persistente publicatiestatus onleesbaar: {exc}"}

    try:
        public_key = (
            GITHUB_PUBLIC_KEY.read_text(encoding="utf-8").strip()
            if GITHUB_PUBLIC_KEY.is_file()
            else ""
        )
    except Exception:
        public_key = ""

    key_ready = bool(public_key) or bool(saved.get("key_ready"))
    remote_reachable = bool(saved.get("remote_reachable"))
    published = bool(saved.get("published"))
    local_version = str(saved.get("local_version") or saved.get("version") or "").strip()
    message = str(saved.get("message") or "").strip()

    if enabled and published:
        label = "Automatisch"
        css = "ok"
        detail = f"GitHub-publicatie actief · laatste publicatie: {local_version or 'gereed'}"
    elif enabled and remote_reachable:
        label = "Automatisch"
        css = "ok"
        detail = message or "GitHub bereikbaar; publicatiegereed"
    elif enabled and key_ready:
        label = "Wacht op GitHub"
        css = "warn"
        detail = message or "Publisher staat aan; wacht op een bevestigde publicatiestatus."
    elif key_ready:
        label = "Configureren"
        css = "warn"
        detail = "Publicatiesleutel gereed; automatische publicatie staat nog uit."
    else:
        label = "Niet gereed"
        css = "warn"
        detail = message or "Publicatiesleutel ontbreekt."

    return {
        "enabled": enabled,
        "published": published,
        "remote_reachable": remote_reachable,
        "key_ready": key_ready,
        "local_version": local_version,
        "label": label,
        "css": css,
        "detail": detail,
        "public_key": public_key,
    }


def html_page(ingress_path: str = "") -> bytes:
    ingress_path = (ingress_path or "").rstrip("/")
    state = load_state()
    github_ui = github_publication_ui_snapshot()
    try:
        options = Options.load()
        default_month = options.target_month or datetime.now(TZ).strftime("%Y-%m")
        op = operation_status(options)
    except Exception:
        options = None
        default_month = datetime.now(TZ).strftime("%Y-%m")
        op = {"workflow": {}, "last_run": {}, "automatic_month_close": {}, "history": []}

    def esc(value: Any) -> str:
        return html.escape(str(value if value is not None else ""))

    def status_class(value: Any) -> str:
        text = str(value or "").lower()
        if text in {"completed", "ok", "ready", "idle", "completed_warning"}:
            return "ok"
        if text in {"running", "importing", "warning", "pending", "attention"}:
            return "warn"
        if text in {"stale", "outdated", "opnieuw testen"}:
            return "neutral"
        if text in {"error", "failed", "unreadable"}:
            return "bad"
        return "neutral"

    def fmt_duration(value: Any) -> str:
        try:
            seconds = float(value)
        except (TypeError, ValueError):
            return "—"
        if seconds < 60:
            return f"{seconds:.1f} s"
        minutes, rest = divmod(int(round(seconds)), 60)
        return f"{minutes}m {rest:02d}s"

    api_test = state.get("api_test") or {}
    api_text = "Nog niet getest"
    if api_test:
        api_text = (
            f"OK — {api_test.get('connections', 0)} aansluiting(en)"
            if api_test.get("status") == "ok"
            else f"Fout — {api_test.get('error', 'onbekend')}"
        )

    workflow = op.get("workflow") or {}
    last_run = op.get("last_run") or {}
    auto_close = op.get("automatic_month_close") or {}
    history = op.get("history") or []
    visual_progress = op.get("visual_progress") or {}
    progress_current = int(visual_progress.get("step_index") or 0)
    progress_total = int(visual_progress.get("steps_total") or WORKFLOW_VISUAL_TOTAL_STEPS)
    progress_pct = float(visual_progress.get("percent") or 0)
    health = op.get("health") or health_dashboard(options) if options else {"score": 0, "checks": []}
    health_score = int(health.get("score") or 0)
    health_rows = "".join(
        "<li><span>" + esc(item.get("name")) + "</span><span><span class='pill "
        + status_class(item.get("status")) + "'>" + esc(item.get("status")) + "</span> "
        + esc(item.get("detail")) + "</span></li>"
        for item in health.get("checks") or []
    ) or "<li><span>Nog geen gezondheidscontrole</span></li>"
    log_month = str(workflow.get("month") or last_run.get("month") or "").strip()

    analysis_context = build_analysis_context()
    analysis_top = analysis_overview(analysis_context)

    history_rows = []
    for item in history:
        failed = item.get("failed_step") or "—"
        steps = f"{item.get('steps_completed', '—')} / {item.get('steps_total', '—')}"
        history_rows.append(
            "<tr>"
            f"<td><strong>{esc(item.get('month'))}</strong></td>"
            f"<td><span class='pill {status_class(item.get('status'))}'>{esc(item.get('status'))}</span></td>"
            f"<td>{esc(steps)}</td>"
            f"<td>{esc(fmt_duration(item.get('duration_seconds')))}</td>"
            f"<td>{esc(failed)}</td>"
            f"<td>{esc(format_local_datetime(item.get('finished_at')) if item.get('finished_at') else '—')}</td>"
            f"<td><a href='workflow-log?month={esc(item.get('month'))}'>open</a></td>"
            "</tr>"
        )
    history_html = "".join(history_rows) or "<tr><td colspan='7'>Nog geen historische runs.</td></tr>"

    downloads = "".join(
        f"<li><a href='download?month={html.escape(month)}'>{html.escape(month)} als archief downloaden</a></li>"
        for month in month_archives()
    ) or "<li>Nog geen uitvoer</li>"

    source_items = "".join(
        f"<li><span>{esc(k)}</span><span class='pill {status_class(v)}'>{esc(v)}</span></li>"
        for k, v in (state.get("workflow_sources") or {}).items()
    ) or "<li><span>Nog geen bronstatus beschikbaar</span></li>"

    auto_text = (
        f"Aan — dag {esc(auto_close.get('day'))} om {esc(auto_close.get('hour'))}:00 · retry na {esc(auto_close.get('retry_hours'))} uur"
        if auto_close.get("enabled") else "Uit"
    )
    auto_preflight = auto_close.get("last_preflight") or {}
    auto_finalization = auto_close.get("last_finalization") or {}
    auto_test = auto_close.get("test_last_result") or {}

    auto_test_current_version = str(auto_test.get("production_core_revision") or "") == PRODUCTION_CORE_REVISION
    if auto_test and not auto_test_current_version:
        auto_test_display_status = "Opnieuw testen"
        auto_test_display_detail = (
            f"Laatste test hoort bij productiekern {esc(auto_test.get('production_core_revision') or 'legacy')}; huidige kern is {esc(PRODUCTION_CORE_REVISION)}."
        )
    else:
        auto_test_display_status = str(auto_test.get("status") or "Nog niet getest")
        auto_test_display_detail = str(auto_test.get("error") or "")

    production = auto_close.get("production_readiness") or automatic_production_readiness(state)
    auto_test_ok = bool(production.get("ready"))
    auto_ready_status = "ready" if auto_test_ok else (
        "running" if str(auto_test.get("status") or "") == "running" and auto_test_current_version
        else "pending"
    )
    auto_ready_text = "Klaar voor automatisch gebruik" if auto_test_ok else (
        "Productietest loopt" if auto_ready_status == "running"
        else "Productietest vereist"
    )
    production_status = "ready" if production.get("ready") else "pending"
    production_text = "Productiegeaccepteerd" if production.get("status") == "accepted" else (
        "Productieklaar" if production.get("ready") else "Kerncertificering vereist"
    )
    production_certificate = production.get("certificate") or {}
    production_certificate_validation = (
        auto_close.get("production_certificate")
        or production.get("certificate_validation")
        or validate_production_certificate()
    )
    production_certificate_text = (
        f"v{production_certificate.get('version')} · Afgegeven · {format_local_datetime(production_certificate.get('accepted_at'))}"
        if production_certificate_validation.get("valid")
        else (
            f"Productiekern {PRODUCTION_CORE_REVISION} nog niet gecertificeerd — één productietest vereist"
            if str(production_certificate_validation.get("production_core_revision") or "") != PRODUCTION_CORE_REVISION
            else "Certificaat vereist aandacht — " + str(production_certificate_validation.get("status") or "ontbreekt")
        )
    )
    production_certificate_history = auto_close.get("production_certificate_history") or []
    production_certificate_management = auto_close.get("production_certificate_management") or state.get("production_certificate_management") or {}
    production_certificate_management_text = (
        "Nog niet handmatig gecontroleerd"
        if not production_certificate_management
        else (
            ("Certificaat hersteld — geldig" if production_certificate_management.get("repaired") else "Certificaat gecontroleerd — geldig")
            if production_certificate_management.get("valid")
            else "Certificaatcontrole vereist aandacht"
        )
    )
    production_certificate_management_status = "ok" if production_certificate_management.get("valid") else ("neutral" if not production_certificate_management else "warning")
    scheduler_effective = bool(auto_close.get("scheduler_effective"))
    scheduler_text = (
        "Actief" if scheduler_effective
        else ("Wacht op kerncertificering" if auto_close.get("enabled") else "Uit")
    )
    next_auto_run = auto_close.get("next_scheduled_run")
    next_auto_run_text = format_local_datetime(next_auto_run)
    latest_published = list(state.get("report_output_last_files") or [])
    latest_output_text = (
        f"{state.get('report_output_last_month')}: {len(latest_published)} bestand(en)"
        if state.get("report_output_last_status") == "completed" and latest_published
        else "Nog geen complete publicatie"
    )

    scheduler_acceptance = auto_close.get("scheduler_acceptance_last_result") or {}
    scheduler_acceptance_current = str(scheduler_acceptance.get("production_core_revision") or "") == PRODUCTION_CORE_REVISION
    scheduler_acceptance_status = (
        str(scheduler_acceptance.get("status") or "Nog niet getest")
        if scheduler_acceptance_current
        else ("Opnieuw testen" if scheduler_acceptance else "Nog niet getest")
    )
    scheduler_acceptance_detail = (
        f"Gesimuleerd voor {format_local_datetime(scheduler_acceptance.get('simulated_at'))} · doelmaand {scheduler_acceptance.get('month') or '—'}"
        + (" · voorbereidende productietest automatisch geslaagd" if scheduler_acceptance.get("prerequisite_product_test_ran") is True else "")
        + (" · schedulerinstelling ongewijzigd" if scheduler_acceptance.get("scheduler_enabled_unchanged") is True else "")
        if scheduler_acceptance_current and scheduler_acceptance.get("simulated_at")
        else ""
    )

    certificate_history_rows = "".join(
        "<tr>"
        f"<td>{esc(item.get('version') or '—')}</td>"
        f"<td>{esc(item.get('production_core_revision') or 'legacy')}</td>"
        f"<td>{esc(format_local_datetime(item.get('accepted_at')) if item.get('accepted_at') else '—')}</td>"
        f"<td><span class='pill {status_class('ok' if item.get('status') == 'accepted' else 'error')}'>{esc(item.get('status') or '—')}</span></td>"
        f"<td>{esc(item.get('month') or '—')}</td>"
        "</tr>"
        for item in production_certificate_history
    ) or "<tr><td colspan='5'>Nog geen productiecertificaten.</td></tr>"

    recovery = auto_close.get("recovery") or {}
    recovery_label = str(recovery.get("label") or "Geen herstelactie nodig")
    recovery_detail = str(recovery.get("detail") or "")
    recovery_status = str(recovery.get("status") or "ready")
    retry_debug = auto_close.get("retry_debug") or {}
    retry_debug_state = retry_debug.get("retry_state_loaded") or {}
    retry_debug_marker = retry_debug.get("completion_marker") or {}
    audit_trail = op.get("audit_trail") or {}
    audit_validation = audit_trail.get("validation") or {}
    audit_rows = "".join(
        "<tr><td>" + esc(format_local_datetime(item.get("recorded_at"))) + "</td>"
        + "<td>" + esc(item.get("event_type") or "—") + "</td>"
        + "<td>" + esc(item.get("action") or "—") + "</td>"
        + "<td><span class='pill " + status_class(item.get("status")) + "'>" + esc(item.get("status") or "—") + "</span></td>"
        + "<td>" + esc(item.get("month") or "—") + "</td></tr>"
        for item in (audit_trail.get("events") or [])
    ) or "<tr><td colspan='5'>Nog geen auditrecords.</td></tr>"
    monitoring = op.get("monitoring") or (
        monitoring_snapshot(options) if options is not None else read_monitoring_status()
    )
    if not monitoring:
        monitoring = {
            "status": "not_configured",
            "checks": [],
            "active_alerts": 0,
            "active_errors": 0,
            "pending_points": 0,
        }
    monitoring_checks = monitoring.get("checks") or []
    monitoring_status = str(monitoring.get("status") or "unknown")
    monitoring_count = int(monitoring.get("active_alerts") or 0)
    monitoring_errors = int(monitoring.get("active_errors") or 0)
    monitoring_pending = int(monitoring.get("pending_points") if monitoring.get("pending_points") is not None else (monitoring.get("attention_points") or 0))
    monitoring_checked = format_local_datetime(monitoring.get("checked_at")) if monitoring.get("checked_at") else "Nog niet gecontroleerd"
    monitoring_rows = "".join(
        f"<li><span>{esc(item.get('name') or '—')}</span><span><span class='pill {status_class(item.get('status'))}'>{esc(item.get('status') or '—')}</span> {esc(item.get('detail') or '')}</span></li>"
        for item in monitoring_checks
    ) or "<li><span>Monitoring</span><span>Nog geen status</span></li>"
    recovery_controller = op.get("recovery_controller") or {}
    recovery_controller_status = str(recovery_controller.get("status") or "not_checked")
    recovery_controller_count = int(recovery_controller.get("repair_count") or 0)
    recovery_controller_checked = format_local_datetime(recovery_controller.get("checked_at"))
    recovery_controller_detail = (
        f"{recovery_controller_count} herstelactie(s) uitgevoerd"
        if recovery_controller_count
        else ("Controle zonder herstelacties" if recovery_controller.get("checked_at") else "Nog niet gecontroleerd")
    )
    if recovery_controller.get("warnings"):
        recovery_controller_detail += " · " + "; ".join(str(x) for x in recovery_controller.get("warnings") or [])
    retry_debug_ledger = retry_debug.get("append_history") or {}
    retry_debug_workflow = retry_debug.get("workflow_history") or {}
    retry_debug_decision = retry_debug.get("current_decision") or {}
    retry_debug_legacy = retry_debug.get("legacy_state") or {}
    finalization_debug = auto_close.get("finalization_debug") or []
    finalization_debug_last = finalization_debug[-1] if finalization_debug else {}

    auto_test_month = str(auto_test.get("month") or datetime.now(TZ).strftime("%Y_%m")).replace("_", "-")
    workflow_active = str(workflow.get("status") or "").lower() in {"running", "importing"}
    resume_available = str(last_run.get("status") or "").lower() in {"error", "failed"}
    disabled_attr = " disabled" if workflow_active else ""
    auto_history_rows = "".join(
        "<tr>"
        f"<td>{esc(item.get('month') or '—')}</td>"
        f"<td>{esc(item.get('run_type') or 'Automatisch')}</td>"
        f"<td>{esc(item.get('version') or '—')}</td>"
        f"<td><span class='pill {status_class(item.get('status'))}'>{esc(item.get('status') or '—')}</span></td>"
        f"<td><span class='pill {status_class(item.get('finalization_status'))}'>{esc(item.get('finalization_status') or '—')}</span></td>"
        f"<td>{esc(format_local_datetime(item.get('finished_at')) if item.get('finished_at') else '—')}</td>"
        f"<td>{esc(f'{float(item.get('duration_seconds')):.1f} s' if item.get('duration_seconds') is not None else '—')}</td>"
        "</tr>"
        for item in (auto_close.get("history") or [])
    ) or "<tr><td colspan='7'>Nog geen automatische runs geregistreerd.</td></tr>"

    resume_html = (
        f"""<form method="post" action="resume-month-workflow"><input type="month" name="month" value="{esc((last_run.get('month') or default_month).replace('_','-'))}" required> <button type="submit" class="secondary workflow-action">Hervat mislukte workflow</button></form>
<p class="hint">Eerder succesvolle stappen worden hergebruikt; hervatten is alleen beschikbaar na een mislukte workflow.</p>"""
        if resume_available
        else """<div class="resume-unavailable"><strong>Geen mislukte workflow om te hervatten.</strong><div class="hint">De hervatknop verschijnt automatisch wanneer een workflow werkelijk is mislukt.</div></div>"""
    )

    return f"""<!doctype html>
<html lang="nl"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Energieproject — operationele console</title>
<style>
:root{{--bg:#f4f7f9;--card:#fff;--text:#17202a;--muted:#61707d;--blue:#039be5;--border:#dfe7ec;--ok:#17864b;--warn:#b87500;--bad:#c0392b}}
*{{box-sizing:border-box}} body{{font-family:system-ui,-apple-system,sans-serif;margin:0;background:var(--bg);color:var(--text)}}
main{{max-width:1180px;margin:22px auto;padding:0 18px 40px}} h1{{margin-bottom:4px}} h2{{margin:0 0 16px}} h3{{margin:0 0 12px}}
.subtitle{{color:var(--muted);margin:0 0 18px}} .grid{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}}
.card{{background:var(--card);border-radius:14px;padding:20px;margin:14px 0;box-shadow:0 2px 12px #00000010;border:1px solid #edf1f3}}
.metric{{padding:16px;border:1px solid var(--border);border-radius:12px;background:#fff}} .metric small{{display:block;color:var(--muted);margin-bottom:7px}} .metric strong{{font-size:1.08rem;overflow-wrap:anywhere}}
.pill{{display:inline-block;padding:4px 9px;border-radius:999px;font-weight:700;font-size:.82rem;background:#e8edf0;color:#4b5963}} .pill.ok{{background:#e6f5ec;color:var(--ok)}} .pill.warn{{background:#fff2d8;color:var(--warn)}} .pill.bad{{background:#fde8e5;color:var(--bad)}}
.progress{{height:12px;background:#e7edf1;border-radius:999px;overflow:hidden;margin:10px 0 5px}} .progress>span{{display:block;height:100%;width:{progress_pct}%;background:var(--blue);transition:width 1.2s ease;position:relative;overflow:hidden}} .progress>span.running::after{{content:"";position:absolute;inset:0;background:linear-gradient(90deg,transparent,#ffffff55,transparent);transform:translateX(-100%);animation:flow 1.6s infinite}} @keyframes flow{{to{{transform:translateX(100%)}}}}
.controls{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}} .control-group{{border:1px solid var(--border);border-radius:12px;padding:16px}} form{{margin:9px 0}} button{{background:var(--blue);color:#fff;border:0;border-radius:8px;padding:11px 15px;font-weight:700;cursor:pointer}} button.secondary{{background:#546e7a}} button.danger{{background:#c0392b}} button:disabled{{background:#aeb8bd;color:#eef2f4;cursor:not-allowed;opacity:.78}} input,select{{padding:10px;border:1px solid #b8c3ca;border-radius:8px;max-width:190px}} .inline-fields{{display:flex;gap:12px;flex-wrap:wrap;align-items:center}} .inline-fields label{{font-size:.9rem;color:var(--muted)}}
.switch-row{{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:12px 14px;margin:2px 0 14px;border:1px solid var(--border);border-radius:12px;background:#f8fafb}} .switch-title{{font-weight:800;color:var(--text)}} .switch-wrap{{display:flex;align-items:center;gap:10px;cursor:pointer;user-select:none}} .switch-wrap input{{position:absolute;opacity:0;pointer-events:none}} .switch-slider{{position:relative;width:54px;height:30px;border-radius:999px;background:#aab5bb;transition:.2s}} .switch-slider::after{{content:"";position:absolute;width:24px;height:24px;left:3px;top:3px;border-radius:50%;background:white;box-shadow:0 1px 4px #0004;transition:.2s}} .switch-wrap input:checked + .switch-slider{{background:var(--ok)}} .switch-wrap input:checked + .switch-slider::after{{transform:translateX(24px)}} .switch-state{{min-width:31px;font-weight:800;color:#65747d}} .switch-wrap input:checked ~ .switch-state{{color:var(--ok)}} .resume-unavailable{{padding:10px 12px;border-radius:9px;background:#f3f6f7;color:#66757e;margin:9px 0}} .planning-fields{{display:grid;grid-template-columns:repeat(3,minmax(110px,1fr));gap:10px}} .planning-fields label{{display:flex;flex-direction:column;gap:5px;font-size:.88rem;color:var(--muted)}} .planning-fields input{{width:100%;max-width:none}} .auto-status{{display:flex;align-items:center;gap:8px;flex-wrap:wrap}} .auto-status small{{color:var(--muted);font-weight:500}} .test-detail{{display:block;margin-top:4px;color:var(--muted);font-size:.78rem;max-width:360px;overflow-wrap:anywhere}}
.hint{{font-size:.9rem;color:var(--muted);margin:7px 0}} table{{width:100%;border-collapse:collapse}} th,td{{text-align:left;border-bottom:1px solid var(--border);padding:10px 8px;vertical-align:top}} th{{font-size:.82rem;color:var(--muted)}} .table-wrap{{overflow-x:auto}}
details{{border:1px solid var(--border);border-radius:10px;padding:11px 13px;margin:9px 0}} summary{{cursor:pointer;font-weight:700}} .source-list{{list-style:none;padding:0;margin:0}} .source-list li{{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-bottom:1px solid #eef2f4}}
a{{color:#0277bd}} .button-link{{display:inline-block;background:#546e7a;color:#fff;text-decoration:none;border-radius:8px;padding:11px 15px;font-weight:700}} .compact-details{{border:0;padding:0;margin:0}} .compact-details>summary{{font-size:1.18rem;padding:2px 0 10px}} .links{{line-height:2}} code{{font-size:.9em}} .log{{background:#101820;color:#e8eef2;border-radius:10px;padding:12px;min-height:110px;max-height:300px;overflow:auto;font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap}} .score{{font-size:2rem;font-weight:800}} 
@media(max-width:850px){{.grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}.controls{{grid-template-columns:1fr}}}} @media(max-width:620px){{.planning-fields{{grid-template-columns:1fr}}}} @media(max-width:520px){{.grid{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>Energieproject</h1><p class="subtitle">Operationele console · SlimmeMeterPortal Import · versie {APP_VERSION}</p>

<div class="grid">
  <div class="metric"><small>Workflow</small><strong><span id="workflow-status" class="pill {status_class(workflow.get('status'))}">{esc(workflow.get('status') or 'onbekend')}</span></strong></div>
  <div class="metric"><small>Laatste maand</small><strong id="last-month">{esc(last_run.get('month') or 'Nog geen')}</strong></div>
  <div class="metric"><small>Laatste run</small><strong><span id="last-run-status" class="pill {status_class(last_run.get('status'))}">{esc(last_run.get('status') or 'Nog geen')}</span></strong></div>
  <div class="metric"><small>Automatische maandafsluiting</small><strong class="auto-status"><span id="auto-close-top-status" class="pill {'ok' if auto_close.get('enabled') else 'neutral'}">{'Aan' if auto_close.get('enabled') else 'Uit'}</span><small id="auto-close-top-detail">{('dag ' + esc(auto_close.get('day')) + ' · ' + esc(auto_close.get('hour')) + ':00 · retry ' + esc(auto_close.get('retry_hours')) + 'u') if auto_close.get('enabled') else 'Scheduler niet actief'}</small></strong>  <div class="metric"><small>Releaseketen</small><strong><span class="pill ok">Automatisch</span></strong><small class="test-detail">QNAP ZIP-only · watcher 5 s · installatie automatisch</small></div>
  <div class="metric"><small>HA-publicatie</small><strong><span id="github-publish-pill" class="pill {esc(github_ui.get('css') or 'warn')}">{esc(github_ui.get('label') or 'Onbekend')}</span></strong><small id="github-publish-detail" class="test-detail">{esc(github_ui.get('detail') or 'Publicatiestatus niet beschikbaar')}</small><button class="secondary" type="button" onclick="refreshGithubPublisherStatus(true)">Toon publicatiesleutel</button><pre id="github-public-key" style="display:none;white-space:pre-wrap;word-break:break-all;margin-top:8px">{esc(github_ui.get('public_key') or 'Publicatiesleutel niet beschikbaar')}</pre><span style="display:none">Automatische GitHub-publicatie wordt door Home Assistant uitgevoerd · Deploy Key</span></div>
</div>
</div>

<div class="card"><h2>Sneloverzicht analyse</h2>
<div class="grid">
  <div class="metric"><small>Historie</small><strong>{esc(analysis_top.get('history'))}</strong><small>{esc(analysis_top.get('months'))} maand(en) · {esc(analysis_top.get('quarters'))} kwartaal(en) · {esc(analysis_top.get('years'))} jaar/jaren</small></div>
  <div class="metric"><small>Laatste analysemaand</small><strong>{esc(analysis_top.get('latest_month'))}</strong><small>Bronnen: {esc(analysis_top.get('latest_sources'))}</small></div>
  <div class="metric"><small>Datakwaliteit</small><strong><span class="pill {'warn' if analysis_top.get('quality') == 'Waarschuwing' else 'ok'}">{esc(analysis_top.get('quality'))}</span></strong><small>{esc(analysis_top.get('warning'))}</small></div>
  <div class="metric"><small>Leverancier</small><strong>NextEnergy</strong><small>Dynamische stroom · variabel gas · voorschot €150</small></div>
<div class="metric"><small>Financiële bouwstatus</small><strong>Financiële keten productie</strong><p class="hint">Analyse, prognose en officiële rapportkoppeling actief. Leverancier-all-in blijft veilig geblokkeerd totdat alle officiële contractcomponenten zijn gevalideerd. Officiële contractwaarden kunnen veilig worden ingelezen uit <code>00_Config/nextenergy_contract_costs.json</code>.</p></div>
  <div class="metric"><small>Analysedata</small><strong>Direct beschikbaar</strong><p><a class="button-link" href="download-analysis-data">Download analysedata</a></p><small><a href="analysis-context">Bekijk technische analysecontext</a></small></div>
<div class="metric"><small>Release-diagnose</small><strong>Ook bij mislukte release</strong><p><a class="button-link secondary" href="download-release-diagnostics">Download release-diagnose</a></p><small>Alleen watcher/publicatie/runtime; geen energiedata.</small></div>
</div>
</div>

<div class="card"><h2>Actuele voortgang</h2>
<div><strong id="progress-message">{esc(visual_progress.get('step') or 'Geen actieve workflow')}</strong></div>
<div class="progress"><span id="progress-bar" class="{'running' if visual_progress.get('running') else ''}"></span></div>
<div class="hint"><span id="progress-count">Stap {progress_current} van {progress_total}</span> · <span id="workflow-detail">{esc(visual_progress.get('detail') or 'Klaar om te starten')}</span> · <span id="workflow-eta">{('nog ongeveer ' + str(int(round(float(visual_progress.get('eta_seconds') or 0)))) + ' s') if visual_progress.get('running') else ''}</span></div>
</div>

<div class="card"><h2>Bediening</h2><div class="controls">
<div class="control-group"><h3>Centrale maandworkflow</h3>
<form method="post" action="start-month-workflow"><input type="month" name="month" value="{esc(default_month)}" required> <button type="submit" class="workflow-action"{disabled_attr}>Start maandverwerking</button></form>
<p class="hint">Start direct op de achtergrond; tijdens een actieve workflow worden andere workflowstarts geblokkeerd.</p>
{resume_html}
<form method="post" action="run-historical-month"><input type="month" name="month" value="{esc(default_month)}" required> <button type="submit" class="workflow-action"{disabled_attr}>Verwerk historische maand</button></form>
<p class="hint">Bij historische verwerking worden geen live snapshots toegevoegd.</p>
<form method="post" action="cancel"><button type="submit" class="danger">Annuleer actieve import</button></form>
</div>
<div class="control-group"><h3>Import en controle</h3>
<form method="post" action="run"><input name="month" type="month" value="{esc(default_month)}" required> <button type="submit">Importeer SMP</button></form>
<form method="post" action="verify"><button type="submit">Controleer laatste maand</button></form>
<form method="post" action="test-api"><button type="submit">Test API-verbinding</button></form>
<form method="post" action="self-test"><button type="submit" class="secondary">Voer volledige zelftest uit</button></form>
</div>
</div></div>

<div class="card"><h2>Productiestatus v{APP_VERSION}</h2><p class="hint">Productiekern: <strong>{esc(PRODUCTION_CORE_REVISION)}</strong> · een geldig kerncertificaat blijft bruikbaar bij releases die deze kern niet wijzigen.</p>
<div class="grid">
<div class="metric"><small>Productiegereedheid</small><strong><span id="production-readiness" class="pill {status_class(production_status)}">{esc(production_text)}</span></strong></div>
<div class="metric"><small>Scheduler</small><strong id="production-scheduler">{esc(scheduler_text)}</strong></div>
<div class="metric"><small>Volgende automatische run</small><strong id="production-next-run">{esc(next_auto_run_text)}</strong></div>
<div class="metric"><small>Laatste definitieve output</small><strong id="production-last-output">{esc(latest_output_text)}</strong></div>
<div class="metric"><small>Productiecertificaat</small><strong id="production-certificate">{esc(production_certificate_text)}</strong></div>
</div>
<p class="hint">Het productiecertificaat wordt automatisch gegenereerd uit een geslaagde productietest van exact deze versie, continu op integriteit gecontroleerd en kan veilig uit bestaand hard testbewijs worden hersteld.</p>
<div class="recovery-row"><strong>Automatisch herstel</strong> <span id="automatic-recovery-status" class="pill {status_class(recovery_status)}">{esc(recovery_label)}</span><div id="automatic-recovery-detail" class="hint">{esc(recovery_detail)}</div></div>
<p><a class="button-link" href="download-diagnostic-package">Download diagnosepakket</a> <a class="button-link secondary" href="download-chat-transfer">Download chat-overdracht</a></p>
<p class="hint">Bevat <strong>beoordeling.json</strong> met automatische technische GO/NO-GO en toont expliciet of het geldige kerncertificaat uit een eerdere release wordt hergebruikt.</p>
<p class="hint">Eén ZIP met samenvatting, SHA-256-controle en de status- en bewijsbestanden die nodig zijn om deze release goed of af te keuren. Bevat geen API-key of options.json.</p>
</div>

<div class="card"><h2>24/7 infrastructuur v{APP_VERSION}</h2>
<div class="grid">
<div class="metric"><small>Backend-runtime</small><strong><span class="pill ok">Actief</span></strong><p class="hint">Diagnose wordt live door backend gegenereerd; 0% CPU in Home Assistant kan normaal idle-gedrag zijn.</p></div>
<div class="metric"><small>QNAP-share</small><strong><span class="pill {status_class((op.get('infrastructure') or {}).get('status'))}">{esc((op.get('infrastructure') or {}).get('status') or 'onbekend')}</span></strong></div>
<div class="metric"><small>Back-updoel</small><strong>{esc((op.get('infrastructure') or {}).get('backup_root') or PROJECT_BACKUP_ROOT)}</strong></div>
<div class="metric"><small>Laatste projectback-up</small><strong>{esc(((op.get('infrastructure') or {}).get('last_backup') or {}).get('status') or 'nog geen')}</strong></div>
</div>
<p class="hint">{esc((op.get('infrastructure') or {}).get('message') or '')}</p>
<p class="hint">Voor externe 24/7 opslag koppel je in Home Assistant éénmalig de QNAP als netwerklocatie van type <strong>Share</strong> met naam <strong>Energie_NAS</strong>. Daarna schrijft de app na iedere geslaagde maandworkflow automatisch een gecontroleerde sidecarback-up weg; de iMac is niet nodig.</p>
</div>

<div class="card"><h2>NAS migratie &amp; release-inbox v{APP_VERSION}</h2>
<div class="grid">
<div class="metric"><small>Migratiestatus</small><strong><span class="pill {status_class((op.get('nas_migration') or {}).get('status'))}">{esc((op.get('nas_migration') or {}).get('status') or 'onbekend')}</span></strong></div>
<div class="metric"><small>Oude mappen gevonden</small><strong>{esc(len((op.get('nas_migration') or {}).get('legacy_found') or []))}</strong></div>
<div class="metric"><small>Release-inbox</small><strong>{esc(((op.get('nas_migration') or {}).get('release_inbox') or {}).get('status') or 'niet beschikbaar')}</strong></div>
</div>
<p class="hint">{esc((op.get('nas_migration') or {}).get('message') or '')}</p>
<p class="hint">v10.3 gebruikt de nieuwe NAS-master. Releases gaan via <code>EnergieProject/Inbox/incoming</code> en worden eerst technisch gevalideerd; backup en rollback blijven verplicht vóór live vervanging.</p>
<p><a href="migration-status">Technische migratiestatus</a></p>
</div>

<div class="card"><h2>Automatische maandafsluiting</h2>
<div class="controls">
<div class="control-group"><h3>Planning</h3>
<form id="automatic-planning-form" method="post" action="save-automatic-month-close">
<div class="switch-row">
<div><div class="switch-title">Automatisch vorige maand verwerken</div><div class="hint">Aan/Uit wordt direct opgeslagen. Dag, tijd en retry worden met Instellingen opslaan bewaard.</div></div>
<label class="switch-wrap" title="Automatische maandafsluiting aan of uit">
<input id="auto-close-enabled" type="checkbox" name="enabled" value="1" {'checked' if auto_close.get('enabled') else ''}>
<span class="switch-slider" aria-hidden="true"></span><span id="auto-close-switch-state" class="switch-state">{'AAN' if auto_close.get('enabled') else 'UIT'}</span>
</label>
</div>
<div class="planning-fields">
<label>Dag van de maand<input type="number" name="day" min="1" max="28" value="{esc(auto_close.get('day') or 2)}" required></label>
<label>Startuur<input type="number" name="hour" min="0" max="23" value="{esc(auto_close.get('hour') if auto_close.get('hour') is not None else 4)}" required></label>
<label>Retry na (uur)<input type="number" name="retry_hours" min="1" max="48" value="{esc(auto_close.get('retry_hours') or 6)}" required></label>
</div>
<p><button type="submit">Instellingen opslaan</button></p>
</form>
<p class="hint">De scheduler verwerkt normaal de vorige kalendermaand. Aan/Uit wordt direct opgeslagen; inschakelen blijft geblokkeerd totdat productiekern {esc(PRODUCTION_CORE_REVISION)} gecertificeerd is.</p>
</div>
<div class="control-group"><h3>Veilige productietest</h3>
<form method="post" action="test-automatic-month-close"><input type="month" name="month" value="{esc(auto_test_month)}" required> <button type="submit" class="secondary workflow-action"{disabled_attr}>Test automatische maandafsluiting nu</button></form>
<p class="hint">Voert preflight → echte maandworkflow → finalization uit, maar markeert de schedulermaand niet als reeds automatisch afgesloten.</p>
<form method="post" action="test-scheduler-acceptance"><button type="submit" class="secondary workflow-action"{disabled_attr}>Simuleer volgende scheduler-run nu</button></form>
<p class="hint">Test exact de echte schedulerroute. Als de actuele productiekern nog geen certificaat heeft, voert v{esc(APP_VERSION)} één veilige productietest uit. UI-/diagnostiekreleases met dezelfde kern hergebruiken daarna dit certificaat.</p>
<ul class="source-list">
<li><span>Scheduler-acceptatietest</span><span><span id="scheduler-acceptance-status" class="pill {status_class(scheduler_acceptance_status)}">{esc(scheduler_acceptance_status)}</span><small id="scheduler-acceptance-detail" class="test-detail">{esc(scheduler_acceptance_detail)}</small></span></li>
<li><span>Automatische gereedheid</span><span id="auto-readiness" class="pill {status_class(auto_ready_status)}">{esc(auto_ready_text)}</span></li>
<li><span>Laatste preflight</span><span id="auto-last-preflight" class="pill {status_class(auto_preflight.get('status'))}">{esc(auto_preflight.get('status') or 'Nog niet getest')}</span></li>
<li><span>Laatste finalization</span><span id="auto-last-finalization" class="pill {status_class(auto_finalization.get('status'))}">{esc(auto_finalization.get('status') or 'Nog niet getest')}</span></li>
<li><span>Laatste productietest</span><span><span id="auto-last-test" class="pill {status_class(auto_test_display_status)}">{esc(auto_test_display_status)}</span><small id="auto-last-test-detail" class="test-detail">{esc(auto_test_display_detail)}</small></span></li>
</ul>
</div>
</div></div>

<div class="card"><h2>Automatische maandhistorie</h2>
<div class="table-wrap"><table>
<thead><tr><th>Maand</th><th>Type</th><th>Versie</th><th>Status</th><th>Eindcontrole</th><th>Afgerond</th><th>Duur</th></tr></thead>
<tbody id="automatic-history-body">{auto_history_rows}</tbody>
</table></div>
<p class="hint">Append-only historie: iedere test, scheduler-test en echte automatische run blijft als afzonderlijk record bewaard.</p>
</div>

<div class="card" id="production-certificates"><details class="compact-details"><summary>Archief productiecertificaten</summary>
<div class="table-wrap"><table>
<thead><tr><th>Release</th><th>Productiekern</th><th>Afgegeven</th><th>Status</th><th>Testmaand</th></tr></thead>
<tbody id="production-certificate-history-body">{certificate_history_rows}</tbody>
</table></div>
<p class="hint">Append-only archief van eerder afgegeven productiecertificaten. Alleen het certificaat van de actieve versie bepaalt de huidige productiegereedheid.</p>
<p><button id="manage-production-certificate-button" type="button" class="secondary">Controleer / herstel productiecertificaat</button></p>
<p><span id="production-certificate-management-status" class="pill {status_class(production_certificate_management_status)}">{esc(production_certificate_management_text)}</span></p>
<p class="hint">Herstel is alleen toegestaan uit aantoonbaar geslaagd testbewijs van de actuele productiekern {esc(PRODUCTION_CORE_REVISION)}; er wordt nooit een certificaat zonder testbewijs aangemaakt.</p>
<p><a href="download-production-certificate">Download huidig productiecertificaat</a></p>
</details></div>


<div class="card" id="complete-crash-recovery">
<h2>Complete Crash Recovery</h2>
<div class="metrics">
<div class="metric"><small>Status</small><strong id="complete-recovery-status">Nog niet uitgevoerd</strong></div>
<div class="metric"><small>Backup</small><strong id="complete-recovery-name">-</strong></div>
<div class="metric"><small>Deep verify</small><strong id="complete-recovery-count">-</strong></div>
<div class="metric"><small>Export bestanden</small><strong id="complete-recovery-export-count">-</strong></div>
<div class="metric"><small>SHA-256</small><strong id="complete-recovery-sha">-</strong></div>
</div>
<p>
<button id="run-complete-crash-recovery-button" type="button">Maak complete Crash Recovery</button>
<button id="download-complete-crash-recovery-button" type="button" class="secondary" disabled onclick="window.location.href='api/crash-recovery/download'">Download Crash Recovery ZIP</button>
<button id="run-complete-restore-staging-button" type="button" class="secondary" disabled>Test herstel naar RestoreStaging</button>
</p>
<p id="complete-recovery-detail" class="hint">Maakt de volledige EnergieProject-browserbackup voor eigen opslag in iCloud. Sluit de maand niet af en RestoreStaging overschrijft geen productiedata.</p>
</div>

<div class="card" id="recovery-v817"><details class="compact-details"><summary>Recovery v{APP_VERSION}</summary>
<div class="metrics"><div class="metric"><small>Status</small><strong><span id="recovery-controller-status" class="pill {status_class(recovery_controller_status)}">{esc(recovery_controller_status)}</span></strong></div><div class="metric"><small>Herstelacties</small><strong id="recovery-controller-count">{esc(recovery_controller_count)}</strong></div><div class="metric"><small>Laatste controle</small><strong id="recovery-controller-checked">{esc(recovery_controller_checked)}</strong></div></div>
<p id="recovery-controller-detail" class="hint">{esc(recovery_controller_detail)}</p>
<p><button id="run-recovery-controller-button" type="button" class="secondary">Controleer recovery nu</button></p>
<p class="hint">Controleert en reconcilieert uitsluitend duurzame status uit bestaand hard bewijs. Start nooit zelfstandig een maandworkflow en wijzigt geen ongeldige auditketen.</p>
</details></div>

<div class="card" id="monitoring-v818"><h2>Monitoring v{APP_VERSION}</h2>
<div class="metrics"><div class="metric"><small>Status</small><strong><span id="monitoring-status" class="pill {status_class(monitoring_status)}">{esc(monitoring_status)}</span></strong></div><div class="metric"><small>Fouten</small><strong id="monitoring-error-count">{esc(monitoring_errors)}</strong></div><div class="metric"><small>Wachtstatussen</small><strong id="monitoring-attention-count">{esc(monitoring_pending)}</strong></div><div class="metric"><small>Laatste controle</small><strong id="monitoring-checked">{esc(monitoring_checked)}</strong></div></div>
<details><summary>Monitoringdetails</summary>
<ul class="source-list" id="monitoring-checks">{monitoring_rows}</ul>
<p><button id="run-monitoring-button" type="button" class="secondary">Controleer monitoring nu</button> <a href="download-monitoring-history">Download monitoringhistorie</a></p>
<p class="hint">Bewaakt API, workflow, productiecertificaat, audittrail, recovery, scheduler en bronstatus. Alleen statuswijzigingen worden append-only opgeslagen; monitoring start zelf geen workflow.</p>
</details></div>

<div class="card"><details class="compact-details"><summary>Audittrail v{APP_VERSION}</summary>
<div class="metrics"><div class="metric"><small>Integriteit</small><strong id="audit-integrity">{esc(audit_validation.get('status') or 'empty')}</strong></div><div class="metric"><small>Records</small><strong id="audit-record-count">{esc(audit_validation.get('records', 0))}</strong></div></div>
<div class="table-wrap"><table><thead><tr><th>Moment</th><th>Type</th><th>Actie</th><th>Status</th><th>Maand</th></tr></thead><tbody id="audit-trail-body">{audit_rows}</tbody></table></div>
<p class="hint">Append-only, hash-gekoppelde audittrail van workflows, productietests, schedulerwijzigingen, scheduler-acceptatietests en productiecertificaten.</p>
<p><a href="download-audit-trail">Download audittrail</a></p>
</details></div>


<div class="card" id="smp-import-status-card"><h2>Laatste SMP-import</h2>
<div><strong>Maand:</strong> {esc(state.get('last_target_month') or 'Nog geen')}</div>
<div><strong>Status:</strong> <span class="pill {status_class(state.get('status'))}">{esc(state.get('status') or 'Nog geen')}</span></div>
<div class="hint"><strong>Gestart:</strong> {esc(state.get('last_started') or '—')} · <strong>Afgerond:</strong> {esc(state.get('last_finished') or '—')}</div>
<div><strong>HA → NAS SMP:</strong> <span class="pill {status_class(state.get('smp_nas_transfer_last_status'))}">{esc(state.get('smp_nas_transfer_last_status') or 'Nog geen')}</span> {esc(state.get('smp_nas_transfer_last_path') or '')}</div>
<div style="display:{'block' if state.get('last_error') else 'none'}"><strong>Fouttype:</strong> {esc(state.get('last_error_type') or '—')}<div class="log">{esc(state.get('last_error') or '')}</div></div>
<div style="display:{'block' if state.get('last_traceback') else 'none'}"><strong>Traceback:</strong><div class="log">{esc(state.get('last_traceback') or '')}</div></div>
<p><a id="download-smp-import-diagnose" href="download-smp-import-diagnose">Download SMP-importdiagnose</a></p>
<p class="hint">Dit blok hoort uitsluitend bij de knop <strong>Importeer SMP</strong>. Het blok Laatste workflowfout hieronder hoort bij de volledige maandworkflow.</p>
</div>

<div class="card" id="last-error-card" style="display:{'block' if last_run.get('error') else 'none'}"><h2>Laatste workflowfout</h2>
<div><strong id="last-error-step">{esc(last_run.get('error_step') or last_run.get('step') or '—')}</strong></div>
<div class="hint" id="last-error-type">{esc(last_run.get('error_type') or '')}</div>
<div id="last-error-message" class="log">{esc(last_run.get('error') or '')}</div>
<p><a id="download-workflow-log" href="download-workflow-log?month={esc(last_run.get('month') or '')}">Download workflowlog</a></p>
</div>

<div class="card"><h2>Gezondheidsdashboard</h2>
<div class="controls"><div><div class="score" id="health-score">{health_score}%</div><p class="hint">Systeemgezondheid: normale wachtstatussen tijdens versiecertificering zijn geen fout; echte storingen wegen zwaar.</p></div><ul class="source-list" id="health-checks">{health_rows}</ul></div>
</div>

<div class="card"><details class="compact-details"><summary>Live workflowlog</summary>
<div id="workflow-log" class="log">Log voor {esc(log_month or 'geen maand geselecteerd')} wordt automatisch bijgewerkt.</div>
<p><a id="live-log-download" href="download-workflow-log?month={esc(log_month or '')}">Download workflowlog</a></p>
</details></div>

<div class="card"><h2>Historische runs</h2><div class="table-wrap"><table><thead><tr><th>Maand</th><th>Status</th><th>Stappen</th><th>Duur</th><th>Mislukte stap</th><th>Afgerond</th><th>Log</th></tr></thead><tbody>{history_html}</tbody></table></div></div>

<div class="card"><h2>Bronstatus</h2><ul class="source-list">{source_items}</ul></div>

<div class="card"><h2>Downloads</h2><ul>{downloads}</ul></div>

<div class="card"><h2>Diagnostiek en beheer</h2>
<div class="grid">
<div class="metric"><small>API-test</small><strong>{esc(api_text)}</strong></div>
<div class="metric"><small>Centrale validatie</small><strong>{esc((state.get('last_central_validation') or {}).get('status', 'Nog niet uitgevoerd'))}</strong></div>
<div class="metric"><small>Integriteit</small><strong>{esc(state.get('last_integrity_status') or 'Nog niet gecontroleerd')}</strong></div>
<div class="metric"><small>Zelftest</small><strong>{esc((state.get('last_self_test') or {}).get('status', 'Nog niet uitgevoerd'))}</strong></div>
</div>
<details><summary>Retry Debug v{APP_VERSION}</summary>
<div class="table-wrap"><table>
<tbody>
<tr><th>Retry-maand</th><td>{esc(retry_debug.get('month_checked') or '—')}</td></tr>
<tr><th>Retry-state</th><td>{esc(retry_debug_decision.get('state') or 'GEEN')}</td></tr>
<tr><th>Reden</th><td>{esc(retry_debug_decision.get('reason') or '—')}</td></tr>
<tr><th>Bron state</th><td>{esc(retry_debug.get('retry_state_path') or '—')} · {'FOUND' if retry_debug.get('retry_state_file_exists') else 'NOT FOUND'}</td></tr>
<tr><th>Legacy bronstatus (historisch)</th><td>maand {esc(retry_debug_legacy.get('last_month') or '—')} · status {esc(retry_debug_legacy.get('last_status') or '—')} · retry {esc(format_local_datetime(retry_debug_legacy.get('next_retry')) if retry_debug_legacy.get('next_retry') else '—')} · alleen diagnose</td></tr>
<tr><th>Completion marker</th><td>{'FOUND' if retry_debug_marker.get('found') else 'NOT FOUND'} · bewijs {'JA' if retry_debug_marker.get('proves_completed') else 'NEE'}</td></tr>
<tr><th>Append history</th><td>{len(retry_debug_ledger.get('matching_records') or [])} record(s) · bewijs {'JA' if retry_debug_ledger.get('proves_completed') else 'NEE'}</td></tr>
<tr><th>Workflow_result</th><td>{'FOUND' if retry_debug_workflow.get('exists') else 'NOT FOUND'} · bewijs {'JA' if retry_debug_workflow.get('proves_completed') else 'NEE'} · {esc(retry_debug_workflow.get('decision') or '—')}</td></tr>
<tr><th>Workflow checks</th><td>{esc(json.dumps(retry_debug_workflow.get('checks') or {}, ensure_ascii=False))}</td></tr>
<tr><th>Beslissing/evidence</th><td>{esc(retry_debug_decision.get('evidence') or '—')}</td></tr>
<tr><th>Productiecertificaat</th><td id="retry-debug-certificate">{'FOUND' if production_certificate_validation.get('exists') else 'NOT FOUND'} · geldig {'JA' if production_certificate_validation.get('valid') else 'NEE'}</td></tr>
<tr><th>Certificaatrelease</th><td id="retry-debug-certificate-version">{esc(production_certificate_validation.get('version') or '—')} · actieve release {esc(APP_VERSION)}</td></tr>
<tr><th>Productiekern</th><td>{esc(production_certificate_validation.get('production_core_revision') or 'legacy')} · verwacht {esc(PRODUCTION_CORE_REVISION)}</td></tr>
<tr><th>Certificaatintegriteit</th><td id="retry-debug-certificate-integrity">{esc(production_certificate_validation.get('integrity') or 'not_checked')}</td></tr>
<tr><th>Certificaatpad</th><td>{esc(production_certificate_validation.get('path') or PRODUCTION_CERTIFICATE_PATH)}</td></tr>
<tr><th>Retry debuglog</th><td>{esc(retry_debug.get('debug_log_path') or RETRY_DEBUG_LOG_PATH)}</td></tr>
<tr><th>Finalization debuglog</th><td>{esc(auto_close.get('finalization_debug_log_path') or FINALIZATION_DEBUG_LOG_PATH)}</td></tr>
<tr><th>Laatste finalization-event</th><td>{esc(finalization_debug_last.get('event') or 'Nog geen nieuwe run voor deze versie')}</td></tr>
<tr><th>Finalization events</th><td>{esc(' → '.join(str(row.get('event') or '?') for row in finalization_debug[-12:]) or 'Nog geen')}</td></tr>
</tbody></table></div>
<p class="hint">Legacy bronstatus is uitsluitend historisch diagnosebewijs. De actuele retry-, workflow- en productiestatus worden bepaald door de duurzame workflow_result- en certificaatvalidatie hierboven.</p>
</details>
<details><summary>Databronnen en snapshots</summary>
<form method="post" action="homewizard-discover"><button type="submit">Detecteer HomeWizard-apparaten</button></form>
<p class="hint">Scanbereik: instelling <code>homewizard_discovery_cidr</code>.</p>
<p class="hint">HomeWizard netwerk: {esc(state.get('homewizard_discovery_cidr') or 'Niet bepaald')}</p>
<form method="post" action="homeassistant-energy-snapshot"><button type="submit">Maak HA energiesnapshot</button></form>
<form method="post" action="homewizard-snapshot"><button type="submit">Maak HomeWizard snapshot</button></form>
<form method="post" action="enphase-import"><button type="submit">Importeer Enphase</button></form>
<form method="post" action="epex-electricity-import"><button type="submit">Importeer EPEX elektriciteit</button></form>
<form method="post" action="epex-gas-import"><button type="submit">Importeer EPEX gas</button></form>
<form method="post" action="epex-import-validate"><button type="submit">Importeer en valideer EPEX</button></form>
</details>
<details><summary>Compatibiliteitsbediening</summary>
<p class="hint">Bestaande 7.0.x-route blijft beschikbaar voor achterwaartse compatibiliteit.</p>
<form method="post" action="run-full-month-workflow"><input type="month" name="month" value="{esc(default_month)}" required> <button type="submit" class="secondary">Verwerk maanddata (legacy)</button></form>
</details>
<div class="card">
<h2>Rapportage</h2>
<p>De rapportpagina is nu rechtstreeks zichtbaar in de Web UI.</p>
<p><a class="button-link" href="reports">Open rapportpagina</a></p>
</div>
<details><summary>Rapportage en overdracht</summary>
<form method="post" action="build-month-input"><button type="submit">Bouw maandmap</button></form>
<form method="post" action="central-validation"><button type="submit">Voer centrale validatie uit</button></form>
<form method="post" action="create-transfer-package"><button type="submit">Maak overdrachtspakket</button></form>
<form method="post" action="check-report-runtime"><button type="submit">Controleer rapportmodules</button></form>
<form method="post" action="build-report-adapter"><button type="submit">Bouw rapportdata-adapter</button></form>
<form method="post" action="install-report-generators"><button type="submit">Installeer officiële rapportgeneratoren</button></form>
<form method="post" action="run-report-page1"><button type="submit">Test rapportgenerator pagina 1</button></form>
<form method="post" action="report-service-check"><button type="submit">Controleer rapportservice</button></form>
<form method="post" action="run-report-generation"><button type="submit">Genereer compleet maandrapport</button></form>
</details>
<p class="links"><a href="analysis-context">Technische analysecontext</a> · <a href="status.json">Technische status</a> · <a href="report-generation-status">Rapportstatus</a> · <a href="workflow-audit-status">Eindcontrole</a> · <a href="workflow-summary">Samenvatting</a> · <a href="workflow-lock-status">Workflowstatus</a> · <a href="operation-status">Operationele status</a> · <a href="health-dashboard">Gezondheidsdashboard</a> · <a href="health">Healthcheck</a></p>
<p class="hint">API-key en algemene importplanning staan op het tabblad <strong>Configuratie</strong>. De automatische maandafsluiting kan vanaf v7.6 ook hierboven worden ingesteld.</p>
</div>
<script>
function escapeHtml(value){{
  return String(value??'').replace(/[&<>"']/g, ch=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}}[ch]));
}}
function formatLocalDateTime(value){{
  if(!value) return 'Niet gepland';
  const d=new Date(value);
  if(Number.isNaN(d.getTime())) return String(value);
  return new Intl.DateTimeFormat('nl-NL',{{day:'2-digit',month:'2-digit',year:'numeric',hour:'2-digit',minute:'2-digit',hour12:false}}).format(d).replace(',','');
}}
async function refreshStatus(){{
  try{{
    const [statusResp, opResp] = await Promise.all([fetch('status.json',{{cache:'no-store'}}),fetch('operation-status',{{cache:'no-store'}})]);
    if(!statusResp.ok || !opResp.ok) return;
    const st=await statusResp.json(), op=await opResp.json();
    const vp=op.visual_progress||{{}};
    const pct=Number(vp.percent||0);
    const bar=document.getElementById('progress-bar');
    bar.style.width=pct+'%';
    bar.className=vp.running?'running':'';
    document.getElementById('progress-count').textContent='Stap '+Number(vp.step_index||0)+' van '+Number(vp.steps_total||8);
    document.getElementById('progress-message').textContent=vp.step || 'Geen actieve workflow';
    document.getElementById('workflow-detail').textContent=vp.detail || 'Klaar om te starten';
    const eta=Number(vp.eta_seconds);
    document.getElementById('workflow-eta').textContent=vp.running && Number.isFinite(eta)?'nog ongeveer '+Math.max(0,Math.round(eta))+' s':'';
    const workflowStatus=document.getElementById('workflow-status');
    const lastRunStatus=document.getElementById('last-run-status');
    const pillClass=(value)=>{{
      const v=String(value||'').toLowerCase();
      if(['completed','ok','ready','idle','completed_warning'].includes(v)) return 'pill ok';
      if(['running','importing','warning','pending','attention'].includes(v)) return 'pill warn';
      if(['error','failed','unreadable'].includes(v)) return 'pill bad';
      return 'pill neutral';
    }};
    workflowStatus.textContent=op.workflow?.status || 'onbekend';
    workflowStatus.className=pillClass(op.workflow?.status);
    document.getElementById('last-month').textContent=op.last_run?.month || 'Nog geen';
    lastRunStatus.textContent=op.last_run?.status || 'Nog geen';
    lastRunStatus.className=pillClass(op.last_run?.status);

    const active=['running','importing'].includes(String(op.workflow?.status||'').toLowerCase());
    document.querySelectorAll('.workflow-action').forEach(btn=>btn.disabled=active);

    const auto=op.automatic_month_close||{{}};
    const topAuto=document.getElementById('auto-close-top-status');
    const topDetail=document.getElementById('auto-close-top-detail');
    if(topAuto){{
      topAuto.textContent=auto.enabled?'Aan':'Uit';
      topAuto.className=auto.enabled?'pill ok':'pill neutral';
    }}
    if(topDetail){{
      topDetail.textContent=auto.enabled?`dag ${{auto.day}} · ${{auto.hour}}:00 · retry ${{auto.retry_hours}}u`:'Scheduler niet actief';
    }}
    [['auto-last-preflight',auto.last_preflight?.status],['auto-last-finalization',auto.last_finalization?.status]].forEach(([id,value])=>{{
      const el=document.getElementById(id); if(el){{el.textContent=value||'Nog niet getest'; el.className=pillClass(value);}}
    }});
    const test=auto.test_last_result||{{}};
    const currentTestVersion=String(test.version||'')===String(op.version||'');
    const testStatus=currentTestVersion?(test.status||'Nog niet getest'):(test.status?'Opnieuw testen':'Nog niet getest');
    const testEl=document.getElementById('auto-last-test');
    if(testEl){{testEl.textContent=testStatus; testEl.className=pillClass(currentTestVersion?test.status:'stale');}}
    const testDetail=document.getElementById('auto-last-test-detail');
    if(testDetail){{
      testDetail.textContent=currentTestVersion?(test.error||''):(test.status?`Laatste test was met versie ${{test.version||'onbekend'}}.`:'');
    }}
    const testOk=currentTestVersion && ['completed','completed_warning'].includes(String(test.status||'')) && test.preflight?.status==='ok' && test.finalization?.status==='ok';
    const prod=auto.production_readiness||{{}};
    const prodEl=document.getElementById('production-readiness');
    if(prodEl){{
      prodEl.textContent=prod.ready?'Productieklaar':`Test vereist voor v${{op.version||''}}`;
      prodEl.className=pillClass(prod.ready?'ready':'pending');
    }}
    const prodScheduler=document.getElementById('production-scheduler');
    if(prodScheduler) prodScheduler.textContent=auto.scheduler_effective?'Actief':(auto.enabled?`Wacht op v${{op.version||''}}-test`:'Uit');
    const prodNext=document.getElementById('production-next-run');
    if(prodNext) prodNext.textContent=formatLocalDateTime(auto.next_scheduled_run);
    const certValidation=auto.production_certificate||{{}};
    const cert=certValidation.certificate||{{}};
    const prodCert=document.getElementById('production-certificate');
    if(prodCert){{
      prodCert.textContent=certValidation.valid?`v${{cert.version||op.version||''}} · Afgegeven · ${{formatLocalDateTime(cert.accepted_at)}}`:(String(certValidation.version||'')!==String(op.version||'')?`Nog niet gecertificeerd — test v${{op.version||''}} vereist`:`Certificaat vereist aandacht — ${{certValidation.status||'ontbreekt'}}`);
    }}
    const retryDebugCert=document.getElementById('retry-debug-certificate');
    if(retryDebugCert) retryDebugCert.textContent=`${{certValidation.exists?'FOUND':'NOT FOUND'}} · geldig ${{certValidation.valid?'JA':'NEE'}}`;
    const retryDebugCertVersion=document.getElementById('retry-debug-certificate-version');
    if(retryDebugCertVersion) retryDebugCertVersion.textContent=`${{certValidation.version||'—'}} · verwacht ${{op.version||''}}`;
    const retryDebugCertIntegrity=document.getElementById('retry-debug-certificate-integrity');
    if(retryDebugCertIntegrity) retryDebugCertIntegrity.textContent=certValidation.integrity||'not_checked';
    const certHistoryBody=document.getElementById('production-certificate-history-body');
    if(certHistoryBody && Array.isArray(auto.production_certificate_history)){{
      certHistoryBody.innerHTML=auto.production_certificate_history.length?auto.production_certificate_history.map(item=>`<tr><td>${{escapeHtml(item.version||'—')}}</td><td>${{escapeHtml(item.accepted_at?formatLocalDateTime(item.accepted_at):'—')}}</td><td><span class="${{pillClass(item.status)}}">${{escapeHtml(item.status||'—')}}</span></td><td>${{escapeHtml(item.month||'—')}}</td></tr>`).join(''):`<tr><td colspan="4">Nog geen productiecertificaten.</td></tr>`;
    }}

    const autoHistory=document.getElementById('automatic-history-body');
    if(autoHistory && Array.isArray(auto.history)){{
      autoHistory.innerHTML=auto.history.length?auto.history.map(item=>`<tr><td>${{escapeHtml(item.month||'—')}}</td><td>${{escapeHtml(item.run_type||'Automatisch')}}</td><td>${{escapeHtml(item.version||'—')}}</td><td><span class="${{pillClass(item.status)}}">${{escapeHtml(item.status||'—')}}</span></td><td><span class="${{pillClass(item.finalization_status)}}">${{escapeHtml(item.finalization_status||'—')}}</span></td><td>${{escapeHtml(item.finished_at?formatLocalDateTime(item.finished_at):'—')}}</td><td>${{item.duration_seconds==null?'—':Number(item.duration_seconds).toFixed(1)+' s'}}</td></tr>`).join(''):`<tr><td colspan="7">Nog geen automatische runs geregistreerd.</td></tr>`;
    }}

    const acceptance=auto.scheduler_acceptance_last_result||{{}};
    const acceptanceCurrent=String(acceptance.version||'')===String(op.version||'');
    const acceptanceStatus=acceptanceCurrent?(acceptance.status||'Nog niet getest'):(acceptance.status?'Opnieuw testen':'Nog niet getest');
    const acceptanceEl=document.getElementById('scheduler-acceptance-status');
    if(acceptanceEl){{acceptanceEl.textContent=acceptanceStatus; acceptanceEl.className=pillClass(acceptanceCurrent?acceptance.status:'stale');}}
    const acceptanceDetail=document.getElementById('scheduler-acceptance-detail');
    if(acceptanceDetail){{acceptanceDetail.textContent=acceptanceCurrent&&acceptance.simulated_at?`Gesimuleerd voor ${{formatLocalDateTime(acceptance.simulated_at)}} · doelmaand ${{acceptance.month||'—'}}${{acceptance.prerequisite_product_test_ran===true?' · voorbereidende productietest automatisch geslaagd':''}}${{acceptance.scheduler_enabled_unchanged===true?' · schedulerinstelling ongewijzigd':''}}`:'';}}

    const recovery=auto.recovery||{{}};
    const recoveryStatus=document.getElementById('automatic-recovery-status');
    if(recoveryStatus){{recoveryStatus.textContent=recovery.label||'Geen herstelactie nodig'; recoveryStatus.className=pillClass(recovery.status||'ready');}}
    const recoveryDetail=document.getElementById('automatic-recovery-detail');
    if(recoveryDetail){{recoveryDetail.textContent=recovery.detail||'';}}

    const ready=document.getElementById('auto-readiness');
    if(ready){{
      const running=currentTestVersion && test.status==='running';
      ready.textContent=testOk?'Klaar voor automatisch gebruik':(running?'Productietest loopt':'Productietest vereist');
      ready.className=pillClass(testOk?'ready':(running?'running':'pending'));
    }}

    document.getElementById('health-score').textContent=(op.health?.score ?? 0)+'%';
    const healthChecks=document.getElementById('health-checks');
    if(healthChecks && Array.isArray(op.health?.checks)){{
      healthChecks.innerHTML=op.health.checks.map(x=>`<li><span>${{escapeHtml(x.name||'')}}</span><span><span class="${{pillClass(x.status)}}">${{escapeHtml(x.status||'')}}</span> ${{escapeHtml(x.detail||'')}}</span></li>`).join('');
    }}

    const monitoring=op.monitoring||{{}};
    const monitoringStatus=document.getElementById('monitoring-status');
    const monitoringErrors=document.getElementById('monitoring-error-count');
    const monitoringAttention=document.getElementById('monitoring-attention-count');
    const monitoringChecked=document.getElementById('monitoring-checked');
    const monitoringChecks=document.getElementById('monitoring-checks');
    if(monitoringStatus){{monitoringStatus.textContent=monitoring.status||'unknown';monitoringStatus.className=pillClass(monitoring.status);}}
    if(monitoringErrors) monitoringErrors.textContent=String(monitoring.active_errors??0);
    if(monitoringAttention) monitoringAttention.textContent=String(monitoring.pending_points??monitoring.attention_points??0);
    if(monitoringChecked) monitoringChecked.textContent=monitoring.checked_at?formatLocalDateTime(monitoring.checked_at):'Nog niet gecontroleerd';
    if(monitoringChecks && Array.isArray(monitoring.checks)){{
      monitoringChecks.innerHTML=monitoring.checks.map(item=>`<li><span>${{escapeHtml(item.name||'—')}}</span><span><span class="${{pillClass(item.status)}}">${{escapeHtml(item.status||'—')}}</span> ${{escapeHtml(item.detail||'')}}</span></li>`).join('');
    }}
    const audit=op.audit_trail||{{}};
    const auditValidation=audit.validation||{{}};
    const auditIntegrity=document.getElementById('audit-integrity');
    const auditCount=document.getElementById('audit-record-count');
    const auditBody=document.getElementById('audit-trail-body');
    if(auditIntegrity) auditIntegrity.textContent=auditValidation.status||'empty';
    if(auditCount) auditCount.textContent=String(auditValidation.records??0);
    if(auditBody && Array.isArray(audit.events)){{
      auditBody.innerHTML=audit.events.length?audit.events.map(item=>`<tr><td>${{escapeHtml(item.recorded_at?formatLocalDateTime(item.recorded_at):'—')}}</td><td>${{escapeHtml(item.event_type||'—')}}</td><td>${{escapeHtml(item.action||'—')}}</td><td><span class="${{pillClass(item.status)}}">${{escapeHtml(item.status||'—')}}</span></td><td>${{escapeHtml(item.month||'—')}}</td></tr>`).join(''):`<tr><td colspan="5">Nog geen auditrecords.</td></tr>`;
    }}

    const recoveryController=op.recovery_controller||{{}};
    const recoveryControllerStatus=document.getElementById('recovery-controller-status');
    const recoveryControllerCount=document.getElementById('recovery-controller-count');
    const recoveryControllerChecked=document.getElementById('recovery-controller-checked');
    const recoveryControllerDetail=document.getElementById('recovery-controller-detail');
    if(recoveryControllerStatus){{recoveryControllerStatus.textContent=recoveryController.status||'not_checked'; recoveryControllerStatus.className=pillClass(recoveryController.status||'neutral');}}
    if(recoveryControllerCount) recoveryControllerCount.textContent=String(recoveryController.repair_count??0);
    if(recoveryControllerChecked) recoveryControllerChecked.textContent=formatLocalDateTime(recoveryController.checked_at);
    if(recoveryControllerDetail){{
      const warns=Array.isArray(recoveryController.warnings)?recoveryController.warnings:[];
      const count=Number(recoveryController.repair_count||0);
      recoveryControllerDetail.textContent=(count?`${{count}} herstelactie(s) uitgevoerd`:(recoveryController.checked_at?'Controle zonder herstelacties':'Nog niet gecontroleerd'))+(warns.length?' · '+warns.join('; '):'');
    }}

    const certMgmt=auto.production_certificate_management||{{}};
    const certMgmtEl=document.getElementById('production-certificate-management-status');
    if(certMgmtEl && Object.keys(certMgmt).length){{
      const valid=Boolean(certMgmt.valid);
      certMgmtEl.textContent=valid?(certMgmt.repaired?'Certificaat hersteld — geldig':'Certificaat gecontroleerd — geldig'):'Certificaatcontrole vereist aandacht';
      certMgmtEl.className=pillClass(valid?'ok':'warning');
    }}
    const errCard=document.getElementById('last-error-card');
    if(op.last_run?.error){{
      errCard.style.display='block';
      document.getElementById('last-error-step').textContent=op.last_run?.error_step || op.last_run?.step || '—';
      document.getElementById('last-error-type').textContent=op.last_run?.error_type || '';
      document.getElementById('last-error-message').textContent=op.last_run?.error || '';
      document.getElementById('download-workflow-log').href='download-workflow-log?month='+encodeURIComponent(op.last_run?.month || '');
    }}else{{ errCard.style.display='none'; }}
    const month=op.workflow?.month || op.last_run?.month;
    if(month){{
      const lines=Array.isArray(op.live_log) ? op.live_log : [];
      const text=lines.map(x=>{{
        let line=`${{x.timestamp||''}} [${{String(x.level||'info').toUpperCase()}}] ${{x.step?x.step+': ':''}}${{x.message||''}}${{x.heartbeat_message?' — '+x.heartbeat_message:''}}${{x.error?' — '+x.error:''}}`;
        if(x.traceback) line+='\\n'+x.traceback;
        return line;
      }}).join('\\n');
      const box=document.getElementById('workflow-log');
      box.textContent=text || 'Nog geen logregels voor '+month;
      box.scrollTop=box.scrollHeight;
      document.getElementById('live-log-download').href='download-workflow-log?month='+encodeURIComponent(month);
    }}
  }}catch(_e){{}}
}}
const certMgmtButton=document.getElementById('manage-production-certificate-button');
if(certMgmtButton){{
  certMgmtButton.addEventListener('click', async()=>{{
    certMgmtButton.disabled=true;
    try{{
      const response=await fetch('manage-production-certificate',{{method:'POST',headers:{{'X-Requested-With':'fetch','Accept':'application/json'}}}});
      const result=await response.json();
      if(!response.ok) throw new Error(result.error||'Certificaatcontrole mislukt');
      await refreshStatus();
      const target=document.getElementById('production-certificates'); if(target) target.scrollIntoView({{block:'start'}});
    }}catch(err){{alert(String(err.message||err));}}finally{{certMgmtButton.disabled=false;}}
  }});
}}

function renderCompleteRecovery(result){{
  const downloadButton=document.getElementById('download-complete-crash-recovery-button');
  const canDownload=['ready_for_download','retry_available'].includes(String(result.status||'')) || ['ready','retry_available'].includes(String(result.download_status||''));
  if(downloadButton) downloadButton.disabled=!canDownload;
  const status=document.getElementById('complete-recovery-status');
  const name=document.getElementById('complete-recovery-name');
  const count=document.getElementById('complete-recovery-count');
  const exportCount=document.getElementById('complete-recovery-export-count');
  const sha=document.getElementById('complete-recovery-sha');
  const detail=document.getElementById('complete-recovery-detail');
  const stage=document.getElementById('run-complete-restore-staging-button');
  if(status) status.textContent=String(result.status||'Nog niet uitgevoerd');
  if(name) name.textContent=String(result.export_name||result.backup_name||'-');
  if(count){{
    const verified=Number(result.verified_files||0);
    const total=Number(result.manifest_file_count||0);
    count.textContent=(verified&&total)?`${{verified}} / ${{total}}`:'-';
  }}
  if(exportCount) exportCount.textContent=String(result.export_file_count||'-');
  if(sha) sha.textContent=String(result.export_sha256||result.backup_sha256||result.sha256||'-');
  if(detail){{
    if(result.error) detail.textContent=String(result.error);
    else if(result.status==='retry_available'||result.download_status==='retry_available') detail.textContent='De download is afgebroken; niets is opgeruimd. Je kunt opnieuw downloaden.';
    else if(result.status==='ready_for_download') detail.textContent='Crash Recovery is volledig geverifieerd en RestoreStaging is geslaagd. Download de ZIP en bewaar hem zelf in iCloud.';
    else if(result.status==='downloaded'&&result.cleanup_status==='ok') detail.textContent='Download afgerond; tijdelijke Crash-Recovery-bestanden op de NAS zijn opgeruimd.';
    else if(result.status==='downloaded') detail.textContent='Download afgerond; tijdelijke cleanup heeft aandacht nodig.';
    else if(result.restore_test_status==='staged') detail.textContent='Hersteltest geslaagd in geïsoleerde RestoreStaging.';
    else if(result.status==='verified') detail.textContent='Complete Crash Recovery is deep geverifieerd. Augustus/lopende maand is niet afgesloten.';
  }}
  if(stage) stage.disabled=!(result.status==='verified' && result.deep_verified && result.backup_name);
}}

async function refreshCompleteRecovery(){{
  try{{
    const response=await fetch('api/crash-recovery/state',{{headers:{{'Accept':'application/json'}}}});
    if(response.ok) renderCompleteRecovery(await response.json());
  }}catch(_err){{}}
}}

const completeRecoveryButton=document.getElementById('run-complete-crash-recovery-button');
const completeRestoreButton=document.getElementById('run-complete-restore-staging-button');
const completeDownloadButton=document.getElementById('download-complete-crash-recovery-button');

if(completeRecoveryButton){{
  completeRecoveryButton.addEventListener('click',async()=>{{
    completeRecoveryButton.disabled=true;
    if(completeRestoreButton) completeRestoreButton.disabled=true;
    try{{
      const response=await fetch('api/crash-recovery/export',{{method:'POST',headers:{{'X-Requested-With':'fetch','Accept':'application/json'}}}});
      const result=await response.json();
      renderCompleteRecovery(result);
      if(!response.ok) throw new Error(result.error||'Complete Crash Recovery mislukt');
    }}catch(err){{alert(String(err.message||err));}}
    finally{{completeRecoveryButton.disabled=false; await refreshCompleteRecovery();}}
  }});
}}

if(completeRestoreButton){{
  completeRestoreButton.addEventListener('click',async()=>{{
    completeRestoreButton.disabled=true;
    try{{
      const response=await fetch('api/crash-recovery/stage',{{method:'POST',headers:{{'X-Requested-With':'fetch','Accept':'application/json'}}}});
      const result=await response.json();
      if(!response.ok) throw new Error(result.error||'RestoreStaging-test mislukt');
      await refreshCompleteRecovery();
    }}catch(err){{alert(String(err.message||err));}}
    finally{{await refreshCompleteRecovery();}}
  }});
}}

refreshCompleteRecovery();

const recoveryButton=document.getElementById('run-recovery-controller-button');
if(recoveryButton){{
  recoveryButton.addEventListener('click', async()=>{{
    recoveryButton.disabled=true;
    try{{
      const response=await fetch('run-recovery-controller',{{method:'POST',headers:{{'X-Requested-With':'fetch','Accept':'application/json'}}}});
      const result=await response.json();
      if(!response.ok) throw new Error(result.error||'Recoverycontrole mislukt');
      await refreshStatus();
    }}catch(err){{alert(String(err.message||err));}}finally{{recoveryButton.disabled=false;}}
  }});
}}
const monitoringButton=document.getElementById('run-monitoring-button');
if(monitoringButton){{
  monitoringButton.addEventListener('click', async()=>{{
    monitoringButton.disabled=true;
    try{{
      const response=await fetch('run-monitoring',{{method:'POST',headers:{{'X-Requested-With':'fetch','Accept':'application/json'}}}});
      const result=await response.json();
      if(!response.ok) throw new Error(result.error||'Monitoringcontrole mislukt');
      await refreshStatus();
    }}catch(err){{alert(String(err.message||err));}}finally{{monitoringButton.disabled=false;}}
  }});
}}
const autoSwitch=document.getElementById('auto-close-enabled');
if(autoSwitch){{
  const switchState=document.getElementById('auto-close-switch-state');
  const syncAutoSwitch=()=>{{switchState.textContent=autoSwitch.checked?'AAN':'UIT';}};
  autoSwitch.addEventListener('change',async()=>{{
    const requested=autoSwitch.checked;
    syncAutoSwitch();
    autoSwitch.disabled=true;
    try{{
      const body=new URLSearchParams({{enabled:requested?'1':'0'}});
      const response=await fetch('set-automatic-month-close-enabled',{{method:'POST',headers:{{'Content-Type':'application/x-www-form-urlencoded'}},body}});
      const data=await response.json();
      if(!response.ok || data.status!=='ok') throw new Error(data.error||'Opslaan mislukt');
    }}catch(err){{
      autoSwitch.checked=!requested;
      syncAutoSwitch();
      alert('Aan/Uit niet opgeslagen: '+err.message);
    }}finally{{
      autoSwitch.disabled=false;
    }}
  }});
  syncAutoSwitch();
}}
document.querySelectorAll('form[action="start-month-workflow"],form[action="resume-month-workflow"],form[action="run-historical-month"],form[action="test-automatic-month-close"],form[action="test-scheduler-acceptance"]').forEach(form=>form.addEventListener('submit',()=>{{
  const bar=document.getElementById('progress-bar'); bar.style.width='0%'; bar.className='running';
  document.getElementById('progress-count').textContent='Stap 0 van 11';
  document.getElementById('progress-message').textContent='Workflow starten';
  document.getElementById('workflow-detail').textContent='Initialiseren…';
  document.getElementById('workflow-eta').textContent='';
}}));
refreshStatus();
const INGRESS_BASE = {json.dumps(ingress_path)};
function ingressApiUrl(path) {{
  const p = path.startsWith('/') ? path : '/'+path;
  return INGRESS_BASE ? INGRESS_BASE+p : '.'+p;
}}

// v7.0.1 compatibiliteitsreferentie: setInterval(refreshStatus,5000)
setInterval(refreshStatus,2500);

function toggleGithubPublicKey(){{
  const key=document.getElementById('github-public-key');
  if(!key) return;
  key.style.display=(key.style.display==='none'||!key.style.display)?'block':'none';
}}

function loadGithubPublisher(){{
  // v32.0.10: status staat server-side in de pagina.
  return true;
}}

function refreshGithubPublisherStatus(showKey=false){{
  // Legacy observability-hook: bewust no-op zonder fetch.
  if(showKey) toggleGithubPublicKey();
  return true;
}}

window.addEventListener('load',()=>{{
  refreshGithubPublisherStatus(false);
  setInterval(()=>refreshGithubPublisherStatus(false),15000);
}});
</script>
</main></body></html>""".encode("utf-8")


ALLOWED_HTTP_CLIENTS = {"172.30.32.2", "132.0.1.1", "::1"}



def _publisher_options():
    path = Path("/data/options.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _run_cmd(args, *, cwd=None, env=None, timeout=30):
    proc = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


def _ensure_github_key():
    GITHUB_PUBLISH_DIR.mkdir(parents=True, exist_ok=True)
    if not GITHUB_PRIVATE_KEY.exists() or not GITHUB_PUBLIC_KEY.exists():
        rc, out, err = _run_cmd(
            ["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C",
             "EnergieProject Home Assistant publisher", "-f", str(GITHUB_PRIVATE_KEY)],
            timeout=30,
        )
        if rc != 0:
            return {"ok": False, "message": f"SSH-sleutel maken mislukt: {err or out}", "public_key": ""}
    try:
        GITHUB_PRIVATE_KEY.chmod(0o600)
        GITHUB_PUBLIC_KEY.chmod(0o644)
    except Exception:
        pass
    if not GITHUB_KNOWN_HOSTS.exists():
        rc, out, err = _run_cmd(["ssh-keyscan", "-t", "ed25519", "github.com"], timeout=20)
        if rc == 0 and out:
            GITHUB_KNOWN_HOSTS.write_text(out + "\n", encoding="utf-8")
    pub = GITHUB_PUBLIC_KEY.read_text(encoding="utf-8").strip() if GITHUB_PUBLIC_KEY.exists() else ""
    return {
        "ok": bool(pub),
        "message": "GitHub publicatiesleutel gereed" if pub else "Publicatiesleutel ontbreekt",
        "public_key": pub,
    }


def _github_git_env():
    env = dict(os.environ)
    env["GIT_SSH_COMMAND"] = (
        f"ssh -i {GITHUB_PRIVATE_KEY} "
        f"-o IdentitiesOnly=yes "
        f"-o UserKnownHostsFile={GITHUB_KNOWN_HOSTS} "
        f"-o StrictHostKeyChecking=yes "
        f"-o BatchMode=yes"
    )
    return env


def github_publication_status(options=None):
    options = options or {}
    key = _ensure_github_key()
    repo = str(options.get("github_repository_ssh") or "git@github.com:kgnfn65498-droid/EnergieProject.git")
    branch = str(options.get("github_branch") or "main")
    enabled = bool(options.get("github_publication_enabled", False))
    result = {
        "enabled": enabled,
        "repository": repo,
        "branch": branch,
        "key_ready": bool(key.get("ok")),
        "public_key": key.get("public_key", ""),
        "remote_reachable": False,
        "message": key.get("message", ""),
    }
    try:
        result["local_version"] = (NAS_PROJECT_ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip()
    except Exception:
        result["local_version"] = ""
    if key.get("ok") and NAS_PROJECT_ROOT.exists():
        rc, out, err = _run_cmd(
            ["git", "-c", f"safe.directory={NAS_PROJECT_ROOT}", "ls-remote", repo, f"refs/heads/{branch}"],
            cwd=NAS_PROJECT_ROOT,
            env=_github_git_env(),
            timeout=20,
        )
        result["remote_reachable"] = rc == 0
        result["remote_head"] = out.split()[0] if rc == 0 and out else ""
        if rc == 0:
            result["message"] = "GitHub bereikbaar; publicatiegereed"
        elif enabled:
            result["message"] = f"GitHub nog niet geautoriseerd: {err or out}"
    try:
        if GITHUB_PUBLISH_STATE.exists():
            saved = json.loads(GITHUB_PUBLISH_STATE.read_text(encoding="utf-8"))
            if isinstance(saved, dict):
                result["last_publication"] = saved
    except Exception:
        pass
    return result


def _remove_path(path: Path):
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path)


def _sync_project_to_github_worktree(source: Path, worktree: Path):
    """Synchroniseer App-inhoud naar de dedicated HA Git-worktree zonder CIFS-modes over te nemen."""
    source = source.resolve()
    worktree.mkdir(parents=True, exist_ok=True)

    source_entries = {p.relative_to(source) for p in source.rglob("*") if ".git" not in p.relative_to(source).parts}
    for dst in sorted((p for p in worktree.rglob("*") if ".git" not in p.relative_to(worktree).parts), key=lambda p: len(p.parts), reverse=True):
        rel = dst.relative_to(worktree)
        if rel not in source_entries:
            _remove_path(dst)

    for src in sorted((p for p in source.rglob("*") if ".git" not in p.relative_to(source).parts), key=lambda p: len(p.parts)):
        rel = src.relative_to(source)
        dst = worktree / rel
        if src.is_symlink():
            if dst.exists() or dst.is_symlink():
                _remove_path(dst)
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.symlink_to(os.readlink(src))
        elif src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
        elif src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            existed = dst.exists()
            shutil.copyfile(src, dst)
            if not existed:
                # Nieuwe bestanden krijgen een voorspelbare Git-mode; CIFS presenteert bestanden vaak als 0755.
                executable = src.suffix in {".sh", ".command"} or src.name in {"run.sh"}
                dst.chmod(0o755 if executable else 0o644)


def _prepare_github_worktree(repo: str, branch: str, env: dict[str, str]):
    GITHUB_PUBLISH_DIR.mkdir(parents=True, exist_ok=True)
    if GITHUB_WORKTREE.exists() and not (GITHUB_WORKTREE / ".git").exists():
        shutil.rmtree(GITHUB_WORKTREE)

    if not GITHUB_WORKTREE.exists():
        rc, out, err = _run_cmd(
            ["git", "clone", "--single-branch", "--branch", branch, repo, str(GITHUB_WORKTREE)],
            cwd=GITHUB_PUBLISH_DIR,
            env=env,
            timeout=120,
        )
        if rc != 0:
            return False, f"Git-worktree clone mislukt: {err or out}"
    else:
        commands = (
            ["git", "remote", "set-url", "origin", repo],
            ["git", "fetch", "origin", branch],
            ["git", "checkout", "-B", branch, f"origin/{branch}"],
            ["git", "reset", "--hard", f"origin/{branch}"],
            ["git", "clean", "-fd"],
        )
        for cmd in commands:
            rc, out, err = _run_cmd(cmd, cwd=GITHUB_WORKTREE, env=env, timeout=120)
            if rc != 0:
                return False, f"Git-worktree voorbereiding mislukt: {err or out}"
    return True, "Git-worktree gereed"


def publish_github_release(options=None):
    options = options or {}
    LOGGER.info("GitHub-publicatie: statuscontrole gestart.")
    status = github_publication_status(options)
    # last_publication is UI/history context only. Never persist it again inside the
    # next publication result, otherwise the JSON state nests itself on every poll.
    publish_status = {k: v for k, v in status.items() if k != "last_publication"}
    if not bool(options.get("github_publication_enabled", False)):
        return {**publish_status, "published": False, "message": "Automatische GitHub-publicatie staat uit"}
    if not status.get("key_ready") or not NAS_PROJECT_ROOT.exists():
        return {**publish_status, "published": False}
    repo = str(options.get("github_repository_ssh") or status["repository"])
    branch = str(options.get("github_branch") or "main")
    env = _github_git_env()

    ready, message = _prepare_github_worktree(repo, branch, env)
    if not ready:
        return {**publish_status, "published": False, "message": message}

    try:
        _sync_project_to_github_worktree(NAS_PROJECT_ROOT, GITHUB_WORKTREE)
    except Exception as exc:
        return {**publish_status, "published": False, "message": f"Git-worktree synchronisatie mislukt: {exc}"}

    rc, out, err = _run_cmd(["git", "add", "-A"], cwd=GITHUB_WORKTREE, env=env, timeout=60)
    if rc != 0:
        return {**publish_status, "published": False, "message": f"Git add mislukt: {err or out}"}

    rc, out, err = _run_cmd(["git", "diff", "--cached", "--quiet"], cwd=GITHUB_WORKTREE, env=env, timeout=30)
    if rc not in (0, 1):
        return {**publish_status, "published": False, "message": f"Git diff mislukt: {err or out}"}
    if rc == 1:
        version = status.get("local_version") or "onbekend"
        rc2, out2, err2 = _run_cmd(
            ["git", "-c", "user.name=EnergieProject Publisher",
             "-c", "user.email=energieproject@local",
             "commit", "-m", f"v{version}: automatic Home Assistant publication"],
            cwd=GITHUB_WORKTREE, env=env, timeout=60,
        )
        if rc2 != 0:
            return {**publish_status, "published": False, "message": f"Commit mislukt: {err2 or out2}"}

    rc, out, err = _run_cmd(["git", "push", "origin", f"HEAD:{branch}"], cwd=GITHUB_WORKTREE, env=env, timeout=120)
    result = {**publish_status, "published": rc == 0, "push_output": out, "push_error": err, "worktree": str(GITHUB_WORKTREE)}
    if rc == 0:
        local_rc, local_out, _ = _run_cmd(["git", "rev-parse", "HEAD"], cwd=GITHUB_WORKTREE, env=env, timeout=20)
        remote_rc, remote_out, _ = _run_cmd(["git", "ls-remote", "origin", f"refs/heads/{branch}"], cwd=GITHUB_WORKTREE, env=env, timeout=20)
        local_head = local_out.strip() if local_rc == 0 else ""
        remote_head = remote_out.split()[0] if remote_rc == 0 and remote_out else ""
        result["local_head"] = local_head
        result["remote_head"] = remote_head
        result["published"] = bool(local_head and local_head == remote_head)
        result["message"] = "GitHub-publicatie geslaagd" if result["published"] else "GitHub-push uitgevoerd maar remote verificatie wijkt af"
    else:
        result["message"] = f"GitHub-publicatie mislukt: {err or out}"
    try:
        GITHUB_PUBLISH_STATE.parent.mkdir(parents=True, exist_ok=True)
        GITHUB_PUBLISH_STATE.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except Exception:
        pass
    return result

def _write_github_publish_state(payload):
    try:
        GITHUB_PUBLISH_STATE.parent.mkdir(parents=True, exist_ok=True)
        GITHUB_PUBLISH_STATE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except Exception:
        LOGGER.exception("GitHub-publisherstatus kon niet worden opgeslagen.")


def _github_publication_loop(stop_event):
    last_seen = ""
    LOGGER.info("GitHub-publisherthread gestart.")
    while not stop_event.wait(2):
        try:
            options = _publisher_options()
            enabled = bool(options.get("github_publication_enabled", False))
            poll = max(5, min(300, int(options.get("github_publication_poll_seconds", 15) or 15)))
            LOGGER.info(
                "GitHub-publishercontrole: enabled=%s; project=%s; processed=%s",
                enabled,
                NAS_PROJECT_ROOT.exists(),
                (NAS_RELEASE_ROOT / "processed").exists(),
            )
            if enabled:
                version_path = NAS_PROJECT_ROOT / "VERSIE.txt"
                version = version_path.read_text(encoding="utf-8").strip() if version_path.exists() else ""
                processed_dir = NAS_RELEASE_ROOT / "processed"
                processed_candidates = []
                if version and processed_dir.exists():
                    processed_candidates = sorted(processed_dir.glob(f"EnergieProject_v{version}*.zip"))
                if not version:
                    LOGGER.warning("GitHub-publisher: VERSIE.txt ontbreekt of is leeg.")
                elif not processed_candidates:
                    LOGGER.info("GitHub-publisher: release %s nog niet in processed.", version)
                elif version != last_seen:
                    LOGGER.info("GitHub-publisher: publicatiepoging voor v%s gestart.", version)
                    result = publish_github_release(options)
                    _write_github_publish_state(result)
                    LOGGER.info(
                        "GitHub-publisherresultaat v%s: published=%s; message=%s",
                        version,
                        result.get("published"),
                        result.get("message"),
                    )
                    if result.get("published"):
                        last_seen = version
            if stop_event.wait(poll):
                return
        except Exception:
            LOGGER.exception("GitHub-publishercontrole mislukt.")
            if stop_event.wait(15):
                return



def render_reports_page() -> bytes:
    """Echte zichtbare rapportpagina voor de Home Assistant Web UI."""
    state = persist_normalized_status(Options.load())
    esc = html.escape
    status = state.get("report_generation_last_status") or "Nog niet gegenereerd"
    month = state.get("report_generation_last_month") or "Nog geen"
    started = state.get("report_generation_last_started") or "—"
    finished = state.get("report_generation_last_finished") or "—"
    error = state.get("report_generation_last_error")
    output_status = state.get("report_output_last_status") or "Nog geen"
    output_folder = state.get("report_output_last_folder") or "—"
    output_files = state.get("report_output_last_files") or []
    handoff_status = state.get("report_handoff_last_status") or "Nog geen"
    handoff_month = state.get("report_handoff_last_month") or "—"
    generator_status = state.get("report_generators_last_status") or state.get("report_runtime_last_status") or "Onbekend"

    file_items = "".join(
        f"<li><code>{esc(str(item))}</code></li>"
        for item in output_files
    ) or "<li>Nog geen rapportbestanden geregistreerd.</li>"

    status_class = "ok" if str(status).lower() in {"completed", "ready", "ok"} else (
        "bad" if str(status).lower() in {"failed", "error"} else "warn"
    )
    error_html = (
        f'<div class="alert bad"><strong>Laatste fout</strong><br>{esc(str(error))}</div>'
        if error else ""
    )
    body = f"""<!doctype html>
<html lang="nl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EnergieProject · Rapportage</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:#f5f6f8;color:#202124;margin:0}}
.wrap{{max-width:1050px;margin:0 auto;padding:18px}}
.header{{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap}}
.card{{background:white;border:1px solid #ddd;border-radius:14px;padding:16px;margin:14px 0;box-shadow:0 1px 3px rgba(0,0,0,.05)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px}}
.metric{{border:1px solid #e2e5e9;border-radius:10px;padding:12px}}
.metric small{{display:block;color:#6b7280;margin-bottom:4px}}
.metric strong{{font-size:1.05rem}}
.pill{{display:inline-block;padding:4px 9px;border-radius:999px;font-size:.9rem}}
.ok{{background:#e8f5e9;color:#1b5e20}} .warn{{background:#fff8e1;color:#7a5200}} .bad{{background:#ffebee;color:#8b1e24}}
button,.button{{display:inline-block;border:0;border-radius:9px;padding:10px 14px;background:#1667c5;color:white;text-decoration:none;font-weight:600;cursor:pointer}}
.secondary{{background:#e9eef5;color:#1f2937}}
form{{display:inline-block;margin:5px 5px 5px 0}}
.alert{{padding:12px;border-radius:10px}}
code{{word-break:break-word}}
a{{color:#1667c5}}
</style>
</head>
<body><div class="wrap">
<div class="header">
<div><h1>Rapportage</h1><div>Home Assistant · EnergieProject v{esc(APP_VERSION)}</div></div>
<a class="button secondary" href="./">← Terug naar overzicht</a>
</div>

<div class="card">
<h2>Rapportstatus</h2>
<div class="grid">
<div class="metric"><small>Status</small><strong><span class="pill {status_class}">{esc(str(status))}</span></strong></div>
<div class="metric"><small>Maand</small><strong>{esc(str(month))}</strong></div>
<div class="metric"><small>Gestart</small><strong>{esc(str(started))}</strong></div>
<div class="metric"><small>Afgerond</small><strong>{esc(str(finished))}</strong></div>
<div class="metric"><small>Overdracht</small><strong>{esc(str(handoff_status))}</strong><br><small>{esc(str(handoff_month))}</small></div>
<div class="metric"><small>Generatoren</small><strong>{esc(str(generator_status))}</strong></div>
</div>
{error_html}
</div>

<div class="card">
<h2>Rapportacties</h2>
<p>Deze bediening gebruikt dezelfde bestaande productie-routes; de rapportfuncties zijn nu niet meer verborgen in een ingeklapt blok.</p>
<form method="post" action="check-report-runtime"><button type="submit">Controleer rapportmodules</button></form>
<form method="post" action="build-report-adapter"><button type="submit">Bouw rapportdata-adapter</button></form>
<form method="post" action="install-report-generators"><button type="submit">Installeer officiële rapportgeneratoren</button></form>
<form method="post" action="run-report-page1"><button type="submit">Test rapportgenerator pagina 1</button></form>
<form method="post" action="report-service-check"><button type="submit">Controleer rapportservice</button></form>
<form method="post" action="run-report-generation"><button type="submit">Genereer compleet maandrapport</button></form>
</div>

<div class="card">
<h2>Laatste rapportuitvoer</h2>
<div class="grid">
<div class="metric"><small>Outputstatus</small><strong>{esc(str(output_status))}</strong></div>
<div class="metric"><small>Outputmap</small><strong><code>{esc(str(output_folder))}</code></strong></div>
</div>
<ul>{file_items}</ul>
<p><a href="report-generation-status">Technische rapportstatus (JSON)</a></p>
</div>
</div></body></html>"""
    return body.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    def _client_allowed(self) -> bool:
        # Home Assistant ingress/proxy addresses can vary between HA releases and
        # supervisor network layouts. Ingress itself is the security boundary;
        # rejecting the proxy here made a healthy app appear "not ready".
        return True

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

    def send_redirect(self, location: str = "./") -> None:
        self.send_response(HTTPStatus.SEE_OTHER)
        self.send_header("Location", location)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self) -> None:
        complete_recovery_path = self.path.split("?", 1)[0].rstrip("/")
        if complete_recovery_path.endswith("/api/crash-recovery/download"):
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

        if complete_recovery_path.endswith("/api/crash-recovery/state"):
            body = json.dumps(
                _complete_recovery_state(),
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            self.send_body(
                HTTPStatus.OK,
                body,
                "application/json; charset=utf-8",
            )
            return
        if self.path.startswith("/api/github-publisher/status"):
            body = json.dumps(github_publication_status(_publisher_options()), ensure_ascii=False, indent=2).encode("utf-8")
            self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
            return
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
        elif path.endswith("/download-analysis-data") or path == "/download-analysis-data":
            try:
                body = json.dumps(build_analysis_context(), ensure_ascii=False, indent=2).encode("utf-8")
                self.send_body(
                    HTTPStatus.OK,
                    body,
                    "application/json; charset=utf-8",
                    disposition=f'attachment; filename="Energie_analyse_{datetime.now(TZ).strftime("%Y%m%d_%H%M%S")}.json"',
                )
            except Exception as exc:
                body = json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self.send_body(HTTPStatus.INTERNAL_SERVER_ERROR, body, "application/json; charset=utf-8")
        elif path.endswith("/analysis-context") or path == "/analysis-context":
            query = parse_qs(parsed.query)
            year_raw = (query.get("year") or [""])[0].strip()
            try:
                year_filter = int(year_raw) if year_raw else None
                if year_filter is not None and not 2000 <= year_filter <= 2100:
                    raise ValueError("Jaar buiten geldig bereik.")
                body = json.dumps(build_analysis_context(year_filter), ensure_ascii=False, indent=2).encode("utf-8")
                self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
            except Exception as exc:
                body = json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self.send_body(HTTPStatus.BAD_REQUEST, body, "application/json; charset=utf-8")
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
        elif path.endswith("/reports") or path == "/reports":
            self.send_body(
                HTTPStatus.OK,
                render_reports_page(),
                "text/html; charset=utf-8",
            )
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
        elif path.endswith("/download-smp-import-diagnose") or path == "/download-smp-import-diagnose":
            state = load_state()
            payload = {
                "version": APP_VERSION,
                "month": state.get("last_target_month"),
                "started": state.get("last_started"),
                "finished": state.get("last_finished"),
                "status": state.get("status"),
                "validation_status": state.get("last_validation_status"),
                "output": state.get("last_output"),
                "error": state.get("last_error"),
                "error_type": state.get("last_error_type"),
                "traceback": state.get("last_traceback"),
                "nas_transfer_status": state.get("smp_nas_transfer_last_status"),
                "nas_transfer_path": state.get("smp_nas_transfer_last_path"),
                "nas_transfer_manifest": state.get("smp_nas_transfer_last_manifest"),
                "nas_transfer_error": state.get("smp_nas_transfer_last_error"),
            }
            body = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            filename = f"SMP_import_diagnose_{state.get('last_target_month') or 'onbekend'}_v{APP_VERSION}.json"
            disposition = f'attachment; filename="{filename}"'
            self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8", disposition)
        elif path.endswith("/operation-status") or path == "/operation-status":
            body = json.dumps(
                operation_status(Options.load()),
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
        elif path.endswith("/workflow-log") or path == "/workflow-log":
            month = (parse_qs(parsed.query).get("month") or [""])[0].strip().replace("-", "_")
            try:
                lines = workflow_log_tail(month) if month else []
                body = json.dumps({"version": APP_VERSION, "month": month, "lines": lines}, ensure_ascii=False, indent=2).encode("utf-8")
                self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
            except Exception as exc:
                body = json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self.send_body(HTTPStatus.BAD_REQUEST, body, "application/json; charset=utf-8")
        elif path.endswith("/download-workflow-log") or path == "/download-workflow-log":
            month = (parse_qs(parsed.query).get("month") or [""])[0].strip().replace("-", "_")
            try:
                log_path = workflow_log_file(month)
                if not log_path.is_file():
                    raise FileNotFoundError(month)
                self.send_body(HTTPStatus.OK, log_path.read_bytes(), "application/x-ndjson; charset=utf-8", f'attachment; filename="workflow_{month}.log"')
            except Exception:
                self.send_body(HTTPStatus.NOT_FOUND, b"Workflowlog niet gevonden", "text/plain; charset=utf-8")
        elif path.endswith("/health-dashboard") or path == "/health-dashboard":
            body = json.dumps(health_dashboard(Options.load()), ensure_ascii=False, indent=2).encode("utf-8")
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
        elif path.endswith("/infrastructure-status") or path == "/infrastructure-status":
            body = json.dumps(infrastructure_snapshot(), ensure_ascii=False, indent=2).encode("utf-8")
            self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
        elif path.endswith("/migration-status") or path == "/migration-status":
            body = json.dumps(nas_migration_snapshot(), ensure_ascii=False, indent=2).encode("utf-8")
            self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
        elif path.endswith("/download-chat-transfer") or path == "/download-chat-transfer":
            try:
                body = build_chat_transfer_package()
                self.send_body(
                    HTTPStatus.OK, body, "application/zip",
                    f'attachment; filename="Energieproject_chat_overdracht_v{APP_VERSION}.zip"',
                )
            except Exception as exc:
                LOGGER.exception("Chat-overdracht kon niet worden gebouwd.")
                self.send_body(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc).encode("utf-8", errors="replace"), "text/plain; charset=utf-8")
        elif path.endswith("/runtime-diagnostics") or path == "/runtime-diagnostics":
            body = json.dumps(runtime_diagnostics_snapshot(), ensure_ascii=False, indent=2).encode("utf-8")
            self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
        elif path.endswith("/release-diagnostics") or path == "/release-diagnostics":
            version = (parse_qs(parsed.query).get("version") or [""])[0].strip()
            body = json.dumps(release_diagnostics_snapshot(version), ensure_ascii=False, indent=2).encode("utf-8")
            self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
        elif path.endswith("/download-release-diagnostics") or path == "/download-release-diagnostics":
            try:
                version = (parse_qs(parsed.query).get("version") or [""])[0].strip()
                body = build_release_diagnostic_package(version)
                label = (version or APP_VERSION).replace("/", "_").replace("\\", "_")
                self.send_body(
                    HTTPStatus.OK, body, "application/zip",
                    f'attachment; filename="EnergieProject_release_diagnose_v{label}.zip"',
                )
            except Exception as exc:
                LOGGER.exception("Release-diagnose kon niet worden gebouwd.")
                self.send_body(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc).encode("utf-8", errors="replace"), "text/plain; charset=utf-8")
        elif path.endswith("/download-diagnostic-package") or path == "/download-diagnostic-package" or path.endswith("/download-test-package") or path == "/download-test-package":
            try:
                body = build_test_package()
                self.send_body(
                    HTTPStatus.OK, body, "application/zip",
                    f'attachment; filename="Energieproject_diagnosepakket_v{APP_VERSION}.zip"',
                )
            except Exception as exc:
                LOGGER.exception("Diagnosepakket kon niet worden gebouwd.")
                self.send_body(HTTPStatus.INTERNAL_SERVER_ERROR, str(exc).encode("utf-8", errors="replace"), "text/plain; charset=utf-8")
        elif path.endswith("/download-monitoring-history") or path == "/download-monitoring-history":
            if not MONITORING_HISTORY_PATH.is_file():
                self.send_body(HTTPStatus.NOT_FOUND, b"Monitoringhistorie niet gevonden", "text/plain; charset=utf-8")
            else:
                self.send_body(HTTPStatus.OK, MONITORING_HISTORY_PATH.read_bytes(), "application/x-ndjson; charset=utf-8", 'attachment; filename="monitoring_history.jsonl"')
        elif path.endswith("/download-audit-trail") or path == "/download-audit-trail":
            if not AUDIT_TRAIL_PATH.is_file():
                self.send_body(HTTPStatus.NOT_FOUND, b"Audittrail ontbreekt", "text/plain")
            else:
                self.send_body(HTTPStatus.OK, AUDIT_TRAIL_PATH.read_bytes(), "application/x-ndjson", 'attachment; filename="audit_trail.jsonl"')

        elif path.endswith("/download-production-certificate") or path == "/download-production-certificate":
            validation = validate_production_certificate()
            if not validation.get("exists"):
                self.send_body(HTTPStatus.NOT_FOUND, b"Productiecertificaat ontbreekt", "text/plain")
            else:
                body = PRODUCTION_CERTIFICATE_PATH.read_bytes()
                self.send_body(
                    HTTPStatus.OK, body, "application/json; charset=utf-8",
                    'attachment; filename="production_certificate.json"',
                )
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
            self.send_body(HTTPStatus.OK, html_page(self.headers.get("X-Ingress-Path", "")), "text/html; charset=utf-8")

    def do_POST(self) -> None:
        if not self._client_allowed():
            self.send_body(HTTPStatus.FORBIDDEN, b"Forbidden", "text/plain")
            return
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/")
        if path.endswith("/set-automatic-month-close-enabled") or path == "/set-automatic-month-close-enabled":
            length = int(self.headers.get("Content-Length", "0") or 0)
            form = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
            try:
                enabled = str((form.get("enabled") or ["0"])[0]).strip() == "1"
                result = set_automatic_month_close_enabled(enabled)
                update_state(automatic_month_close_ui_settings_last=result)
                body = json.dumps({
                    "status": "ok",
                    "enabled": enabled,
                    "version": APP_VERSION,
                }, ensure_ascii=False).encode("utf-8")
                self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
            except Exception as exc:
                body = json.dumps({
                    "status": "error",
                    "error": str(exc),
                    "version": APP_VERSION,
                }, ensure_ascii=False).encode("utf-8")
                self.send_body(HTTPStatus.BAD_REQUEST, body, "application/json; charset=utf-8")
            return

        if path.endswith("/save-automatic-month-close") or path == "/save-automatic-month-close":
            length = int(self.headers.get("Content-Length", "0") or 0)
            form = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
            try:
                result = save_automatic_month_close_settings(
                    enabled=str((form.get("enabled") or [""])[0]).strip() == "1",
                    day=int((form.get("day") or ["2"])[0]),
                    hour=int((form.get("hour") or ["4"])[0]),
                    retry_hours=int((form.get("retry_hours") or ["6"])[0]),
                )
                update_state(automatic_month_close_ui_settings_last=result)
                self.send_redirect("./")
            except Exception as exc:
                self.send_body(
                    HTTPStatus.BAD_REQUEST,
                    ("<html><meta charset='utf-8'><p>Instellingen niet opgeslagen: "
                     + html.escape(str(exc))
                     + "</p><p><a href='./'>Terug</a></p></html>").encode("utf-8"),
                    "text/html; charset=utf-8",
                )
            return

        if path.endswith("/test-scheduler-acceptance") or path == "/test-scheduler-acceptance":
            try:
                if WORKFLOW_LOCK.locked():
                    raise RuntimeError("Er draait al een maandworkflow.")
                update_state(automatic_scheduler_acceptance_last_result={
                    "version": APP_VERSION,
                    "started_at": datetime.now(TZ).isoformat(),
                    "tested_at": None,
                    "simulated_at": None,
                    "month": None,
                    "status": "running",
                    "execution": None,
                    "scheduler_bookkeeping_restored": False,
                    "scheduler_config_unchanged": None,
                    "error": None,
                })
                def scheduler_acceptance_worker() -> None:
                    try:
                        automatic_scheduler_acceptance_test()
                    except Exception as exc:
                        previous = load_state().get("automatic_scheduler_acceptance_last_result") or {}
                        update_state(automatic_scheduler_acceptance_last_result={
                            **previous,
                            "version": APP_VERSION,
                            "tested_at": datetime.now(TZ).isoformat(),
                            "status": "error",
                            "error": str(exc),
                        })
                threading.Thread(target=scheduler_acceptance_worker, daemon=True).start()
                self.send_redirect("./")
            except Exception as exc:
                self.send_body(
                    HTTPStatus.BAD_REQUEST,
                    ("<html><meta charset='utf-8'><p>Scheduler-acceptatietest kon niet starten: "
                     + html.escape(str(exc))
                     + "</p><p><a href='./'>Terug</a></p></html>").encode("utf-8"),
                    "text/html; charset=utf-8",
                )
            return

        if path.endswith("/test-automatic-month-close") or path == "/test-automatic-month-close":
            length = int(self.headers.get("Content-Length", "0") or 0)
            form = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
            selected = str((form.get("month") or [""])[0]).strip().replace("-", "_")
            try:
                month_key = historical_month_allowed(selected)
                update_state(
                    automatic_month_close_test_last_result={
                        "version": APP_VERSION,
                        "started_at": datetime.now(TZ).isoformat(),
                        "tested_at": None,
                        "month": month_key,
                        "status": "running",
                        "preflight": None,
                        "workflow": None,
                        "finalization": None,
                        "error": None,
                        "scheduler_state_changed": False,
                    }
                )
                def worker() -> None:
                    try:
                        run_automatic_month_close_test(month_key)
                    except Exception as exc:
                        previous_test = (load_state().get("automatic_month_close_test_last_result") or {})
                        update_state(automatic_month_close_test_last_result={
                            "version": APP_VERSION,
                            "started_at": previous_test.get("started_at"),
                            "tested_at": datetime.now(TZ).isoformat(),
                            "month": month_key,
                            "status": "error",
                            "preflight": previous_test.get("preflight"),
                            "workflow": previous_test.get("workflow"),
                            "finalization": previous_test.get("finalization"),
                            "error": str(exc),
                            "scheduler_state_changed": False,
                        })
                threading.Thread(target=worker, daemon=True).start()
                self.send_redirect("./")
            except Exception as exc:
                self.send_body(
                    HTTPStatus.BAD_REQUEST,
                    ("<html><meta charset='utf-8'><p>Automatische productietest kon niet starten: "
                     + html.escape(str(exc))
                     + "</p><p><a href='./'>Terug</a></p></html>").encode("utf-8"),
                    "text/html; charset=utf-8",
                )
            return

        if path.endswith("/start-month-workflow") or path == "/start-month-workflow":
            length = int(self.headers.get("Content-Length", "0") or 0)
            form = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
            selected = str((form.get("month") or [""])[0]).strip().replace("-", "_")
            try:
                month_key = historical_month_allowed(selected)
                result = start_workflow_background(
                    month_key,
                    collect_live_snapshots=(month_key == datetime.now(TZ).strftime("%Y_%m")),
                    resume=False,
                )
                code = HTTPStatus.ACCEPTED if result.get("status") == "started" else HTTPStatus.CONFLICT
            except Exception as exc:
                result = {"status": "error", "error": str(exc)}
                code = HTTPStatus.BAD_REQUEST
            self.send_body(code, ("<html><meta charset='utf-8'><meta http-equiv='refresh' content='1;url=./'><p>" + html.escape(json.dumps(result, ensure_ascii=False)) + "</p><p><a href='./'>Terug</a></p></html>").encode("utf-8"), "text/html; charset=utf-8")
            return

        if path.endswith("/resume-month-workflow") or path == "/resume-month-workflow":
            length = int(self.headers.get("Content-Length", "0") or 0)
            form = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
            selected = str((form.get("month") or [""])[0]).strip().replace("-", "_")
            try:
                month_key = historical_month_allowed(selected)
                previous = previous_workflow_result(month_key)
                if not previous or previous.get("status") in {"completed", "completed_warning"}:
                    raise ValueError("Voor deze maand is geen mislukte/onvolledige workflow beschikbaar om te hervatten.")
                result = start_workflow_background(
                    month_key,
                    collect_live_snapshots=False,
                    resume=True,
                )
                code = HTTPStatus.ACCEPTED if result.get("status") == "started" else HTTPStatus.CONFLICT
            except Exception as exc:
                result = {"status": "error", "error": str(exc)}
                code = HTTPStatus.BAD_REQUEST
            self.send_body(code, ("<html><meta charset='utf-8'><meta http-equiv='refresh' content='1;url=./'><p>" + html.escape(json.dumps(result, ensure_ascii=False)) + "</p><p><a href='./'>Terug</a></p></html>").encode("utf-8"), "text/html; charset=utf-8")
            return

        if path.endswith("/cancel") or path == "/cancel":
            if RUN_LOCK.locked():
                update_state(cancel_requested=True, progress_message="Annulering aangevraagd", last_cancel_reason="user_requested")
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

        if path.endswith("/run-monitoring") or path == "/run-monitoring":
            try:
                result = monitoring_snapshot(Options.load(), force=True, trigger="manual")
                body = json.dumps(result, ensure_ascii=False, indent=2).encode("utf-8")
                self.send_body(HTTPStatus.OK, body, "application/json; charset=utf-8")
            except Exception as exc:
                body = json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False).encode("utf-8")
                self.send_body(HTTPStatus.INTERNAL_SERVER_ERROR, body, "application/json; charset=utf-8")
            return

        if path.endswith("/api/crash-recovery/export"):
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

        if path.endswith("/api/crash-recovery/complete"):
            result = run_complete_crash_recovery()
            status = str(result.get("status") or "")
            code = (
                HTTPStatus.OK if status == "verified"
                else HTTPStatus.CONFLICT if status == "busy"
                else HTTPStatus.BAD_GATEWAY
            )
            body = json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            self.send_body(code, body, "application/json; charset=utf-8")
            return

        if path.endswith("/api/crash-recovery/stage"):
            result = run_complete_restore_staging()
            status = str(result.get("status") or "")
            code = (
                HTTPStatus.OK if status == "staged"
                else HTTPStatus.CONFLICT if status == "busy"
                else HTTPStatus.BAD_REQUEST
            )
            body = json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            ).encode("utf-8")
            self.send_body(code, body, "application/json; charset=utf-8")
            return

        if path.endswith("/run-recovery-controller") or path == "/run-recovery-controller":
            try:
                result = run_recovery_controller(trigger="manual")
                code = HTTPStatus.OK if result.get("status") in {"ok", "attention"} else HTTPStatus.BAD_REQUEST
            except Exception as exc:
                result = {"status": "error", "error": str(exc), "version": APP_VERSION}
                code = HTTPStatus.BAD_REQUEST
            self.send_body(code, json.dumps(result, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return

        if path.endswith("/manage-production-certificate") or path == "/manage-production-certificate":
            try:
                result = manage_production_certificate(allow_repair=True)
                append_audit_event(
                    "production_certificate_management", action=str(result.get("action") or "validated"),
                    status="ok" if result.get("valid") else "attention",
                    month=str(result.get("source_test_month") or "") or None,
                    details={"repaired": result.get("repaired"), "certificate_id": result.get("certificate_id")},
                )
                code = HTTPStatus.OK if result.get("valid") else HTTPStatus.BAD_REQUEST
            except Exception as exc:
                result = {"status": "error", "error": str(exc), "version": APP_VERSION}
                code = HTTPStatus.BAD_REQUEST
            self.send_body(code, json.dumps(result, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")
            return

        if path.endswith("/self-test") or path == "/self-test":
            try:
                result = run_self_test()
                code = HTTPStatus.OK if result.get("status") != "error" else HTTPStatus.BAD_REQUEST
            except Exception as exc:
                LOGGER.exception("HomeWizard-detectie mislukt.")
                result = {"status": "error", "error": str(exc), "type": type(exc).__name__}
                code = HTTPStatus.BAD_REQUEST
            checks = result.get("checks") or []
            rows = "".join(
                "<tr><td>" + html.escape(str(item.get("name") or "")) + "</td>"
                + "<td><strong>" + ("OK" if item.get("status") == "ok" else html.escape(str(item.get("status") or ""))) + "</strong></td>"
                + "<td>" + html.escape(str(item.get("detail") or "")) + "</td></tr>"
                for item in checks
            )
            overall = "ALLE TESTS GESLAAGD" if result.get("status") == "ok" else "AANDACHT NODIG"
            page = (
                "<!doctype html><html lang='nl'><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                "<title>Volledige zelftest</title><style>body{font-family:system-ui,-apple-system,sans-serif;background:#f4f7f9;color:#17202a;margin:0}"
                ".wrap{max-width:980px;margin:28px auto;padding:0 18px}.card{background:#fff;border-radius:14px;padding:22px;box-shadow:0 2px 12px #00000010}"
                "table{width:100%;border-collapse:collapse;margin-top:16px}th,td{text-align:left;padding:10px;border-bottom:1px solid #dfe7ec;vertical-align:top}"
                ".ok{color:#17864b}.bad{color:#c0392b}.meta{color:#61707d}a{color:#0277bd}</style><body><div class='wrap'><div class='card'>"
                "<h1>Volledige zelftest</h1><p class='meta'>Versie " + html.escape(str(result.get("version") or APP_VERSION))
                + " · uitgevoerd " + html.escape(str(result.get("checked_at") or "")) + "</p>"
                + "<h2 class='" + ("ok" if result.get("status") == "ok" else "bad") + "'>" + overall + "</h2>"
                + "<table><thead><tr><th>Controle</th><th>Status</th><th>Detail</th></tr></thead><tbody>" + rows + "</tbody></table>"
                + "<p><a href='./'>Terug naar operationele console</a></p></div></div></body></html>"
            )
            self.send_body(code, page.encode("utf-8"), "text/html; charset=utf-8")
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
            form = parse_qs(self.rfile.read(length).decode("utf-8", errors="replace"))
            selected = (form.get("month") or [""])[0].strip().replace("-", "_")
            try:
                month_key = historical_month_allowed(selected)
                result = start_workflow_background(
                    month_key,
                    collect_live_snapshots=False,
                    resume=False,
                    trigger="historical",
                )
                code = HTTPStatus.ACCEPTED if result.get("status") == "started" else HTTPStatus.CONFLICT
            except Exception as exc:
                result = {"status": "error", "error": str(exc)}
                code = HTTPStatus.BAD_REQUEST
            if code == HTTPStatus.ACCEPTED:
                self.send_redirect("./")
            else:
                self.send_body(
                    code,
                    (
                        "<html><meta charset='utf-8'><p>"
                        + html.escape(json.dumps(result, ensure_ascii=False))
                        + "</p><p><a href='./'>Terug naar operationele console</a></p></html>"
                    ).encode("utf-8"),
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
                    trigger="manual",
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
            if result.get("status") == "ok":
                self.send_redirect("./")
            else:
                self.send_body(
                    HTTPStatus.BAD_REQUEST,
                    (
                        "<html><meta charset='utf-8'><p>"
                        + html.escape(
                            f"API-test mislukt — {result.get('error') or 'onbekende fout'}."
                        )
                        + "</p><p><a href='./'>Terug naar operationele console</a></p></html>"
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

    processed_retention = cleanup_processed_release_retention_on_app_start(
        PROJECT_BACKUP_RETENTION
    )
    if processed_retention.get("status") == "ok":
        LOGGER.info(
            "HA-app processed-retentie v32.0.30: OK before=%s after=%s keep=%s kept=%s removed=%s",
            processed_retention.get("before"),
            processed_retention.get("after"),
            processed_retention.get("keep"),
            processed_retention.get("kept"),
            processed_retention.get("removed"),
        )
    else:
        LOGGER.error(
            "HA-app processed-retentie v32.0.30: FOUT %s",
            processed_retention.get("error"),
        )
    signal.signal(signal.SIGTERM, stop_handler)
    signal.signal(signal.SIGINT, stop_handler)
    update_state(version=APP_VERSION)
    threading.Thread(target=scheduler, daemon=True).start()
    server = ThreadingHTTPServer(("0.0.0.0", 8099), Handler)
    LOGGER.info("SlimmeMeterPortal Import v%s gestart.", APP_VERSION)

    def startup_self_test() -> None:
        try:
            time.sleep(1)
            recovery_result = run_recovery_controller(trigger="startup")
            LOGGER.info("Recovery startupcontrole: %s; herstelacties=%s", recovery_result.get("status"), recovery_result.get("repair_count"))
            result = run_self_test()
            LOGGER.info(
                "Automatische zelftest afgerond: %s; installatie_gereed=%s",
                result.get("status"),
                result.get("status") != "error",
            )
            try:
                monitor_options = Options.load()
            except Exception as exc:
                LOGGER.warning("Monitoring startupcontrole overgeslagen zolang configuratie niet gereed is: %s", exc)
            else:
                monitor = monitoring_snapshot(monitor_options, force=True, trigger="startup")
                LOGGER.info("Monitoring startupcontrole v%s: %s; meldingen=%s", APP_VERSION, monitor.get("status"), monitor.get("active_alerts"))
        except Exception:
            LOGGER.exception("Automatische zelftest mislukt.")

    threading.Thread(target=startup_self_test, daemon=True).start()
    try:
        publisher_options = _publisher_options()
        LOGGER.info(
            "GitHub-publisher startup: enabled=%s; repository=%s; branch=%s",
            bool(publisher_options.get("github_publication_enabled", False)),
            publisher_options.get("github_repository_ssh", ""),
            publisher_options.get("github_branch", "main"),
        )
        publisher_thread = threading.Thread(target=_github_publication_loop, args=(STOP,), daemon=True, name="github-publisher")
        publisher_thread.start()
        server.serve_forever()
    finally:
        STOP.set()
        server.server_close()


if __name__ == "__main__":
    main()
