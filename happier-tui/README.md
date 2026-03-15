# Happier TUI

A terminal dashboard for all your [Happier](https://github.com/gptlabs/happier) sessions across machines. The relay knows about every session on every device — the TUI is the single pane of glass.

## What works for everyone vs what's specific to our setup

**Works for anyone with happier + relay:**
- Session list across all machines (host, agent, title, status)
- Filters (recent/active/all), search, detail sidebar
- Remote chat view via relay stream API (Enter on remote session)
- Local resume of local sessions (Enter on local session)

**Requires our specific multi-machine setup:**
- **Local resume of remote sessions** (R key) — needs all of:
  - [Mutagen](https://mutagen.io/) (or similar) syncing `~/Projects/` between machines
  - A path bridge so both machines see the same relative paths (we use a symlink `/home/luis` → `/Users/luischavesrodriguez` on Linux)
  - The same agent binary (`claude`, `codex`, etc.) installed on both machines
  - Conversation sync from relay → local JSONL (this is what `sync.py` does)

Without Mutagen + the path setup, the R key will show "Directory not found" and block. The chat view (Enter) still works since it just proxies messages through the relay without needing local files.

## Two modes of interaction

```
┌─────────────────────────────────────────────────────────────┐
│                    Happier TUI                              │
│  Lists ALL sessions from relay (arch, macbook, phone)       │
│                                                             │
│  Session selected → is it local?                            │
│        │                                                    │
│    ┌───┴───┐                                                │
│    │  YES  │──→ happier --resume <id> --yolo                │
│    │       │    (exits TUI, spawns local Claude process)     │
│    └───────┘                                                │
│    ┌───────┐                                                │
│    │  NO   │──→ ChatScreen (relay stream API)               │
│    │       │    You type → stream-start → arch runs it      │
│    │       │    stream-read polls → shows Claude's response  │
│    └───────┘                                                │
└─────────────────────────────────────────────────────────────┘
```

### Mode 1: Local resume (Enter on local session)

- Session was started on this machine
- TUI exits, `happier --resume <id>` takes over
- Claude picks up the `.jsonl` conversation file from `~/.claude/projects/`
- You're now in a normal Claude Code terminal session

### Mode 2: Remote chat (Enter on remote session)

- Session lives on arch (or another machine)
- TUI opens a chat view with history loaded from relay
- You type a message → relay forwards it to the running agent on arch
- Agent's response streams back through relay → displayed in real-time
- Like the phone app but in your terminal

### Mode 3: Local resume of a remote session (R key)

Syncs the conversation from the relay and resumes it locally:

1. Pull full history from relay via `happier session history <id> --format raw --json`
2. Transform relay messages into Claude Code's JSONL format (user messages, assistant text, tool_use blocks with placeholder results)
3. Write to `~/.claude/projects/<encoded-path>/<session-uuid>.jsonl` with a `sync_metadata` line linking back to the relay origin
4. `cd` into the project directory and run `claude --resume <session-uuid>`

For this to work:

1. **Agent binary** must exist locally (`claude`, `codex`, etc.)
2. **Working directory** must exist locally (Mutagen handles this for `~/Projects/`)

If either fails, the TUI shows why: "Directory not found: /home/luis", "'codex' not installed locally".

## How conversation sync works

Claude Code stores conversations as JSONL files in `~/.claude/projects/`. Each line is a JSON object — `user` messages (text + tool results) and `assistant` messages (text + tool_use blocks), chained by `parentUuid` fields.

The relay stores conversation history in its own format (raw events over socket.io). The sync module (`sync.py`) bridges the two:

```
Relay (happier session history --format raw --json)
  │
  │  Each relay message has: role, createdAt, raw.content.data
  │
  ▼
relay_to_jsonl_lines()
  │
  │  Transforms to Claude Code format:
  │  - user text → {type: "user", message: {role: "user", content: [{type: "text", ...}]}}
  │  - assistant text → {type: "assistant", message: {role: "assistant", content: [{type: "text", ...}]}}
  │  - tool_use → assistant line + placeholder tool_result line
  │  - thinking blocks → skipped (signatures won't validate)
  │  - system/progress → skipped (not needed for resume)
  │  - UUID chain: each line gets a uuid, parentUuid points to previous
  │
  ▼
~/.claude/projects/<encoded-path>/<session-uuid>.jsonl
  │
  │  First line: sync_metadata (relay_session_id, relay_host, synced_at)
  │  claude --resume <session-uuid>  (from the correct cwd)
  │
  ▼
Claude Code picks up the conversation and continues
```

**Path normalisation** maps any `/home/<user>/X` → `~/X` on Mac, and `/Users/<user>/X` → `~/X` on Linux. No per-user config needed — but the directories must actually exist (via Mutagen or similar).

**Limitations:**
- Tool results are placeholders ("synced from relay — original output not available") since the relay doesn't store full tool output
- The synced session is a fork — new UUID, shown as a separate session. The `sync_metadata` line links it back to the relay origin for deduplication
- Only works when the project directory is available locally (via Mutagen or similar file sync)

## Cross-device session continuity

| From → To | How | Works? |
|-----------|-----|--------|
| **MacBook → Phone** | Phone app sends messages through relay stream API — no local files needed | Yes |
| **Arch → MacBook** | TUI ChatScreen reads history + sends messages through relay | Yes |
| **MacBook → Arch (local resume)** | Sync JSONL from relay + Mutagen provides the code directory | Yes (needs Mutagen) |
| **Arch → MacBook (local resume)** | Same — sync JSONL + Mutagen provides `~/Projects/` | Yes (needs Mutagen) |
| **Phone → any machine** | TUI R key syncs + resumes, or Enter for chat view | Yes (R needs Mutagen) |

## Keybindings

| Key     | Action                              |
|---------|-------------------------------------|
| Enter   | Resume local / open remote chat     |
| R       | Local resume (syncs from relay first) |
| a       | Cycle filter: recent → active → all |
| /       | Search by title or path             |
| i       | Toggle detail sidebar               |
| t       | Toggle dark/light theme             |
| r       | Refresh session list                |
| s       | Stop selected session               |
| n       | New session                         |
| q       | Quit                                |

## Install & run

```bash
cd happier-tui
uv sync
uv run happier-tui
```

Requires `happier` CLI to be installed and authenticated with a relay.
