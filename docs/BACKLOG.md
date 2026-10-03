# CalendarCopier — Backlog

Goal: give my wife a reliable, near-real-time view of when I'm on work calls,
without screenshots or memory.

## Decisions so far
| Topic | Decision |
|---|---|
| Work calendar source | Microsoft 365 / Outlook (Exchange) |
| Destination | A dedicated Google Calendar, shared with my wife |
| Event content (v1) | Generic "Busy"; category label added in a later feature |
| Working-hours block | Deferred (see F7) |
| Hosting | Cloud, independent of my Mac (platform TBD after F0) |

## Features (one at a time, in order)

- [ ] **F0 — Spike: can the cloud read my work calendar?**
  Find a read path for the M365 calendar that works without my devices:
  1. Outlook web "Publish a calendar" ICS link (no auth, easiest)
  2. Microsoft Graph API (may need IT/admin consent)
  3. Fallback: iPhone Shortcut pushes events to a cloud endpoint
  Done when: we can fetch today's events from a script and see the right times,
  plus how quickly edits and cancellations show up.

- [ ] **F1 — One-shot copy (manual run)**
  A script reads the next N days of work events and writes "Busy" blocks into the
  shared Google Calendar. Re-running it adds no duplicates.

- [ ] **F2 — Keep in sync: updates and cancellations**
  Moved meetings move, cancelled meetings disappear, declined meetings are skipped.

- [ ] **F3 — Cloud schedule every 10–15 minutes**
  Deploy F1+F2 to a scheduled cloud job, with secrets stored securely.

- [ ] **F4 — Failure visibility**
  If the sync breaks (expired token, revoked link), I get notified rather than
  the calendar silently going stale.

- [ ] **F5 — Categorization v1 (rules)**
  Label each block, e.g. "Video call", "Webinar (listening, can be interrupted?)",
  "Away from house", using title, attendees, location, and meeting links.
  Mockups first.

- [ ] **F6 — Categorization v2 (smarter/overrides)**
  Manual override keywords and/or an LLM classifier for ambiguous invites.

- [ ] **F7 — Working-hours background block** (deferred; decide later)
