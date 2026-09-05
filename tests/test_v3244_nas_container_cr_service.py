from __future__ import annotations

import hashlib
import sys
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[1]
PM = ROOT / 'slimmemeterportal_import/rootfs/app/projectmanager_v2'
if str(PM) not in sys.path:
    sys.path.insert(0, str(PM))


class FakeDocker:
    def __init__(self):
        self.export_calls = 0
        self.created = []
        self.removed = []
        self.containers = {
            'energie-filesystem-mcp': self._container('c1', 'energie-filesystem-mcp:runtime-v1'),
            'energie-quarter-hour-scheduler': self._container('c2', 'python:3.12-slim'),
            'energie-ngrok': self._container('c3', 'ngrok/ngrok:latest'),
            'energie-release-watcher': self._container('c4', 'python:3.12-slim'),
            'energie-git': self._container('c5', 'alpine/git:2.54.0'),
        }

    @staticmethod
    def _container(cid, image):
        return {
            'Id': cid,
            'Image': 'sha256:' + cid,
            'Name': '/' + cid,
            'Config': {'Image': image},
            'State': {'Status': 'running', 'Running': True, 'Paused': False, 'Restarting': False, 'Dead': False, 'StartedAt': 'fixed'},
            'RestartCount': 0,
        }

    def ping(self):
        return {'ok': True}

    def container_inspect(self, name):
        item = self.containers.get(name)
        return None if item is None else {**item, 'Config': dict(item['Config']), 'State': dict(item['State'])}

    def image_inspect(self, name):
        return {'Id': 'sha256:' + hashlib.sha256(name.encode()).hexdigest(), 'RepoTags': [name]}

    def image_export(self, names, destination):
        self.export_calls += 1
        destination = Path(destination)
        payload = destination.parent / 'image-manifest.txt'
        payload.write_text('\n'.join(names) + '\n')
        with tarfile.open(destination, 'w') as archive:
            archive.add(payload, arcname='image-manifest.txt')
        payload.unlink()
        return {'ok': True, 'bytes': destination.stat().st_size, 'images': list(names)}

    def container_create_probe(self, image, name):
        self.created.append((image, name))
        return {'Id': 'probe-' + str(len(self.created))}

    def container_remove_probe(self, name):
        self.removed.append(name)
        return {'ok': True, 'name': name}


def make_project(tmp_path: Path) -> Path:
    root = tmp_path / 'EnergieProject'
    (root / 'Infra/Docker').mkdir(parents=True)
    (root / 'App').mkdir()
    (root / 'Backups/NAS Container').mkdir(parents=True)
    (root / 'Infra/docker-compose.yml').write_text('services: {}\n')
    (root / 'Infra/Docker/Energie.env').write_text('SECRET=not-for-ui\n')
    (root / 'App/VERSIE.txt').write_text('32.4.4\n')
    return root


def make_old_valid_set(target: Path, stem='2026-09-04 12.29 CrashRecovery NAS Containers'):
    z = target / f'{stem}.zip'
    with zipfile.ZipFile(z, 'w') as archive:
        archive.writestr('ok.txt', 'ok')
    digest = hashlib.sha256(z.read_bytes()).hexdigest()
    s = target / f'{stem}.zip.sha256'
    v = target / f'{stem} VERIFY.txt'
    s.write_text(f'{digest}  {z.name}\n')
    v.write_text('NAS_CONTAINER_CR_ACCEPTANCE_OK\nPRODUCTION_CONTAINERS_CHANGED=NO\n')
    return z, s, v


def fixed_now():
    return datetime(2026, 9, 5, 13, 27, tzinfo=ZoneInfo('Europe/Amsterdam'))


def test_unusable_target_fails_before_image_export(tmp_path):
    from nas_container_cr_service import NasContainerCrService

    root = make_project(tmp_path)
    target = root / 'Backups/NAS Container'
    target.rmdir()
    target.write_text('not-a-directory')
    docker = FakeDocker()
    with pytest.raises(RuntimeError, match='backupmap'):
        NasContainerCrService(root, docker, now=fixed_now).create()
    assert docker.export_calls == 0


def test_lock_blocks_concurrent_second_run(tmp_path):
    from nas_container_cr_service import NasContainerCrService

    root = make_project(tmp_path)
    target = root / 'Backups/NAS Container'
    (target / '.nas-container-cr.lock').mkdir()
    docker = FakeDocker()
    with pytest.raises(RuntimeError, match='al actief'):
        NasContainerCrService(root, docker, now=fixed_now).create()
    assert docker.export_calls == 0


