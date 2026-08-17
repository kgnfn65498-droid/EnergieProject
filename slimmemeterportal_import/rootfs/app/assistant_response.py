from __future__ import annotations

from typing import Any

_MONTHS_NL = {
    1: "januari", 2: "februari", 3: "maart", 4: "april", 5: "mei", 6: "juni",
    7: "juli", 8: "augustus", 9: "september", 10: "oktober", 11: "november", 12: "december",
}


def _month_label(month_key: str | None) -> str:
    try:
        year = int(str(month_key)[:4])
        month = int(str(month_key)[5:7])
    except (TypeError, ValueError):
        return "de gekozen periode"
    return f"{_MONTHS_NL.get(month, 'maand')} {year}"


def _number(value: Any, decimals: int = 3) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return "onbekend"
    rendered = f"{number:.{decimals}f}".rstrip("0").rstrip(".")
    return rendered.replace(".", ",")


def render_assistant_response(context: dict[str, Any]) -> str:
    """Render a deterministic, information-only Dutch answer from validated context."""
    resolved = context.get("resolved") or {}
    evidence = context.get("evidence") or {}
    metrics = evidence.get("metrics") or {}
    domains = set(resolved.get("domains") or [])
    month = _month_label(resolved.get("month"))
    quality = str((context.get("quality") or {}).get("status") or "ONBEKEND")
    partial_suffix = " De periode is nog PARTIEEL." if quality.upper() == "PARTIAL" else ""

    if "finance" in domains:
        finance = evidence.get("finance") or {}
        supplier = str(finance.get("supplier") or "de leverancier")
        advance = finance.get("monthly_advance_eur")
        if not finance.get("invoice_actuals_present"):
            advance_text = f" Het termijnbedrag in het project is €{_number(advance, 2)}." if advance is not None else ""
            return (
                f"Voor {month} is bij {supplier} nog geen officiële factuuractual beschikbaar."
                f" De beschikbare kostencontext is daarom gemodelleerd of partieel.{advance_text}"
            )
        invoice = finance.get("invoice_actual_eur")
        return f"De officiële factuuractual bij {supplier} voor {month} is €{_number(invoice, 2)}."

    if "apparatus" in domains:
        knowledge = evidence.get("knowledge") or {}
        matches = knowledge.get("matches") or []
        texts = [str(item.get("text") or "").strip() for item in matches if isinstance(item, dict)]
        texts = [text for text in texts if text]
        if texts:
            return "Volgens de Knowledge Base: " + " ".join(texts[:3])
        return "Voor dit apparaat is in de gevalideerde Knowledge Base geen concreet bewijs gevonden."

    parts: list[str] = []
    if "gas" in domains and metrics.get("gas_m3") is not None:
        parts.append(f"In {month} heb je {_number(metrics.get('gas_m3'))} m³ gas gebruikt.")
    if "electricity" in domains and metrics.get("grid_import_kwh") is not None:
        parts.append(f"In {month} heb je {_number(metrics.get('grid_import_kwh'))} kWh van het net afgenomen.")
    if ("export" in domains or "electricity" in domains) and metrics.get("grid_export_kwh") is not None:
        parts.append(f"Je hebt in {month} {_number(metrics.get('grid_export_kwh'))} kWh teruggeleverd.")

    if parts:
        return " ".join(parts) + partial_suffix

    available = []
    for label, key, unit in (
        ("netafname", "grid_import_kwh", "kWh"),
        ("teruglevering", "grid_export_kwh", "kWh"),
        ("gas", "gas_m3", "m³"),
    ):
        if metrics.get(key) is not None:
            available.append(f"{label} {_number(metrics.get(key))} {unit}")
    if available:
        return f"Voor {month} is beschikbaar: " + ", ".join(available) + "." + partial_suffix
    return f"Voor {month} is geen passende gevalideerde meetwaarde beschikbaar."


def build_assistant_response_payload(engine: Any, app_version: str, query: str, session_id: str | None = None) -> dict[str, Any]:
    """Build the shared deterministic information-only assistant response payload."""
    context = engine.context(query, session_id=session_id)
    return {
        "schema": "energie_assistant_response_v1",
        "version": app_version,
        "speech": render_assistant_response(context),
        "session_id": context.get("session_id"),
        "context": context,
    }
