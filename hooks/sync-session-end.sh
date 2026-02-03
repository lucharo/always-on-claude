#!/bin/bash
# Sync conversation files at session end
# Resumes sync and flushes to push local changes to remote

SYNC_NAME="claude-config"

# Check if this sync exists
if ! mutagen sync list "$SYNC_NAME" &>/dev/null; then
    exit 0  # No sync configured, nothing to do
fi

# Small delay to ensure all writes are complete
sleep 1

# Resume sync (was paused at session start)
mutagen sync resume "$SYNC_NAME" 2>/dev/null

# Flush to push changes immediately
mutagen sync flush "$SYNC_NAME" 2>/dev/null

exit 0
