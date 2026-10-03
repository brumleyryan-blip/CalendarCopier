# CalendarCopier — Backlog

Goal: give my wife a reliable, near-real-time view of when I'm on work calls,
without screenshots or memory.

## Decisions so far
| Topic | Decision |
|---|---|
| Work calendar source | Microsoft 365 / Outlook (Exchange) |
| Destination | iCloud calendar "CalendarCopier", written locally via EventKit, shared to her Apple ID (replaces Google: no OAuth needed) |
| Event content (v1) | Generic "Busy"; category label added in a later feature |
| Window | Next 7 days |
| Source lookup | Exchange account + server name "Calendar" (local renames of Exchange calendars revert) |
| Status rules | Declined hidden; tentative, unanswered and organizer shown as busy; all-day skipped |
| Self-blocks | Shown as Busy in F1; distinct label (e.g. "Focus") in F5 |
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

- [ ] **F2 — Keep in sync: updates and cancellations** — built, awaiting test on the Mac
  Moved meetings update in place; cancelled/declined meetings are removed silently.
  Ended meetings stay for the day; days before today are never touched. If the work
  calendar reads as empty, removals are skipped so a glitch can't wipe her calendar.

- [ ] **F3 — Run every 10–15 minutes on the Mac**
  launchd agent; confirm calendar permission works when not launched from Terminal,
  and that the docked, clamshell Mac stays awake overnight.

- [ ] **F4 — Failure visibility**
  If the sync breaks (calendar missing, permission revoked, Mac asleep), I get notified
  rather than the calendar silently going stale. Also: look up calendars by their stable
  identifier instead of title (a renamed Exchange calendar broke the lookup during F1).

- [ ] **F5 — Categorization v1 (rules)**
  Label each block, e.g. "Video call", "Webinar (listening, can be interrupted?)",
  "Away from house", using title, attendees, location, and meeting links.
  Mockups first.

- [ ] **F6 — Categorization v2 (smarter/overrides)**
  Manual override keywords and/or an LLM classifier for ambiguous invites.

- [ ] **F7 — Working-hours background block** (deferred; decide later)
