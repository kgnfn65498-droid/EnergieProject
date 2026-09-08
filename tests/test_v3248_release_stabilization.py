from __future__ import annotations

from release_test_contract import CURRENT_RELEASE, CURRENT_PM_VERSION
import builtins
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "slimmemeterportal_import" / "rootfs" / "app"
CONFIG = ROOT / "slimmemeterportal_import" / "config.yaml"


def test_v3248_release_identity_is_consistent():
    assert (ROOT / "VERSIE.txt").read_text(encoding="utf-8").strip() == CURRENT_RELEASE
    assert f'version: "{CURRENT_RELEASE}"' in CONFIG.read_text(encoding="utf-8")
    assert f'APP_VERSION = "{CURRENT_RELEASE}"' in (APP / "main.py").read_text(encoding="utf-8")
    assert f'TARGET_RELEASE_VERSION = "{CURRENT_RELEASE}"' in (APP / "mode_entrypoint.py").read_text(encoding="utf-8")
    assert (APP / "projectmanager_v2" / "VERSION.txt").read_text(encoding="utf-8").strip() == CURRENT_PM_VERSION


def test_github_publication_is_enabled_by_default_on_reset_or_fresh_install():
    config = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    assert config["options"]["github_publication_enabled"] is True
    assert config["schema"]["github_publication_enabled"] == "bool"


def test_full_ha_mode_entrypoint_import_survives_missing_optional_docker_tls_modules():
    code = r'''import builtins,sys
sys.path.insert(0,%r)
real=builtins.__import__
def blocked(name,*a,**k):
    if name.endswith('docker_engine_tls_client') or name.endswith('nas_docker_tls'):
        raise ImportError('optional docker/tls intentionally unavailable')
    return real(name,*a,**k)
builtins.__import__=blocked
import mode_entrypoint
print(mode_entrypoint.TARGET_RELEASE_VERSION)
''' % str(APP)
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == CURRENT_RELEASE


def test_abandoned_nas_publisher_stays_inert_by_default():
    bootstrap = (ROOT / "tools" / "bootstrap_nas_github_publisher.sh").read_text(encoding="utf-8")
    assert 'PUBLICATION_ENABLED=NO' in bootstrap
    assert '/publisher-private/enabled' in bootstrap
    assert 'python3' not in bootstrap
    assert '"$DOCKER" build' not in bootstrap
