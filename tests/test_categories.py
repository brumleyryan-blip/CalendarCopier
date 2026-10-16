import unittest
from datetime import datetime, timedelta, timezone

from calcopier.categories import AWAY, BUSY, WEBINAR, classify
from calcopier.model import WorkEvent, short_hash
from calcopier.rules import Existing, plan, to_block

T0 = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
TODAY = T0.replace(hour=5)


def ev(title="Weekly sync", attendees=4, location="", group=False, room=False, key="k", status="accepted"):
    return WorkEvent(key=key, title=title, start=T0, end=T0 + timedelta(minutes=30), all_day=False,
                     my_status=status, attendee_count=attendees, location=location,
                     has_group=group, has_room=room)


def cat(**kw):
    return classify(ev(**kw))[0]


class ClassifyTest(unittest.TestCase):
    def test_webinar_keywords(self):
        for title in ["Partner Webinar", "Q3 AHOD", "All Hands", "Town Hall", "The 'It Depends' Hour - OP SE Office Hours",
                      "FY27 CWA AE Enablement", "Lunch & Learn: Gong"]:
            self.assertEqual(cat(title=title), WEBINAR, title)

    def test_large_audience_and_distribution_lists(self):
        self.assertEqual(cat(attendees=70), WEBINAR)
        self.assertEqual(cat(attendees=6, group=True), WEBINAR)
        self.assertEqual(cat(attendees=49), BUSY)

    def test_away_signals(self):
        self.assertEqual(cat(location="1200 Main St, Suite 400, Dallas TX"), AWAY)
        self.assertEqual(cat(room=True), AWAY)
        self.assertEqual(cat(title="Customer onsite - Bepco"), AWAY)
        self.assertEqual(cat(title="Lunch w/ Jacob"), AWAY)

    def test_away_beats_size_but_not_webinar_words(self):
        self.assertEqual(cat(title="Lunch & Learn", location="100 Elm St"), WEBINAR)
        self.assertEqual(cat(title="Team offsite", group=True), AWAY)

    def test_meeting_links_are_not_addresses(self):
        self.assertEqual(cat(location="https://teams.microsoft.com/l/meetup-join/19%3ameeting"), BUSY)
        self.assertEqual(cat(location="Microsoft Teams Meeting"), BUSY)
        self.assertEqual(cat(location="Conference ID: 123 456 789"), BUSY)

    def test_keywords_match_whole_words_only(self):
        self.assertEqual(cat(title="Revisit pricing"), BUSY)       # not "visit"
        self.assertEqual(cat(title="Retraining plan review"), BUSY)  # not "training"

    def test_override_tag_wins(self):
        self.assertEqual(cat(title="All Hands [busy]"), BUSY)
        self.assertEqual(cat(title="Pipeline review [AWAY]"), AWAY)
        self.assertEqual(cat(title="Deal review [listen]"), WEBINAR)
        self.assertEqual(classify(ev(title="x [away]"))[1], "set manually")

    def test_default_is_busy(self):
        self.assertEqual(classify(ev()), (BUSY, ""))


class BlockLabelTest(unittest.TestCase):
    def test_labels_and_reason(self):
        b = to_block(ev(title="All Hands"))
        self.assertEqual(b.title, "Webinar - Off Camera")
        self.assertIn("large session", b.notes)
        self.assertEqual(to_block(ev(room=True)).title, "Away from Home")
        self.assertEqual(to_block(ev()).title, "Busy")

    def test_title_never_copied(self):
        b = to_block(ev(title="Bepco - Phone # Porting [away]"))
        self.assertNotIn("Bepco", b.title + b.notes)


def existing(key, title):
    return Existing(hash=short_hash(key), title=title, start=T0, end=T0 + timedelta(minutes=30))


class RecategorizeTest(unittest.TestCase):
    def test_new_blocks_get_category_titles(self):
        p = plan([ev(key="a", title="All Hands"), ev(key="b")], [], TODAY)
        self.assertEqual(sorted(b.title for b in p.creates), ["Busy", "Webinar - Off Camera"])

    def test_category_change_updates_title_in_place(self):
        p = plan([ev(key="a", title="All Hands")], [existing("a", "Busy")], TODAY)
        self.assertEqual((p.creates, p.deletes), ([], []))
        self.assertEqual(p.updates[0][1].title, "Webinar - Off Camera")

    def test_settled_block_left_alone(self):
        p = plan([ev(key="a", title="All Hands")], [existing("a", "Webinar - Off Camera")], TODAY)
        self.assertEqual((p.creates, p.updates, p.deletes, p.kept), ([], [], [], 1))
