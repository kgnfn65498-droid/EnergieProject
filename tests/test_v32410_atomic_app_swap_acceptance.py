#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from tools.atomic_app_swap import (  # type: ignore[import-not-found]
    RecoveryRequired,
    SwapPaths,
    finalize_acceptance,
    rollback_after_activation_failure,
    write_journal_atomic,
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write_release_tree(path: Path, *, version: str, pm_version: str) -> None:
    files: dict[str, bytes] = {
        "README.md": b"readme\n",
        "INSTALL.md": b"install\n",
        "CHANGELOG.md": b"changelog\n",
        "repository.yaml": b"name: energie\n",
        "VERSIE.txt": (version + "\n").encode(),
        "SHA256SUMS.json": b"{}\n",
        "slimmemeterportal_import/rootfs/app/projectmanager_v2/VERSION.txt": (pm_version + "\n").encode(),
    }
    path.mkdir(parents=True, exist_ok=True)
    for rel, data in files.items():
        target = path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    manifest = "".join(f"{sha256(data)}  {name}\n" for name, data in sorted(files.items()))
    (path / "MANIFEST.sha256").write_text(manifest, encoding="utf-8")


def read_version(path: Path) -> str:
    return (path / "VERSIE.txt").read_text(encoding="utf-8").strip()


class AtomicSwapAcceptanceTests(unittest.TestCase):
    def test_finalize_acceptance_marks_accepted_but_retains_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            write_release_tree(paths.app, version="32.4.10", pm_version="2.0.0-rc7")
            write_release_tree(paths.rollback, version="32.4.9", pm_version="2.0.0-rc6")
            write_journal_atomic(paths, state="LIVE_ACCEPTANCE", artifact_sha256="abc123")

            result = finalize_acceptance(paths, expected_target_pm_version="2.0.0-rc7")

            self.assertEqual(result["state"], "ACCEPTED")
            self.assertEqual(read_version(paths.app), "32.4.10")
            self.assertEqual(read_version(paths.rollback), "32.4.9")
            saved = json.loads(paths.journal.read_text(encoding="utf-8"))
            self.assertEqual(saved["state"], "ACCEPTED")

    def test_finalize_acceptance_refuses_before_live_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            write_release_tree(paths.app, version="32.4.10", pm_version="2.0.0-rc7")
            write_release_tree(paths.rollback, version="32.4.9", pm_version="2.0.0-rc6")
            write_journal_atomic(paths, state="NEW_ACTIVE", artifact_sha256="abc123")

            with self.assertRaisesRegex(RecoveryRequired, "LIVE_ACCEPTANCE"):
                finalize_acceptance(paths, expected_target_pm_version="2.0.0-rc7")

            self.assertEqual(read_version(paths.app), "32.4.10")
            self.assertEqual(read_version(paths.rollback), "32.4.9")

    def test_explicit_rollback_quarantines_new_app_and_restores_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            write_release_tree(paths.app, version="32.4.10", pm_version="2.0.0-rc7")
            write_release_tree(paths.rollback, version="32.4.9", pm_version="2.0.0-rc6")
            write_journal_atomic(paths, state="LIVE_ACCEPTANCE", artifact_sha256="abc123")

            result = rollback_after_activation_failure(paths, reason="live acceptance failed")

            self.assertEqual(result["state"], "ROLLED_BACK")
            self.assertEqual(read_version(paths.app), "32.4.9")
            self.assertFalse(paths.rollback.exists())
            failed = list(root.glob("App.__failed_32.4.10_*"))
            self.assertEqual(len(failed), 1)
            self.assertEqual(read_version(failed[0]), "32.4.10")
            saved = json.loads(paths.journal.read_text(encoding="utf-8"))
            self.assertEqual(saved["state"], "ROLLED_BACK")
            self.assertIn("live acceptance failed", saved["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
