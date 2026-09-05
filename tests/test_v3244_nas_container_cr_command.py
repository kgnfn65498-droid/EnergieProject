from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
if str(PM) not in sys.path:
    sys.path.insert(0, str(PM))


def test_nas_container_cr_intent_is_installed_and_parameterless():
    from command_gateway import COMMANDS

    assert COMMANDS['nas_container_cr_create'] == {
        'action': 'nas_container_cr_create',
        'allowed_without_approval': True,
    }
