# Always-On Claude

Two machines (MacBook + arch-lenovo) with synchronized development environments, enabling Claude Code sessions from anywhere.

> **Note:** This setup repurposes a personal Arch Linux laptop as a home server. It's not a fresh cloud VM or purpose-built server. Your mileage may vary - this documents what worked (and what went wrong) for this specific setup.

## Our Hardware

**Server (arch-lenovo):**
- Lenovo ThinkPad (2020-era)
- Arch Linux (rolling release)
- 25 GB root partition (`/dev/sda3`)
- 192 GB home partition (`/dev/sda4`)
- Runs 24/7 with lid closed, WiFi + Tailscale

**Client (MacBook):**
- MacBook Pro (primary development machine)
- macOS
- Runs Mutagen daemon for sync

## Requirements Checklist

### Core Requirements

| # | Requirement | Solution | Status |
|---|-------------|----------|--------|
| 1 | Start Claude session from phone in any project folder | Happy daemon on server (`happy claude` in project dir) | ✅ Validated |
| 2 | Resume conversation on laptop that was started on server | Bind mount makes paths identical (`/Users/luischavesrodriguez/...` on both machines) | 🧪 Testing |
| 3 | Continue conversation from server that started on laptop | Same bind mount solution - paths match so session keys match | 🧪 Testing |
| 4 | Continue conversation from phone that started on laptop | Would require: (a) starting laptop sessions with Happy, or (b) Happy feature to list/resume any conversation | ❌ Missing feature in Happy |

### Secondary Requirements

| # | Requirement | Solution | Status |
|---|-------------|----------|--------|
| 5 | Create git worktrees from phone | Happy does not support worktree creation | ❌ Missing feature in Happy |

### Notes on Happy CLI

Happy (`happy-coder`) appears to be lightly maintained. Known limitations:
- Cannot list/resume arbitrary conversations (only those started via Happy)
- No worktree management
- Phone app may have sync delays

Consider contributing to Happy or building alternatives if these limitations become blocking.

---

## Architecture

```
MacBook (Primary)                    arch-lenovo (Always-On Server)
├── ~/Projects/ ◄────────────────────► /Users/luischavesrodriguez/Projects/
│   (native path)       Mutagen           (bind mount from /home)
│                     bidirectional
├── ~/.claude/ ◄─────────────────────► /home/luis/.claude/
│   (except CLAUDE.md)  Mutagen        (except CLAUDE.md)
│
└── Mutagen daemon                   └── SSH access via Tailscale
```

### Bind Mount Explained

```
Server Storage Layout:
┌─────────────────────────────────────────────────────────────────┐
│ /dev/sda4 (/home) - 192GB                                       │
│  └── /home/luischavesrodriguez_macpath/                         │
│       └── Projects/  ◄── actual data lives here                 │
└─────────────────────────────────────────────────────────────────┘
          │
          │ bind mount (not symlink!)
          ▼
┌─────────────────────────────────────────────────────────────────┐
│ /dev/sda3 (/) - 25GB                                            │
│  └── /Users/luischavesrodriguez/  ◄── appears as real directory │
│       └── Projects/                                             │
└─────────────────────────────────────────────────────────────────┘

Why bind mount?
- Symlink: Programs see "/home/..." (resolved path) ❌
- Bind mount: Programs see "/Users/..." (mount path) ✅

Key point: Bind mount ≠ copy. It's like having two doors to the same room.
```

