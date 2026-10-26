"""Offline unit tests: do not contact CGV or Telegram."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import watcher


class WatcherTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        patcher = patch.object(watcher, 'STATE_FILE', Path(self.temp.name) / 'state.json')
        patcher.start()
        self.addCleanup(patcher.stop)
        self.sent = []
        self.row = {
            'movNm': '극장판 명탐정 코난-예고',
            'movNo': '30000123', 'scnsrtTm': '1430', 'scnYmd': '20261101',
            'scnsNo': '02', 'scnsNm': '2관', 'movkndDsplNm': '2D'
        }
        self.one = watcher.session_from_row('0074', '20261101', self.row)

    def test_names_match(self):
        self.assertTrue(watcher.is_conan('명탐정 코난 - 30기'))
        self.assertTrue(watcher.is_conan('Detective Conan Movie'))
        self.assertFalse(watcher.is_conan('다른 영화'))

    def test_theaters_and_key(self):
        self.assertEqual(watcher.THEATERS, {'0074': '왕십리', '0191': '홍대'})
        self.assertTrue(self.one['key'].startswith('0074|30000123|20261101|1430|02'))

    def test_baseline_then_new_session_and_no_duplicates(self):
        self.assertEqual(watcher.run_once(fetcher=lambda: {self.one['key']: self.one},
                                          sender=self.sent.append), 0)
        self.assertEqual(self.sent, [])
        another = watcher.session_from_row('0074', '20261101', {**self.row, 'scnsrtTm': '1700'})
        both = {x['key']: x for x in (self.one, another)}
        self.assertEqual(watcher.run_once(fetcher=lambda: both,
                                          sender=self.sent.append), 1)
        self.assertEqual(len(self.sent), 1)
        self.assertIn('17:00', self.sent[0])
        self.assertEqual(watcher.run_once(fetcher=lambda: both,
                                          sender=self.sent.append), 0)
        self.assertEqual(len(self.sent), 1)

    def test_empty_baseline_then_first_new_booking(self):
        watcher.run_once(fetcher=lambda: {}, sender=self.sent.append)
        self.assertEqual(watcher.run_once(fetcher=lambda: {self.one['key']: self.one},
                                          sender=self.sent.append), 1)
        self.assertEqual(len(self.sent), 1)

    def test_query_failure_does_not_initialize(self):
        def failing():
            raise RuntimeError('CGV HTTP 403')
        with self.assertRaises(RuntimeError):
            watcher.run_once(fetcher=failing, sender=self.sent.append)
        state = watcher.load_state()
        self.assertFalse(state.get('initialized', False))
        self.assertEqual(len(self.sent), 1)  # Sends a single warning.

    def test_no_seen_on_send_failure(self):
        watcher.run_once(fetcher=lambda: {}, sender=self.sent.append)
        def failing_send(msg):
            raise RuntimeError('Telegram failed')
        with self.assertRaises(RuntimeError):
            watcher.run_once(fetcher=lambda: {self.one['key']: self.one}, sender=failing_send)
        self.assertEqual(watcher.load_state()['seen'], [])


if __name__ == '__main__':
    unittest.main()
