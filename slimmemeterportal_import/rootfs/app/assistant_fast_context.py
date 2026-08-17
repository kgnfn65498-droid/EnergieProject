from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Any, Iterable


_CACHE_LOCK = threading.RLock()
_QUARTER_HOUR_CACHE: dict[tuple[str, tuple[str, ...]], dict[str, Any]] = {}


def clear_quarter_hour_series_cache() -> None:
    """Clear only the in-memory assistant quarter-hour cache."""
    with _CACHE_LOCK:
        _QUARTER_HOUR_CACHE.clear()


def _copy_series(result: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    return {
        entity_id: [dict(item) for item in items]
        for entity_id, items in result.items()
    }


def load_quarter_hour_series_once(
    data_root: Path,
    month_key: str,
    entity_ids: Iterable[str],
) -> dict[str, list[dict[str, Any]]]:
    """Read HA quarter-hour snapshots once, then incrementally consume new files.

    Snapshot files are append-only collector evidence. The first call validates the
    existing month by parsing every snapshot. Later calls reuse that validated
    in-memory series and parse only newly appended filenames. If the filename prefix
    changes or files disappear, the cache is invalidated and the month is rebuilt.
    """
    requested = tuple(dict.fromkeys(str(item) for item in entity_ids if str(item)))
    empty: dict[str, list[dict[str, Any]]] = {entity_id: [] for entity_id in requested}
    if not requested:
        return empty

    folder = data_root / "01_Input" / month_key / "HomeAssistant" / "QuarterHour"
    if not folder.is_dir():
        return empty

    cache_key = (str(folder), requested)
    pattern = re.compile(r"home_assistant_quarter_(\d{8}T\d{6}Z)\.json$")

    with _CACHE_LOCK:
        files = tuple(sorted(folder.glob("home_assistant_quarter_*.json")))
        names = tuple(path.name for path in files)
        state = _QUARTER_HOUR_CACHE.get(cache_key)

        if state is not None:
            old_names = tuple(state.get("names") or ())
            prefix_ok = len(names) >= len(old_names) and names[: len(old_names)] == old_names
        else:
            old_names = ()
            prefix_ok = False

        if state is None or not prefix_ok:
            result: dict[str, list[dict[str, Any]]] = {
                entity_id: [] for entity_id in requested
            }
            start_index = 0
        else:
            result = _copy_series(state["result"])
            start_index = len(old_names)

        wanted = set(requested)
        for snapshot in files[start_index:]:
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

        _QUARTER_HOUR_CACHE[cache_key] = {
            "names": names,
            "result": _copy_series(result),
        }
        return _copy_series(result)