def test_old_set_is_untouched_when_archive_validation_fails(tmp_path, monkeypatch):
    from nas_container_cr_service import NasContainerCrService

    root = make_project(tmp_path)
    target = root / 'Backups/NAS Container'
    old = make_old_valid_set(target)
    docker = FakeDocker()
    service = NasContainerCrService(root, docker, now=fixed_now)
    monkeypatch.setattr(service, '_verify_archive', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('ZIP validation forced')))
    with pytest.raises(RuntimeError, match='ZIP validation forced'):
        service.create()
    assert all(path.exists() for path in old)


def test_success_creates_three_file_set_then_keep1(tmp_path):
    from nas_container_cr_service import NasContainerCrService

    root = make_project(tmp_path)
    target = root / 'Backups/NAS Container'
    old = make_old_valid_set(target)
    docker = FakeDocker()
    result = NasContainerCrService(root, docker, now=fixed_now).create()

    assert result['ok'] is True
    assert result['backup_dir'].endswith('Backups/NAS Container')
    assert result['retention']['removed'] == 1
    assert not any(path.exists() for path in old)
    assert Path(result['zip']).is_file()
    assert Path(result['sha256_file']).is_file()
    verify = Path(result['verify_file'])
    assert verify.is_file()
    text = verify.read_text()
    assert 'NAS_CONTAINER_CR_ACCEPTANCE_OK' in text
    assert 'PRODUCTION_CONTAINERS_CHANGED=NO' in text
    assert 'NAS_CR_RETENTION_KEEP1_OK' in text
    assert len(docker.created) == result['image_count']
    assert len(docker.removed) == result['image_count']


class CorruptExportDocker(FakeDocker):
    def image_export(self, names, destination):
        self.export_calls += 1
        Path(destination).write_bytes(b'NOT_A_TAR')
        return {'ok': True, 'bytes': Path(destination).stat().st_size, 'images': list(names)}


def test_corrupt_docker_image_tar_fails_before_old_retention(tmp_path):
    from nas_container_cr_service import NasContainerCrService

    root = make_project(tmp_path)
    target = root / 'Backups/NAS Container'
    old = make_old_valid_set(target)
    docker = CorruptExportDocker()
    with pytest.raises(RuntimeError, match='image export.*tar'):
        NasContainerCrService(root, docker, now=fixed_now).create()
    assert all(path.exists() for path in old)


def test_old_set_is_restored_when_final_retention_marker_write_fails(tmp_path, monkeypatch):
    import nas_container_cr_service as mod

    root = make_project(tmp_path)
    target = root / 'Backups/NAS Container'
    old = make_old_valid_set(target)
    docker = FakeDocker()
    original = mod._atomic_text

    def fail_final_marker(path, text, **kwargs):
        if 'NAS_CR_RETENTION_KEEP1_OK' in text:
            raise OSError('forced final marker failure')
        return original(path, text, **kwargs)

    monkeypatch.setattr(mod, '_atomic_text', fail_final_marker)
    with pytest.raises(OSError, match='final marker failure'):
        mod.NasContainerCrService(root, docker, now=fixed_now).create()
    assert all(path.exists() for path in old)


def test_stale_lock_from_dead_process_is_recovered_without_terminal(tmp_path):
    from nas_container_cr_service import NasContainerCrService

    root = make_project(tmp_path)
    lock = root / 'Backups/NAS Container/.nas-container-cr.lock'
    lock.mkdir()
    (lock / 'owner.txt').write_text('pid=99999999\n')
    result = NasContainerCrService(root, FakeDocker(), now=fixed_now).create()
    assert result['ok'] is True
    assert not lock.exists()


def test_failed_new_attempt_cleans_its_partial_top_level_files(tmp_path, monkeypatch):
    from nas_container_cr_service import NasContainerCrService

    root = make_project(tmp_path)
    target = root / 'Backups/NAS Container'
    docker = FakeDocker()
    service = NasContainerCrService(root, docker, now=fixed_now)
    monkeypatch.setattr(service, '_verify_archive', lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError('forced archive failure')))
    with pytest.raises(RuntimeError, match='forced archive failure'):
        service.create()
    stem = '2026-09-05 13.27 CrashRecovery NAS Containers'
    assert not (target / f'{stem}.zip').exists()
    assert not (target / f'{stem}.zip.sha256').exists()
    assert not (target / f'{stem} VERIFY.txt').exists()
