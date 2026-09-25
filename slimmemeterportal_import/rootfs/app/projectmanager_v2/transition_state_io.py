from __future__ import annotations

"""Standalone bridge to the app-level transition state I/O implementation."""
import importlib.util
from pathlib import Path

_IMPL = Path(__file__).resolve().parents[1] / "transition_state_io.py"
_spec = importlib.util.spec_from_file_location("energie_app_transition_state_io", _IMPL)
if _spec is None or _spec.loader is None:
    raise ImportError(f"Cannot load transition state I/O: {_IMPL}")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
read_transition_state = _mod.read_transition_state
TransitionStateReadError = _mod.TransitionStateReadError
