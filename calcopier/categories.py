"""Decide what kind of block a work meeting becomes. Pure Python; rules are checked in order."""

import re

from .model import WorkEvent

BUSY, WEBINAR, AWAY = "busy", "webinar", "away"

LABELS = {
    BUSY: "Busy",
    WEBINAR: "Webinar - Off Camera",
    AWAY: "Away from Home",
}

# [tag] in the meeting title forces a category.
OVERRIDES = {"busy": BUSY, "webinar": WEBINAR, "listen": WEBINAR, "away": AWAY}
OVERRIDE_RE = re.compile(r"\[(" + "|".join(OVERRIDES) + r")\]", re.I)

WEBINAR_WORDS = ["webinar", "ahod", "all hands", "all-hands", "town hall", "townhall", "office hours",
                 "training", "enablement", "lunch & learn", "lunch and learn", "lunch n learn"]
AWAY_WORDS = ["onsite", "on-site", "on site", "visit", "lunch", "dinner", "offsite", "off-site",
              "travel", "flight", "in person", "in-person"]
LARGE_AUDIENCE = 50
STREET = re.compile(r"\b\d{2,6}\s+[\w .'-]+\b(st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|"
                    r"ln|lane|way|pkwy|parkway|hwy|highway|ct|court|pl|place|suite|ste)\b\.?", re.I)


def _has_word(text, words):
    text = text.lower()
    return next((w for w in words if re.search(r"(?<!\w)" + re.escape(w) + r"(?!\w)", text)), None)


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

    # Webinar keywords before away keywords so "Lunch & Learn" isn't read as an away lunch.
    if _has_word(event.title, WEBINAR_WORDS):
        return WEBINAR, "large session"
    if _has_word(event.title, AWAY_WORDS):
        return AWAY, "in-person meeting"

    if event.attendee_count >= LARGE_AUDIENCE:
        return WEBINAR, "large audience"
    if event.has_group:
        return WEBINAR, "sent to a distribution list"

    return BUSY, ""
