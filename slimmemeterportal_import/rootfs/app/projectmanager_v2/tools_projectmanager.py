from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from config import READ_ONLY_ANNOTATIONS, WRITE_ANNOTATIONS
from projectmanager_api import ProjectmanagerAPI
from registry import mcp

RUNTIME_ROOT = Path(os.environ.get('PM_SYSTEM_ROOT', '/system/Projectmanager/RuntimeV2')).resolve()


def _api() -> ProjectmanagerAPI:
    return ProjectmanagerAPI(RUNTIME_ROOT)


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def projectmanager_status() -> dict[str, Any]:
    """Return the compact factual status from the Energie Projectmanager runtime."""
    return _api().status()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def projectmanager_handover() -> dict[str, Any]:
    """Return the persistent compact working-context handover."""
    return _api().handover()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def projectmanager_decisions() -> dict[str, Any]:
    """Return only pending decisions that require Peter."""
    return _api().decisions()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def projectmanager_opportunities() -> dict[str, Any]:
    """Return the evidence-based Opportunity Register."""
    return _api().opportunities()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def projectmanager_nomad_context() -> dict[str, Any]:
    """Return the compact Projectmanager truth intended for Nomad."""
    return _api().nomad_context()


@mcp.tool(annotations=READ_ONLY_ANNOTATIONS)
def projectmanager_parent_summary() -> dict[str, Any]:
    """Return compact status for a future overarching multi-project manager."""
    return _api().parent_summary()


@mcp.tool(annotations=WRITE_ANNOTATIONS)
def projectmanager_submit_command(
    intent: str,
    text: str = '',
    source: str = 'chat',
    title: str = '',
    goal: str = '',
    steps_total: int = 1,
    priority: int = 2,
    next_action: str = '',
) -> dict[str, Any]:
    """Queue a Projectmanager command. Protected intents create approval requests and never execute directly."""
    return _api().submit_command({
        'intent': intent,
        'text': text,
        'source': source,
        'title': title,
        'goal': goal,
        'steps_total': steps_total,
        'priority': priority,
        'next_action': next_action,
    })


@mcp.tool(annotations=WRITE_ANNOTATIONS)
def projectmanager_resolve_decision(
    decision_id: str,
    approved: bool,
    approved_by: str = 'Peter',
) -> dict[str, Any]:
    """Record Peter's explicit approval/rejection for one already-pending protected decision. This does not itself deploy, purchase or change architecture."""
    return _api().resolve_decision(decision_id, approved=approved, approved_by=approved_by)