### Session Portability Flow

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     SESSION PORTABILITY                                   │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ✅ WORKS: Start on Server (Happy) → Continue on MacBook (Claude)        │
│  ┌─────────┐                              ┌─────────┐                    │
│  │  Phone  │ ──Happy──► Server creates    │ MacBook │                    │
│  │         │           session at         │         │                    │
│  └─────────┘           /Users/.../foo     └─────────┘                    │
│                              │                  │                        │
│                              │   Mutagen sync   │                        │
│                              └────────►─────────┘                        │
│                                             │                            │
│                              Session key: -Users-luischavesrodriguez-... │
│                              Same on both machines ✓                     │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ✅ WORKS: Start on MacBook (Claude) → Continue on Server (SSH)          │
│  ┌─────────┐         Mutagen sync         ┌─────────┐                    │
│  │ MacBook │ ─────────────►───────────────│ Server  │                    │
│  │         │  session + files sync        │         │                    │
│  └─────────┘                              └─────────┘                    │
│       │                                        │                         │
│       └── /Users/.../foo ══════════════════════┘                         │
│           Same path, same session key ✓                                  │
│                                                                          │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ❌ NOT SUPPORTED: Start on MacBook → Continue on Phone (Happy)          │
│  ┌─────────┐                              ┌─────────┐                    │
│  │ MacBook │                              │  Phone  │                    │
│  │         │                              │         │                    │
│  └─────────┘                              └─────────┘                    │
│       │                                        │                         │
│       └── Session created                      └── Happy can only see    │
│           locally                                  sessions it started   │
│                                                                          │
│  Happy limitation: Cannot list/resume arbitrary Claude sessions          │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### Important: Use Correct Path in Happy

When starting a session from Happy, **always use the full path**:

```
/Users/luischavesrodriguez/Projects/yourproject
```

