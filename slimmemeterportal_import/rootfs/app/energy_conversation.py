from __future__ import annotations

import re
import threading
import time
import uuid
from collections import OrderedDict
from datetime import datetime
from typing import Any, Callable


CONTEXT_SCHEMA = "energie_conversation_context_v1"


class EnergyConversationEngine:
    """Read-only context resolver for EnergieProject questions.

    The engine does not fetch the network or mutate project data. Providers are
    injected by the runtime and are expected to return already validated,
    read-only project context.
    """

    def __init__(
        self,
        *,
        app_version: str,
        analysis_provider: Callable[..., dict[str, Any]],
        knowledge_provider: Callable[[str, list[str]], dict[str, Any]],
        now_provider: Callable[[], datetime],
        session_ttl_seconds: int = 7200,
        max_sessions: int = 100,
    ) -> None:
        self.app_version = str(app_version)
        self.analysis_provider = analysis_provider
        self.knowledge_provider = knowledge_provider
        self.now_provider = now_provider
        self.session_ttl_seconds = max(60, int(session_ttl_seconds))
        self.max_sessions = max(1, int(max_sessions))
        self._sessions: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._lock = threading.RLock()

    def health(self) -> dict[str, Any]:
        self._purge_sessions()
        return {
            "status": "ready",
            "schema": CONTEXT_SCHEMA,
            "version": self.app_version,
            "read_only": True,
            "session_ttl_seconds": self.session_ttl_seconds,
            "max_sessions": self.max_sessions,
            "active_sessions": len(self._sessions),
        }

    def context(self, query: str, session_id: str | None = None) -> dict[str, Any]:
        text = str(query or "").strip()
        if not text:
            raise ValueError("query is required")
        if len(text) > 2000:
            raise ValueError("query is too long")

        now = self.now_provider()
        sid = self._normalize_session_id(session_id)
        previous = self._get_session(sid)
        domains = self._resolve_domains(text, previous)
        month_key = self._resolve_month(text, now, previous)

        year = int(month_key[:4]) if month_key else now.year
        analysis = self.analysis_provider(year=year)
        month = self._find_month(analysis, month_key)
        evidence = self._build_evidence(text, domains, month, analysis)
        quality = self._build_quality(month, evidence, domains, month_key, now)
        observations = self._proactive_observations(month, evidence, quality)

        result = {
            "schema": CONTEXT_SCHEMA,
            "version": self.app_version,
            "generated_at": now.isoformat(),
            "session_id": sid,
            "query": text,
            "resolved": {
                "month": month_key,
                "domains": domains,
            },
            "quality": quality,
            "evidence": evidence,
            "proactive_observations": observations[:3],
        }
        self._store_session(sid, domains, month_key, now)
        return result

    def _normalize_session_id(self, session_id: str | None) -> str:
        raw = str(session_id or "").strip()
        if raw:
            if len(raw) > 128 or not re.fullmatch(r"[A-Za-z0-9_.:-]+", raw):
                raise ValueError("invalid session_id")
            return raw
        return uuid.uuid4().hex

    def _purge_sessions(self) -> None:
        now_mono = time.monotonic()
        with self._lock:
            expired = [
                sid for sid, item in self._sessions.items()
                if now_mono - float(item.get("seen_monotonic", 0.0)) > self.session_ttl_seconds
            ]
            for sid in expired:
                self._sessions.pop(sid, None)

    def _get_session(self, session_id: str) -> dict[str, Any] | None:
        self._purge_sessions()
        with self._lock:
            item = self._sessions.get(session_id)
            if not item:
                return None
            self._sessions.move_to_end(session_id)
            return dict(item)

    def _store_session(self, session_id: str, domains: list[str], month_key: str, now: datetime) -> None:
        with self._lock:
            self._sessions[session_id] = {
                "domains": list(domains),
                "month": month_key,
                "seen_at": now.isoformat(),
                "seen_monotonic": time.monotonic(),
            }
            self._sessions.move_to_end(session_id)
            while len(self._sessions) > self.max_sessions:
                self._sessions.popitem(last=False)

    @staticmethod
    def _resolve_domains(text: str, previous: dict[str, Any] | None) -> list[str]:
        q = text.casefold()
        rules = [
            ("gas", ("gas", "m³", "m3")),
            ("export", ("teruglever", "export", "teruggeleverd", "zonnebonus")),
            ("electricity", ("stroom", "elektr", "kwh", "afname", "import", "verbruik")),
            ("finance", ("kost", "euro", "€", "prijs", "tarief", "nextenergy", "termijn", "voorschot", "rekening", "factuur")),
            ("apparatus", ("airco", "apparaat", "socket", "heater", "koelkast", "diepvries", "warmte", "wasmachine", "vaatwasser")),
            ("report", ("rapport", "print", "pdf", "dashboard")),
        ]
        found: list[str] = []
        for domain, needles in rules:
            if any(needle in q for needle in needles):
                found.append(domain)

        # Generic "verbruik" without a more specific energy carrier maps to electricity.
        if "verbruik" in q and "gas" in found and "electricity" in found:
            found.remove("electricity")

        if not found and previous:
            inherited = [str(item) for item in previous.get("domains") or []]
            if inherited:
                return inherited
        return found or ["energy"]

    @staticmethod
    def _month_shift(year: int, month: int, delta: int) -> str:
        absolute = year * 12 + (month - 1) + delta
        target_year, target_month0 = divmod(absolute, 12)
        return f"{target_year:04d}_{target_month0 + 1:02d}"

    def _resolve_month(self, text: str, now: datetime, previous: dict[str, Any] | None) -> str:
        q = text.casefold()
        explicit = re.search(r"\b(20\d{2})[-_/](0?[1-9]|1[0-2])\b", q)
        if explicit:
            return f"{int(explicit.group(1)):04d}_{int(explicit.group(2)):02d}"

        month_names = {
            "januari": 1, "februari": 2, "maart": 3, "april": 4, "mei": 5, "juni": 6,
            "juli": 7, "augustus": 8, "september": 9, "oktober": 10, "november": 11, "december": 12,
        }
        named = next(((name, number) for name, number in month_names.items() if name in q), None)
        if named:
            year_match = re.search(r"\b(20\d{2})\b", q)
            year = int(year_match.group(1)) if year_match else now.year
            return f"{year:04d}_{named[1]:02d}"

        if "vorige maand" in q or "afgelopen maand" in q:
            if previous and re.fullmatch(r"\d{4}_\d{2}", str(previous.get("month") or "")):
                base = str(previous["month"])
                return self._month_shift(int(base[:4]), int(base[5:7]), -1)
            return self._month_shift(now.year, now.month, -1)

        if "deze maand" in q or "huidige maand" in q or "lopende maand" in q:
            return f"{now.year:04d}_{now.month:02d}"

        if previous and re.fullmatch(r"\d{4}_\d{2}", str(previous.get("month") or "")):
            return str(previous["month"])
        return f"{now.year:04d}_{now.month:02d}"

    @staticmethod
    def _find_month(analysis: dict[str, Any], month_key: str) -> dict[str, Any]:
        for item in analysis.get("months") or []:
            if str(item.get("month")) == month_key:
                return item
        return {"month": month_key, "metrics": {}, "quality": {"status": "missing"}, "financial_context": {}}

    def _build_evidence(
        self,
        text: str,
        domains: list[str],
        month: dict[str, Any],
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        metrics = month.get("metrics") or {}
        quality = month.get("quality") or {}
        sources = {
            "electricity": quality.get("grid_import_source"),
            "export": quality.get("grid_export_source"),
            "gas": quality.get("gas_source"),
        }
        evidence: dict[str, Any] = {
            "month": month.get("month"),
            "metrics": {
                "grid_import_kwh": metrics.get("grid_import_kwh"),
                "grid_export_kwh": metrics.get("grid_export_kwh"),
                "gas_m3": metrics.get("gas_m3"),
            },
            "sources": sources,
        }

        if "finance" in domains:
            supplier = analysis.get("supplier_context") or {}
            validation = supplier.get("contract_validation") or {}
            financial = month.get("financial_context") or {}
            evidence["finance"] = {
                "supplier": (supplier.get("contract") or {}).get("supplier") or "NextEnergy",
                "monthly_advance_eur": (supplier.get("contract") or {}).get("monthly_advance_eur"),
                "contract_components_ready": bool(validation.get("modeled_contract_components_ready")),
                "invoice_actuals_present": bool(validation.get("invoice_actuals_present")),
                "invoice_actual_eur": None,
                "observed_variable_electricity_cost_eur": financial.get("observed_variable_electricity_cost_eur"),
                "financial_status": financial.get("status"),
                "limitations": list(financial.get("limitations") or []),
            }

        if "apparatus" in domains:
            try:
                evidence["knowledge"] = self.knowledge_provider(text, domains) or {"matches": []}
            except Exception as exc:
                evidence["knowledge"] = {"matches": [], "status": "unavailable", "error": str(exc)}

        return evidence

    @staticmethod
    def _build_quality(
        month: dict[str, Any],
        evidence: dict[str, Any],
        domains: list[str],
        month_key: str,
        now: datetime,
    ) -> dict[str, Any]:
        quality = month.get("quality") or {}
        quarter = quality.get("quarter_hour") or {}
        current_key = f"{now.year:04d}_{now.month:02d}"
        partial = month_key == current_key or str(quarter.get("coverage_status") or "").startswith("partial")
        if not (month.get("metrics") or {}):
            status = "UNKNOWN"
        else:
            status = "PARTIAL" if partial else "COMPLETE"

        result: dict[str, Any] = {
            "status": status,
            "source_quality": quality,
        }
        if "finance" in domains:
            finance = evidence.get("finance") or {}
            result["financial_claim"] = (
                "INVOICE_ACTUAL"
                if finance.get("invoice_actuals_present") and finance.get("invoice_actual_eur") is not None
                else "MODELED_OR_PARTIAL_NOT_INVOICE_ACTUAL"
            )
        return result

    @staticmethod
    def _proactive_observations(
        month: dict[str, Any],
        evidence: dict[str, Any],
        quality: dict[str, Any],
    ) -> list[dict[str, Any]]:
        observations: list[dict[str, Any]] = []
        if quality.get("status") == "PARTIAL":
            observations.append({
                "type": "partial_period",
                "message": "De lopende maand is nog PARTIEEL; totalen gelden alleen voor de beschikbare meetperiode.",
                "confidence": "high",
            })
        quarter = ((month.get("quality") or {}).get("quarter_hour") or {})
        if quarter.get("available"):
            observations.append({
                "type": "quarter_hour_coverage",
                "message": "De actuele maand gebruikt de gevalideerde kwartierreeks als primaire meetbron.",
                "confidence": "high",
                "sample_count": quarter.get("sample_count"),
            })
        finance = evidence.get("finance") or {}
        if finance and not finance.get("invoice_actuals_present"):
            observations.append({
                "type": "financial_gate",
                "message": "Contractcomponenten kunnen worden gemodelleerd, maar er is nog geen officiële factuuractual voor deze periode.",
                "confidence": "high",
            })
        return observations[:3]
