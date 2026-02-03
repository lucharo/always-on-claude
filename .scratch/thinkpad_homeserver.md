# ThinkPad Arch Linux Home Server: Claude Code Always-On Setup

A guide for setting up a Lenovo ThinkPad running Arch Linux as a persistent Claude Code home server. Run directly on the ThinkPad. Access from MacBook via SSH or phone via Happy CLI.

---

## Architecture

```
┌──────────────┐    Tailscale/SSH    ┌────────────────────────────┐
│   MacBook    │◄───────────────────►│  ThinkPad (Arch)           │
│              │     Syncthing       │  Always-on, lid closed     │
│ ~/Projects   │◄───────────────────►│  ~/Projects                │
│  (work here  │                     │  Claude Code via Happy     │
│   or SSH in) │                     │  happy daemon always on    │
└──────────────┘                     └────────────────────────────┘
                                               ▲
     ┌──────────────┐    Happy App             │
     │   Phone      │◄────────────────────────┘
     │  (iOS/Web)   │  (encrypted, push notifs)
     └──────────────┘
```

**Why this setup:**
- ThinkPad is always on - Claude Code sessions never die
- Happy CLI wraps Claude Code and handles session persistence (no tmux needed)
- Phone gets push notifications when Claude needs permission or finishes
- MacBook can disconnect anytime, pick up from phone or vice versa
- Syncthing keeps ~/Projects identical across machines

**Where to run this guide:** Directly on the ThinkPad, at the keyboard. Once Claude Code is installed, you can use it to execute the remaining steps.

---

## Phase 0: Refresh Arch & Bootstrap Claude Code

### 0.1 System Update

Your ThinkPad hasn't been used in a while. Expect keyring issues.

```bash
# If you get signature errors, fix keyring first
sudo pacman -Sy archlinux-keyring
sudo pacman -Syu
```

**Validation:**
```bash
pacman -Qu | wc -l
# Expected: 0 (fully up to date)
# If kernel was upgraded: sudo reboot
```

### 0.2 Install Essential Packages

```bash
sudo pacman -S --needed \
    base-devel git openssh tmux htop btop jq ripgrep fd \
    unzip wget curl mosh networkmanager
```

### 0.3 Install Node.js via nvm

Don't use pacman's nodejs - it conflicts with ICU versions used by other packages (mpd, ncmpcpp, etc.). nvm bundles its own ICU.

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
source ~/.bashrc
nvm install 20
nvm use 20
nvm alias default 20
```

**Validation:**
```bash
node --version   # Expected: v20.x
npm --version    # Expected: 10.x+
```

### 0.4 Install Claude Code

```bash
npm install -g @anthropic-ai/claude-code
```

**Validation:**
```bash
claude --version
```

**Set API key:**
```bash
echo 'export ANTHROPIC_API_KEY="sk-ant-your-key-here"' >> ~/.bashrc
source ~/.bashrc
```

### 0.5 Install yay (AUR Helper)

```bash
command -v yay || {
    cd /tmp
    git clone https://aur.archlinux.org/yay-bin.git
    cd yay-bin
    makepkg -si
}
```

### 0.6 Install Happy CLI

```bash
npm install -g happy-coder
```

**Validation:**
```bash
happy --version
```

---

## Phase 1: Sudo for Claude Code

Claude Code blocks `sudo` by default and won't run with `--dangerously-skip-permissions` as root. There are two workarounds.

### Option A: Passwordless sudo + allow in permissions (recommended)

Configure your user for passwordless sudo, then tell Claude Code it's allowed:

```bash
# Add passwordless sudo for your user
# IMPORTANT: Use visudo, never edit sudoers directly
sudo EDITOR=nano visudo -f /etc/sudoers.d/claude-code
```

Add this line (replace `luis` with your username):
```
luis ALL=(ALL) NOPASSWD: ALL
```

Then allow sudo in Claude Code's permissions:
```bash
mkdir -p ~/.claude

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
      "Bash(syncthing:*)",
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

**Validation:**
```bash
# Test passwordless sudo
sudo whoami
# Expected: root (no password prompt)

# Test Claude Code can use sudo
claude -p "run 'sudo whoami' and tell me the output"
# Expected: Should execute without permission prompt
```

