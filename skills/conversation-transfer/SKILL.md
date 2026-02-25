---
name: conversation-transfer
description: This skill should be used when the user asks to "transfer a conversation from the server", "pull a conversation from arch", "copy a session from the other machine", "find a conversation on the server", "resume a server conversation here", "bring over a conversation", or mentions "conversation transfer", "session transfer", "copy conversation logs", or "find conversation on arch-lenovo". Transfers Claude Code conversation logs between the local machine and arch-lenovo server so conversations can be resumed on either machine.
---

# Server Conversation Transfer

Transfer Claude Code conversation logs between this machine and arch-lenovo so conversations can be resumed on either side.

**Important:** Conversations (JSONL logs) are NOT synced by Mutagen because they update too frequently and cause lock/override conflicts. This skill handles on-demand transfer instead.

## How It Works

Claude Code stores conversations as JSONL files in:
```
~/.claude/projects/<project-path-key>/<session-uuid>.jsonl
```

Each conversation may also have associated data:
```
~/.claude/projects/<project-path-key>/<session-uuid>/
  subagents/       # subagent conversation logs
  tool-results/    # cached tool results (PDF pages, etc.)
```

To resume a conversation on another machine, you need to copy the JSONL file (and its associated directory if it exists) into the correct project directory on the target machine.

## Transfer Procedure

### Step 1: Connect to arch-lenovo

```bash
ssh arch-lenovo "echo connected"
```

If this fails, check Tailscale (`tailscale status`) and SSH config.

### Step 2: Find the conversation

The user will usually describe the conversation by topic. Search for it:

```bash
# Search all conversation logs for a keyword
ssh arch-lenovo "grep -rl '<keyword>' ~/.claude/projects/ 2>/dev/null | grep -v subagent | grep -v tool-results"
```

If there are many matches, count occurrences to find the most relevant conversation:

```bash
ssh arch-lenovo "grep -rl '<keyword>' ~/.claude/projects/ 2>/dev/null | grep -v subagent | grep -v tool-results | while read f; do count=\$(grep -c '<keyword>' \"\$f\" 2>/dev/null); echo \"\$count \$f\"; done | sort -rn | head -10"
```

To confirm you have the right conversation, extract user messages:

```bash
ssh arch-lenovo "python3 -c '
import json, sys
with open(sys.argv[1]) as f:
    for line in f:
        d = json.loads(line)
        if d.get(\"type\") == \"user\":
            msg = d.get(\"message\", {})
            content = msg.get(\"content\", \"\")
            if isinstance(content, str) and len(content) > 10:
                print(content[:300])
                print(\"---\")
            elif isinstance(content, list):
                for c in content:
                    if isinstance(c, dict) and c.get(\"type\") == \"text\" and len(c.get(\"text\",\"\")) > 10:
                        print(c[\"text\"][:300])
                        print(\"---\")
' <path-to-jsonl> 2>/dev/null | head -40"
```

**Always confirm with the user** that you've found the right conversation before copying.

### Step 3: Determine the target project directory

The conversation needs to go into the project directory for the current working directory. The project key is the cwd with `/` replaced by `-`:

```bash
# Current project's conversation directory
ls ~/.claude/projects/-Users-luischavesrodriguez-Projects-<project-path>/
```

### Step 4: Copy the conversation

```bash
# Copy the JSONL file
SESSION_ID="<uuid>"
SOURCE_PROJECT="<source-project-key>"
TARGET_DIR=~/.claude/projects/-Users-luischavesrodriguez-Projects-<target-project-key>

scp arch-lenovo:~/.claude/projects/$SOURCE_PROJECT/$SESSION_ID.jsonl $TARGET_DIR/

# Copy associated data (subagents, tool-results) if they exist
scp -r arch-lenovo:~/.claude/projects/$SOURCE_PROJECT/$SESSION_ID/ $TARGET_DIR/ 2>/dev/null
```

### Step 5: Verify and inform the user

```bash
ls -la $TARGET_DIR/$SESSION_ID*
```

Tell the user they can resume with:
```bash
claude --resume <session-uuid>
```

## Reverse Transfer (Local to Server)

The same process works in reverse. Copy from the local machine to arch-lenovo:

```bash
SESSION_ID="<uuid>"
SOURCE_DIR=~/.claude/projects/-Users-luischavesrodriguez-Projects-<project-key>

scp $SOURCE_DIR/$SESSION_ID.jsonl arch-lenovo:~/.claude/projects/<target-project-key>/
scp -r $SOURCE_DIR/$SESSION_ID/ arch-lenovo:~/.claude/projects/<target-project-key>/ 2>/dev/null
```

## Notes

- The source and target project directories don't need to match - the conversation will appear under whichever project you copy it into
- Path keys on arch-lenovo use the same `/Users/luischavesrodriguez/...` prefix thanks to the bind mount (see always-on-setup skill)
- Large conversations can be 10MB+ due to embedded tool results; `scp` handles this fine over Tailscale
- If the conversation used context compaction, there may be a `compact` subagent log - make sure to copy the full subagents directory
