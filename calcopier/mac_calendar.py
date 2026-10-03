"""EventKit read/write. macOS only."""

import threading
import time
from datetime import datetime, timedelta, timezone

import EventKit
from Foundation import NSDate, NSRunLoop

from .model import WorkEvent, make_key, marker_in

PARTICIPANT_STATUS = {
    0: "unknown", 1: "pending", 2: "accepted", 3: "declined",
    4: "tentative", 5: "delegated", 6: "completed", 7: "in process",
}
FULL_ACCESS = 3


class CalendarError(RuntimeError):
    pass


def open_store():
    store = EventKit.EKEventStore.alloc().init()
    status = EventKit.EKEventStore.authorizationStatusForEntityType_(EventKit.EKEntityTypeEvent)
    if status == FULL_ACCESS:
        return store

    done, result = threading.Event(), {}

    def handler(granted, error):
        result["granted"] = granted
        done.set()

    if hasattr(store, "requestFullAccessToEventsWithCompletion_"):
        store.requestFullAccessToEventsWithCompletion_(handler)
    else:
        store.requestAccessToEntityType_completion_(EventKit.EKEntityTypeEvent, handler)
    if not done.wait(timeout=60) or not result.get("granted"):
        raise CalendarError("No calendar access. Check System Settings > Privacy & Security > Calendars.")
    return store


def find_calendar(store, title, timeout=10.0):
    """Calendar accounts load asynchronously in a fresh store, so poll briefly before giving up."""
    store.refreshSourcesIfNecessary()
    deadline = time.monotonic() + timeout
    while True:
        calendars = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent) or []
        matches = [c for c in calendars if str(c.title()) == title]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise CalendarError(f"Found {len(matches)} calendars titled {title!r}; rename one.")
        if time.monotonic() >= deadline:
            seen = ", ".join(sorted(repr(str(c.title())) for c in calendars)) or "none"
            raise CalendarError(f"No calendar titled {title!r} after {timeout:.0f}s. Visible: {seen}")
        # Spin the run loop so EventKit can deliver the account data it loads in the background.
        NSRunLoop.currentRunLoop().runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.5))


def window(days):
    """Start of today (local) through `days` days later."""
    today = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    return today, today + timedelta(days=days + 1)


def _nsdate(dt):
    return NSDate.dateWithTimeIntervalSince1970_(dt.timestamp())


def _dt(nsdate):
    return datetime.fromtimestamp(nsdate.timeIntervalSince1970(), tz=timezone.utc)


def _events(store, calendar, start, end):
    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(_nsdate(start), _nsdate(end), [calendar])
    return list(store.eventsMatchingPredicate_(predicate) or [])


def _my_status(event):
    for attendee in event.attendees() or []:
        if attendee.isCurrentUser():
            return PARTICIPANT_STATUS.get(attendee.participantStatus(), "unknown")
    return "organizer/none"


def read_work_events(store, calendar, start, end):
    result = []
    for e in _events(store, calendar, start, end):
        recurring = bool(e.hasRecurrenceRules()) or bool(e.isDetached())
        occurrence = e.occurrenceDate() or e.startDate()
        result.append(WorkEvent(
            key=make_key(str(e.calendarItemExternalIdentifier()), recurring, occurrence.timeIntervalSince1970()),
            title=str(e.title() or ""),
            start=_dt(e.startDate()),
            end=_dt(e.endDate()),
            all_day=bool(e.isAllDay()),
            my_status=_my_status(e),
            attendee_count=len(e.attendees() or []),
            location=str(e.location() or ""),
            notes=str(e.notes() or ""),
        ))
    return result


def existing_hashes(store, calendar, start, end):
    """Marker hashes of blocks this tool already wrote. Unmarked events are left alone."""
    return {h for h in (marker_in(str(e.notes() or "")) for e in _events(store, calendar, start, end)) if h}


def create_blocks(store, calendar, blocks):
    if not calendar.allowsContentModifications():
        raise CalendarError(f"Calendar {calendar.title()!r} is read-only.")
    for block in blocks:
        ev = EventKit.EKEvent.eventWithEventStore_(store)
        ev.setCalendar_(calendar)
        ev.setTitle_(block.title)
        ev.setStartDate_(_nsdate(block.start))
        ev.setEndDate_(_nsdate(block.end))
        ev.setAvailability_(EventKit.EKEventAvailabilityBusy)
        ev.setNotes_(f"Synced from Ryan's work calendar.\n{block.marker}")
        ok, error = store.saveEvent_span_commit_error_(ev, EventKit.EKSpanThisEvent, False, None)
        if not ok:
            raise CalendarError(f"Failed to save block at {block.start}: {error}")
    ok, error = store.commit_(None)
    if not ok:
        raise CalendarError(f"Failed to commit changes: {error}")
