from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable


def load_quarter_hour_series_once(
    data_root: Path,
    month_key: str,
    entity_ids: Iterable[str],
) -> dict[str, list[dict[str, Any]]]:
    """Read one HA quarter-hour folder once and extract all requested entities.

    This is deliberately filesystem-only and read-only. It avoids N repeated JSON
    parses of the same month when several cumulative meters are needed together.
    """
    requested = tuple(dict.fromkeys(str(item) for item in entity_ids if str(item)))
    result: dict[str, list[dict[str, Any]]] = {entity_id: [] for entity_id in requested}
    if not requested:
        return result

    folder = data_root / "01_Input" / month_key / "HomeAssistant" / "QuarterHour"
    if not folder.is_dir():
        return result

    wanted = set(requested)
    pattern = re.compile(r"home_assistant_quarter_(\d{8}T\d{6}Z)\.json$")
    for snapshot in sorted(folder.glob("home_assistant_quarter_*.json")):
        match = pattern.search(snapshot.name)
        if not match:
            continue
        try:
            payload = json.loads(snapshot.read_text(encoding="utf-8"))
        except Exception:
            continue
        entities = payload.get("entities") if isinstance(payload, dict) else None
        if not isinstance(entities, list):
            continue
        remaining = set(wanted)
        for entity in entities:
            if not isinstance(entity, dict):
                continue
            entity_id = str(entity.get("entity_id") or "")
            if entity_id not in remaining:
                continue
            try:
                value = float(str(entity.get("state")).replace(",", "."))
            except (TypeError, ValueError):
                remaining.remove(entity_id)
                continue
            result[entity_id].append(
                {
                    "snapshot_timestamp": match.group(1),
                    "entity_timestamp": entity.get("last_updated") or entity.get("last_changed"),
                    "value": value,
                    "transport": "nas_data_filesystem_read_only_single_pass",
                }
            )
            remaining.remove(entity_id)
            if not remaining:
                break

    for entity_id, items in result.items():
        dedup = {item["snapshot_timestamp"]: item for item in items}
        result[entity_id] = [dedup[key] for key in sorted(dedup)]
    return result
