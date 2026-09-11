from __future__ import annotations

STATUS_DOTS = {"GREEN": "🟢", "RED": "🔴", "ORANGE": "🟠"}

def audit_badge(*, status: str, repair_round: int, label: str) -> str:
    state = str(status or "").upper().strip()
    if state not in STATUS_DOTS:
        raise ValueError("unsupported audit status")
    try:
        round_no = int(repair_round)
    except (TypeError, ValueError) as exc:
        raise ValueError("repair_round must be an integer") from exc
    if round_no < 0:
        raise ValueError("repair_round must be >= 0")
    name = str(label or "").strip()
    if not name:
        raise ValueError("label required")
    return f"{STATUS_DOTS[state]} {round_no} — {name}"

def audit_rows(items):
    rows=[]
    for item in items or []:
        if not isinstance(item, dict):
            continue
        row=dict(item)
        row["badge"] = audit_badge(status=row.get("status"), repair_round=row.get("repair_round", 0), label=row.get("label"))
        rows.append(row)
    return rows
