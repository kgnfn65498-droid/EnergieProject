from __future__ import annotations

import hashlib
import json
import os
import shutil
import tarfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Europe/Amsterdam')
CORE_CONTAINERS = (
    'energie-filesystem-mcp',
    'energie-quarter-hour-scheduler',
    'energie-ngrok',
    'energie-release-watcher',
)
OPTIONAL_CONTAINERS = ('energie-git',)
BASE_IMAGE = 'python:3.12-slim'
ACCEPTANCE_MARKER = 'NAS_CONTAINER_CR_ACCEPTANCE_OK'
UNCHANGED_MARKER = 'PRODUCTION_CONTAINERS_CHANGED=NO'
RETENTION_MARKER = 'NAS_CR_RETENTION_KEEP1_OK'


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def _atomic_text(path: Path, text: str, *, mode: int = 0o660) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + f'.tmp-{os.getpid()}')
    fd = os.open(str(temp), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink(missing_ok=True)
        except OSError:
            pass


def _safe_member(name: str) -> Path:
    member = Path(name)
    if member.is_absolute() or '..' in member.parts or not name or '\\' in name:
        raise RuntimeError(f'Onveilig ZIP-lid: {name}')
    return member


def _stable_container_view(item: dict[str, Any] | None) -> dict[str, Any] | None:
    if item is None:
        return None
    state = item.get('State') or {}
    config = item.get('Config') or {}
    return {
        'Id': item.get('Id'),
        'Image': item.get('Image'),
        'Name': item.get('Name'),
        'Config.Image': config.get('Image'),
        'State.Status': state.get('Status'),
        'State.Running': state.get('Running'),
        'State.Paused': state.get('Paused'),
        'State.Restarting': state.get('Restarting'),
        'State.Dead': state.get('Dead'),
        'State.StartedAt': state.get('StartedAt'),
        'RestartCount': item.get('RestartCount'),
    }


class NasContainerCrService:
    def __init__(
        self,
        project_root: Path | str,
        docker_client,
        *,
        now: Callable[[], datetime] | None = None,
    ):
        self.project_root = Path(project_root)
        self.docker = docker_client
        self.now = now or (lambda: datetime.now(TZ))
        self.target = self.project_root / 'Backups' / 'NAS Container'
        self.lock = self.target / '.nas-container-cr.lock'

    def _prepare_target(self) -> None:
        if self.target.exists() and not self.target.is_dir():
            raise RuntimeError(f'NAS Container backupmap is geen directory: {self.target}')
        try:
            self.target.mkdir(parents=True, exist_ok=True)
            probe = self.target / f'.write-probe-{os.getpid()}'
            probe.write_text('ok\n', encoding='utf-8')
            probe.unlink()
        except OSError as exc:
            raise RuntimeError(f'NAS Container backupmap is niet schrijfbaar: {exc}') from exc

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True

    def _recover_dead_lock(self) -> bool:
        owner = self.lock / 'owner.txt'
        try:
            text = owner.read_text(encoding='utf-8').strip()
            pid = int(text.removeprefix('pid='))
        except (OSError, ValueError):
            return False
        if self._pid_alive(pid):
            return False
        try:
            entries = list(self.lock.iterdir())
            if entries != [owner]:
                return False
            owner.unlink()
            self.lock.rmdir()
            return True
        except OSError:
            return False

    def _acquire_lock(self) -> None:
        try:
            self.lock.mkdir()
        except FileExistsError as exc:
            if not self._recover_dead_lock():
                raise RuntimeError('NAS Container Crash Recovery is al actief') from exc
            self.lock.mkdir()
        _atomic_text(self.lock / 'owner.txt', f'pid={os.getpid()}\n')

    def _release_lock(self) -> None:
        try:
            (self.lock / 'owner.txt').unlink(missing_ok=True)
            self.lock.rmdir()
        except OSError:
            pass

    def _new_stem(self, at: datetime) -> str:
        base = at.astimezone(TZ).strftime('%Y-%m-%d %H.%M') + ' CrashRecovery NAS Containers'
        stem = base
        seq = 2
        while any((self.target / suffix).exists() for suffix in (
            f'{stem}.zip', f'{stem}.zip.sha256', f'{stem} VERIFY.txt'
        )):
            stem = f'{base} ({seq})'
            seq += 1
        return stem

    def _required_project_files(self) -> tuple[tuple[Path, str, int], ...]:
        return (
            (self.project_root / 'Infra/docker-compose.yml', 'project/Infra/docker-compose.yml', 0o640),
            (self.project_root / 'Infra/Docker/Energie.env', 'private/Energie.env', 0o600),
            (self.project_root / 'App/VERSIE.txt', 'project/VERSIE.txt', 0o640),
        )

    def _copy_project_files(self, stage: Path) -> str:
        for source, rel, mode in self._required_project_files():
            if not source.is_file() or source.is_symlink():
                raise RuntimeError(f'Vereist NAS CR-bronbestand ontbreekt of is onveilig: {source}')
            target = stage / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            try:
                target.chmod(mode)
            except OSError:
                pass
        return (self.project_root / 'App/VERSIE.txt').read_text(encoding='utf-8').strip()

    def _container_snapshot(self) -> tuple[dict[str, Any], list[str]]:
        snapshot: dict[str, Any] = {}
        images: list[str] = []
        for name in CORE_CONTAINERS + OPTIONAL_CONTAINERS:
            item = self.docker.container_inspect(name)
            if name in CORE_CONTAINERS and item is None:
                raise RuntimeError(f'Vereiste productiecontainer ontbreekt: {name}')
            snapshot[name] = _stable_container_view(item)
            if item is not None:
                image = str((item.get('Config') or {}).get('Image') or '').strip()
                if not image:
                    raise RuntimeError(f'Container {name} heeft geen image-referentie')
                if image not in images:
                    images.append(image)
        if BASE_IMAGE not in images:
            images.append(BASE_IMAGE)
        return snapshot, sorted(images)

    def _write_runtime_evidence(self, stage: Path, *, at: datetime, snapshot: dict[str, Any], images: list[str]) -> None:
        runtime = stage / 'runtime'
        private = stage / 'private'
        runtime.mkdir(parents=True, exist_ok=True)
        private.mkdir(parents=True, exist_ok=True)
        lines = [
            at.astimezone(TZ).isoformat(),
            'Docker TLS ping: OK',
            '--- production containers ---',
        ]
        for name in CORE_CONTAINERS + OPTIONAL_CONTAINERS:
            view = snapshot.get(name)
            if view is None:
                lines.append(f'{name}|ABSENT_OPTIONAL')
            else:
                lines.append(f"{name}|{view.get('Config.Image')}|{view.get('State.Status')}")
        (runtime / 'runtime_snapshot.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        (runtime / 'images.txt').write_text(''.join(f'{image}\n' for image in images), encoding='utf-8')
        for name in CORE_CONTAINERS + OPTIONAL_CONTAINERS:
            item = self.docker.container_inspect(name)
            if item is not None:
                (private / f'inspect_{name}.json').write_text(
                    json.dumps(item, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8'
                )
        for image in images:
            detail = self.docker.image_inspect(image)
            safe = ''.join(ch if ch.isalnum() or ch in '._-' else '_' for ch in image)
            (runtime / f'image_{safe}.json').write_text(
                json.dumps(detail, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8'
            )

    @staticmethod
    def _write_restore_doc(stage: Path) -> None:
        docs = stage / 'docs'
        docs.mkdir(parents=True, exist_ok=True)
        (docs / 'RESTORE_ACCEPTANCE.txt').write_text(
            'NAS/Containers Crash Recovery acceptance package.\n'
            'Doel: herstel van container-runtime na vervanging/herbouw NAS.\n'
            'Vereist daarnaast de afzonderlijk groen-geteste EnergieProject CR voor projectdata/broncode.\n'
            'Deze acceptatietest wijzigt geen productiecontainers.\n',
            encoding='utf-8',
        )

    @staticmethod
    def _write_internal_hashes(stage: Path) -> int:
        paths = sorted(
            p for p in stage.rglob('*')
            if p.is_file() and p.name not in {'SHA256SUMS.txt', 'INTERNAL_VERIFY.txt'}
        )
        rows = []
        for path in paths:
            rel = path.relative_to(stage).as_posix()
            rows.append(f'{_sha256_file(path)}  {rel}')
        (stage / 'SHA256SUMS.txt').write_text('\n'.join(rows) + '\n', encoding='utf-8')
        NasContainerCrService._verify_hash_manifest(stage)
        (stage / 'INTERNAL_VERIFY.txt').write_text(
            ''.join(f'{row.split("  ", 1)[1]}: OK\n' for row in rows), encoding='utf-8'
        )
        return len(rows)

    @staticmethod
    def _verify_hash_manifest(root: Path) -> int:
        manifest = root / 'SHA256SUMS.txt'
        if not manifest.is_file():
            raise RuntimeError('SHA256SUMS.txt ontbreekt')
        count = 0
        for raw in manifest.read_text(encoding='utf-8').splitlines():
            if not raw.strip():
                continue
            try:
                expected, rel = raw.split('  ', 1)
            except ValueError as exc:
                raise RuntimeError('Ongeldige SHA256SUMS-regel') from exc
            if len(expected) != 64 or any(ch not in '0123456789abcdef' for ch in expected):
                raise RuntimeError('Ongeldige SHA256 in manifest')
            path = root / _safe_member(rel)
            if not path.is_file() or _sha256_file(path) != expected:
                raise RuntimeError(f'SHA256-validatie mislukt: {rel}')
            count += 1
        if count < 1:
            raise RuntimeError('SHA256SUMS bevat geen bestanden')
        return count

    @staticmethod
    def _build_zip(stage: Path, output: Path) -> None:
        temp = output.with_name(output.name + f'.tmp-{os.getpid()}')
        try:
            with zipfile.ZipFile(temp, 'w', allowZip64=True) as archive:
                for path in sorted(stage.rglob('*')):
                    if not path.is_file():
                        continue
                    rel = path.relative_to(stage).as_posix()
                    compression = zipfile.ZIP_STORED if path.suffix == '.tar' else zipfile.ZIP_DEFLATED
                    archive.write(path, rel, compress_type=compression)
            os.replace(temp, output)
        finally:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass

    def _verify_archive(self, archive_path: Path, restore: Path) -> int:
        restore.mkdir(parents=True, exist_ok=False)
        with zipfile.ZipFile(archive_path, 'r') as archive:
            for item in archive.infolist():
                _safe_member(item.filename)
            bad = archive.testzip()
            if bad:
                raise RuntimeError(f'ZIP-integriteit mislukt: {bad}')
            archive.extractall(restore)
        return self._verify_hash_manifest(restore)

    def _probe_images(self, images: list[str], stamp: str) -> int:
        count = 0
        for index, image in enumerate(images):
            name = f'nas-cr-probe-{stamp}-{index}'
            created = False
            try:
                self.docker.container_create_probe(image, name)
                created = True
            finally:
                if created:
                    self.docker.container_remove_probe(name)
            count += 1
        return count

    @staticmethod
    def _set_paths(target: Path, stem: str) -> tuple[Path, Path, Path]:
        return target / f'{stem}.zip', target / f'{stem}.zip.sha256', target / f'{stem} VERIFY.txt'

    @staticmethod
    def _validate_set(target: Path, stem: str, *, require_retention_marker: bool = False) -> bool:
        z, sha, verify = NasContainerCrService._set_paths(target, stem)
        if not z.is_file() or not sha.is_file() or not verify.is_file():
            return False
        try:
            expected = sha.read_text(encoding='utf-8').split()[0]
        except (OSError, IndexError):
            return False
        if len(expected) != 64 or _sha256_file(z) != expected:
            return False
        text = verify.read_text(encoding='utf-8', errors='replace')
        required = (ACCEPTANCE_MARKER, UNCHANGED_MARKER)
        if require_retention_marker:
            required = required + (RETENTION_MARKER,)
        return all(f'{marker}\n' in text or text.endswith(marker) for marker in required)

    def _rollback_keep1(self, transaction: dict[str, Any]) -> None:
        for batch_info in reversed(transaction.get('_staged') or []):
            batch = Path(batch_info['batch'])
            for original_s, dest_s in reversed(batch_info.get('moved') or []):
                original = Path(original_s)
                dest = Path(dest_s)
                if dest.exists() and not original.exists():
                    os.replace(dest, original)
            try:
                batch.rmdir()
            except OSError:
                pass

    def _stage_keep1(self, new_stem: str) -> dict[str, Any]:
        if not self._validate_set(self.target, new_stem):
            raise RuntimeError('Nieuwe NAS Container CR-set is niet compleet/geldig voor retentie')
        transaction: dict[str, Any] = {
            'removed': 0,
            'skipped_unverified': 0,
            'kept': new_stem,
            '_staged': [],
        }
        try:
            for zip_path in sorted(self.target.glob('* CrashRecovery NAS Containers*.zip')):
                stem = zip_path.name[:-4]
                if stem == new_stem:
                    continue
                if not self._validate_set(self.target, stem):
                    transaction['skipped_unverified'] += 1
                    continue
                z, sha, verify = self._set_paths(self.target, stem)
                batch = self.target / f'.nas-cr-retention-delete-{os.getpid()}-{transaction["removed"]}'
                batch.mkdir()
                moved: list[tuple[str, str]] = []
                try:
                    for path in (z, sha, verify):
                        dest = batch / path.name
                        os.replace(path, dest)
                        moved.append((str(path), str(dest)))
                except Exception:
                    for original_s, dest_s in reversed(moved):
                        original = Path(original_s)
                        dest = Path(dest_s)
                        if dest.exists() and not original.exists():
                            os.replace(dest, original)
                    try:
                        batch.rmdir()
                    except OSError:
                        pass
                    raise
                transaction['_staged'].append({'batch': str(batch), 'moved': moved})
                transaction['removed'] += 1
            if not self._validate_set(self.target, new_stem):
                raise RuntimeError('Nieuwe NAS Container CR-set werd tijdens retentiestaging beschadigd')
            return transaction
        except Exception:
            self._rollback_keep1(transaction)
            raise

    def _commit_keep1(self, transaction: dict[str, Any]) -> dict[str, Any]:
        for batch_info in transaction.get('_staged') or []:
            batch = Path(batch_info['batch'])
            for _, dest_s in batch_info.get('moved') or []:
                dest = Path(dest_s)
                if dest.exists():
                    dest.unlink()
            batch.rmdir()
        return {
            'removed': int(transaction.get('removed') or 0),
            'skipped_unverified': int(transaction.get('skipped_unverified') or 0),
            'kept': str(transaction.get('kept') or ''),
        }

    def create(self) -> dict[str, Any]:
        self._prepare_target()
        self._acquire_lock()
        stage: Path | None = None
        restore: Path | None = None
        output_paths: tuple[Path, Path, Path] | None = None
        retention_commit_started = False
        try:
            at = self.now()
            stamp = at.astimezone(TZ).strftime('%Y%m%dT%H%M%S')
            stem = self._new_stem(at)
            zip_path, sha_path, verify_path = self._set_paths(self.target, stem)
            output_paths = (zip_path, sha_path, verify_path)
            stage = self.target / f'.nas-cr-acceptance-{stamp}-{os.getpid()}'
            restore = self.target / f'.nas-cr-restore-{stamp}-{os.getpid()}'
            stage.mkdir()

            self.docker.ping()
            before, images = self._container_snapshot()
            version = self._copy_project_files(stage)
            self._write_runtime_evidence(stage, at=at, snapshot=before, images=images)
            self._write_restore_doc(stage)
            offline = stage / 'offline'
            offline.mkdir(parents=True, exist_ok=True)
            image_tar = offline / 'docker_images_current.tar'
            export_result = self.docker.image_export(images, image_tar)
            if int(export_result.get('bytes') or 0) <= 0:
                raise RuntimeError('Docker image export is leeg')
            try:
                with tarfile.open(image_tar, 'r:*') as exported:
                    if not exported.getmembers():
                        raise RuntimeError('Docker image export tar bevat geen leden')
            except (tarfile.TarError, OSError) as exc:
                raise RuntimeError('Docker image export tar is ongeldig') from exc
            hash_count = self._write_internal_hashes(stage)
            self._build_zip(stage, zip_path)
            verified_files = self._verify_archive(zip_path, restore)
            probe_count = self._probe_images(images, stamp)
            after, _ = self._container_snapshot()
            if before != after:
                raise RuntimeError('Productiecontainers wijzigden tijdens NAS Container CR; backup niet geaccepteerd')

            digest = _sha256_file(zip_path)
            _atomic_text(sha_path, f'{digest}  {zip_path.name}\n')
            verify_text = (
                f'ZIP_INTEGRITY_OK\n'
                f'RESTORE_HASHES_OK={verified_files}\n'
                f'IMAGE_CREATE_REMOVE_OK={probe_count}\n\n'
                f'{ACCEPTANCE_MARKER}\n'
                f'VERSION={version}\n'
                f'ZIP={zip_path}\n'
                f'SHA256={digest}\n'
                f'IMAGE_COUNT={len(images)}\n'
                f'{UNCHANGED_MARKER}\n'
            )
            _atomic_text(verify_path, verify_text)
            if not self._validate_set(self.target, stem):
                raise RuntimeError('Finale NAS Container CR SHA256/VERIFY-validatie mislukt')

            retention_tx = self._stage_keep1(stem)
            try:
                _atomic_text(verify_path, verify_text + f'{RETENTION_MARKER}\n')
                if not self._validate_set(self.target, stem, require_retention_marker=True):
                    raise RuntimeError('Finale NAS Container CR-retentiemarker-validatie mislukt')
            except Exception:
                self._rollback_keep1(retention_tx)
                raise
            retention_commit_started = True
            try:
                retention = self._commit_keep1(retention_tx)
            except Exception:
                try:
                    _atomic_text(verify_path, verify_text)
                finally:
                    self._rollback_keep1(retention_tx)
                raise

            return {
                'ok': True,
                'status': 'GREEN',
                'backup_dir': str(self.target),
                'stem': stem,
                'zip': str(zip_path),
                'sha256_file': str(sha_path),
                'verify_file': str(verify_path),
                'sha256': digest,
                'version': version,
                'image_count': len(images),
                'hash_count': hash_count,
                'verified_files': verified_files,
                'production_containers_changed': False,
                'retention': retention,
            }
        except Exception:
            if output_paths is not None and not retention_commit_started:
                for output in output_paths:
                    try:
                        output.unlink(missing_ok=True)
                    except OSError:
                        pass
            raise
        finally:
            if restore is not None:
                shutil.rmtree(restore, ignore_errors=True)
            if stage is not None:
                shutil.rmtree(stage, ignore_errors=True)
            self._release_lock()


class ConfiguredNasContainerCrService:
    """Lazy adapter so an unconfigured TLS setup never breaks PM startup."""

    def __init__(self, project_root: Path | str, *, private_root: Path | str):
        self.project_root = Path(project_root)
        self.private_root = Path(private_root)

    def create(self) -> dict[str, Any]:
        from docker_engine_tls_client import DockerEngineTlsClient
        from nas_docker_tls import DockerTlsConfig

        config = DockerTlsConfig.load(self.private_root, project_root=self.project_root)
        client = DockerEngineTlsClient(config)
        return NasContainerCrService(self.project_root, client).create()
