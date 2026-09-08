from release_test_contract import CURRENT_RELEASE, CURRENT_PM_VERSION
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
PUB=ROOT/'tools/nas_github_publisher.sh'
BOOT=ROOT/'tools/bootstrap_nas_github_publisher.sh'

def test_release_identity_and_ha_default():
    assert (ROOT/'VERSIE.txt').read_text().strip()==CURRENT_RELEASE
    assert f'version: "{CURRENT_RELEASE}"' in (ROOT/'slimmemeterportal_import/config.yaml').read_text()
    assert 'github_publication_enabled: true' in (ROOT/'slimmemeterportal_import/config.yaml').read_text()
    assert f'APP_VERSION = "{CURRENT_RELEASE}"' in (ROOT/'slimmemeterportal_import/rootfs/app/main.py').read_text()

def test_publisher_fail_closed_contract_and_no_force():
    s=PUB.read_text()
    for x in ('processed_zip_sha256','expected_previous_manifest_sha256','target_manifest_sha256','PUBLISHER_PROBE_GREEN','validated_historical_previous'):
        assert x in s
    assert '--force' not in s and 'force-with-lease' not in s
    assert 'release_validation_hold.json' not in s

def test_bootstrap_qnap_safe_no_image_build_no_host_python():
    s=BOOT.read_text()
    assert 'RUNTIME_TAG="alpine/git:2.54.0"' in s
    assert '"$DOCKER" build' not in s
    assert 'DOCKER_CONFIG' in s and '/tmp/energie-docker-client-' in s
    assert 'python3' not in s
    assert 'ssh-keyscan' not in s
    assert '/publisher-private/enabled' in s
    assert 'PUBLICATION_ENABLED=NO' in s
