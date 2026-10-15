import unittest
from datetime import datetime, timedelta, timezone

from calcopier.model import WorkEvent, short_hash
from calcopier.rules import HEARTBEAT_KEY, Existing, heartbeat_block, plan

NOW = datetime(2026, 10, 5, 13, 20, tzinfo=timezone(timedelta(hours=-5)))
TODAY = NOW.replace(hour=0, minute=0)


def marker(start):
    return Existing(hash=short_hash(HEARTBEAT_KEY), title="Sync paused", start=start, end=start + timedelta(minutes=30))


def meeting(key="m"):
    return WorkEvent(key=key, title="x", start=NOW, end=NOW + timedelta(minutes=30),
                     all_day=False, my_status="accepted", attendee_count=2)


class HeartbeatTest(unittest.TestCase):
    def test_block_sits_two_hours_ahead_and_names_last_update(self):
        hb = heartbeat_block(NOW)
        self.assertEqual(hb.start, NOW + timedelta(hours=2))
        self.assertEqual(hb.title, "Sync paused")
        self.assertIn("Mon 10/05 at 1:20 PM", hb.notes)

    def test_created_when_missing(self):
        p = plan([meeting()], [], TODAY, heartbeat_block(NOW), NOW)
        self.assertIn(HEARTBEAT_KEY, [b.key for b in p.creates])

    def test_left_alone_while_far_enough_ahead(self):
        p = plan([], [marker(NOW + timedelta(minutes=100))], TODAY, heartbeat_block(NOW), NOW)
        self.assertEqual((p.creates, p.updates, p.deletes, p.kept), ([], [], [], 1))

    def test_moved_forward_when_close(self):
        p = plan([], [marker(NOW + timedelta(minutes=80))], TODAY, heartbeat_block(NOW), NOW)
        self.assertEqual(len(p.updates), 1)
        self.assertEqual(p.updates[0][1].start, NOW + timedelta(hours=2))

    def test_moved_forward_after_outage(self):
        overdue = marker(NOW - timedelta(hours=3))
        p = plan([meeting()], [overdue], TODAY, heartbeat_block(NOW), NOW)
        self.assertEqual(len(p.updates), 1)

    def test_never_deleted_as_a_stale_meeting_block(self):
        p = plan([meeting()], [marker(NOW + timedelta(minutes=100))], TODAY, heartbeat_block(NOW), NOW)
        self.assertEqual(p.deletes, [])

    def test_untouched_when_heartbeat_not_requested(self):
        p = plan([meeting()], [marker(NOW + timedelta(minutes=10))], TODAY)
        self.assertEqual((p.updates, p.deletes), ([], []))

    def test_duplicate_markers_removed(self):
        p = plan([], [marker(NOW + timedelta(minutes=100)), marker(NOW + timedelta(minutes=110))],
                 TODAY, heartbeat_block(NOW), NOW)
        self.assertEqual(len(p.deletes), 1)

    def test_empty_read_still_keeps_heartbeat_out_of_suppression(self):
        p = plan([], [marker(NOW + timedelta(minutes=10))], TODAY, heartbeat_block(NOW), NOW)
        self.assertFalse(p.deletes_suppressed)
        self.assertEqual(len(p.updates), 1)
