# Happier TUI

A terminal dashboard for all your [Happier](https://github.com/gptlabs/happier) sessions across machines. The relay knows about every session on every device — the TUI is the single pane of glass.

> **Important: cross-device resume requires file sync.** Local resume of remote sessions (R key) only works if the session's working directory exists on both machines. This project assumes [Mutagen](https://mutagen.io/) (or similar) is syncing project directories between your machines. Without that, the agent binary has no code to work with and resume will fail. The relay chat view (Enter key) works without file sync since it just proxies messages.

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

This is the ambitious one. For it to work:

1. **Agent binary** must exist locally (`claude`, `codex`, etc.)
2. **Working directory** must exist locally (Mutagen handles this for `~/Projects/`)
3. **Conversation JSONL** needs to be reconstructable from relay history → written to the right path (`~/.claude/projects/<encoded-path>/<session-id>.jsonl` for Claude, equivalent for codex/opencode)

If any of these fail, the TUI tells you exactly why ("Directory not found: /home/luis", "codex not installed locally").

## Cross-device session continuity

What works today and what doesn't:

| From → To | How | Works? |
|-----------|-----|--------|
| **MacBook → Phone** | Phone app sends messages through relay stream API — no local files needed | Yes |
| **Arch → MacBook** | TUI ChatScreen reads history + sends messages through relay | Yes |
| **MacBook → Arch (local resume)** | Only if `.jsonl` is synced via Mutagen AND path exists locally | Partial (~/Projects/ only) |
| **Start on Mac, go offline, pick up on Arch** | Relay has the history but no mechanism to reconstruct `.jsonl` on arch | **Not yet** |

The missing piece is **conversation sync**: pulling history from the relay, reconstructing it as a `.jsonl` in the format the agent expects (`~/.claude/projects/<encoded-path>/<session-id>.jsonl` for Claude Code), and placing it so `happier --resume` can find it. This would enable true device-agnostic session continuity.

## Keybindings

| Key     | Action                              |
|---------|-------------------------------------|
| Enter   | Resume local / open remote chat     |
| R       | Local resume (blocked if not possible) |
| a       | Toggle active/running filter        |
| /       | Search by title or path             |
| i       | Toggle detail sidebar               |
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
