"""F0 spike: can Python on this Mac read the work calendar, and which fields do we get?

Read-only. Prints the calendars macOS Calendar knows about, then the events in the
next N days for one calendar, plus a summary of which fields are populated
(needed later for categorization).

Usage:
    pip install -r requirements.txt
    python spikes/read_calendar.py                       # list calendars only
    python spikes/read_calendar.py --calendar "Calendar" --days 7
    python spikes/read_calendar.py --calendar "Calendar" --days 7 --details
"""

import argparse
import sys
import threading
from datetime import datetime

import EventKit
from Foundation import NSDate

AUTH_STATUS = {0: "not determined", 1: "restricted", 2: "denied", 3: "full access", 4: "write only"}
PARTICIPANT_STATUS = {
    0: "unknown", 1: "pending", 2: "accepted", 3: "declined",
    4: "tentative", 5: "delegated", 6: "completed", 7: "in process",
}


def request_access(store):
    status = EventKit.EKEventStore.authorizationStatusForEntityType_(EventKit.EKEntityTypeEvent)
    print(f"Calendar permission before request: {AUTH_STATUS.get(status, status)}")
    if status == 3:
        return True

    done = threading.Event()
    result = {}

    def handler(granted, error):
        result["granted"], result["error"] = granted, error
        done.set()

    # macOS 14+ uses full-access API; older versions use the legacy one.
    if hasattr(store, "requestFullAccessToEventsWithCompletion_"):
        store.requestFullAccessToEventsWithCompletion_(handler)
    else:
        store.requestAccessToEntityType_completion_(EventKit.EKEntityTypeEvent, handler)

    if not done.wait(timeout=60):
        print("Timed out waiting for the permission prompt.")
        return False
    if result.get("error"):
        print(f"Permission error: {result['error']}")
    return bool(result.get("granted"))


def to_dt(nsdate):
    return datetime.fromtimestamp(nsdate.timeIntervalSince1970()) if nsdate else None


def my_status(event):
    for attendee in event.attendees() or []:
        if attendee.isCurrentUser():
            return PARTICIPANT_STATUS.get(attendee.participantStatus(), "?")
    return "organizer/none"


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--calendar", help="Calendar title to read (see the list printed first)")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--details", action="store_true", help="Also print location, URL and attendee names")
    args = parser.parse_args()

    store = EventKit.EKEventStore.alloc().init()
    if not request_access(store):
        print("No calendar access. Check System Settings > Privacy & Security > Calendars.")
        sys.exit(1)

    calendars = store.calendarsForEntityType_(EventKit.EKEntityTypeEvent)
    print("\nCalendars:")
    for cal in calendars:
        print(f"  - {cal.title()!r}  (account: {cal.source().title()})")

    if not args.calendar:
        print("\nRe-run with --calendar \"<title>\" to list events.")
        return

    selected = [c for c in calendars if c.title() == args.calendar]
    if not selected:
        print(f"\nNo calendar titled {args.calendar!r}.")
        sys.exit(1)

    start = NSDate.date()
    end = NSDate.dateWithTimeIntervalSinceNow_(args.days * 86400)
    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(start, end, selected)
    events = sorted(store.eventsMatchingPredicate_(predicate) or [], key=lambda e: e.startDate().timeIntervalSince1970())

    print(f"\n{len(events)} events in the next {args.days} days:\n")
    coverage = {"id": 0, "attendees": 0, "location": 0, "url": 0, "notes": 0, "all_day": 0}
    for e in events:
        attendees = e.attendees() or []
        coverage["id"] += bool(e.calendarItemExternalIdentifier())
        coverage["attendees"] += bool(attendees)
        coverage["location"] += bool(e.location())
        coverage["url"] += bool(e.URL())
        coverage["notes"] += bool(e.notes())
        coverage["all_day"] += bool(e.isAllDay())

        s, f = to_dt(e.startDate()), to_dt(e.endDate())
        print(f"{s:%a %m/%d %H:%M}-{f:%H:%M}  {e.title()}  [me: {my_status(e)}, attendees: {len(attendees)}]")
        if args.details:
            print(f"    location: {e.location()}")
            print(f"    url:      {e.URL()}")
            print(f"    people:   {', '.join(str(a.name()) for a in attendees[:8])}")

    if events:
        print("\nField coverage (events with a value / total):")
        for field, n in coverage.items():
            print(f"  {field:<10} {n}/{len(events)}")


if __name__ == "__main__":
    main()