### Option B: IS_SANDBOX=1 (quick and dirty, for initial setup only)

For the initial system setup phase, you can bypass all restrictions:

```bash
IS_SANDBOX=1 claude --dangerously-skip-permissions
```

This tells Claude Code it's in a sandboxed environment. Use this to get the system configured, then switch to Option A for daily use.

---

## Phase 2: Always-On Configuration

**You can now use Claude Code itself to execute these steps.** Start a session:

```bash
claude
```

Then ask it to follow this guide from here.

### 2.1 Prevent Sleep on Lid Close

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

**Validation:**
```bash
# Close the lid, wait 30 seconds, check the machine is still responsive
# (If running Claude Code, it should still be responding)
```

### 2.2 WiFi Always On

```bash
# Disable WiFi power saving (causes disconnects)
sudo tee /etc/NetworkManager/conf.d/wifi-powersave-off.conf << 'EOF'
[connection]
wifi.powersave = 2
EOF

sudo systemctl restart NetworkManager
```

**Validation:**
```bash
iwconfig 2>/dev/null | grep "Power Management"
# Expected: Power Management:off
```

### 2.3 Auto-Connect WiFi on Boot

```bash
sudo systemctl enable NetworkManager

# Make your WiFi auto-connect
nmcli connection show  # find your connection name
nmcli connection modify "YOUR_WIFI_NAME" connection.autoconnect yes
```

### 2.4 Static IP (Optional but Recommended)

```bash
nmcli connection modify "YOUR_WIFI_NAME" \
    ipv4.method manual \
    ipv4.addresses 192.168.1.100/24 \
    ipv4.gateway 192.168.1.1 \
    ipv4.dns "1.1.1.1,8.8.8.8"

nmcli connection down "YOUR_WIFI_NAME"
nmcli connection up "YOUR_WIFI_NAME"
```

---

## Phase 3: SSH Setup

```bash
sudo pacman -S --needed openssh

sudo systemctl enable sshd
sudo systemctl start sshd

# Harden SSH
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

**On MacBook** - add your key and SSH config:
```bash
ssh-copy-id luis@192.168.1.100

cat >> ~/.ssh/config << 'EOF'

Host thinkpad
    HostName 192.168.1.100
    User luis
    ServerAliveInterval 60
    ServerAliveCountMax 120
    ForwardAgent yes
EOF
```

**Validation (from MacBook):**
```bash
ssh thinkpad "echo 'working'"
```

---

## Phase 4: Tailscale

### On ThinkPad

```bash
sudo pacman -S tailscale
sudo systemctl enable tailscaled
sudo systemctl start tailscaled
sudo tailscale up
# Authenticate via the URL it prints
```

**Validation:**
```bash
tailscale ip -4
# Expected: 100.x.x.x
```

### On MacBook

```bash
brew install tailscale
# Or download from https://tailscale.com/download/mac
# Sign in with same account
```

### On Phone

Install Tailscale from App Store, sign in with same account.

**Validation (from MacBook):**
```bash
tailscale ping thinkpad
# Expected: pong

# Update SSH config with Tailscale hostname
cat >> ~/.ssh/config << 'EOF'

Host thinkpad-ts
    HostName thinkpad
    User luis
    ServerAliveInterval 60
    ServerAliveCountMax 120
    ForwardAgent yes
EOF
```

Now `ssh thinkpad-ts` works from anywhere, not just home WiFi.

---

## Phase 5: Syncthing (~/Projects Sync)

### 5.1 Safety First: Receive Only

**Your MacBook's files are precious. We start with the ThinkPad as "Receive Only"** so it can only pull files from your MacBook, never push deletions back. Switch to Send & Receive only after you've verified everything works.

### 5.2 Install

**On ThinkPad:**
```bash
sudo pacman -S syncthing
systemctl --user enable syncthing
systemctl --user start syncthing

# Ensure user services run without login session
sudo loginctl enable-linger $USER
```

**On MacBook:**
```bash
brew install syncthing
brew services start syncthing
```

### 5.3 Create .stignore

**On both machines** (place in `~/Projects/.stignore`):

```bash
cat > ~/Projects/.stignore << 'STIGNORE'
// === Platform-specific environments (rebuild locally) ===
node_modules
.venv
venv
__pycache__
*.pyc
.pixi
.tox
.eggs
*.egg-info
.cargo
target
.bun

