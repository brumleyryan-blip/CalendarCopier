# CalendarCopier — Backlog

Goal: give my wife a reliable, near-real-time view of when I'm on work calls,
without screenshots or memory.

## Decisions so far
| Topic | Decision |
|---|---|
| Work calendar source | Microsoft 365 / Outlook (Exchange) |
| Destination | iCloud calendar "CalendarCopier", written locally via EventKit, shared to her Apple ID (replaces Google: no OAuth needed) |
| Event content (v1) | Generic "Busy"; category label added in a later feature |
| Window | Today + next 21 days (was 7 until 2026-10-16) |
| Source lookup | Exchange account + server name "Calendar" (local renames of Exchange calendars revert) |
| Status rules | Declined hidden; tentative, unanswered and organizer shown as busy; all-day skipped |
| Self-blocks | Shown as "Busy" (no separate focus category) |
| Wife's devices | iPhone + Google account |
| Working-hours block | Deferred (see F7) |
| Hosting | Local on the docked MacBook (launchd); reader/writer split so a phone or cloud reader can replace it later |
| Read path | Local Python on the Mac via EventKit (Power Automate + Google connector blocked by DLP) |
| Language | Python |
| Data leaving phone | Full detail OK (titles/attendees); wife still sees only Busy + category |

## Features (one at a time, in order)

- [x] **F0 — Spike: can the cloud read my work calendar?**
  Find a read path for the M365 calendar that works without my devices:
  1. Outlook web "Publish a calendar" ICS link (no auth, easiest)
  2. Microsoft Graph API (may need IT/admin consent)
  3. Fallback: iPhone Shortcut pushes events to a cloud endpoint
  Findings (2026-10-03):
  - "Publish a calendar" is missing from Outlook web settings, so ICS publishing is off for the tenant.
  - Sharing to any external address (including Gmail) is blocked, so a separate Gmail account won't help.
  - Power Automate: Outlook.com connector blocked by DLP policy 'Core: Default'.
  - Shortcut path shelved in favor of the Mac (only needed when working from home, when the Mac is docked).
  - RESULT: `spikes/read_calendar.py` works on Homebrew Python 3.12. Calendar "RB Work" (Exchange),
    full access granted from Terminal. Coverage over 22 events: id 22/22, attendees 21/22,
    location 15/22, notes 17/22, url 0/22 (meeting links live in location/notes), all-day 5/22.
  - Observations for F1/F2: all-day events are mostly colleagues' OOO/PTO; recurring events
    likely share one external ID (key on ID + occurrence start); some events report
    "organizer/none" or "unknown" status.
  Done when: we can fetch today's events from a script and see the right times,
  plus how quickly edits and cancellations show up.

- [x] **F1 — One-shot copy (manual run)** — verified 2026-10-03: 17 blocks created, re-run created 0
  `python -m calcopier.sync [--dry-run]` reads today + 7 days of the Exchange "Calendar" and writes "Busy"
  blocks into "CalendarCopier". Each block carries a hashed marker in its notes, so re-runs
  add no duplicates and only tool-written events are ever touched.

- [x] **F2 — Keep in sync: updates and cancellations** — verified 2026-10-03: create, move (in place), remove
  Moved meetings update in place; cancelled/declined meetings are removed silently.
  Ended meetings stay for the day; days before today are never touched. If the work
  calendar reads as empty, removals are skipped so a glitch can't wipe her calendar.

- [x] **F3 — Run every 10 minutes on the Mac, around the clock** — verified 2026-10-03 (launchd run logged, no extra permission prompt)
  `scripts/install_agent.sh` installs a launchd agent (every 600s + at login), logging to
  `~/Library/Logs/CalendarCopier/sync.log`. Docked Mac confirmed to stay awake overnight.

- [ ] **F3.5 — Sharing setup (no code)** — sharing 2026-10-16; watching alerts, latency, label clarity
  Decided: normal iCloud share to her Apple ID, view-only. She turns off
  Settings > Notifications > Calendar > Shared Calendar Changes (she has no other shared
  calendars). Still to verify on her phone: no alerts from default alert times.

- [x] **F4 — Failure visibility** — verified 2026-10-15: marker created, notification once per error
  Chosen design: option C, a 30-min "Sync paused" marker on the shared calendar. Each good run
  keeps it ~2h ahead (moved only when <90 min away, ~48 writes/day), so if syncing stops it
  comes due 90–120 min after the last update. Its notes give the last-update time. Any hour.
  macOS notification on sync errors only, once per distinct error. Log trimmed past 1 MB.

- [ ] **F4.1 — Rename-proof calendar lookup** — parked; F4 alerts catch a rename quickly
  Find calendars by their stable identifier instead of title (a renamed Exchange calendar
  broke the lookup during F1). Low priority while the title matches the server name.

- [x] **F5 — Categorization v1 (rules)** — verified 2026-10-16 on real meetings
  Labels: "Webinar - Off Camera", "Away from Home", "Video Call - On Camera", "Busy".
  Single calendar ("CalendarCopier"); category in the title, reason in the notes.
  (Per-category calendars for color were considered and dropped.) Rules in order:
  1. [tag] override: [webinar]/[listen]/[away]/[video]/[busy]
  2. Away: street address in location, or a booked conference room
  3. Webinar: keywords (webinar, AHOD, all hands, town hall, office hours, training,
     enablement, lunch & learn, AI Easy Button); livestream links (livestreaming/partnersuccess.cisco.com,
     Cisco TV, location "Webinar"); 50+ attendees; distribution list with <=3 attendees
  4. Away: keywords (onsite, visit, lunch, dinner, offsite, travel, flight, in person)
  5. Video: "red river" or "sync" in title; Jacob Shaver attending
  6. Customer: outside @cisco.com attendee(s) -> "Customer Call - On Video"
     (2+ needed when a distribution list is invited)
  7. Video: 1:1 / 1x1 / 1-on-1 / one-on-one in title (after customer, so customer 1:1s
     keep the customer label)
  8. Busy
  Hand edits: a block renamed on the shared calendar keeps its title (times still sync);
  delete it to get the automatic label back.
  Not copied at all: reminders ("due by", "Friday EOD") and time off (OOO, PTO, VTO,
  out of office), all-day or timed, unless [tagged].
  Learned 2026-10-16: distribution lists alone over-matched (team meetings use them);
  no meetings had external attendees, so customer detection is deferred.

- [x] **F5b — Customer calls** — verified 2026-10-16 against a month of meetings
  Outside @cisco.com people (not rooms or lists); partners count too. One label for all.

- [ ] **F6 — Categorization v2 (smarter/overrides)**
  Manual override keywords and/or an LLM classifier for ambiguous invites.

- [ ] **F7 — Working-hours background block** (deferred; decide later)
