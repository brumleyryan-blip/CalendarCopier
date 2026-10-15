"""Error notifications and log upkeep for unattended runs."""

import json
import subprocess
from pathlib import Path

STATE_FILE = Path.home() / "Library/Application Support/CalendarCopier/state.json"
LOG_FILE = Path.home() / "Library/Logs/CalendarCopier/sync.log"
LOG_MAX_BYTES = 1_000_000
LOG_KEEP_BYTES = 200_000


def notify_mac(title, message):
    script = f"display notification {json.dumps(message)} with title {json.dumps(title)}"
    subprocess.run(["osascript", "-e", script], check=False, capture_output=True)


def _load(path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def record_result(error, state_file=STATE_FILE, notify=notify_mac):
    """Notify on a new or changed error only, so a lasting failure doesn't ping every run."""
    state = _load(state_file)
    if error and error != state.get("last_error"):
        notify("CalendarCopier sync failed", error)
    state["last_error"] = error
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state))


def trim_log(path=LOG_FILE, max_bytes=LOG_MAX_BYTES, keep_bytes=LOG_KEEP_BYTES):
    """Keep the newest lines in place. launchd appends to the same file, so trim rather than rotate."""
    try:
        if path.stat().st_size <= max_bytes:
            return
        with open(path, "r+b") as f:
            f.seek(-keep_bytes, 2)
            tail = f.read()
            tail = tail[tail.find(b"\n") + 1:]  # start on a whole line
            f.seek(0)
            f.write(tail)
            f.truncate()
    except OSError:
        pass
