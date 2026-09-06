#!/usr/bin/env python3
from __future__ import annotations

import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP_ROOT))

from tools.atomic_app_swap import (  # type: ignore[import-not-found]
    RecoveryRequired,
    SwapPaths,
    acquire_swap_lock,
    reconcile_state,
    write_journal_atomic,
)


def write_version(path: Path, version: str) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / "VERSIE.txt").write_text(version + "\n", encoding="utf-8")


class AtomicSwapJournalLockTests(unittest.TestCase):
    def test_journal_is_atomic_and_contains_exact_release_identity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")

            write_journal_atomic(paths, state="PREPARED", artifact_sha256="abc123")

            saved = json.loads(paths.journal.read_text(encoding="utf-8"))
            self.assertEqual(saved["state"], "PREPARED")
            self.assertEqual(saved["from_version"], "32.4.9")
            self.assertEqual(saved["to_version"], "32.4.10")
            self.assertEqual(saved["candidate_path"], "App.__candidate_32.4.10")
            self.assertEqual(saved["rollback_path"], "App.__rollback_32.4.9")
            self.assertEqual(saved["artifact_sha256"], "abc123")
            self.assertEqual(stat.S_IMODE(paths.journal.stat().st_mode), 0o644)
            self.assertEqual(list(paths.inbox.glob("atomic_app_swap_state.json.tmp.*")), [])

    def test_second_lock_owner_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")

            acquire_swap_lock(paths)

            with self.assertRaisesRegex(RuntimeError, "swap lock"):
                acquire_swap_lock(paths)


class AtomicSwapReconciliationTests(unittest.TestCase):
    def test_prepared_state_never_blindly_renames(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            write_version(paths.app, "32.4.9")
            write_version(paths.candidate, "32.4.10")
            write_journal_atomic(paths, state="PREPARED", artifact_sha256="abc123")

            before = sorted(p.name for p in root.iterdir())
            result = reconcile_state(paths)
            after = sorted(p.name for p in root.iterdir())

            self.assertEqual(result["state"], "PREPARED")
            self.assertEqual(before, after)
            self.assertTrue(paths.app.is_dir())
            self.assertTrue(paths.candidate.is_dir())
            self.assertFalse(paths.rollback.exists())

    def test_rolled_back_state_never_retries_swap(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            write_version(paths.app, "32.4.9")
            write_version(paths.candidate, "32.4.10")
            write_journal_atomic(paths, state="ROLLED_BACK", artifact_sha256="abc123")

            result = reconcile_state(paths)

            self.assertEqual(result["state"], "ROLLED_BACK")
            self.assertEqual((paths.app / "VERSIE.txt").read_text().strip(), "32.4.9")
            self.assertTrue(paths.candidate.exists())
            self.assertFalse(paths.rollback.exists())

    def test_old_renamed_state_with_only_rollback_restores_old_app(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            write_version(paths.rollback, "32.4.9")
            write_journal_atomic(paths, state="OLD_RENAMED", artifact_sha256="abc123")

            result = reconcile_state(paths)

            self.assertEqual(result["state"], "ROLLED_BACK")
            self.assertTrue(paths.app.is_dir())
            self.assertEqual((paths.app / "VERSIE.txt").read_text().strip(), "32.4.9")
            self.assertFalse(paths.rollback.exists())
            saved = json.loads(paths.journal.read_text(encoding="utf-8"))
            self.assertEqual(saved["state"], "ROLLED_BACK")

    def test_new_active_state_requires_active_target_identity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Inbox").mkdir()
            paths = SwapPaths.for_release(root, "32.4.9", "32.4.10")
            write_version(paths.app, "32.4.9")
            write_version(paths.rollback, "32.4.9")
            write_journal_atomic(paths, state="NEW_ACTIVE", artifact_sha256="abc123")

            with self.assertRaisesRegex(RecoveryRequired, "target version"):
                reconcile_state(paths)

            self.assertEqual((paths.app / "VERSIE.txt").read_text().strip(), "32.4.9")
            self.assertTrue(paths.rollback.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
