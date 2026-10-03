"""Sync work meetings into the shared calendar as 'Busy' blocks.

Creates new blocks, moves blocks whose meeting moved, and removes blocks for meetings that
were cancelled or declined. Days before today are never touched.

Usage:
    python -m calcopier.sync --dry-run     # show what would change
    python -m calcopier.sync               # apply changes
"""

import argparse
import sys
from datetime import datetime

from . import rules


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

    try:
        store = cal.open_store()
        source = cal.find_calendar(store, args.source, args.source_account)
        dest = cal.find_calendar(store, args.dest)
        start, end = cal.window(args.days)

        events = cal.read_work_events(store, source, start, end)
        existing = cal.existing_blocks(store, dest, start, end)
        p = rules.plan(events, existing, start)

        print(f"[{_stamp()}] {len(events)} work events: {len(p.creates)} to create, {len(p.updates)} to move, "
              f"{len(p.deletes)} to remove, {p.kept} unchanged.")
        for b in p.creates:
            print(f"  + {_fmt(b.start, b.end)}  {b.title}")
        for ex, b in p.updates:
            print(f"  ~ {_fmt(ex.start, ex.end)} -> {_fmt(b.start, b.end)}")
        for ex in p.deletes:
            print(f"  - {_fmt(ex.start, ex.end)}  {ex.title}")
        if p.deletes_suppressed:
            print("Warning: work calendar returned no events; skipping removals as a safety measure.")

        if args.dry_run:
            print("Dry run: nothing written.")
        elif p.creates or p.updates or p.deletes:
            cal.apply_plan(store, dest, p)
            print("Changes applied.")
    except cal.CalendarError as exc:
        print(f"[{_stamp()}] Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
