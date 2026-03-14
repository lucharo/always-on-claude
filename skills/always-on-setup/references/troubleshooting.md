# Troubleshooting Guide

Extended troubleshooting for common issues with always-on Claude setups.

## Session Portability Issues

### Sessions Not Resumable Between Machines

**Symptom:** Started a session on server, can't resume on MacBook (or vice versa)

**Cause:** Path mismatch. Claude stores sessions keyed by path. If the server uses `/home/...` and MacBook uses `/Users/...`, the session keys won't match.

**Diagnosis:**
```bash
# Check what path Claude sees on server
ssh server 'cd ~/Projects/myproject && pwd && pwd -P'

# Should show /Users/luischavesrodriguez/Projects/myproject (not /home/...)
```

**Solution:** Use bind mount instead of symlink for `/Users/luischavesrodriguez`:
```bash
# On server as root:
umount /Users/luischavesrodriguez 2>/dev/null  # if currently mounted
rm /Users/luischavesrodriguez  # remove symlink if exists
mkdir -p /Users/luischavesrodriguez
mount --bind /home/luischavesrodriguez_macpath /Users/luischavesrodriguez
echo '/home/luischavesrodriguez_macpath /Users/luischavesrodriguez none bind 0 0' >> /etc/fstab
```

### Why Bind Mount Not Symlink?

**Symlink:** A pointer that says "look over there." Programs can see it's a symlink and resolve to the real path.

**Bind mount:** Makes a directory appear in two places. Programs can't tell it's not the "real" location.

For Claude session portability, we need programs to see `/Users/luischavesrodriguez`, not resolve through to `/home/...`.

## Sync Issues

### Sync Stuck in "Scanning files"

**Symptoms:** Mutagen shows "Scanning files" indefinitely

**Causes:**
- Very large directory (100k+ files)
- Slow network connection
- File permissions issues

**Solutions:**
```bash
# Check what's being scanned
mutagen sync list -l

# If stuck, terminate and recreate with more excludes
mutagen sync terminate projects

# Add excludes for large directories
mutagen sync create \
  --name=projects \
  --mode=two-way-safe \
  --ignore="large-directory/" \
  ...
```

### Sync Shows Conflicts

**Symptoms:** `Conflicts: N` in sync status

**Causes:**
- Daemon wasn't running (e.g., after reboot without `mutagen daemon register`) and both sides diverged
- Same file modified on both machines
- File type changed (e.g., file → symlink)

**Most common case:** `.git/` internal files (index, logs, COMMIT_EDITMSG, etc.) diverge when both machines do git operations while sync is down. These are safe to resolve by picking one side.

**Solutions:**

```bash
# 1. View conflict details
mutagen sync list -l

# 2. Summarize conflicts by project
mutagen sync list -l | grep "(alpha)" | sed 's/.*) //' | sed 's/ (.*//' | cut -d/ -f1-3 | sort | uniq -c | sort -rn

# 3. Resolve by deleting the conflicting files on the NON-primary side
#    (Mac is alpha/primary — delete arch's versions so Mac wins)
ssh arch-lenovo "rm -rf /path/to/conflicting/.git"
# Or for individual source files:
ssh arch-lenovo "rm -f /path/to/conflicting/file.py"

# 4. Flush to apply
mutagen sync flush projects

# 5. Repeat until Conflicts: 0

# Nuclear option: terminate and recreate the session (clears all history)
# Only needed if conflicts keep reappearing after resolution
mutagen sync terminate projects
# Recreate with same config (see setup-scripts.md)
```

**Prevention:** Run `mutagen daemon register` so the daemon auto-starts on login and sync never silently stops.

### Sync Error: "Too many levels of symbolic links"

**Symptoms:** Sync fails with symlink error

**Causes:**
- Circular symlinks
- Changed directory to symlink while sync running

**Solutions:**
```bash
# Terminate sync
mutagen sync terminate projects

# Fix symlink issues on server
ssh server 'ls -la /problematic/path'

# Recreate sync
```

## Connection Issues

### SSH Connection Refused

**Symptoms:** `ssh: connect to host ... port 22: Connection refused`

**Causes:**
- SSH service not running
- Firewall blocking port 22
- Wrong hostname

**Solutions:**
```bash
# On server - check SSH service
sudo systemctl status sshd
sudo systemctl start sshd

# Check if listening on port 22
ss -tlnp | grep 22

# Check firewall (if using ufw)
sudo ufw status
sudo ufw allow ssh
```

