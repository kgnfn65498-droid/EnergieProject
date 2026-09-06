#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from tools.atomic_app_swap import (  # type: ignore[import-not-found]
    RecoveryRequired,
    SwapPaths,
    materialize_candidate,
    verify_candidate,
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def release_files(*, version: str = "32.4.10", pm_version: str = "2.0.0-rc7") -> dict[str, bytes]:
    files: dict[str, bytes] = {
        "README.md": b"readme\n",
        "INSTALL.md": b"install\n",
        "CHANGELOG.md": b"changelog\n",
        "repository.yaml": b"name: energie\n",
        "VERSIE.txt": (version + "\n").encode(),
        "SHA256SUMS.json": b"{}\n",
        "slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt": (pm_version + "\n").encode(),
    }
    manifest = "".join(f"{sha256(data)}  {name}\n" for name, data in sorted(files.items()))
    files["MANIFEST.sha256"] = manifest.encode()
    return files


def write_zip(path: Path, files: dict[str, bytes]) -> None:
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)


class AtomicSwapCandidateIntegrityTests(unittest.TestCase):
    def test_valid_flat_release_materializes_only_as_sibling_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            (root / "App").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            artifact = root / "release.zip"
            write_zip(artifact, release_files())

            result = materialize_candidate(paths, artifact, expected_pm_version="2.0.0-rc7")

            self.assertEqual(result["target_version"], "32.4.10")
            self.assertEqual(result["target_pm_version"], "2.0.0-rc7")
            self.assertTrue(paths.candidate.is_dir())
            self.assertTrue((paths.candidate / "MANIFEST.sha256").is_file())
            self.assertTrue(paths.app.is_dir())
            self.assertFalse(paths.rollback.exists())

    def test_unsafe_zip_member_is_rejected_without_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            (root / "App").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            artifact = root / "release.zip"
            files = release_files()
            files["../escape.txt"] = b"no\n"
            write_zip(artifact, files)

            with self.assertRaisesRegex(ValueError, "unsafe ZIP member"):
                materialize_candidate(paths, artifact, expected_pm_version="2.0.0-rc7")

            self.assertFalse(paths.candidate.exists())
            self.assertFalse((root.parent / "escape.txt").exists())

    def test_manifest_mismatch_is_rejected_and_candidate_removed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            (root / "App").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            artifact = root / "release.zip"
            files = release_files()
            files["README.md"] = b"tampered\n"
            write_zip(artifact, files)

            with self.assertRaisesRegex(RecoveryRequired, "manifest"):
                materialize_candidate(paths, artifact, expected_pm_version="2.0.0-rc7")

            self.assertFalse(paths.candidate.exists())

    def test_wrong_target_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            (root / "App").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            artifact = root / "release.zip"
            write_zip(artifact, release_files(version="32.4.11"))

            with self.assertRaisesRegex(RecoveryRequired, "target version"):
                materialize_candidate(paths, artifact, expected_pm_version="2.0.0-rc7")

            self.assertFalse(paths.candidate.exists())

    def test_wrong_target_pm_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            (root / "App").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            artifact = root / "release.zip"
            write_zip(artifact, release_files(pm_version="2.0.0-rc8"))

            with self.assertRaisesRegex(RecoveryRequired, "target PM version"):
                materialize_candidate(paths, artifact, expected_pm_version="2.0.0-rc7")

            self.assertFalse(paths.candidate.exists())

    def test_cache_or_metadata_member_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            (root / "App").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            artifact = root / "release.zip"
            files = release_files()
            files[".DS_Store"] = b"metadata"
            write_zip(artifact, files)

            with self.assertRaisesRegex(ValueError, "forbidden release member"):
                materialize_candidate(paths, artifact, expected_pm_version="2.0.0-rc7")

            self.assertFalse(paths.candidate.exists())

    def test_verify_candidate_is_read_only_after_materialization(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            (root / "App").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            artifact = root / "release.zip"
            write_zip(artifact, release_files())
            materialize_candidate(paths, artifact, expected_pm_version="2.0.0-rc7")
            before = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))

            result = verify_candidate(paths, expected_pm_version="2.0.0-rc7")
            after = sorted(p.relative_to(root).as_posix() for p in root.rglob("*"))

            self.assertEqual(result["target_version"], "32.4.10")
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main(verbosity=2)
