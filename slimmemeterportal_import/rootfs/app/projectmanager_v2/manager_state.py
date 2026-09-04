from dataclasses import dataclass, asdict, field
from typing import List, Optional
import json

EVIDENCE_STATES = {'BEWEZEN', 'AANGENOMEN', 'NOG_TE_CONTROLEREN', 'GEBLOKKEERD'}

@dataclass
class ActiveTask:
    title: str
    goal: str
    step: int
    steps_total: int
    next_action: str
    blocker: Optional[str] = None
    pending_approval: Optional[str] = None

@dataclass
class ManagerState:
    project_id: str = 'energie'
    mode: str = 'DEVELOPMENT'
    health: str = 'GREEN'
    active_task: Optional[ActiveTask] = None
    decisions_needed: List[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def evidence_status(status: str) -> str:
    if status not in EVIDENCE_STATES:
        raise ValueError(f'unknown evidence status: {status}')
    return status