// === Build artifacts ===
dist
build
.next
.nuxt
*.o
*.so
*.dylib

// === Large/generated data ===
*.parquet
*.arrow
*.h5
*.hdf5
*.pkl
*.pickle
data/raw
datasets/
checkpoints/
wandb/
mlruns/

// === IDE/editor local state ===
.idea
*.swp
*.swo
.vscode/settings.json
.vscode/*.log

// === OS junk ===
.DS_Store
Thumbs.db
._*

// === Logs ===
*.log
logs/
.npm/_logs

// === Sensitive (handle separately) ===
.env
.env.local
.env.*.local
secrets.yaml
*.pem
*.key

// === Temporary ===
tmp/
temp/
.cache
.pytest_cache
.mypy_cache
.ruff_cache
STIGNORE
```

Key point: `.pixi`, `.venv`, `node_modules` are all ignored. They're platform-specific and get rebuilt locally with `pixi install`, `uv sync`, `npm install`, etc.

### 5.4 Pair Devices

1. Open MacBook Syncthing: `http://localhost:8384`
2. Open ThinkPad Syncthing: `http://thinkpad:8384` (via Tailscale) or `http://192.168.1.100:8384`
3. Exchange device IDs, add each other
4. Share `~/Projects` folder
5. **On ThinkPad: Set folder type to "Receive Only"**
6. Optionally share `~/.claude` for Claude config sync

### 5.5 Validation

```bash
# On MacBook
echo "sync-test-$(date +%s)" > ~/Projects/sync-test.txt

# Wait a few seconds, then on ThinkPad
cat ~/Projects/sync-test.txt
# Expected: Same content

# Clean up
rm ~/Projects/sync-test.txt
```

### 5.6 Switch to Send & Receive (Once Confident)

After a few days of verified syncing with no issues:
1. Open ThinkPad Syncthing UI
2. Edit the Projects folder
3. Change type from "Receive Only" to "Send & Receive"

Now changes flow both ways.

### 5.7 Post-Sync: Rebuild Environments

After syncing a project to a new machine, rebuild platform-specific dependencies:

```bash
#!/bin/bash
# ~/bin/sync-setup - run after switching machines
cd "${1:-.}"
echo "Setting up deps for $(basename $(pwd))..."

[[ -f pixi.toml ]]        && pixi install
[[ -f pyproject.toml ]]    && command -v uv &>/dev/null && uv sync
[[ -f requirements.txt ]]  && python -m venv .venv && .venv/bin/pip install -r requirements.txt
[[ -f package.json ]]      && npm install
[[ -f bun.lockb ]]         && bun install

echo "Done."
```

---

## Phase 6: Happy CLI (Phone Access & Session Management)

Happy replaces both tmux and Blink. It wraps Claude Code, handles session persistence, and gives you a phone interface with push notifications.

### 6.1 Setup on ThinkPad

```bash
# Already installed in Phase 0
happy --version

# Connect to your Anthropic account
happy connect claude

# Start the daemon (runs in background, survives disconnects)
happy daemon start
```

### 6.2 Start a Session

```bash
# Start Claude Code through Happy in a project
cd ~/Projects/hobby/my-agent
happy claude
```

This starts Claude Code wrapped by Happy. You can now:
- See this session from the Happy mobile app
- Get push notifications when Claude needs permission
- Switch between phone and ThinkPad keyboard seamlessly

### 6.3 Session Management

```bash
# List active sessions
happy daemon list

# Check daemon status
happy daemon status

# Stop daemon (sessions stay alive)
happy daemon stop

# Clean up all processes
happy doctor clean
```

### 6.4 Quick Start Script

```bash
cat > ~/bin/cc << 'SCRIPT'
#!/bin/bash
# Quick start: cc my-project
# Finds project in ~/Projects/*, cd's into it, starts Happy+Claude
PROJECT_NAME="${1:?Usage: cc <project-name>}"

PROJECT_PATH=$(find ~/Projects -maxdepth 2 -mindepth 2 -type d -name "$PROJECT_NAME" 2>/dev/null | head -1)

if [[ -z "$PROJECT_PATH" ]]; then
    echo "Project not found: $PROJECT_NAME"
    echo ""
    echo "Available projects:"
    find ~/Projects -maxdepth 2 -mindepth 2 -type d -printf "  %f\n" | sort
    exit 1
fi

echo "Starting Claude Code in: $PROJECT_PATH"
cd "$PROJECT_PATH" && happy claude
SCRIPT

chmod +x ~/bin/cc
```

**From any SSH session or the ThinkPad directly:**
```bash
cc my-agent       # Starts Happy+Claude in ~/Projects/*/my-agent
```

**From MacBook via SSH:**
```bash
ssh thinkpad "cd ~/Projects/hobby/my-agent && happy claude"
```

### 6.5 Phone Setup

1. Install Happy app from App Store (or use web UI at happy.engineering)
2. Scan QR code shown by `happy claude` on first run
3. Sessions appear automatically with full interactivity

---

## Phase 7: Project Conventions

### Don't Be Rigid About Tooling

Projects use whatever dependency manager they already use. The only rule: **platform-specific directories don't sync and get rebuilt locally.**

| If project has... | Rebuild with... |
|---|---|
| `pixi.toml` | `pixi install` |
| `pyproject.toml` + uv | `uv sync` |
| `requirements.txt` | `pip install -r requirements.txt` |
| `package.json` | `npm install` |
| `bun.lockb` | `bun install` |
| `Cargo.toml` | `cargo build` |

### For New Projects: Prefer Pixi

Pixi gives cross-platform lockfiles that resolve for both linux-64 and osx-arm64:

```bash
cd ~/Projects/research
mkdir my-model && cd my-model
pixi init
pixi workspace platform add linux-64 osx-arm64
pixi add python=3.12 numpy pandas
```

But if a project already uses uv, bun, whatever - **that's fine**. Don't force-migrate.

### Install Pixi (Both Machines)

**ThinkPad:**
```bash
curl -fsSL https://pixi.sh/install.sh | bash
source ~/.bashrc
```

**MacBook:**
```bash
curl -fsSL https://pixi.sh/install.sh | zsh
# Or: brew install pixi
```

---

## Phase 8: CLAUDE.md

### Global CLAUDE.md

```bash
mkdir -p ~/.claude

