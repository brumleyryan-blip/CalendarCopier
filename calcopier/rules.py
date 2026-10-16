"""Which work events become busy blocks, and how the shared calendar is reconciled."""

from collections import defaultdict
from dataclasses import dataclass, field, replace
from datetime import datetime
from typing import Any

from .categories import LABELS, classify, is_skipped
from .model import Block, WorkEvent, short_hash


def should_copy(event: WorkEvent) -> bool:
    if event.all_day:  # mostly colleagues' OOO/PTO
        return False
    if event.my_status == "declined":
        return False
    if is_skipped(event):  # reminders and time off don't take up meeting time
        return False
    return True  # accepted, tentative, no response, organizer


AUTO_TITLES = set(LABELS.values())


def to_block(event: WorkEvent) -> Block:
    category, reason = classify(event)
    notes = f"Ryan's work calendar ({reason})." if reason else ""
    return Block(key=event.key, title=LABELS[category], start=event.start, end=event.end, notes=notes)


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


def plan(events, existing, window_start: datetime) -> Plan:
    """Make the shared calendar match the copyable work events within the window.

    Only blocks starting on or after `window_start` are ever deleted, so past days are left alone.
    """
    desired = {short_hash(b.key): b for b in (to_block(e) for e in events if should_copy(e))}
    result = Plan()

    by_hash = defaultdict(list)
    for ex in existing:
        by_hash[ex.hash].append(ex)

    stale = []
    for h, found in by_hash.items():
        block = desired.get(h)
        if block is None:  # gone from work calendar
            stale.extend(found)
            continue
        match, duplicates = found[0], found[1:]
        stale.extend(duplicates)
        if match.title not in AUTO_TITLES:  # renamed by hand on the shared calendar: keep it
            block = replace(block, title=match.title)
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
    return result
