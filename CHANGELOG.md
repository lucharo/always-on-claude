# Changelog

## v3.0.0 — Conversation sync via Happier relay

**The big shift:** Conversations now sync through Happier's cloud relay (E2E encrypted, Postgres-backed, socket.io protocol) instead of being tied to JSONL files on a single machine. Each tool does one job — Mutagen handles code, the relay handles conversations.

### Changed
- Happier daemon now runs on **both** MacBook and server (previously server-only)
- `~/Projects` is the only Mutagen sync; conversations sync through the relay
- README rewritten around the relay model — setup flow, architecture diagram, "what syncs" table
- `always-on-setup` skill updated to reflect the new model (no more `claude-config` sync)
- Server setup installs Happier instead of `happy-coder`

### Removed
- `skills/conversation-transfer` — manual JSONL transfer skill, no longer needed
- `~/.claude` Mutagen sync (`claude-config`) — root cause of v2 race conditions
- `hooks/sync-session-start.sh` and `hooks/sync-session-end.sh` — pause/resume workarounds for the old sync
- "Why session sync doesn't work" README section — no longer applicable

### Fixed
- Race conditions from bidirectional sync of live JSONL files ([issue #1](../../issues/1))
- Stale Happy CLI references in example CLAUDE.md
- Plugin version drift between `plugin.json` and `.claude-plugin/plugin.json`

### Added
- macOS Tailscale troubleshooting (MagicDNS / CLI variant guidance)

## v2.0.0 — Migration to Happier

Migrated from Happy CLI (unmaintained) to [Happier](https://github.com/happier-dev/happier), a fork with multi-backend support (Claude, Gemini, OpenCode) and active development. Attempted to sync `~/.claude` via Mutagen for cross-machine session continuity — worked intermittently but caused race conditions with live JSONL writes. Documented as a known limitation.

## v1.0.0 — Initial release (Happy CLI)

Initial always-on Claude setup: Tailscale mesh network + Mutagen bidirectional `~/Projects` sync + bind mount for path compatibility + Happy CLI for phone/remote session management. Tagged as [`v1.0-happy`](../../tree/v1.0-happy).
