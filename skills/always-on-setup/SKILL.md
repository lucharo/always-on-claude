---
name: always-on-setup
description: This skill should be used when the user asks to "set up an always-on Claude server", "configure a home server for Claude Code", "access Claude sessions from any device via Happier relay", "access Claude from my phone", "set up Happier CLI with Tailscale", or mentions "always-on Claude setup", "remote Claude via Tailscale", "bidirectional Claude sync", or "Happier daemon configuration". Provides guidance for multi-machine Claude Code setups within a secure Tailscale network.
---

# Always-On Claude Setup

Configure a secondary machine (server) within a Tailscale network for remote Claude Code sessions, with bidirectional sync and phone access via Happier CLI.

**Adapt to your setup:** This guide documents a specific configuration (MacBook + old ThinkPad running Arch Linux). The concepts apply to any server — a DigitalOcean Droplet, Hetzner VM, Mac Mini, Raspberry Pi, etc. Paths, package managers, usernames, and partition layouts will differ. For example, our bind mount maps `/Users/luischavesrodriguez/Projects` because that's the macOS path — yours will be different. Use this as a reference, not a copy-paste script.

**Important:** This setup is specifically designed for a secure Tailscale mesh network. All tools (Mutagen, SSH, Happier) operate within this private network. Do not expose these services to the public internet.

## Core Components

| Component | Purpose | Required? |
|-----------|---------|-----------|
| **Tailscale** | Secure mesh network connecting all devices | Yes |
| **Mutagen** | Bidirectional file sync (code only) | Yes |
| **Symlinks** | Path compatibility for Claude session portability | Yes |
| **Happier CLI** | Phone/mobile session management, multi-backend support | Yes |

### Why Each Component Matters

**Tailscale:** Creates a secure, private network between your laptop, server, and phone. All other tools communicate through this network.

**Mutagen:** Syncs `~/Projects` bidirectionally between machines. Conversations sync separately through Happier's relay server.

**Symlinks:** Claude Code stores sessions keyed by path (e.g., `-Users-luischavesrodriguez-Projects-foo`). Both machines must resolve `~/Projects` to `/Users/luischavesrodriguez/Projects` for sessions to be portable.

**Happier CLI:** Open-source companion for AI coding agents. Runs sessions on the server, accessible from phone/web/desktop. Supports Claude, Gemini, OpenCode and more. The Happier daemon keeps sessions alive in the background. See `happier-setup.md` for install details.

---

## Requirements Checklist

### Core Requirements

| # | Requirement | Solution | Status |
|---|-------------|----------|--------|
| 1 | Start Claude session from phone in any project folder | Happier daemon on server (`happier` in project dir) | **Working** |
| 2 | Resume conversation on laptop that was started on server | Happier relay syncs sessions across devices (bind mount ensures path compatibility) | **Working** |
| 3 | Continue conversation from server that started on laptop | Happier relay syncs sessions across devices (bind mount ensures path compatibility) | **Working** |
| 4 | Continue conversation from phone that started on laptop | Happier relay — all sessions accessible from any authenticated device | **Working** |

### Notes on Happier CLI

Happier is an actively maintained open-source fork of Happy with significant improvements:
- Multi-backend support (Claude, Gemini, OpenCode, Codex, and more)
- Session resume from any device
- Cloud or self-hosted relay options
- See `happier-setup.md` for install details and known issues

---

## Critical Safety Rules

### All Operations Within Tailscale

Never expose SSH, Mutagen, or Happier to the public internet. Always access via Tailscale hostnames:

```bash
# Correct - via Tailscale
ssh arch-lenovo      # Uses Tailscale DNS
ssh arch-lenovo-ts   # Explicit Tailscale suffix

# Dangerous - never do this
# Exposing port 22 to 0.0.0.0
```

### Mutagen Sync is Opt-In

Bidirectional file syncing carries real risk of data loss on your primary machine. Conflicts, race conditions, or interrupted transfers can delete or overwrite files on either side. `two-way-safe` mode helps but isn't bulletproof. If you're not comfortable with this, use `git push`/`pull` or manual `scp` instead. Always keep backups.

### Pause Sync Before Path Changes

NEVER move directories while Mutagen sync is running:

```bash
mutagen sync pause projects
# Make changes
mutagen sync resume projects
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

### Start Happier Session on Server
```bash
ssh arch
cd ~/Projects/myproject
happier                # Claude (default)
happier gemini         # Gemini
happier opencode       # OpenCode
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

### MagicDNS Broken on macOS

If `tailscale ping arch` works but `curl http://arch:3001/` fails with `Could not resolve host`, the Tailscale network is up and the problem is local macOS DNS integration.

For macOS laptops, prefer the standalone Tailscale app when you want reliable MagicDNS and hostname-based access. It still provides a usable `tailscale` CLI on the machine.

Keep the open-source `tailscale + tailscaled` variant only if that Mac must act as a **Tailscale SSH server**. After switching variants, sign in again and remove the stale old device entry once the new node is online.

### Tailscale File Sharing

Send files to any device on your tailnet (including phones with Tailscale installed):

```bash
# Allow tailscale commands without sudo (run once):
sudo tailscale set --operator=$USER

# Send files
tailscale file cp myfile.md device-name:
```

### SSH from Phone

Use [Termius](https://termius.com/) or any SSH client on your phone, connecting over the Tailscale network. Useful for running `sudo` commands that Claude can't do (e.g., installing packages).

### Passwordless Sudo (Optional)

To let Claude (or scripts) run `sudo` without a password prompt:

```bash
echo "$USER ALL=(ALL:ALL) NOPASSWD: ALL" | sudo tee /etc/sudoers.d/$USER
```

Convenient but less secure — any process running as your user gets root. Acceptable on a home server behind Tailscale, but understand the trade-off.

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
  --ignore=".env.local" \
  ~/Projects server:/Users/luischavesrodriguez/Projects
```
