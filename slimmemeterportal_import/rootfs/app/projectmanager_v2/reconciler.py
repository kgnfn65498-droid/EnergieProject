from dataclasses import dataclass
from typing import Any, Dict, List

@dataclass
class Drift:
    key: str
    runtime_value: Any
    documented_value: Any


def find_drift(runtime: Dict[str, Any], documented: Dict[str, Any]) -> List[Drift]:
    drift = []
    for key, value in runtime.items():
        if key in documented and documented[key] != value:
            drift.append(Drift(key, value, documented[key]))
    return drift


def reconciliation_action(*, certain: bool, safe: bool) -> str:
    return 'AUTO_RECONCILE' if certain and safe else 'STAGE_AND_ISSUE'
