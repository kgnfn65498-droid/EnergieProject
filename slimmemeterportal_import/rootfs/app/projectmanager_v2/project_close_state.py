"""Projectmanager import bridge to the canonical app-level project-close state.

The shared closure state is implemented once at app level because both the
Home Assistant clearup worker and Projectmanager consume the same file/contract.
Projectmanager can also be imported standalone in tests/tools with only its own
source directory on ``sys.path``; this bridge keeps that import mode working
without duplicating the state implementation.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

_CANONICAL_PATH = Path(__file__).resolve().parents[1] / 'project_close_state.py'
_SPEC = importlib.util.spec_from_file_location('_energie_project_close_state', _CANONICAL_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise ImportError(f'canonical project_close_state unavailable: {_CANONICAL_PATH}')
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)

SCHEMA = _MODULE.SCHEMA
VALID_STATES = _MODULE.VALID_STATES
RELATIVE_PATH = _MODULE.RELATIVE_PATH
project_close_path = _MODULE.project_close_path
load_project_close = _MODULE.load_project_close
write_project_close = _MODULE.write_project_close

__all__ = [
    'SCHEMA', 'VALID_STATES', 'RELATIVE_PATH',
    'project_close_path', 'load_project_close', 'write_project_close',
]
