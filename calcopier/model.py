"""Plain-Python event model, independent of macOS so it can be unit tested anywhere."""

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime

MARKER_RE = re.compile(r"\[cc:([0-9a-f]{12})\]")


@dataclass(frozen=True)
class WorkEvent:
    key: str            # stable per occurrence; see make_key
    title: str
    start: datetime     # timezone-aware
    end: datetime
    all_day: bool
    my_status: str      # accepted, declined, tentative, pending, unknown, organizer/none, ...
    attendee_count: int
    location: str = ""
    notes: str = ""


@dataclass(frozen=True)
class Block:
    """What gets written to the shared calendar."""
    key: str
    title: str
    start: datetime
    end: datetime

    @property
    def marker(self) -> str:
        return f"[cc:{short_hash(self.key)}]"


def make_key(external_id: str, recurring: bool, occurrence_ts: float) -> str:
    """Recurring events share one external ID, so each occurrence is keyed by its original date."""
    if recurring:
        return f"{external_id}|{int(occurrence_ts)}"
    return external_id


def short_hash(key: str) -> str:
    # Hash rather than store the Exchange ID so nothing work-identifying lands in the shared calendar.
    return hashlib.sha1(key.encode()).hexdigest()[:12]


def marker_in(notes: str):
    match = MARKER_RE.search(notes or "")
    return match.group(1) if match else None
