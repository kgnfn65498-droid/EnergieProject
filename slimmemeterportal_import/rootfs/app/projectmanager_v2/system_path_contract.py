from __future__ import annotations

"""Standalone bridge to the app-level Type2 system path contract.

Projectmanager modules are also imported in isolation by tests/tools with only
this directory on sys.path. Load the canonical parent implementation under an
alias so both embedded runtime and standalone imports use one contract.
"""
import importlib.util
from pathlib import Path

_IMPL = Path(__file__).resolve().parents[1] / "system_path_contract.py"
_spec = importlib.util.spec_from_file_location("energie_app_system_path_contract", _IMPL)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load system path contract: {_IMPL}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

project_system_path = _mod.project_system_path
mapping_for_source = _mod.mapping_for_source
MAPPINGS = _mod.MAPPINGS
SCHEMA = _mod.SCHEMA
ACTIVATION_ROOT = _mod.ACTIVATION_ROOT

active_mapping_fingerprint = _mod.active_mapping_fingerprint
