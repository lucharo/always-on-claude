# Setup Scripts

Complete scripts for server and client setup.

## Server Setup Script (Arch Linux)

Run on the always-on machine:

```bash
#!/bin/bash
# server-setup.sh

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
# Create on /home partition for space
# Use BIND MOUNT (not symlink) to /Users for macOS path compatibility
# Bind mount is critical - symlinks get "resolved" and break session portability
sudo mkdir -p /home/${USER}_macpath/Projects
sudo chown $USER:wheel /home/${USER}_macpath

sudo mkdir -p /Users/luischavesrodriguez
sudo mount --bind /home/${USER}_macpath /Users/luischavesrodriguez

# Make bind mount permanent (survives reboot)
echo "/home/${USER}_macpath /Users/luischavesrodriguez none bind 0 0" | sudo tee -a /etc/fstab

# Note: Do NOT create ~/Projects symlink
# Always use /Users/luischavesrodriguez/Projects directly in Happy
# to ensure correct session paths for Claude portability

echo "=== 6. Install Node.js via nvm ==="
# Use nvm, not system node (avoids ICU conflicts on Arch)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
nvm install 22

echo "=== 7. Install Claude Code ==="
npm install -g @anthropic-ai/claude-code

echo "=== 8. Install Happy CLI ==="
npm install -g happy-coder

echo "=== 9. Verify Installation ==="
echo "Node: $(node --version)"
echo "Claude Code: $(claude --version)"
echo "Happy: $(happy --version)"

echo "=== Done! ==="
echo "Server IP: $(tailscale ip -4)"
echo "Now run the client setup script on your MacBook."
```

## Client Setup Script (macOS)

Run on your MacBook:

```bash
#!/bin/bash
# client-setup.sh

set -e

SERVER_HOST="arch-lenovo"  # Change to your server hostname
SERVER_USER="luis"         # Change to your server username
SERVER_PATH="/Users/luischavesrodriguez/Projects"

echo "=== 1. Install Mutagen ==="
brew install mutagen-io/mutagen/mutagen

echo "=== 2. Start Mutagen Daemon ==="
mutagen daemon start

echo "=== 3. Add SSH Config ==="
if ! grep -q "Host ${SERVER_HOST}" ~/.ssh/config 2>/dev/null; then
  cat >> ~/.ssh/config << EOF

Host ${SERVER_HOST}
    HostName ${SERVER_HOST}
    User ${SERVER_USER}

Host ${SERVER_HOST}-ts
    HostName ${SERVER_HOST}
    User ${SERVER_USER}
EOF
  echo "SSH config added"
else
  echo "SSH config already exists"
fi

echo "=== 4. Test SSH Connection ==="
ssh ${SERVER_HOST} 'echo "Connected to $(hostname)"'

echo "=== 5. Initial File Transfer ==="
echo "Copying ~/Projects to server (this may take a while)..."
scp -r ~/Projects/* ${SERVER_HOST}:${SERVER_PATH}/

echo "=== 6. Create Projects Sync ==="
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
  ~/Projects ${SERVER_HOST}:${SERVER_PATH}

echo "=== 7. Create Claude Config Sync ==="
mutagen sync create \
  --name=claude-config \
  --mode=two-way-safe \
  --ignore="CLAUDE.md" \
  ~/.claude ${SERVER_HOST}:/home/${SERVER_USER}/.claude

echo "=== 8. Verify Syncs ==="
mutagen sync list

echo "=== Done! ==="
```

## Post-Setup Verification

### On Server

```bash
# Check directory structure
ls -la ~/Projects
ls -la /Users/luischavesrodriguez

# Check services
systemctl status sshd
systemctl status tailscaled
tailscale status

# Check Claude Code
claude --version
```

### On Client

```bash
# Check syncs are running
mutagen sync list

# Wait for "Watching for changes" status
watch mutagen sync list

# Test creating a file
echo "test" > ~/Projects/test-sync.txt
# Check it appears on server
ssh arch-lenovo 'cat ~/Projects/test-sync.txt'
# Clean up
rm ~/Projects/test-sync.txt
```

## Customization

### Different Server OS

For Ubuntu/Debian:
```bash
sudo apt update && sudo apt upgrade
sudo apt install tailscale openssh-server
```

For Fedora:
```bash
sudo dnf update
sudo dnf install tailscale openssh-server
```

### Different Path Structure

Adjust these variables in scripts:
- `SERVER_PATH` - where Projects lives on server
- Path in Mutagen sync commands
- Symlink targets

### Additional Excludes

Add project-specific excludes:
```bash
--ignore="large-dataset/"
--ignore="*.mp4"
--ignore="courses/large-course/"
```
