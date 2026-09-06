#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
MODULE = APP_ROOT / "tools/atomic_app_swap.py"
INSTALLER = APP_ROOT / "tools/release_installer.sh"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def release_files(*, version: str, pm_version: str) -> dict[str, bytes]:
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


def write_tree(path: Path, *, version: str, pm_version: str) -> None:
    for rel, data in release_files(version=version, pm_version=pm_version).items():
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)


def write_zip(path: Path) -> str:
    files = release_files(version="32.4.10", pm_version="2.0.0-rc7")
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_prepare(root: Path, artifact: Path, artifact_sha: str, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            sys.executable,
            str(MODULE),
            "prepare-and-swap",
            "--root", str(root),
            "--artifact", str(artifact),
            "--expected-sha256", artifact_sha,
            "--from-version", "32.4.9",
            "--from-pm-version", "2.0.0-rc6",
            "--to-version", "32.4.10",
            "--to-pm-version", "2.0.0-rc7",
            *extra,
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class AtomicSwapInstallerContextTests(unittest.TestCase):
    def test_direct_cli_blocks_incoming_release_before_any_swap_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox/incoming").mkdir(parents=True)
            write_tree(root / "App", version="32.4.9", pm_version="2.0.0-rc6")
            artifact = root / "release.zip"
            artifact_sha = write_zip(artifact)
            (root / "Inbox/incoming/other.zip").write_bytes(b"other")

            result = run_prepare(root, artifact, artifact_sha)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("incoming", result.stderr.lower())
            self.assertEqual((root / "App/VERSIE.txt").read_text().strip(), "32.4.9")
            self.assertFalse((root / "App.__rollback_32.4.9").exists())
            self.assertFalse((root / "App.__candidate_32.4.10").exists())
            self.assertFalse((root / "Inbox/atomic_app_swap_state.json").exists())

    def test_installer_context_allows_own_lock_and_exact_processing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox/processing").mkdir(parents=True)
            (root / "Inbox/.installer.lock").mkdir()
            write_tree(root / "App", version="32.4.9", pm_version="2.0.0-rc6")
            artifact = root / "Inbox/processing/EnergieProject_v32.4.10.zip"
            artifact_sha = write_zip(artifact)

            result = run_prepare(root, artifact, artifact_sha, "--installer-context")

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["state"], "LIVE_ACCEPTANCE")
            self.assertEqual((root / "App/VERSIE.txt").read_text().strip(), "32.4.10")
            self.assertEqual((root / "App.__rollback_32.4.9/VERSIE.txt").read_text().strip(), "32.4.9")

    def test_installer_context_requires_active_installer_lock(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox/processing").mkdir(parents=True)
            write_tree(root / "App", version="32.4.9", pm_version="2.0.0-rc6")
            artifact = root / "Inbox/processing/EnergieProject_v32.4.10.zip"
            artifact_sha = write_zip(artifact)

            result = run_prepare(root, artifact, artifact_sha, "--installer-context")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("installer", result.stderr.lower())
            self.assertEqual((root / "App/VERSIE.txt").read_text().strip(), "32.4.9")
            self.assertFalse((root / "App.__rollback_32.4.9").exists())
            self.assertFalse((root / "App.__candidate_32.4.10").exists())

    def test_installer_context_rejects_extra_processing_zip_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox/processing").mkdir(parents=True)
            (root / "Inbox/.installer.lock").mkdir()
            write_tree(root / "App", version="32.4.9", pm_version="2.0.0-rc6")
            artifact = root / "Inbox/processing/EnergieProject_v32.4.10.zip"
            artifact_sha = write_zip(artifact)
            (root / "Inbox/processing/other.zip").write_bytes(b"other")

            result = run_prepare(root, artifact, artifact_sha, "--installer-context")

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("processing", result.stderr.lower())
            self.assertEqual((root / "App/VERSIE.txt").read_text().strip(), "32.4.9")
            self.assertFalse((root / "App.__rollback_32.4.9").exists())
            self.assertFalse((root / "App.__candidate_32.4.10").exists())

    def test_installer_explicitly_marks_its_owned_atomic_context(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("--installer-context", text)
        self.assertIn('ATOMIC_SWAP_RUNNER', text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
