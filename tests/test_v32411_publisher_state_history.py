#!/usr/bin/env python
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISHER = ROOT / 'tools/nas_github_publisher.sh'


class PublisherStateHistoryTests(unittest.TestCase):
    def test_publisher_archives_previous_state_before_replacing_current_state(self):
        text = PUBLISHER.read_text(encoding='utf-8')
        self.assertIn('HISTORY="$ROOT/Inbox/github_publisher_history.jsonl"', text)
        self.assertIn('archive_previous_state()', text)
        write_state = text.split('write_state()', 1)[1].split('\nfail()', 1)[0]
        self.assertIn('archive_previous_state', write_state)
        self.assertLess(write_state.index('archive_previous_state'), write_state.index('mv "$TMP_STATE" "$STATE"'))

    def test_history_is_append_only_and_current_state_remains_atomic(self):
        text = PUBLISHER.read_text(encoding='utf-8')
        self.assertIn('archive_previous_state()', text)
        archive = text.split('archive_previous_state()', 1)[1].split('\nwrite_state()', 1)[0]
        self.assertIn('>> "$HISTORY"', archive)
        self.assertNotIn('> "$HISTORY"', archive.replace('>> "$HISTORY"', ''))
        write_state = text.split('write_state()', 1)[1].split('\nfail()', 1)[0]
        self.assertIn('TMP_STATE="$STATE.tmp.$$"', write_state)
        self.assertIn('mv "$TMP_STATE" "$STATE"', write_state)


if __name__ == '__main__':
    unittest.main(verbosity=2)