Do NOT use:
- `~/Projects/...` (expands to /home/luis/...)
- `/home/luischavesrodriguez_macpath/...` (won't match MacBook)

## What Gets Synced

| Path | Synced? | Notes |
|------|---------|-------|
| ~/Projects | YES | Bidirectional, excludes build artifacts |
| ~/.claude | YES | Conversations, settings, plugins, skills |
| ~/.claude/CLAUDE.md | NO | Machine-specific instructions |

### Excluded from sync (rebuild locally)
- `node_modules/`, `.venv/`, `venv/`, `__pycache__/`
- `.pixi/`, `.cache/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`
- `target/`, `dist/`, `build/`, `.next/`
- `.DS_Store`, `*.log`, `.env`, `.env.local`
- `courses/AWS-SAA-SAAC003-cantrill/` (large course content)

## Path Mapping

Both machines must resolve `~/Projects` to `/Users/luischavesrodriguez/Projects` for Claude session compatibility:

- **MacBook**: Native path (already `/Users/luischavesrodriguez/Projects`)
- **arch-lenovo**: Symlink `~/Projects -> /Users/luischavesrodriguez/Projects`

This ensures Claude session keys match across machines.

## Infrastructure

| Component | Purpose |
|-----------|---------|
| Tailscale | Secure mesh network (access from anywhere) |
| Happy CLI | Phone notifications + session management |
| Mutagen | Bidirectional file sync |
| SSH | Remote access to arch-lenovo |

## Access Patterns

```bash
# From MacBook (local network)
ssh arch-lenovo

# From MacBook (via Tailscale, from anywhere)
ssh arch-lenovo-ts

# From phone
# Use Happy app - sessions visible automatically

# Start a new session on arch-lenovo
ssh arch-lenovo 'cd ~/Projects/myproject && happy claude'
```

## Mutagen Sync Commands

```bash
# Check sync status
mutagen sync list

# Pause sync (REQUIRED before path changes)
mutagen sync pause projects
mutagen sync pause claude-config

# Resume sync
mutagen sync resume projects
mutagen sync resume claude-config

# Terminate and recreate (if broken)
mutagen sync terminate projects
# Then recreate with proper excludes
```

## File Sync Safety Rules

**CRITICAL: These rules prevent data loss and sync corruption**

### NEVER do while sync is running:
- Move or rename synced directories (`mv ~/Projects` anywhere)
- Create symlinks in place of synced directories
- Run scripts that bulk-move files in synced locations
- Change the path structure of synced roots

### ALWAYS do before ANY path changes:
1. PAUSE the sync first: `mutagen sync pause <name>`
2. Verify it's paused: `mutagen sync list`
3. Make your changes
4. CAREFULLY resume: `mutagen sync resume <name>`
5. Monitor for conflicts: `mutagen sync list`

### If something goes wrong:
- Files are rarely deleted by sync tools in "safe" modes
- Check both endpoints - data is usually still there
- Don't panic, don't run more commands - stop and assess

## Initial Setup (for reference)

### 1. Create directory structure on arch-lenovo
```bash
sudo mkdir -p /Users/luischavesrodriguez/Projects
sudo chown luis:wheel /Users/luischavesrodriguez/Projects
ln -s /Users/luischavesrodriguez/Projects ~/Projects
```

### 2. Initial file transfer (before enabling sync)
```bash
# From MacBook - copy files to arch-lenovo
scp -r ~/Projects/* arch-lenovo:/Users/luischavesrodriguez/Projects/
```

### 3. Enable Mutagen sync
```bash
# Projects sync
mutagen sync create \
  --name=projects \
  --mode=two-way-safe \
  --ignore="node_modules" \
  --ignore=".venv" \
  --ignore="venv" \
  --ignore="__pycache__" \
  --ignore=".pixi" \
  --ignore=".cache" \
  --ignore=".pytest_cache" \
  --ignore=".mypy_cache" \
  --ignore=".ruff_cache" \
  --ignore="target" \
  --ignore="dist" \
  --ignore="build" \
  --ignore=".next" \
  --ignore=".DS_Store" \
  --ignore="*.log" \
  --ignore=".env" \
  --ignore=".env.local" \
  --ignore="courses/AWS-SAA-SAAC003-cantrill" \
  ~/Projects arch-lenovo:/Users/luischavesrodriguez/Projects

# Claude config sync
mutagen sync create \
  --name=claude-config \
  --mode=two-way-safe \
  --ignore="CLAUDE.md" \
  ~/.claude arch-lenovo:/home/luis/.claude
```

## Troubleshooting

### Sync stuck in error loop
```bash
mutagen sync terminate projects
# Wait, then recreate
```

### Conflicts
```bash
mutagen sync list  # Shows conflict count
# Manually resolve by choosing which version to keep
```

### Lost connection
- Check Tailscale: `tailscale status`
- Check arch-lenovo is awake: `ping arch-lenovo`
- SSH directly: `ssh arch-lenovo-ts`

### Missing dependencies after sync
Dependencies (node_modules, .venv, etc.) don't sync. Rebuild locally:
```bash
npm install     # or bun install
uv sync         # or pip install -r requirements.txt
pixi install    # for pixi projects
```

---

## Understanding Linux Partitions

If you're repurposing a personal Linux machine, you need to understand its partition layout.

### Root Partition (`/`)

The root partition contains:
- `/usr` - System programs and libraries
- `/var` - Variable data (logs, package cache)
- `/opt` - Optional/third-party software
- `/etc` - System configuration
- Any directory NOT on a separate partition

This is protected space for the system. On our machine: **25 GB** (small!)

### Home Partition (`/home`)

The home partition contains:
- `/home/username/` - User files, downloads, documents

Typically much larger. On our machine: **192 GB**

### The Problem We Hit

We created `/Users/luischavesrodriguez/Projects` for macOS path compatibility. But `/Users` landed on the **root partition** (25 GB), not `/home` (192 GB).

**Solution:** Move data to `/home` and use a **bind mount** (not symlink):
```bash
mv /Users/luischavesrodriguez /home/luischavesrodriguez_macpath
mkdir /Users/luischavesrodriguez
mount --bind /home/luischavesrodriguez_macpath /Users/luischavesrodriguez
# Make permanent:
echo '/home/luischavesrodriguez_macpath /Users/luischavesrodriguez none bind 0 0' >> /etc/fstab
```

**Why bind mount instead of symlink?** Symlinks get "resolved" by programs - Claude would see `/home/...` instead of `/Users/...`, breaking session portability. Bind mounts make the directory appear as a real location.

### Check Your Partitions

```bash
# See partition layout
df -h

# See what's eating space
du -sh /* 2>/dev/null | sort -hr | head -10
```

---

## Postmortem: What Went Wrong

This setup had several issues. Documenting them so you don't repeat our mistakes.

### Issue 1: Running Scripts While Sync Was Active

**What happened:** Ran a shell script that moved `~/Projects` to a different location while Mutagen was actively syncing.

**Result:** Mutagen lost track of the sync root, started erroring. The Claude Code session's working directory vanished mid-session, breaking the shell.

**Lesson:** ALWAYS pause sync before ANY path changes.

### Issue 2: Partition Confusion

**What happened:** Created `/Users/luischavesrodriguez/Projects` assuming it would have plenty of space. Didn't realize `/Users` was on the tiny 25 GB root partition, not the 192 GB `/home` partition.

**Result:** Root partition filled to 100%, couldn't install packages, sync struggled.

**Lesson:** Check `df -h` before deciding where to put large directories. On Linux, only `/home` typically has lots of space.

### Issue 3: Sudo Not Working

**What happened:** User was in the `wheel` group but couldn't run `sudo`. Password kept being rejected.

**Root cause:** Two possibilities:
1. The `%wheel` line in `/etc/sudoers` was commented out (Arch default)
2. User password vs root password confusion

**Solution:** Log in as root (`su -`) and ensure `/etc/sudoers` has:
```
%wheel ALL=(ALL:ALL) ALL
```

**Lesson:** On a fresh Arch install, sudo isn't enabled by default. Fix it early.

### Issue 4: Accumulated Cruft from Personal Use

**What happened:** This was a personal laptop before becoming a server. It had:
- 12 GB movie torrent in Downloads
- 3.5 GB pacman cache (never cleaned)
- Discord, Zoom, Brave, Bisq, Tor browser installed
- Old WiFi capture files, password wordlists

**Result:** Disk filled up faster than expected.

**Lesson:** Clean up personal files before repurposing as a server:
```bash
# Clean pacman cache (keep only 1 version)
sudo paccache -rk1

# Remove unused packages
sudo pacman -Rns discord zoom bisq brave-bin tor-browser

# Check for large files
find ~ -type f -size +100M -exec ls -lh {} \;
```

### Issue 5: Kernel Updates Require Restart

**What happened:** After `pacman -Syu`, some things broke until reboot.

**Lesson:** On Arch, kernel updates are live but modules may not load until restart. After major updates:
```bash
sudo reboot
```

---

## What Could Go Wrong (Checklist)

Before and during setup, watch for these:

### Before Starting
- [ ] Check partition layout (`df -h`) - know where space is
- [ ] Know your root password (different from user password!)
- [ ] Verify sudo works (`sudo whoami`)
- [ ] Clean up personal files if repurposing a personal machine
- [ ] Update system and reboot (`sudo pacman -Syu && sudo reboot`)

### During Sync Setup
- [ ] Pause sync before ANY path changes
- [ ] Use SCP for initial transfer (no sync running = no conflicts)
- [ ] Only enable Mutagen AFTER both sides are stable
- [ ] Check for conflicts after sync: `mutagen sync list`

### Ongoing
- [ ] Monitor disk space: `df -h`
- [ ] Rebuild dependencies after syncing new projects
- [ ] Keep pacman cache clean: `sudo paccache -rk1` monthly

---

## Step-by-Step Setup Scripts

### On the Server (arch-lenovo)

```bash
#!/bin/bash
# server-setup.sh - Run this on the always-on machine

set -e

echo "=== 1. System Update ==="
sudo pacman -Syu

echo "=== 2. Install Required Packages ==="
sudo pacman -S --needed tailscale openssh

echo "=== 3. Enable Services ==="
sudo systemctl enable --now sshd
sudo systemctl enable --now tailscaled

echo "=== 4. Connect to Tailscale ==="
sudo tailscale up

echo "=== 5. Create Directory Structure ==="
# Create /Users path for macOS compatibility, but on /home partition
sudo mkdir -p /home/luischavesrodriguez_macpath/Projects
sudo chown $USER:wheel /home/luischavesrodriguez_macpath
sudo mkdir -p /Users/luischavesrodriguez

# Use bind mount (NOT symlink) - critical for session portability
sudo mount --bind /home/luischavesrodriguez_macpath /Users/luischavesrodriguez
echo '/home/luischavesrodriguez_macpath /Users/luischavesrodriguez none bind 0 0' | sudo tee -a /etc/fstab

# Note: Do NOT create ~/Projects symlink - use /Users/luischavesrodriguez/Projects directly
# to ensure correct session paths for Claude

echo "=== 6. Install Claude Code ==="
# Requires Node.js via nvm (not system node - avoids ICU conflicts)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
source ~/.bashrc
nvm install 22
npm install -g @anthropic-ai/claude-code

echo "=== 7. Install Happy CLI ==="
npm install -g happy-coder

echo "=== Done! ==="
echo "Now run the MacBook setup and start the Mutagen sync."
```

### On the Client (MacBook)

```bash
#!/bin/bash
# client-setup.sh - Run this on your MacBook

set -e

echo "=== 1. Install Mutagen ==="
brew install mutagen-io/mutagen/mutagen

echo "=== 2. Start Mutagen Daemon ==="
mutagen daemon start

echo "=== 3. Add SSH Config ==="
cat >> ~/.ssh/config << 'EOF'

Host arch-lenovo
    HostName arch-lenovo
    User luis

Host arch-lenovo-ts
    HostName arch-lenovo
    User luis
    # Uses Tailscale DNS
EOF

echo "=== 4. Test SSH Connection ==="
ssh arch-lenovo 'echo "Connected to $(hostname)"'

echo "=== 5. Initial File Transfer (SCP) ==="
echo "Copying ~/Projects to server..."
scp -r ~/Projects/* arch-lenovo:/Users/luischavesrodriguez/Projects/

echo "=== 6. Create Mutagen Syncs ==="
# Projects sync
mutagen sync create \
  --name=projects \
  --mode=two-way-safe \
  --ignore="node_modules" \
  --ignore=".venv" \
  --ignore="venv" \
  --ignore="__pycache__" \
  --ignore=".pixi" \
  --ignore=".cache" \
  --ignore=".pytest_cache" \
  --ignore=".mypy_cache" \
  --ignore=".ruff_cache" \
  --ignore="target" \
  --ignore="dist" \
  --ignore="build" \
  --ignore=".next" \
  --ignore=".DS_Store" \
  --ignore="*.log" \
  --ignore=".env" \
  --ignore=".env.local" \
  ~/Projects arch-lenovo:/Users/luischavesrodriguez/Projects

# Claude config sync
mutagen sync create \
  --name=claude-config \
  --mode=two-way-safe \
  --ignore="CLAUDE.md" \
  ~/.claude arch-lenovo:/home/luis/.claude

echo "=== 7. Verify Sync ==="
mutagen sync list

echo "=== Done! ==="
echo "Syncs are running. Check status with: mutagen sync list"
```

---

## Happy CLI Integration

[Happy](https://github.com/lucharo/happy) enables phone notifications and session management.

### On the Server
```bash
# Start Happy daemon
happy daemon start

# Start a Claude session (notifies your phone)
cd ~/Projects/myproject
happy claude
```

### On Your Phone
- Install Happy app
- Sessions appear automatically when daemon is running
- Get notifications when Claude needs input or finishes

---

## Alternative: Cloud VM

If repurposing a personal laptop sounds like too much trouble, consider:

- **DigitalOcean Droplet** - $6/mo for basic, $12/mo for 2GB RAM
- **Hetzner Cloud** - Even cheaper in EU
- **Oracle Cloud Free Tier** - Free ARM instance

Pros: Fresh system, no partition surprises, no personal cruft
Cons: Monthly cost, data egress costs, latency

This guide focuses on the "repurposed laptop" approach because:
1. No ongoing cost
2. Your data stays local
3. The hardware was already sitting there
