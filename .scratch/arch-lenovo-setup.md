# arch-lenovo Setup Instructions

Execute these steps in order. Pause for user input where indicated.

---

## Completed Steps

- [x] **Phase 1:** System configuration (lid switch, WiFi, SSH)
- [x] **Phase 3:** Tailscale installed and authenticated
- [x] **Phase 4:** File sync configured (Mutagen from MacBook)

---

## Phase 1: System Configuration ✓ DONE

### 1.1 Prevent Sleep on Lid Close

```bash
sudo mkdir -p /etc/systemd/logind.conf.d

sudo tee /etc/systemd/logind.conf.d/lid.conf << 'EOF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
IdleAction=ignore
EOF

sudo systemctl restart systemd-logind
```

### 1.2 WiFi Always On

```bash
sudo tee /etc/NetworkManager/conf.d/wifi-powersave-off.conf << 'EOF'
[connection]
wifi.powersave = 2
EOF

sudo systemctl restart NetworkManager
```

### 1.3 SSH Hardening

```bash
sudo pacman -S --needed openssh
sudo systemctl enable sshd
sudo systemctl start sshd

sudo tee /etc/ssh/sshd_config.d/hardened.conf << 'EOF'
PasswordAuthentication no
PubkeyAuthentication yes
PermitRootLogin no
ClientAliveInterval 60
ClientAliveCountMax 120
AllowTcpForwarding yes
EOF

sudo systemctl restart sshd
```

---

## Phase 2: Directory Structure ✓ DONE

```bash
mkdir -p ~/Projects
```

---

## Phase 3: Tailscale ✓ DONE

```bash
sudo pacman -S tailscale
sudo systemctl enable tailscaled
sudo systemctl start tailscaled
sudo tailscale up  # User authenticated
```

---

## Phase 4: File Sync (Mutagen) ✓ DONE

**We switched from Syncthing to Mutagen** - better for dev workflows.

Mutagen is managed from MacBook. This machine is the **beta** (destination).

### Current Sync Status

- **Mode:** `one-way-safe` (initial sync in progress)
- **Source:** MacBook ~/Projects (source of truth)
- **Destination:** This machine ~/Projects
- **Ignores:** node_modules, .venv, .pixi, __pycache__, dist, build, .next, .cache, .env, *.log, .DS_Store

### After Initial Sync Completes

MacBook will switch to `two-way-safe` mode, then:
- Changes you make here sync back to MacBook
- Changes on MacBook sync here
- Conflicts pause for manual resolution

### Checking Sync Status (from MacBook)

```bash
mutagen sync list
```

### Syncthing Disabled

Syncthing was stopped and disabled on this machine. Mutagen handles sync instead.

---

## Phase 5: Happy CLI

```bash
npm install -g happy-coder
```

**Validation:**
```bash
happy --version
```

### ⏸️ PAUSE: User must authenticate Happy

```bash
happy connect claude
```

This requires browser auth.

### 5.1 Happy Daemon Systemd Service

```bash
mkdir -p ~/.config/systemd/user

cat > ~/.config/systemd/user/happy-daemon.service << 'EOF'
[Unit]
Description=Happy CLI Daemon
After=network.target

[Service]
Type=simple
ExecStart=%h/.nvm/versions/node/v25.4.0/bin/happy daemon start --foreground
Restart=on-failure
RestartSec=10
Environment=HOME=%h
Environment=PATH=%h/.nvm/versions/node/v25.4.0/bin:%h/bin:/usr/local/bin:/usr/bin:/bin

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable happy-daemon
systemctl --user start happy-daemon
```

### ⏸️ PAUSE: User must scan QR code on phone

Start a test session:
```bash
happy daemon start
```

Then scan QR code with Happy mobile app.

---

## Phase 6: ~/.claude Configuration

### 6.1 settings.json

