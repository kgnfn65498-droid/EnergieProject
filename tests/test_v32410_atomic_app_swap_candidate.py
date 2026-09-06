#!/usr/bin/env python3
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from tools.atomic_app_swap import (  # type: ignore[import-not-found]
    RecoveryRequired,
    SwapPaths,
    probe_sibling_rename,
    verify_same_filesystem,
)


def write_version(path: Path, version: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "VERSIE.txt").write_text(version + "\n", encoding="utf-8")


class AtomicSwapFilesystemPreflightTests(unittest.TestCase):
    def test_same_filesystem_reports_one_device_without_touching_app(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            write_version(paths.app, "32.4.9")
            write_version(paths.candidate, "32.4.10")
            before_inode = paths.app.stat().st_ino

            result = verify_same_filesystem(paths)

            self.assertEqual(result["root_dev"], result["app_dev"])
            self.assertEqual(result["app_dev"], result["candidate_dev"])
            self.assertEqual(paths.app.stat().st_ino, before_inode)

    def test_cross_filesystem_identity_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            write_version(paths.app, "32.4.9")
            write_version(paths.candidate, "32.4.10")

            with self.assertRaisesRegex(RecoveryRequired, "same filesystem"):
                verify_same_filesystem(paths, device_ids=(1, 1, 2))

    def test_sibling_rename_probe_roundtrip_leaves_app_untouched(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            write_version(paths.app, "32.4.9")
            before_inode = paths.app.stat().st_ino

            result = probe_sibling_rename(paths)

            self.assertEqual(result["status"], "GREEN")
            self.assertEqual(paths.app.stat().st_ino, before_inode)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["App", "Inbox"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