### SSH Timeout via Tailscale

**Symptoms:** Connection times out when using Tailscale hostname

**Causes:**
- Tailscale not running on server
- Server not connected to Tailnet
- Different Tailscale account

**Solutions:**
```bash
# On server - check Tailscale
sudo systemctl status tailscaled
tailscale status

# Reconnect if needed
sudo tailscale up

# On client - verify can see server
tailscale status | grep server-name
```

### "Host key verification failed"

**Symptoms:** SSH refuses to connect, mentions host key

**Causes:**
- Server was reinstalled
- IP address changed
- Man-in-the-middle (unlikely on Tailscale)

**Solutions:**
```bash
# Remove old host key
ssh-keygen -R server-hostname

# Or for IP
ssh-keygen -R 192.168.x.x

# Then reconnect (will prompt to accept new key)
ssh server
```

## Disk Space Issues

### Server Disk Full

**Symptoms:** Commands fail with "No space left on device"

**Diagnosis:**
```bash
# Check partitions
df -h

# Find large directories
du -sh /* 2>/dev/null | sort -hr | head -10

# Find large files
find / -type f -size +100M -exec ls -lh {} \; 2>/dev/null | head -20
```

**Common culprits on Arch:**
```bash
# Pacman cache (can be huge)
du -sh /var/cache/pacman/pkg/
sudo paccache -rk1  # Keep only 1 version

# Journal logs
journalctl --disk-usage
sudo journalctl --vacuum-size=100M

# Old kernels (if not auto-cleaned)
sudo pacman -Rns $(pacman -Qdtq)
```

### Wrong Partition Used

**Diagnosis:**
```bash
# Check which partition a path is on
df /path/to/directory

# See partition layout
lsblk
```

**Solution:** Move data to correct partition. See `partition-fix.md`.

## Permission Issues

### Sudo: "User is not in the sudoers file"

**Symptoms:** `sudo` fails even with correct password

**Causes:**
- User not in wheel/sudo group
- Wheel group not enabled in sudoers

**Solutions:**
```bash
# Log in as root
su -

# Check user groups
groups username

# Add to wheel group if missing
usermod -aG wheel username

# Enable wheel in sudoers
visudo
# Uncomment: %wheel ALL=(ALL:ALL) ALL
```

### Permission Denied on Synced Files

**Symptoms:** Can't read/write files that synced from other machine

**Causes:**
- Different UID/GID between machines
- Mutagen permissions mode

**Solutions:**
```bash
# Check file ownership
ls -la problematic-file

# Fix ownership
sudo chown -R $USER:$GROUP /path/to/files

# For future syncs, adjust Mutagen permissions mode
mutagen sync create \
  --default-file-mode=0644 \
  --default-directory-mode=0755 \
  ...
```

## Happier CLI Issues

### Happier Daemon Not Running

**Symptoms:** `happier` fails or no phone notifications

**Solutions:**
```bash
# Check daemon status
happier daemon status

# Start if not running
happier daemon install

# Check logs
happier daemon logs
```

### Sessions Not Visible on Phone

**Causes:**
- Daemon not running
- Wrong Happier account
- Network issues

**Solutions:**
```bash
# Verify daemon is running and connected
happier daemon status

# Re-authenticate if needed
happier auth login
```

## Arch Linux Specific

### Node.js Broken After pacman -Syu

**Symptoms:** Node commands fail with ICU or library errors

**Causes:**
- System update changed shared libraries
- ICU version mismatch

**Solutions:**
```bash
# Reinstall node via nvm
nvm reinstall 22

# Or if nvm not working
rm -rf ~/.nvm
# Reinstall nvm and node
```

### Kernel Module Issues After Update

**Symptoms:** Hardware not working, strange errors

**Solutions:**
```bash
# Reboot to load new kernel
sudo reboot
```

## Recovery Procedures

### Complete Sync Reset

If sync is hopelessly broken:

```bash
# On client
mutagen sync terminate projects

# On server - delete synced data (if client has good copy)
ssh server 'rm -rf /path/to/Projects/*'

# Re-transfer from client
scp -r ~/Projects/* server:/path/to/Projects/

# Recreate syncs
# (use commands from setup-scripts.md)
```

### Server Unreachable

If server is unreachable and you need your data:

1. **If you have physical access:** Connect keyboard/monitor, check network
2. **If WiFi dropped:** Server may have overheated (check ventilation)
3. **If power lost:** Check UPS or power supply
4. **Data safety:** Your client (MacBook) has a full copy of synced data
