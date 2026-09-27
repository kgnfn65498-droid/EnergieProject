"""Repository-wide pytest safety boundaries."""

import os
import sys
from pathlib import Path

from offline_test_guard import install_offline_guard


_ROOT = str(Path(__file__).resolve().parent)
_pythonpath = os.environ.get("PYTHONPATH", "")
_parts = [part for part in _pythonpath.split(os.pathsep) if part]
if _ROOT not in _parts:
    os.environ["PYTHONPATH"] = os.pathsep.join([_ROOT, *_parts])

# Make every test file order-independent. Some historical tests import runtime
# modules by their installed names; relying on an earlier test to mutate
# sys.path hides packaging regressions when a subset is run in isolation.
for _path in (
    _ROOT,
    str(Path(_ROOT) / "tools"),
    str(Path(_ROOT) / "slimmemeterportal_import/rootfs/app"),
    str(Path(_ROOT) / "slimmemeterportal_import/rootfs/app/projectmanager_v2"),
):
    if _path not in sys.path:
        sys.path.insert(0, _path)

install_offline_guard()

# Production uses a 20s post-delete soak. Unit/E2E tests exercise the same
# code path with a bounded 0.02s window; dedicated tests simulate late writers.
os.environ.setdefault("ENERGIE_CLEARUP_TYPE2_POST_DELETE_SOAK_SECONDS", "0.02")
