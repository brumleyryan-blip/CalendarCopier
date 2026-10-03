"""Which work events become busy blocks, and how they're labeled."""

from .model import Block, WorkEvent, short_hash


def should_copy(event: WorkEvent) -> bool:
    if event.all_day:  # mostly colleagues' OOO/PTO
        return False
    if event.my_status == "declined":
        return False
    return True  # accepted, tentative, no response, organizer


def to_block(event: WorkEvent) -> Block:
    return Block(key=event.key, title="Busy", start=event.start, end=event.end)


def plan_creates(events, existing_hashes):
    """Blocks to create: copyable events whose marker isn't already in the shared calendar."""
    blocks = [to_block(e) for e in events if should_copy(e)]
    return [b for b in blocks if short_hash(b.key) not in existing_hashes]
