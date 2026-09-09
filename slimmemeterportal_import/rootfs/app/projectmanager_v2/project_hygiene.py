from __future__ import annotations

"""Projectmanager-local import bridge for project hygiene checks.

The Home Assistant Projectmanager runtime can place only this directory on
``sys.path``.  The implementation intentionally remains one level up so the
housekeeping and release code share a single source of truth.
"""

import importlib.util
from pathlib import Path

_IMPL = Path(__file__).resolve().parents[1] / "project_hygiene.py"
_spec = importlib.util.spec_from_file_location("energie_project_hygiene_impl", _IMPL)
if _spec is None or _spec.loader is None:  # pragma: no cover - packaging corruption
    raise ImportError(f"Cannot load project hygiene implementation: {_IMPL}")
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)

project_hygiene_check = _module.project_hygiene_check
ngrok_security_check = _module.ngrok_security_check

__all__ = ["project_hygiene_check", "ngrok_security_check"]
