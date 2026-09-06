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
sys.path.insert(0, str(APP_ROOT))

from tools.atomic_app_swap import (  # type: ignore[import-not-found]
    RecoveryRequired,
    assert_no_release_conflict,
)

MODULE = APP_ROOT / "tools/atomic_app_swap.py"


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


def write_zip(path: Path, *, version: str = "32.4.10", pm_version: str = "2.0.0-rc7") -> str:
    files = release_files(version=version, pm_version=pm_version)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(MODULE), *args],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


class AtomicSwapConflictAndCliTests(unittest.TestCase):
    def test_release_conflict_predicate_blocks_legacy_release_work(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            inbox = root / "Inbox"
            inbox.mkdir()
            assert_no_release_conflict(root)

            lock = inbox / ".installer.lock"
            lock.mkdir()
            with self.assertRaisesRegex(RecoveryRequired, "installer"):
                assert_no_release_conflict(root)
            lock.rmdir()

            processing = inbox / "processing"
            processing.mkdir()
            (processing / "release.zip").write_bytes(b"x")
            with self.assertRaisesRegex(RecoveryRequired, "processing"):
                assert_no_release_conflict(root)
            (processing / "release.zip").unlink()

            incoming = inbox / "incoming"
            incoming.mkdir()
            (incoming / "release.zip").write_bytes(b"x")
            with self.assertRaisesRegex(RecoveryRequired, "incoming"):
                assert_no_release_conflict(root)

    def test_prepare_and_swap_cli_reaches_live_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            write_tree(root / "App", version="32.4.9", pm_version="2.0.0-rc6")
            artifact = root / "release.zip"
            artifact_sha = write_zip(artifact)

            result = run_cli(
                "prepare-and-swap",
                "--root", str(root),
                "--artifact", str(artifact),
                "--expected-sha256", artifact_sha,
                "--from-version", "32.4.9",
                "--from-pm-version", "2.0.0-rc6",
                "--to-version", "32.4.10",
                "--to-pm-version", "2.0.0-rc7",
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["state"], "LIVE_ACCEPTANCE")
            self.assertEqual((root / "App/VERSIE.txt").read_text().strip(), "32.4.10")
            self.assertEqual((root / "App.__rollback_32.4.9/VERSIE.txt").read_text().strip(), "32.4.9")

    def test_rollback_cli_restores_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            write_tree(root / "App", version="32.4.10", pm_version="2.0.0-rc7")
            write_tree(root / "App.__rollback_32.4.9", version="32.4.9", pm_version="2.0.0-rc6")
            (root / "Inbox/atomic_app_swap_state.json").write_text(
                json.dumps({
                    "state": "LIVE_ACCEPTANCE",
                    "from_version": "32.4.9",
                    "to_version": "32.4.10",
                    "artifact_sha256": "abc",
                    "candidate_path": "App.__candidate_32.4.10",
                    "rollback_path": "App.__rollback_32.4.9",
                    "error": "",
                }),
                encoding="utf-8",
            )

            result = run_cli(
                "rollback",
                "--root", str(root),
                "--from-version", "32.4.9",
                "--to-version", "32.4.10",
                "--reason", "test rollback",
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["state"], "ROLLED_BACK")
            self.assertEqual((root / "App/VERSIE.txt").read_text().strip(), "32.4.9")

    def test_accept_cli_marks_accepted_and_retains_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            write_tree(root / "App", version="32.4.10", pm_version="2.0.0-rc7")
            write_tree(root / "App.__rollback_32.4.9", version="32.4.9", pm_version="2.0.0-rc6")
            (root / "Inbox/atomic_app_swap_state.json").write_text(
                json.dumps({
                    "state": "LIVE_ACCEPTANCE",
                    "from_version": "32.4.9",
                    "to_version": "32.4.10",
                    "artifact_sha256": "abc",
                    "candidate_path": "App.__candidate_32.4.10",
                    "rollback_path": "App.__rollback_32.4.9",
                    "error": "",
                }),
                encoding="utf-8",
            )

            result = run_cli(
                "accept",
                "--root", str(root),
                "--from-version", "32.4.9",
                "--to-version", "32.4.10",
                "--to-pm-version", "2.0.0-rc7",
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["state"], "ACCEPTED")
            self.assertTrue((root / "App.__rollback_32.4.9").is_dir())


if __name__ == "__main__":
    unittest.main(verbosity=2)
