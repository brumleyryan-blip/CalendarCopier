import unittest
from datetime import datetime, timedelta, timezone

from calcopier.model import make_key, marker_in, short_hash, WorkEvent
from calcopier.rules import Existing, plan, should_copy, to_block

T0 = datetime(2026, 10, 5, 13, 30, tzinfo=timezone.utc)


def event(key="abc", status="accepted", all_day=False, title="Weekly Commit Call", attendees=5):
    return WorkEvent(key=key, title=title, start=T0, end=T0 + timedelta(minutes=30),
                     all_day=all_day, my_status=status, attendee_count=attendees)


class ShouldCopyTest(unittest.TestCase):
    def test_copies_accepted_tentative_and_unanswered(self):
        for status in ("accepted", "tentative", "unknown", "pending", "organizer/none"):
            self.assertTrue(should_copy(event(status=status)), status)

    def test_skips_declined(self):
        self.assertFalse(should_copy(event(status="declined")))

    def test_skips_all_day(self):
        self.assertFalse(should_copy(event(all_day=True, title="Jacob OOO")))

    def test_self_blocks_copied_for_now(self):
        self.assertTrue(should_copy(event(title="Busy", attendees=0, status="organizer/none")))


class BlockTest(unittest.TestCase):
    def test_block_hides_title(self):
        block = to_block(event(title="Security Sync - Ryan"))
        self.assertEqual(block.title, "Busy")
        self.assertEqual((block.start, block.end), (T0, T0 + timedelta(minutes=30)))

    def test_marker_round_trips_and_hides_key(self):
        block = to_block(event(key="AAMkAGI2-exchange-id"))
        notes = f"Synced from Ryan's work calendar.\n{block.marker}"
        self.assertEqual(marker_in(notes), short_hash("AAMkAGI2-exchange-id"))
        self.assertNotIn("AAMkAGI2", block.marker)

    def test_marker_absent(self):
        self.assertIsNone(marker_in("dentist"))
        self.assertIsNone(marker_in(None))


class KeyTest(unittest.TestCase):
    def test_recurring_occurrences_get_distinct_keys(self):
        a = make_key("series-1", True, T0.timestamp())
        b = make_key("series-1", True, (T0 + timedelta(days=7)).timestamp())
        self.assertNotEqual(a, b)

    def test_one_off_key_is_external_id(self):
        self.assertEqual(make_key("one-off", False, T0.timestamp()), "one-off")


def existing(key, start=T0, minutes=30, title="Busy"):
    return Existing(hash=short_hash(key), title=title, start=start, end=start + timedelta(minutes=minutes))


TODAY = T0.replace(hour=5, minute=0)  # window start (local midnight, in UTC)


class PlanTest(unittest.TestCase):
    def test_creates_new_and_skips_filtered(self):
        events = [event(key="new"), event(key="declined", status="declined")]
        p = plan(events, [], TODAY)
        self.assertEqual([b.key for b in p.creates], ["new"])

    def test_rerun_is_idempotent(self):
        events = [event(key="a"), event(key="b")]
        first = plan(events, [], TODAY)
        second = plan(events, [existing(b.key) for b in first.creates], TODAY)
        self.assertEqual((len(second.creates), len(second.updates), len(second.deletes), second.kept), (0, 0, 0, 2))

    def test_moved_meeting_updates_in_place(self):
        moved = WorkEvent(key="a", title="x", start=T0 + timedelta(hours=1), end=T0 + timedelta(hours=2),
                          all_day=False, my_status="accepted", attendee_count=3)
        p = plan([moved], [existing("a")], TODAY)
        self.assertEqual(len(p.updates), 1)
        self.assertEqual(p.updates[0][1].start, T0 + timedelta(hours=1))
        self.assertEqual((p.creates, p.deletes), ([], []))

    def test_cancelled_meeting_removed(self):
        p = plan([event(key="still-on")], [existing("still-on"), existing("cancelled")], TODAY)
        self.assertEqual([ex.hash for ex in p.deletes], [short_hash("cancelled")])

    def test_newly_declined_meeting_removed(self):
        p = plan([event(key="a", status="declined")], [existing("a")], TODAY)
        self.assertEqual(len(p.deletes), 1)

    def test_past_days_never_deleted(self):
        yesterday = existing("old", start=TODAY - timedelta(hours=10))
        p = plan([event(key="a")], [existing("a"), yesterday], TODAY)
        self.assertEqual(p.deletes, [])

    def test_ended_meeting_today_kept(self):
        earlier = TODAY + timedelta(hours=1)
        ev = WorkEvent(key="a", title="x", start=earlier, end=earlier + timedelta(minutes=30),
                       all_day=False, my_status="accepted", attendee_count=2)
        p = plan([ev], [existing("a", start=earlier)], TODAY)
        self.assertEqual((p.kept, p.deletes), (1, []))

    def test_duplicates_removed(self):
        p = plan([event(key="a")], [existing("a"), existing("a")], TODAY)
        self.assertEqual((p.kept, len(p.deletes)), (1, 1))

    def test_empty_read_does_not_wipe_calendar(self):
        p = plan([], [existing("a"), existing("b")], TODAY)
        self.assertEqual(p.deletes, [])
        self.assertTrue(p.deletes_suppressed)

    def test_title_change_counts_as_update(self):
        p = plan([event(key="a")], [existing("a", title="Old label")], TODAY)
        self.assertEqual(len(p.updates), 1)


if __name__ == "__main__":
    unittest.main()
