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

## Cross-device session continuity

| From → To | How | Works? |
|-----------|-----|--------|
| **MacBook → Phone** | Phone app sends messages through relay stream API — no local files needed | Yes |
| **Arch → MacBook** | TUI ChatScreen reads history + sends messages through relay | Yes |
| **MacBook → Arch (local resume)** | Sync JSONL from relay + Mutagen provides the code directory | Partial — see limitations |
| **Arch → MacBook (local resume)** | Same — sync JSONL + Mutagen provides `~/Projects/` | Partial — see limitations |
| **Phone → any machine** | TUI R key syncs + resumes, or Enter for chat view | Partial (R — see limitations) |

## Known limitations

### Local resume creates a fork, not a transfer ([#133](https://github.com/happier-dev/happier/issues/133))

When you press R to resume a remote session locally, the TUI syncs the conversation and starts a new Claude session. This is a **fork** — the relay sees it as a separate session. The original session on the remote machine still exists.

Happier has the right primitive for this (`session.continueWithReplay`) which does a proper transfer: fetches the encrypted transcript, builds a replay prompt, and spawns a linked session. But this RPC is only accessible from the relay cloud via socket.io — not exposed on the local daemon HTTP API or CLI.

**Impact**: after local resume, you may see duplicate sessions. The TUI marks synced sessions with ⇅ and uses deterministic UUIDs to avoid accumulating forks, but it's a workaround.

**Tracking**: [happier-dev/happier#133](https://github.com/happier-dev/happier/issues/133)

### Local resume bypasses happier ([related: #131](https://github.com/happier-dev/happier/issues/131))

Synced sessions resume via `claude --resume` directly, not via `happier`. This means the resumed session loses happier features: relay sync, phone access, session management. Using `happier --resume` instead would create a duplicate relay session because happier doesn't know this JSONL is a continuation of an existing relay session.

**Tracking**: [happier-dev/happier#131](https://github.com/happier-dev/happier/issues/131)

### Can't message inactive sessions ([#134](https://github.com/happier-dev/happier/issues/134))

The stream API (`stream-start`/`stream-read`) only works when a session is actively connected to the relay via socket.io. If the agent process isn't running on the remote machine, messaging fails with "RPC method not available."

The phone app can message inactive sessions because it uses the relay's server-side pending message queue — messages are stored on the relay and delivered when the session reconnects. This queue API isn't exposed in the CLI, so the TUI can't do the same. The chat view shows history for inactive sessions but is read-only until the session reconnects.

**Tracking**: [happier-dev/happier#134](https://github.com/happier-dev/happier/issues/134)

### Tool results are placeholders

The relay doesn't store full tool output in its history. Synced JSOKNLs have placeholder tool results ("synced from relay — original output not available"). Claude can still continue the conversation but doesn't have the original tool output for context.

### Requires file sync (Mutagen or similar)

Local resume only works when the session's working directory exists on both machines. Path normalisation maps `/home/<user>/X` ↔ `/Users/<user>/X` automatically, but the files must actually be there. This assumes a setup like [Mutagen](https://mutagen.io/) syncing `~/Projects/` bidirectionally.

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
