#!/usr/bin/env python3
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "tools/release_installer.sh"
WATCHER = ROOT / "tools/release_watcher.sh"


class AtomicReleaseInstallerIntegrationTests(unittest.TestCase):
    def test_installer_never_empties_or_recopies_active_app(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertNotIn(
            'find "$PROJECT" -mindepth 1 -maxdepth 1 ! -name .git -exec rm -rf {} +',
            text,
        )
        self.assertNotIn('copy_tree_no_metadata "$STAGE" "$PROJECT"', text)

        if "restore_backup(){" in text:
            restore = text.split("restore_backup(){", 1)[1].split("\n}", 1)[0]
            self.assertNotIn('find "$PROJECT"', restore)
            self.assertNotIn('copy_tree_no_metadata "$RESTORE_STAGE" "$PROJECT"', restore)

    def test_installer_arms_release_hold_before_atomic_swap(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        hold_call = 'write_release_validation_hold || fail "release validation hold activeren mislukt"'
        self.assertEqual(text.count(hold_call), 1)
        self.assertIn("atomic_app_swap.py", text)
        self.assertIn("prepare-and-swap", text)
        self.assertLess(text.index(hold_call), text.index("prepare-and-swap"))

    def test_installer_delegates_activation_and_rollback_to_atomic_swap(self) -> None:
        text = INSTALLER.read_text(encoding="utf-8")
        self.assertIn('ATOMIC_SWAP="$PROJECT/tools/atomic_app_swap.py"', text)
        self.assertIn('prepare-and-swap', text)
        self.assertIn('rollback', text)
        self.assertNotIn('WORKTREE_REPLACED=1', text)

    def test_watcher_blocks_release_ingress_during_atomic_swap(self) -> None:
        text = WATCHER.read_text(encoding="utf-8")
        self.assertIn('ATOMIC_SWAP_LOCK="$INBOX/.atomic_app_swap.lock"', text)
        self.assertIn('ATOMIC_SWAP_JOURNAL="$INBOX/atomic_app_swap_state.json"', text)
        self.assertIn('atomic_swap_allows_release_ingress(){', text)
        function = text.split('atomic_swap_allows_release_ingress(){', 1)[1].split('\n}', 1)[0]
        self.assertIn('OLD_RENAMED', function)
        self.assertIn('NEW_ACTIVE', function)
        self.assertIn('LIVE_ACCEPTANCE', function)
        self.assertIn('ATOMIC_SWAP_LOCK', function)
        loop = text.split('while :; do', 1)[1]
        self.assertIn('atomic_swap_allows_release_ingress', loop)


if __name__ == "__main__":
    unittest.main(verbosity=2)