```bash
cat > ~/.claude/settings.json << 'EOF'
{
  "permissions": {
    "allow": [
      "Bash(sudo:*)",
      "Bash(pacman:*)",
      "Bash(systemctl:*)",
      "Bash(git:*)",
      "Bash(npm:*)",
      "Bash(pixi:*)",
      "Bash(happy:*)",
      "Bash(tailscale:*)",
      "Bash(ls:*)",
      "Bash(cat:*)",
      "Bash(mkdir:*)",
      "Bash(cp:*)",
      "Bash(mv:*)",
      "Bash(chmod:*)",
      "Bash(chown:*)",
      "Bash(curl:*)",
      "Bash(wget:*)",
      "Bash(pip:*)",
      "Bash(python:*)",
      "Bash(node:*)",
      "Bash(nvm:*)"
    ],
    "deny": [
      "Bash(rm -rf /)*",
      "Bash(dd:*)",
      "Bash(mkfs:*)"
    ]
  }
}
EOF
```

### 6.2 CLAUDE.md (Machine-Specific)

```bash
cat > ~/.claude/CLAUDE.md << 'CLAUDEMD'
# Machine Context

This is a Lenovo ThinkPad running Arch Linux, configured as a persistent home
server for Claude Code. It runs 24/7 with the lid closed, connected via WiFi
and Tailscale. Access from MacBook via SSH or from phone via Happy CLI.

## System

- **OS:** Arch Linux (rolling release)
- **Package managers:** pacman, yay (AUR)
- **Node.js:** Via nvm (not system pacman - avoids ICU conflicts)
- **Sudo:** Requires password (passwordless not configured)

## Access Patterns

- From MacBook: `ssh arch-lenovo` (local) or `ssh arch-lenovo-ts` (Tailscale)
- From phone: Happy app (sessions visible automatically)
- Start session: `happy claude` in project directory
- Dev servers accessible at http://arch-lenovo:PORT via Tailscale

## File Sync (Mutagen)

~/Projects syncs bidirectionally with MacBook via **Mutagen** (not Syncthing).

- Mutagen runs on MacBook and pushes/pulls to this machine
- Mode: `two-way-safe` - changes sync both directions
- Conflicts pause for manual resolution

**Ignored (not synced, rebuild locally):**
- node_modules, .venv, .pixi, __pycache__
- dist, build, .next, .cache
- .env, .env.local, *.log, .DS_Store

**After switching to a project, always rebuild deps:**
```bash
# Check what the project uses and run appropriate command:
pixi install      # pixi.toml
uv sync           # pyproject.toml with uv
npm install       # package.json
bun install       # bun.lockb
```

## Secrets

- Environment vars: ~/.bashrc
- Encrypted: SOPS + age (~/.config/sops/age/)
- NEVER commit secrets to git

## GPU Access

This machine has no GPU. For GPU workloads, use Modal:
```bash
modal run script.py  # Provisions cloud GPU on demand
```

## System Maintenance

```bash
sudo pacman -Syu                            # Update system
npm update -g @anthropic-ai/claude-code     # Update Claude Code
npm update -g happy-coder                   # Update Happy
```

## Things to Watch Out For

- After pacman -Syu, check that node still works (ICU conflicts).
  If node breaks: `nvm reinstall 25`
- After syncing new projects, always rebuild deps locally
- WiFi can drop if laptop overheats with lid closed - check ventilation
CLAUDEMD
```

---

## Phase 7: Final Validation

Run these checks manually:

```bash
# System
grep -rq 'HandleLidSwitch=ignore' /etc/systemd/logind.conf.d/ && echo "✓ Lid switch ignored"
iwconfig 2>/dev/null | grep -q 'Power Management:off' && echo "✓ WiFi power save off"
systemctl is-active sshd && echo "✓ SSHD running"

# Tools
node --version && echo "✓ Node.js"
claude --version && echo "✓ Claude Code"
happy --version && echo "✓ Happy CLI"

# Networking
tailscale status && echo "✓ Tailscale connected"

# Config
test -f ~/.claude/CLAUDE.md && echo "✓ CLAUDE.md exists"
test -f ~/.claude/settings.json && echo "✓ settings.json exists"
test -d ~/Projects && echo "✓ ~/Projects exists"

# Happy daemon
systemctl --user is-active happy-daemon && echo "✓ Happy daemon running"
```

---

## Summary of Remaining Interactive Steps

1. **Phase 5:** `happy connect claude` → browser auth
2. **Phase 5:** Happy phone app QR scan
