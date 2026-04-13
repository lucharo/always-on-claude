# Changelog

## v3.1.0 — happier-upgrade skill + self-hosted relay cleanup

### Added
- `happier-upgrade` skill — codifies the multi-machine Happier upgrade workflow (Mac prebuilt vs arch source build), including daemon restart warnings and gotchas learned the hard way (SSH flap-safe yarn builds, `HAPPIER_CHANNEL=preview` env var scoping, Node engine pins, npm uninstall silent no-op across node versions)
- Note in `happier-setup.md` documenting self-hosted relay as an available option via `hstack`

### Changed
- Server setup instructions note AVX2 requirement for the prebuilt installer and point older CPUs to `happier-setup.md` for the build-from-source path
- Bumped both `plugin.json` and `.claude-plugin/plugin.json` to 3.1.0 (were drifted at 3.0.0 and 1.1.0 respectively before v3.0.0 merge)

### Removed
- Self-hosted Happier relay on arch (`happier-daemon.arch-happier-relay-server.service` + `dev.happier.stack.repo-happier-dev-1097aa2624.service`) — this setup now uses the default hosted cloud relay only
- Stale v1 Happy daemon on arch (`happy-daemon.service` + `happy-coder` package) — leftover from the pre-v2 Happy CLI era

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
