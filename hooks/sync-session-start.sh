#!/bin/bash
# Sync conversation files at session start
# Flushes pending syncs, then pauses to prevent race conditions during the session

SYNC_NAME="claude-config"

# Check if this sync exists
if ! mutagen sync list "$SYNC_NAME" &>/dev/null; then
    exit 0  # No sync configured, nothing to do
fi

# Flush any pending changes (pull latest from remote)
mutagen sync flush "$SYNC_NAME" 2>/dev/null

# Pause sync during the session to prevent mid-write overwrites
mutagen sync pause "$SYNC_NAME" 2>/dev/null

exit 0