cat > ~/.claude/CLAUDE.md << 'CLAUDEMD'
# Machine Context

This is a Lenovo ThinkPad running Arch Linux, configured as a persistent home
server for Claude Code. It runs 24/7 with the lid closed, connected via WiFi
and Tailscale. Access from MacBook via SSH or from phone via Happy CLI.

## System

- **OS:** Arch Linux (rolling release)
- **Package managers:** pacman, yay (AUR)
- **Node.js:** Via nvm (not system pacman - avoids ICU conflicts)
- **Sudo:** Passwordless for this user, allowed in Claude Code permissions

## Access Patterns

- From MacBook: `ssh thinkpad` (local) or `ssh thinkpad-ts` (Tailscale)
- From phone: Happy app (sessions visible automatically)
- Start session: `cc <project-name>` (wraps happy claude)
- Dev servers accessible at http://thinkpad:PORT via Tailscale

## Project Structure

```
~/Projects/
├── hobby/       # Personal projects
├── OSS/         # Open source
├── research/    # ML research, experiments
└── work/        # Professional
```

## Dependency Management

Projects use whatever tool they already use. Don't force-migrate.
- Pixi projects: `pixi install`
- uv projects: `uv sync`
- npm projects: `npm install`
- bun projects: `bun install`

For NEW projects, prefer pixi with:
```
pixi workspace platform add linux-64 osx-arm64
```

**Critical:** Platform-specific dirs (.pixi, .venv, node_modules) do NOT sync.
Always run the appropriate install command after syncing to this machine.

## Syncthing

~/Projects syncs bidirectionally with MacBook. The .stignore excludes all
platform-specific environments, build artifacts, large data, and secrets.

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
pixi self-update                            # Update Pixi
```

## Things to Watch Out For

- After pacman -Syu, check that node still works (ICU conflicts).
  If node breaks: `nvm reinstall 20`
- After syncing new projects, always rebuild deps locally
- WiFi can drop if laptop overheats with lid closed - check ventilation
CLAUDEMD
```

---

## Phase 9: Final Validation

