"""Which work events become busy blocks, and how the shared calendar is reconciled."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from .categories import LABELS, classify
from .model import Block, WorkEvent, short_hash


def should_copy(event: WorkEvent) -> bool:
    if event.all_day:  # mostly colleagues' OOO/PTO
        return False
    if event.my_status == "declined":
        return False
    return True  # accepted, tentative, no response, organizer


def to_block(event: WorkEvent) -> Block:
    category, reason = classify(event)
    notes = f"Ryan's work calendar ({reason})." if reason else ""
    return Block(key=event.key, title=LABELS[category], start=event.start, end=event.end, notes=notes)


HEARTBEAT_KEY = "__calcopier_heartbeat__"
HEARTBEAT_HASH = short_hash(HEARTBEAT_KEY)
HEARTBEAT_LEAD = timedelta(minutes=120)     # where each refresh places the marker
HEARTBEAT_REFRESH = timedelta(minutes=90)   # refresh once it is closer than this
HEARTBEAT_LENGTH = timedelta(minutes=30)


def heartbeat_block(now: datetime) -> Block:
    """A 'Sync paused' marker kept ahead of now. If syncs stop, nothing moves it and it comes due.

    `now` should be local time so the notes read naturally.
    """
    start = now + HEARTBEAT_LEAD
    when = now.strftime("%a %m/%d at %I:%M %p").replace(" 0", " ")
    notes = (f"Ryan's work calendar last updated {when}. "
             "Busy blocks after that may be out of date; check with Ryan.")
    return Block(key=HEARTBEAT_KEY, title="Sync paused", start=start, end=start + HEARTBEAT_LENGTH, notes=notes)


@dataclass(frozen=True)
class Existing:
    """A block already in the shared calendar. `ref` is the platform handle (an EKEvent on macOS)."""
    hash: str
    title: str
    start: datetime
    end: datetime
    ref: Any = None


@dataclass
class Plan:
    creates: list = field(default_factory=list)   # [Block]
    updates: list = field(default_factory=list)   # [(Existing, Block)]
    deletes: list = field(default_factory=list)   # [Existing]
    kept: int = 0
    deletes_suppressed: bool = False


def _same(existing: Existing, block: Block) -> bool:
    return (existing.title == block.title
            and int(existing.start.timestamp()) == int(block.start.timestamp())
            and int(existing.end.timestamp()) == int(block.end.timestamp()))


def plan(events, existing, window_start: datetime, heartbeat: Block = None, now: datetime = None) -> Plan:
    """Make the shared calendar match the copyable work events within the window.

    Only blocks starting on or after `window_start` are ever deleted, so past days are left alone.
    With `heartbeat` (and `now`), also keep the stale-sync marker ahead of now.
    """
    desired = {short_hash(b.key): b for b in (to_block(e) for e in events if should_copy(e))}
    result = Plan()

    markers = [ex for ex in existing if ex.hash == HEARTBEAT_HASH]
    by_hash = defaultdict(list)
    for ex in existing:
        if ex.hash != HEARTBEAT_HASH:
            by_hash[ex.hash].append(ex)

    stale = []
    for h, found in by_hash.items():
        block = desired.get(h)
        if block is None:  # gone from work calendar
            stale.extend(found)
            continue
        match, duplicates = found[0], found[1:]
        stale.extend(duplicates)
        if _same(match, block):
            result.kept += 1
        else:
            result.updates.append((match, block))

    result.creates.extend(b for h, b in desired.items() if h not in by_hash)

    stale = [ex for ex in stale if ex.start >= window_start]
    if stale and not events:
        # An empty read most likely means the work calendar failed to load, not that every
        # meeting was cancelled. Don't wipe her calendar on a glitch.
        result.deletes_suppressed = True
    else:
        result.deletes = stale

    if heartbeat is not None:
        _plan_heartbeat(result, markers, heartbeat, now)
    return result


def _plan_heartbeat(result: Plan, markers, heartbeat: Block, now: datetime):
    if not markers:
        result.creates.append(heartbeat)
        return
    current, extras = markers[0], markers[1:]
    if current.start - now < HEARTBEAT_REFRESH:
        result.updates.append((current, heartbeat))
    else:
        result.kept += 1
    result.deletes.extend(extras)
