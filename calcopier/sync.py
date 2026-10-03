"""F1: one-shot copy of work meetings into the shared calendar as 'Busy' blocks.

Usage:
    python -m calcopier.sync --dry-run     # show what would be created
    python -m calcopier.sync               # create missing blocks
"""

import argparse
import sys

from . import rules


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
        existing = cal.existing_hashes(store, dest, start, end)
        creates = rules.plan_creates(events, existing)

        copyable = sum(rules.should_copy(e) for e in events)
        print(f"{len(events)} work events, {copyable} copyable, {copyable - len(creates)} already synced, "
              f"{len(creates)} to create.")
        for b in creates:
            local = b.start.astimezone()
            print(f"  + {local:%a %m/%d %H:%M}-{b.end.astimezone():%H:%M}  {b.title}")

        if args.dry_run:
            print("Dry run: nothing written.")
        elif creates:
            cal.create_blocks(store, dest, creates)
            print(f"Created {len(creates)} blocks in {args.dest!r}.")
    except cal.CalendarError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
