---
name: always-on-setup
description: This skill should be used when the user asks to "set up an always-on Claude server", "configure a home server for Claude Code", "sync Claude sessions between machines", "access Claude from my phone", "set up Happy CLI with Tailscale", or mentions "always-on Claude setup", "remote Claude via Tailscale", "bidirectional Claude sync", or "Happy daemon configuration". Provides guidance for multi-machine Claude Code setups within a secure Tailscale network.
---

# Always-On Claude Setup

Configure a secondary machine (server) within a Tailscale network for remote Claude Code sessions, with bidirectional sync and phone access via Happy CLI.

**Important:** This setup is specifically designed for a secure Tailscale mesh network. All tools (Mutagen, SSH, Happy) operate within this private network. Do not expose these services to the public internet.

## Core Components

| Component | Purpose | Required? |
|-----------|---------|-----------|
| **Tailscale** | Secure mesh network connecting all devices | Yes |
| **Mutagen** | Bidirectional file sync (Projects + Claude config) | Yes |
| **Symlinks** | Path compatibility for Claude session portability | Yes |
| **Happy CLI** | Phone notifications + session management | Yes |

### Why Each Component Matters

**Tailscale:** Creates a secure, private network between your laptop, server, and phone. All other tools communicate through this network.

**Mutagen:** Syncs `~/Projects` and `~/.claude` bidirectionally between machines. Without this, code changes and Claude conversations stay isolated on one machine.

**Symlinks:** Claude Code stores sessions keyed by path (e.g., `-Users-luischavesrodriguez-Projects-foo`). Both machines must resolve `~/Projects` to `/Users/luischavesrodriguez/Projects` for sessions to be portable.

**Happy CLI:** Enables starting Claude sessions from your phone and receiving notifications. The Happy daemon runs on the server and connects to your phone via Tailscale.

---

## Requirements Checklist

### Core Requirements

| # | Requirement | Solution | Status |
|---|-------------|----------|--------|
| 1 | Start Claude session from phone in any project folder | Happy daemon on server (`happy claude` in project dir) | **Validated** |
| 2 | Resume conversation on laptop that was started on server | Bind mount makes paths identical (`/Users/luischavesrodriguez/...` on both machines) | **Testing** |
| 3 | Continue conversation from server that started on laptop | Same bind mount solution - paths match so session keys match | **Testing** |
| 4 | Continue conversation from phone that started on laptop | Would require: (a) starting laptop sessions with Happy, or (b) Happy feature to list/resume any conversation | **Missing feature in Happy** |

### Secondary Requirements

| # | Requirement | Solution | Status |
|---|-------------|----------|--------|
| 5 | Create git worktrees from phone | Happy does not support worktree creation | **Missing feature in Happy** |

### Notes on Happy CLI

Happy appears to be lightly maintained. Known limitations:
- Cannot list/resume arbitrary conversations (only those started via Happy)
- No worktree management
- Phone app may have sync delays

Consider contributing to Happy or building alternatives if these limitations are blocking.

---

## Critical Safety Rules

### All Operations Within Tailscale

Never expose SSH, Mutagen, or Happy to the public internet. Always access via Tailscale hostnames:

```bash
# Correct - via Tailscale
ssh arch-lenovo      # Uses Tailscale DNS
ssh arch-lenovo-ts   # Explicit Tailscale suffix

# Dangerous - never do this
# Exposing port 22 to 0.0.0.0
```

### Pause Sync Before Path Changes

NEVER move directories while Mutagen sync is running:

```bash
mutagen sync pause projects
mutagen sync pause claude-config
# Make changes
mutagen sync resume projects
mutagen sync resume claude-config
```

### Transfer Before Sync

Use SCP for initial file transfer. Only enable Mutagen AFTER both sides are stable.

---

## Quick Reference

### Check Sync Status
```bash
mutagen sync list
```

### Check Tailscale Connection
```bash
tailscale status
```

### Start Happy Session on Server
```bash
ssh arch-lenovo
cd ~/Projects/myproject
happy claude
```

### Check Disk Space
```bash
df -h
du -sh /* 2>/dev/null | sort -hr | head -10
```

---

## Path Mapping (Critical for Session Portability)

Both machines must resolve `~/Projects` to the same absolute path for Claude sessions to be portable.

**MacBook (primary):**
```
~/Projects = /Users/luischavesrodriguez/Projects  (native)
```

**Server (arch-lenovo):**
```
~/Projects → /Users/luischavesrodriguez/Projects  (symlink)
/Users/luischavesrodriguez ← bind mount from /home/luischavesrodriguez_macpath
```

**Why bind mount instead of symlink?**

A symlink gets "resolved" by programs - they see the real path (`/home/...`). A bind mount makes the directory appear as a real location - programs see `/Users/luischavesrodriguez` and don't know it's mounted from elsewhere. This is critical for Claude session portability.

This ensures Claude session keys like `-Users-luischavesrodriguez-Projects-hobby` match on both machines.

---

## Common Issues

### Disk Full on Server

Check partition layout - data may be on wrong partition:
```bash
df -h
```

On Linux, `/home` has space, root (`/`) often doesn't. See `references/partition-fix.md`.

### Sync Stuck or Erroring

Terminate and recreate:
```bash
mutagen sync terminate projects
# Then recreate with proper configuration
```

### Can't SSH to Server

1. Check Tailscale: `tailscale status`
2. Check server is on: `ping arch-lenovo`
3. Check SSH: `ssh arch-lenovo 'echo ok'`

### Sudo Not Working (Arch Linux)

Ensure `/etc/sudoers` has wheel group enabled. Log in as root (`su -`) to fix.

---

## Additional Resources

### Reference Files

- **`references/partition-fix.md`** - Moving data between partitions safely
- **`references/setup-scripts.md`** - Complete server and client setup scripts
- **`references/troubleshooting.md`** - Extended troubleshooting guide

### Project Documentation

- **`~/Projects/always-on-claude/README.md`** - Full guide with architecture, postmortem, detailed explanations

---

## Mutagen Sync Configuration

Projects sync (with recommended excludes):

```bash
mutagen sync create \
  --name=projects \
  --mode=two-way-safe \
  --ignore="node_modules" \
  --ignore=".venv" \
  --ignore="venv" \
  --ignore="__pycache__" \
  --ignore=".pixi" \
  --ignore=".cache" \
  --ignore="dist" \
  --ignore="build" \
  --ignore=".next" \
  --ignore=".DS_Store" \
  --ignore="*.log" \
  --ignore=".env" \
  ~/Projects server:/Users/luischavesrodriguez/Projects
```

Claude config sync (exclude machine-specific CLAUDE.md):

```bash
mutagen sync create \
  --name=claude-config \
  --mode=two-way-safe \
  --ignore="CLAUDE.md" \
  ~/.claude server:/home/user/.claude
```
