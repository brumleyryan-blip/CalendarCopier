"""Which work events become busy blocks, and how the shared calendar is reconciled."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .model import Block, WorkEvent, short_hash


def should_copy(event: WorkEvent) -> bool:
    if event.all_day:  # mostly colleagues' OOO/PTO
        return False
    if event.my_status == "declined":
        return False
    return True  # accepted, tentative, no response, organizer


def to_block(event: WorkEvent) -> Block:
    return Block(key=event.key, title="Busy", start=event.start, end=event.end)


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

    seen = set()
    stale = []
    for ex in existing:
        block = desired.get(ex.hash)
        if block is None or ex.hash in seen:  # gone from work calendar, or a duplicate
            stale.append(ex)
            continue
        seen.add(ex.hash)
        if _same(ex, block):
            result.kept += 1
        else:
            result.updates.append((ex, block))

    result.creates = [b for h, b in desired.items() if h not in seen]

    stale = [ex for ex in stale if ex.start >= window_start]
    if stale and not events:
        # An empty read most likely means the work calendar failed to load, not that every
        # meeting was cancelled. Don't wipe her calendar on a glitch.
        result.deletes_suppressed = True
    else:
        result.deletes = stale
    return result
