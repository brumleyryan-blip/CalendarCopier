"""F5 spike: what does each work meeting reveal that could drive a category?

Read-only. For each meeting in the window, prints the signals a categorizer could use:
conferencing app found in location/notes, whether the location looks like a physical place,
internal vs external attendee counts, and title keywords. Ends with a tally.

Usage:
    python spikes/category_signals.py                 # past 30 days + next 14
    python spikes/category_signals.py --past 60 --days 14
"""

import argparse
import re
from collections import Counter
from datetime import timedelta

from calcopier import mac_calendar as cal

CONFERENCING = {
    "teams": r"teams\.microsoft\.com|microsoft teams",
    "zoom": r"zoom\.us|zoomgov\.com",
    "webex": r"webex\.com",
    "meet": r"meet\.google\.com",
    "gotomeeting": r"gotomeeting\.com|gotomeet\.me",
    "phone": r"dial[- ]?in|conference id|\+1[\s(-]*\d{3}",
}
KEYWORDS = ["webinar", "office hours", "town hall", "all hands", "training", "enablement", "session",
            "onsite", "on-site", "visit", "lunch", "dinner", "travel", "flight", "drive", "offsite",
            "ooo", "pto", "focus", "hold", "busy", "1:1", "sync", "interview", "demo", "customer"]
ADDRESS = re.compile(r"\d+\s+\w+.*\b(st|street|ave|avenue|rd|road|blvd|dr|drive|ln|lane|way|pkwy|suite)\b", re.I)


def domain(url):
    m = re.search(r"@([\w.-]+)", str(url or ""))
    return m.group(1).lower() if m else None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--source", default="Calendar")
    parser.add_argument("--source-account", default="Exchange")
    parser.add_argument("--past", type=int, default=30)
    parser.add_argument("--days", type=int, default=14)
    args = parser.parse_args()

    store = cal.open_store()
    source = cal.find_calendar(store, args.source, args.source_account)
    today, end = cal.window(args.days)
    events = [e for e in cal._events(store, source, today - timedelta(days=args.past), end) if not e.isAllDay()]
    events.sort(key=lambda e: e.startDate().timeIntervalSince1970())

    tally = Counter()
    for e in events:
        attendees = list(e.attendees() or [])
        me = next((a for a in attendees if a.isCurrentUser()), None)
        my_domain = domain(me.URL()) if me else None
        domains = [domain(a.URL()) for a in attendees]
        external = sum(1 for d in domains if d and my_domain and d != my_domain)

        text = " ".join(str(x or "") for x in (e.location(), e.notes(), e.URL()))
        apps = [name for name, pat in CONFERENCING.items() if re.search(pat, text, re.I)]
        location = str(e.location() or "").strip()
        physical = bool(ADDRESS.search(location))
        title = str(e.title() or "")
        words = [k for k in KEYWORDS if k in title.lower()]

        start = cal._dt(e.startDate()).astimezone()
        mins = int((e.endDate().timeIntervalSince1970() - e.startDate().timeIntervalSince1970()) / 60)
        loc_short = (location[:40] + "...") if len(location) > 40 else location
        print(f"{start:%a %m/%d %H:%M} {mins:>4}m  {title[:55]:<55}  "
              f"att={len(attendees):<3} ext={external:<3} app={','.join(apps) or '-':<12} "
              f"physical={'Y' if physical else '-'}  kw={','.join(words) or '-'}  loc={loc_short!r}")

        tally["meetings"] += 1
        tally["app:" + (apps[0] if apps else "none")] += 1
        tally["physical location"] += physical
        tally["has external attendees"] += external > 0
        tally["no attendees"] += not attendees
        tally["50+ attendees"] += len(attendees) >= 50
        for k in words:
            tally["kw:" + k] += 1

    print("\nTally:")
    for k, v in sorted(tally.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"  {k:<26} {v}")


if __name__ == "__main__":
    main()
