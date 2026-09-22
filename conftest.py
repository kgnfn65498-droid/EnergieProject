"""Repository-wide pytest safety boundaries."""

import os
from pathlib import Path

from offline_test_guard import install_offline_guard


_ROOT = str(Path(__file__).resolve().parent)
_pythonpath = os.environ.get("PYTHONPATH", "")
_parts = [part for part in _pythonpath.split(os.pathsep) if part]
if _ROOT not in _parts:
    os.environ["PYTHONPATH"] = os.pathsep.join([_ROOT, *_parts])

install_offline_guard()
