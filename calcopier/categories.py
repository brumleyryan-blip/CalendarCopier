"""Decide what kind of block a work meeting becomes. Pure Python; rules are checked in order."""

import re

from .model import WorkEvent

BUSY, WEBINAR, AWAY, VIDEO, CUSTOMER = "busy", "webinar", "away", "video", "customer"

LABELS = {
    BUSY: "Busy",
    WEBINAR: "Webinar - Off Camera",
    AWAY: "Away from Home",
    VIDEO: "Video Call - On Camera",
    CUSTOMER: "Customer Call - On Video",
}

# [tag] in the meeting title forces a category.
OVERRIDES = {"busy": BUSY, "webinar": WEBINAR, "listen": WEBINAR, "away": AWAY, "video": VIDEO,
             "customer": CUSTOMER}
OVERRIDE_RE = re.compile(r"\[(" + "|".join(OVERRIDES) + r")\]", re.I)

WEBINAR_WORDS = ["webinar", "ahod", "all hands", "all-hands", "town hall", "townhall", "office hours",
                 "training", "enablement", "lunch & learn", "lunch and learn", "lunch n learn",
                 "ai easy button"]
AWAY_WORDS = ["onsite", "on-site", "on site", "visit", "lunch", "dinner", "offsite", "off-site",
              "travel", "flight", "in person", "in-person"]
# Broadcast/livestream links: watched, not joined on camera.
LIVESTREAM_HINTS = ["livestreaming.cisco.com", "partnersuccess.cisco.com", "cisco tv"]
LARGE_AUDIENCE = 50
BROADCAST_MAX_ATTENDEES = 3   # a distribution list plus little more than you = a broadcast invite

# Not copied at all: reminders that aren't really meetings, and time off (teammates' OOO
# invites, or my own full-day block so nobody books over it).
SKIP_WORDS = ["due by", "friday eod", "ooo", "pto", "vto", "out of office"]

# Meetings where Ryan is expected on camera.
VIDEO_TITLE_WORDS = ["red river", "sync"]
VIDEO_PEOPLE = ["jacob shaver"]
# Checked after the customer rule, so a 1:1 with a customer keeps the customer label.
ONE_ON_ONE_WORDS = ["1:1", "1x1", "1-on-1", "one on one", "one-on-one"]
STREET = re.compile(r"\b\d{2,6}\s+[\w .'-]+\b(st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|"
                    r"ln|lane|way|pkwy|parkway|hwy|highway|ct|court|pl|place|suite|ste)\b\.?", re.I)


def _has_word(text, words):
    text = text.lower()
    return next((w for w in words if re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", text)), None)


def is_skipped(event: WorkEvent) -> bool:
    if OVERRIDE_RE.search(event.title):  # a [tag] means it's a real meeting
        return False
    return _has_word(event.title, SKIP_WORDS) is not None


def classify(event: WorkEvent):
    """Return (category, reason). The reason is short and safe to show on her calendar."""
    tag = OVERRIDE_RE.search(event.title)
    if tag:
        return OVERRIDES[tag.group(1).lower()], "set manually"

    # A real place beats any keyword: an in-person lunch & learn still means you're out.
    if STREET.search(event.location):
        return AWAY, "in-person location"
    if event.has_room:
        return AWAY, "meeting room booked"

    # Webinars before video, so a big all-hands with a teammate in it stays off camera.
    if _has_word(event.title, WEBINAR_WORDS):
        return WEBINAR, "webinar-style session"
    where = f"{event.location} {event.notes}".lower()
    if any(h in where for h in LIVESTREAM_HINTS) or _has_word(event.location, ["webinar"]):
        return WEBINAR, "livestream"
    if event.attendee_count >= LARGE_AUDIENCE:
        return WEBINAR, "large audience"
    if event.has_group and event.attendee_count <= BROADCAST_MAX_ATTENDEES:
        return WEBINAR, "broadcast to a distribution list"

    # After webinar keywords so "Lunch & Learn" stays a webinar; before customer so a
    # customer lunch reads as away.
    if _has_word(event.title, AWAY_WORDS):
        return AWAY, "in-person meeting"

    # Known team calls before customer: both mean on camera, and team calls often have one
    # outside guest.
    if _has_word(event.title, VIDEO_TITLE_WORDS):
        return VIDEO, "team call"
    names = " | ".join(event.attendee_names).lower()
    if any(p in names for p in VIDEO_PEOPLE):
        return VIDEO, "team call"

    # An internal list invite with one stray outside address is still an internal meeting.
    if event.external_count >= (2 if event.has_group else 1):
        return CUSTOMER, "outside attendees"

    if _has_word(event.title, ONE_ON_ONE_WORDS):
        return VIDEO, "1:1"

    return BUSY, ""