```bash
cat > ~/bin/validate-homeserver << 'SCRIPT'
#!/bin/bash
echo "=== ThinkPad Home Server Validation ==="
echo ""

total=0; passed=0

check() {
    ((total++))
    if eval "$2" &>/dev/null; then
        echo "✓ $1"; ((passed++))
    else
        echo "✗ $1"
        [[ -n "$3" ]] && echo "  → $3"
    fi
}

echo "--- System ---"
check "Lid switch ignored" \
    "grep -rq 'HandleLidSwitch=ignore' /etc/systemd/logind.conf.d/" \
    "See Phase 2.1"
check "WiFi power save off" \
    "iwconfig 2>/dev/null | grep -q 'Power Management:off'" \
    "See Phase 2.2"
check "SSHD running" \
    "systemctl is-active sshd" \
    "sudo systemctl enable --now sshd"
check "Passwordless sudo" \
    "sudo -n true" \
    "See Phase 1"

echo ""
echo "--- Tools ---"
check "Node.js (nvm)" \
    "node --version" \
    "nvm install 20"
check "Claude Code" \
    "command -v claude" \
    "npm install -g @anthropic-ai/claude-code"
check "Happy CLI" \
    "command -v happy" \
    "npm install -g happy-coder"
check "ANTHROPIC_API_KEY" \
    "test -n \"$ANTHROPIC_API_KEY\"" \
    "Add to ~/.bashrc"
check "Pixi" \
    "pixi --version" \
    "curl -fsSL https://pixi.sh/install.sh | bash"
check "yay" \
    "command -v yay" \
    "See Phase 0.5"

echo ""
echo "--- Networking ---"
check "Tailscale running" \
    "tailscale status" \
    "sudo systemctl enable --now tailscaled && sudo tailscale up"
check "Internet" \
    "ping -c 1 -W 3 google.com" \
    "Check WiFi"

echo ""
echo "--- Syncthing ---"
check "Syncthing running" \
    "systemctl --user is-active syncthing" \
    "systemctl --user enable --now syncthing"
check "Linger enabled" \
    "ls /var/lib/systemd/linger/$USER" \
    "sudo loginctl enable-linger $USER"
check "~/Projects exists" \
    "test -d ~/Projects" \
    "mkdir -p ~/Projects/{hobby,OSS,research,work}"
check ".stignore exists" \
    "test -f ~/Projects/.stignore" \
    "See Phase 5.3"

echo ""
echo "--- Config ---"
check "CLAUDE.md exists" \
    "test -f ~/.claude/CLAUDE.md" \
    "See Phase 8"
check "settings.json (sudo allowed)" \
    "grep -q 'sudo' ~/.claude/settings.json" \
    "See Phase 1"
check "cc script" \
    "test -x ~/bin/cc" \
    "See Phase 6.4"
check "~/bin in PATH" \
    "echo \$PATH | grep -q \"\$HOME/bin\"" \
    "echo 'export PATH=\$HOME/bin:\$PATH' >> ~/.bashrc"

echo ""
echo "=== $passed/$total passed ==="

if [[ $passed -eq $total ]]; then
    echo ""
    echo "🎉 Ready!"
    echo ""
    echo "  From ThinkPad:  cc my-project"
    echo "  From MacBook:   ssh thinkpad"
    echo "  From phone:     Happy app"
    echo "  Dev servers:    http://thinkpad:PORT"
fi
SCRIPT

chmod +x ~/bin/validate-homeserver
```

Run: `validate-homeserver`

---

## Quick Reference

```bash
# Start Claude Code on a project (from anywhere)
cc my-project

# From MacBook
ssh thinkpad                              # local network
ssh thinkpad-ts                           # anywhere via Tailscale
ssh thinkpad "cc my-project"              # start remote session

# Happy daemon
happy daemon start                        # start background service
happy daemon list                         # list sessions
happy daemon status                       # check health

# After syncing a project to this machine
cd ~/Projects/hobby/my-app
pixi install        # or: uv sync / npm install / bun install

# Access dev servers (from any Tailscale device)
# http://thinkpad:3000
# http://thinkpad:8080

# Update everything
sudo pacman -Syu
npm update -g @anthropic-ai/claude-code happy-coder
pixi self-update
```
