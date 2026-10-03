import unittest
from datetime import datetime, timedelta, timezone

from calcopier.model import make_key, marker_in, short_hash, WorkEvent
from calcopier.rules import plan_creates, should_copy, to_block

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


class PlanCreatesTest(unittest.TestCase):
    def test_skips_already_synced_and_filtered(self):
        events = [event(key="new"), event(key="synced"), event(key="declined", status="declined")]
        creates = plan_creates(events, {short_hash("synced")})
        self.assertEqual([b.key for b in creates], ["new"])

    def test_rerun_is_idempotent(self):
        events = [event(key="a"), event(key="b")]
        first = plan_creates(events, set())
        second = plan_creates(events, {short_hash(b.key) for b in first})
        self.assertEqual(len(first), 2)
        self.assertEqual(second, [])


if __name__ == "__main__":
    unittest.main()
