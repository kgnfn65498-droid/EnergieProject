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
    perform_swap,
    reconcile_state,
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


class AtomicSwapTransactionTests(unittest.TestCase):
    def test_happy_path_uses_exact_two_rename_transaction_and_keeps_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            write_release_tree(paths.app, version="32.4.9", pm_version="2.0.0-rc6")
            write_release_tree(paths.candidate, version="32.4.10", pm_version="2.0.0-rc7")
            events: list[str] = []

            result = perform_swap(
                paths,
                artifact_sha256="abc123",
                expected_target_pm_version="2.0.0-rc7",
                event_hook=events.append,
            )

            self.assertEqual(
                events,
                [
                    "journal:PREPARED",
                    "rename:App->rollback",
                    "journal:OLD_RENAMED",
                    "rename:candidate->App",
                    "journal:NEW_ACTIVE",
                    "validate:active-target",
                    "journal:LIVE_ACCEPTANCE",
                ],
            )
            self.assertEqual(result["state"], "LIVE_ACCEPTANCE")
            self.assertEqual(read_version(paths.app), "32.4.10")
            self.assertEqual(read_version(paths.rollback), "32.4.9")
            self.assertFalse(paths.candidate.exists())

    def test_failure_between_renames_restores_source_without_retry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            write_release_tree(paths.app, version="32.4.9", pm_version="2.0.0-rc6")
            write_release_tree(paths.candidate, version="32.4.10", pm_version="2.0.0-rc7")

            def fail_after_old_renamed(event: str) -> None:
                if event == "journal:OLD_RENAMED":
                    raise RuntimeError("injected between renames")

            with self.assertRaisesRegex(RuntimeError, "injected between renames"):
                perform_swap(
                    paths,
                    artifact_sha256="abc123",
                    expected_target_pm_version="2.0.0-rc7",
                    event_hook=fail_after_old_renamed,
                )

            self.assertEqual(read_version(paths.app), "32.4.9")
            self.assertTrue(paths.candidate.is_dir())
            self.assertFalse(paths.rollback.exists())
            journal = json.loads(paths.journal.read_text(encoding="utf-8"))
            self.assertEqual(journal["state"], "ROLLED_BACK")

    def test_post_activation_validation_failure_quarantines_target_and_restores_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            write_release_tree(paths.app, version="32.4.9", pm_version="2.0.0-rc6")
            write_release_tree(paths.candidate, version="32.4.10", pm_version="2.0.0-rc7")

            def corrupt_after_activation(event: str) -> None:
                if event == "rename:candidate->App":
                    (paths.app / "VERSIE.txt").write_text("32.4.99\n", encoding="utf-8")

            with self.assertRaisesRegex(RecoveryRequired, "target version"):
                perform_swap(
                    paths,
                    artifact_sha256="abc123",
                    expected_target_pm_version="2.0.0-rc7",
                    event_hook=corrupt_after_activation,
                )

            self.assertEqual(read_version(paths.app), "32.4.9")
            self.assertFalse(paths.rollback.exists())
            self.assertFalse(paths.candidate.exists())
            failed = list(root.glob("App.__failed_32.4.10_*"))
            self.assertEqual(len(failed), 1)
            self.assertEqual(read_version(failed[0]), "32.4.99")
            journal = json.loads(paths.journal.read_text(encoding="utf-8"))
            self.assertEqual(journal["state"], "ROLLED_BACK")

    def test_reconcile_new_active_valid_state_never_performs_second_swap(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            write_release_tree(paths.app, version="32.4.10", pm_version="2.0.0-rc7")
            write_release_tree(paths.rollback, version="32.4.9", pm_version="2.0.0-rc6")
            write_journal_atomic(paths, state="NEW_ACTIVE", artifact_sha256="abc123")
            app_inode = paths.app.stat().st_ino
            rollback_inode = paths.rollback.stat().st_ino

            result = reconcile_state(paths)

            self.assertEqual(result["state"], "NEW_ACTIVE")
            self.assertEqual(paths.app.stat().st_ino, app_inode)
            self.assertEqual(paths.rollback.stat().st_ino, rollback_inode)


if __name__ == "__main__":
    unittest.main(verbosity=2)
