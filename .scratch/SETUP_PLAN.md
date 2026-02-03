# Setup Plan: arch-lenovo Always-On Claude

## Final State (completed 2026-02-01)

| Component | Status |
|-----------|--------|
| Node.js | v25.4.0 (nvm) ✓ |
| Claude Code | Installed ✓ |
| yay | Fixed ✓ |
| Tailscale | Installed & authenticated (both machines) ✓ |
| Mutagen | Two-way-safe sync running ✓ |
| ~/Projects | Synced (5.0 GB, excludes AWS course) ✓ |
| ~/.claude | Configured with CLAUDE.md ✓ |
| Happy CLI | Installed, daemon running, phone connected ✓ |
| GitHub CLI | Auth copied from MacBook ✓ |
| SSH config | arch-lenovo-ts for Tailscale access ✓ |

---

## What Was Done

### MacBook Side

1. **Mutagen installed** - `brew install mutagen-io/mutagen/mutagen`
2. **Sync configured** - `~/Projects` syncs bidirectionally with arch-lenovo
   - Mode: `two-way-safe`
   - Excludes: node_modules, .venv, .pixi, __pycache__, dist, build, .next, .cache, .env, *.log, .DS_Store, courses/AWS-SAA-SAAC003-cantrill
3. **Tailscale installed** - `brew install --cask tailscale`
4. **SSH config updated** - added `arch-lenovo-ts` host for Tailscale access
5. **GitHub auth copied** - `~/.config/gh/` SCP'd to arch-lenovo

### arch-lenovo Side

1. **System config** - lid switch ignored, WiFi power save off, SSH hardened
2. **Tailscale** - installed, authenticated, connected to mesh
3. **Happy CLI** - installed, daemon as systemd user service, phone paired
4. **Claude alias** - `claude` → `happy claude --dangerously-skip-permissions`
5. **CLAUDE.md** - machine-specific context with env var guidance
6. **settings.json** - permissions for common commands
7. **GITHUB_TOKEN fix** - `unset GITHUB_TOKEN` in bashrc (use gh config files instead)

---

## Architecture

```
┌──────────────┐    Tailscale    ┌────────────────────────────┐
│   MacBook    │◄───────────────►│  arch-lenovo (Arch Linux)  │
│              │     Mutagen     │  Always-on, lid closed     │
│ ~/Projects   │◄───────────────►│  ~/Projects                │
│  (edit here) │   two-way-safe  │  Claude via Happy          │
└──────────────┘                 └────────────────────────────┘
                                           ▲
     ┌──────────────┐    Happy App         │
     │   Phone      │◄─────────────────────┘
     │  (iOS)       │  (notifications, control)
     └──────────────┘
```

---

## Daily Workflow

1. **From phone:** Open Happy app → see/control Claude sessions on arch-lenovo
2. **From MacBook:** `ssh arch-lenovo` or `ssh arch-lenovo-ts` (anywhere)
3. **File sync:** Automatic via Mutagen - edit either machine, changes sync
4. **Start Claude:** `claude` (aliased to `happy claude --dangerously-skip-permissions`)

---

## Key Commands

```bash
# Check sync status
mutagen sync list

# SSH to arch-lenovo
ssh arch-lenovo      # local network
ssh arch-lenovo-ts   # anywhere via Tailscale

# On arch-lenovo
claude               # starts happy claude session
happy daemon status  # check daemon
```

---

## Maintenance

```bash
# MacBook
mutagen daemon start           # if not running
brew upgrade mutagen

# arch-lenovo
sudo pacman -Syu
npm update -g @anthropic-ai/claude-code happy-coder
```

---

## Key Decisions Made

1. **Mutagen over Syncthing** - better for dev workflows, CLI-based
2. **Two-way-safe mode** - bidirectional sync, pauses on conflicts
3. **Happy over tmux** - phone notifications, easier session management
4. **Git is the real safety net** - commit often, Mutagen just syncs files
5. **MacBook is primary** - initial sync was one-way-safe, env vars live here
6. **claude alias** - wraps happy claude for seamless phone access
