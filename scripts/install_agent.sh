#!/bin/bash
# Install (or reinstall) the launchd agent that runs the sync every 10 minutes.
# Usage: scripts/install_agent.sh            install and run once now
#        scripts/install_agent.sh uninstall  stop and remove
set -euo pipefail

LABEL="local.calendarcopier"
REPO="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$REPO/.venv/bin/python"
LOGDIR="$HOME/Library/Logs/CalendarCopier"
PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
DOMAIN="gui/$(id -u)"

launchctl bootout "$DOMAIN/$LABEL" 2>/dev/null || true

if [[ "${1:-}" == "uninstall" ]]; then
    rm -f "$PLIST"
    echo "Uninstalled $LABEL."
    exit 0
fi

if [[ ! -x "$PYTHON" ]]; then
    echo "No virtualenv at $PYTHON. Create it first (see README)." >&2
    exit 1
fi

mkdir -p "$LOGDIR" "$(dirname "$PLIST")"
sed -e "s|__PYTHON__|$PYTHON|" -e "s|__REPO__|$REPO|" -e "s|__LOGDIR__|$LOGDIR|g" \
    "$REPO/launchd/$LABEL.plist.template" > "$PLIST"
plutil -lint "$PLIST" >/dev/null

launchctl bootstrap "$DOMAIN" "$PLIST"
echo "Installed $LABEL: runs every 10 minutes and at login."
echo "Log: $LOGDIR/sync.log"
