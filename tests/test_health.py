import tempfile
import unittest
from pathlib import Path

from calcopier.health import record_result, trim_log


class RecordResultTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.state = Path(self.dir.name) / "sub" / "state.json"
        self.sent = []

    def tearDown(self):
        self.dir.cleanup()

    def run_with(self, error):
        record_result(error, self.state, notify=lambda t, m: self.sent.append(m))

    def test_notifies_once_per_distinct_error(self):
        self.run_with("calendar missing")
        self.run_with("calendar missing")
        self.run_with("permission revoked")
        self.assertEqual(self.sent, ["calendar missing", "permission revoked"])

    def test_success_resets_so_repeat_failure_notifies_again(self):
        self.run_with("calendar missing")
        self.run_with(None)
        self.run_with("calendar missing")
        self.assertEqual(len(self.sent), 2)

    def test_success_never_notifies(self):
        self.run_with(None)
        self.assertEqual(self.sent, [])


class TrimLogTest(unittest.TestCase):
    def test_keeps_newest_whole_lines(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "sync.log"
            log.write_text("".join(f"line {i}\n" for i in range(1000)))
            trim_log(log, max_bytes=500, keep_bytes=100)
            lines = log.read_text().splitlines()
            self.assertEqual(lines[-1], "line 999")
            self.assertTrue(all(l.startswith("line ") for l in lines))
            self.assertLessEqual(log.stat().st_size, 100)

    def test_small_or_missing_log_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "sync.log"
            trim_log(log)
            log.write_text("ok\n")
            trim_log(log, max_bytes=500)
            self.assertEqual(log.read_text(), "ok\n")
