import unittest
from datetime import datetime, timedelta, timezone

from calcopier.categories import AWAY, BUSY, VIDEO, WEBINAR, classify
from calcopier.model import WorkEvent, short_hash
from calcopier.rules import Existing, plan, to_block

T0 = datetime(2026, 10, 20, 15, 0, tzinfo=timezone.utc)
TODAY = T0.replace(hour=5)


def ev(title="Pipeline review", attendees=4, location="", group=False, room=False, key="k", status="accepted",
       notes="", names=()):
    return WorkEvent(key=key, title=title, start=T0, end=T0 + timedelta(minutes=30), all_day=False,
                     my_status=status, attendee_count=attendees, location=location, notes=notes,
                     has_group=group, has_room=room, attendee_names=tuple(names))


def cat(**kw):
    return classify(ev(**kw))[0]


class ClassifyTest(unittest.TestCase):
    def test_webinar_keywords(self):
        for title in ["Partner Webinar", "Q3 AHOD", "All Hands", "Town Hall", "The 'It Depends' Hour - OP SE Office Hours",
                      "FY27 CWA AE Enablement", "Lunch & Learn: Gong"]:
            self.assertEqual(cat(title=title), WEBINAR, title)

    def test_large_audience(self):
        self.assertEqual(cat(attendees=70), WEBINAR)
        self.assertEqual(cat(attendees=49), BUSY)

    def test_distribution_list_only_counts_as_broadcast(self):
        self.assertEqual(cat(title="Cisco Beat", attendees=2, group=True), WEBINAR)        # you + the list
        self.assertEqual(cat(title="NPG Kick-Off", attendees=31, group=True), BUSY)        # real meeting
        self.assertEqual(cat(title="Tiger Team Call", attendees=12, group=True), BUSY)

    def test_livestream_links(self):
        self.assertEqual(cat(location="https://livestreaming.cisco.com/viewer/abc"), WEBINAR)
        self.assertEqual(cat(location="https://partnersuccess.cisco.com/Partner/x"), WEBINAR)
        self.assertEqual(cat(location="Cisco TV; SJC20-2-Imperia (16) (Public)"), WEBINAR)
        self.assertEqual(cat(location="Webinar"), WEBINAR)
        self.assertEqual(cat(notes="Watch at https://livestreaming.cisco.com/viewer/x"), WEBINAR)

    def test_away_signals(self):
        self.assertEqual(cat(location="1200 Main St, Suite 400, Dallas TX"), AWAY)
        self.assertEqual(cat(room=True), AWAY)
        self.assertEqual(cat(title="Customer onsite - Bepco"), AWAY)
        self.assertEqual(cat(title="Lunch w/ Jacob"), AWAY)

    def test_address_or_room_beats_webinar_words(self):
        self.assertEqual(cat(title="Netsync/Cisco - AI and Splunk Lunch & Learn",
                             location="5301 Alpha Rd, Dallas, TX"), AWAY)
        self.assertEqual(cat(title="Enablement session", room=True), AWAY)

    def test_webinar_words_beat_away_words(self):
        self.assertEqual(cat(title="Lunch & Learn: Gong"), WEBINAR)

    def test_away_beats_size(self):
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
        self.assertEqual(cat(title="Red River call [busy]"), BUSY)
        self.assertEqual(cat(title="Partner call [video]"), VIDEO)
        self.assertEqual(cat(title="Deal review [listen]"), WEBINAR)
        self.assertEqual(classify(ev(title="x [away]"))[1], "set manually")

    def test_video_title_words(self):
        for title in ["Red River Jockey School", "Red River FY27 Weekly Commit Call", "Security Sync - Ryan",
                      "Peer Accelerator sync", "Jacob and Ryan Sync"]:
            self.assertEqual(cat(title=title, attendees=15, group=True), VIDEO, title)

    def test_video_people(self):
        self.assertEqual(cat(title="Deal review", names=("Jacob Shaver", "Ryan Brumley")), VIDEO)
        self.assertEqual(cat(title="Deal review", names=("Jacob Smith",)), BUSY)

    def test_webinar_beats_video(self):
        self.assertEqual(cat(title="Global Sales All Hands", attendees=36, names=("Jacob Shaver",)), WEBINAR)
        self.assertEqual(cat(title="Red River enablement"), WEBINAR)
        self.assertEqual(cat(title="Red River lunch", location="100 Main St"), AWAY)

    def test_sync_is_whole_word(self):
        self.assertEqual(cat(title="Async updates"), BUSY)

    def test_default_is_busy(self):
        self.assertEqual(classify(ev()), (BUSY, ""))


class ReminderTest(unittest.TestCase):
    def test_reminders_not_copied(self):
        from calcopier.rules import should_copy
        for title in ["My Performance Weekly Check In | Due by Noon Thursday Weekly", "Friday EOD"]:
            self.assertFalse(should_copy(ev(title=title, names=("Jacob Shaver",))), title)

    def test_tagged_reminder_is_copied(self):
        from calcopier.rules import should_copy
        self.assertTrue(should_copy(ev(title="Friday EOD [video]")))

    def test_ordinary_meetings_still_copied(self):
        from calcopier.rules import should_copy
        self.assertTrue(should_copy(ev(title="EOD review with team")))


class BlockLabelTest(unittest.TestCase):
    def test_labels_and_reason(self):
        b = to_block(ev(title="All Hands"))
        self.assertEqual(b.title, "Webinar - Off Camera")
        self.assertIn("webinar-style session", b.notes)
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
