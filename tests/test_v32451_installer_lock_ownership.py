from pathlib import Path
import os
import subprocess

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / 'tests' / 'fixtures' / 'pre57' / 'release_installer.sh'


def test_second_installer_must_not_remove_lock_owned_by_active_installer(tmp_path: Path):
    inbox = tmp_path / 'Inbox'
    (inbox / '.installer.lock').mkdir(parents=True)
    (tmp_path / 'App').mkdir()
    env = os.environ.copy()
    env['ENERGIE_ROOT'] = str(tmp_path)
    env['ENERGIE_INSTALLER_REEXEC'] = '1'

    result = subprocess.run(
        ['sh', str(INSTALLER)],
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert 'installer is al actief' in (result.stdout + result.stderr)
    assert (inbox / '.installer.lock').is_dir(), (
        'A second installer that did not acquire the lock must not remove the active installer lock'
    )
