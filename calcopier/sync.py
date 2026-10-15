"""Sync work meetings into the shared calendar as 'Busy' blocks.

Creates new blocks, moves blocks whose meeting moved, and removes blocks for meetings that
were cancelled or declined. Days before today are never touched. Keeps a "Sync paused" marker
ahead of now that comes due on its own if syncing stops, and notifies on this Mac when a sync fails.

Usage:
    python -m calcopier.sync --dry-run     # show what would change
    python -m calcopier.sync               # apply changes
"""

import argparse
import sys
from datetime import datetime

from . import health, rules
from .categories import AWAY, BUSY, WEBINAR

# Each category gets its own iCloud calendar so it can have its own color on her phone.
CATEGORY_CALENDARS = {WEBINAR: "CalendarCopier Webinar", AWAY: "CalendarCopier Away"}


def _stamp():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _fmt(start, end):
    return f"{start.astimezone():%a %m/%d %H:%M}-{end.astimezone():%H:%M}"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default="Calendar", help="Work calendar title (server name for Exchange)")
    parser.add_argument("--source-account", default="Exchange", help="Account the work calendar belongs to")
    parser.add_argument("--dest", default="CalendarCopier", help="Shared calendar title")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    from . import mac_calendar as cal

    if not args.dry_run:
        health.trim_log()

    error = None
    try:
        store = cal.open_store()
        source = cal.find_calendar(store, args.source, args.source_account)
        calendars = {args.dest: cal.find_calendar(store, args.dest)}
        calendar_for = {BUSY: args.dest}
        for category, title in CATEGORY_CALENDARS.items():
            try:
                calendars[title] = cal.find_calendar(store, title)
                calendar_for[category] = title
            except cal.CalendarError:
                print(f"Note: no {title!r} calendar; {category} blocks go to {args.dest!r}.")
                calendar_for[category] = args.dest
        start, end = cal.window(args.days)

        events = cal.read_work_events(store, source, start, end)
        existing = cal.existing_blocks(store, list(calendars.values()), start, end)
        now = datetime.now().astimezone()
        p = rules.plan(events, existing, start, heartbeat=rules.heartbeat_block(now), now=now,
                       calendar_for=calendar_for)

        print(f"[{_stamp()}] {len(events)} work events: {len(p.creates)} to create, {len(p.updates)} to move, "
              f"{len(p.deletes)} to remove, {p.kept} unchanged.")
        for b in p.creates:
            print(f"  + {_fmt(b.start, b.end)}  {b.title}")
        for ex, b in p.updates:
            print(f"  ~ {_fmt(ex.start, ex.end)} -> {_fmt(b.start, b.end)}  {b.title}")
        for ex in p.deletes:
            print(f"  - {_fmt(ex.start, ex.end)}  {ex.title}")
        if p.deletes_suppressed:
            print("Warning: work calendar returned no events; skipping removals as a safety measure.")

        if args.dry_run:
            print("Dry run: nothing written.")
        elif p.creates or p.updates or p.deletes:
            cal.apply_plan(store, calendar_for, calendars, p)
            print("Changes applied.")
    except cal.CalendarError as exc:
        error = str(exc)
    except Exception as exc:  # unattended: report anything unexpected rather than die silently
        error = f"Unexpected {type(exc).__name__}: {exc}"

    if error:
        print(f"[{_stamp()}] Error: {error}", file=sys.stderr)
    if not args.dry_run:
        health.record_result(error)
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
