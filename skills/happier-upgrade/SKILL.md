---
name: happier-upgrade
description: This skill should be used when the user asks to "upgrade Happier", "update Happier on both machines", "sync Happier versions", "happier-system-upgrade", "update the daemon", "Happier is out of date", or mentions version drift between the MacBook and the arch server. Handles the multi-machine Happier CLI upgrade workflow, including daemon restarts and session impact warnings.
---

# Happier Upgrade

Upgrade Happier CLI across all machines (MacBook + arch server) and keep versions in sync. The two machines use different install methods so one command won't work for both.

## Key constraints

- **Restarting a daemon kills its active sessions.** Phone-initiated sessions routed through the daemon get dropped. Always check for active work before restart.
- **Mac uses the prebuilt installer** (`curl https://happier.dev/install | bash`). The binary lives at `~/.happier/cli/current/happier` with a shim at `~/.local/bin/happier`.
- **Arch builds from source** because the CPU (Sandy Bridge) lacks AVX2 — the prebuilt binary crashes ([issue #117](https://github.com/happier-dev/happier/issues/117)). Source lives at `~/Projects/oss/happier-dev`, built with `yarn cli:build`.
- **Arch runs multiple daemons.** Expect at least `happier-daemon.cloud.service` (the one actually in use) and possibly others like `happier-daemon.arch-happier-relay-server.service` for a self-hosted relay.
- **Both arch daemons share the same source build** — the ExecStart path points at `apps/cli/dist/index.mjs`, so one build serves both.

## Upgrade procedure

### Step 0: Reconnaissance

Always run this first. Version drift, orphan processes, and active sessions will change what you do next.

```bash
# Mac
happier --version
happier daemon status | head -20

# Arch
ssh arch-lenovo 'export PATH="$HOME/.npm-global/bin:$PATH"; happier --version; happier daemon status | head -20'

# What services exist on arch?
ssh arch-lenovo 'systemctl --user list-units --all | grep -iE "happy|happier"'

# What's actually running?
ps aux | grep -iE "claude|happier" | grep -v grep
ssh arch-lenovo 'ps aux | grep -iE "claude|happier" | grep -v grep'

# How far behind is the arch source checkout?
ssh arch-lenovo 'cd ~/Projects/oss/happier-dev && git fetch origin preview && git rev-list --count HEAD..origin/preview'
```

**Things to check:**
- Version numbers on both sides (big drift = higher chance of breaking changes)
- Active `claude` processes — these will be killed when the daemon restarts
- Multiple daemon PIDs — investigate before killing any of them
- Stale v1 `happy-daemon.service` — if present, `happy-coder` package needs cleanup too

### Step 1: Warn about active sessions

Before touching anything, tell the user:
1. How many active claude processes exist on each machine
2. Which ones were spawned by the daemon (look for `--started-by daemon` or `/happier-dev/apps/cli/dist/index.mjs ... claude` as a parent)
3. That restarting the daemon will kill phone-initiated sessions

Use `AskUserQuestion` to confirm proceeding. Sessions in the relay are resumable later (that's the whole point of v3), so this is usually fine.

### Step 2: Upgrade Mac

The Mac installer changed locations between versions (it used to ship through npm global, now it's a standalone install). If there's an old NVM/npm install still winning the PATH race, remove it first.

```bash
# Stop the daemon
happier daemon stop

# Run the installer. Default channel is `stable`, which on Happier is
# actually a slower-moving preview-tagged release. For closer parity
# with arch's source build (which tracks the `preview` branch tip),
# install the preview channel instead:
curl -fsSL https://happier.dev/install | HAPPIER_CHANNEL=preview bash
# NOTE: the env var must come AFTER the pipe (applied to bash),
# not before curl — otherwise it scopes to curl only.

# The preview channel installs side-by-side with stable at
# ~/.happier/cli-preview/ with a shim at ~/.local/bin/hprev.
# To make `happier` resolve to the preview binary, repoint the shim:
rip ~/.happier/cli ~/.happier/bin/happier ~/.local/bin/happier
ln -sf ~/.happier/cli-preview/current/happier ~/.happier/bin/happier
ln -sf ~/.happier/bin/happier ~/.local/bin/happier
rip ~/.local/bin/hprev ~/.happier/bin/hprev
hash -r

# Check PATH — if an old nvm/npm happier shadows the new one, remove it
which happier
happier --version

# If the old nvm install is still winning:
ls ~/.nvm/versions/node/*/lib/node_modules/@happier-dev/ 2>/dev/null
# If found, delete the stale install:
rip ~/.nvm/versions/node/<node-version>/lib/node_modules/@happier-dev ~/.nvm/versions/node/<node-version>/bin/happier
hash -r
which happier  # should now be ~/.local/bin/happier

# Reinstall daemon
happier daemon install
happier daemon status
```

Note: `npm uninstall -g @happier-dev/cli` may report "up to date" and do nothing if the active node (e.g. homebrew node 25) differs from the nvm node the package is installed under. Directly removing the files is more reliable.

### Step 3: Upgrade arch (source build)

```bash
ssh arch-lenovo '
set -e
cd ~/Projects/oss/happier-dev

# Stash any local build drift (yarn.lock, etc.)
git status --short
git stash push yarn.lock -m "pre-upgrade drift" 2>/dev/null || true

# Pull latest preview
git pull origin preview
'
```

Then run the build **detached over SSH**, because `yarn install` takes several minutes and any SSH flap will kill a foreground command. Write output to a log file and poll for completion:

```bash
# Kick off yarn install detached
ssh arch-lenovo 'cd ~/Projects/oss/happier-dev && nohup yarn install --ignore-engines > /tmp/yarn-install.log 2>&1 < /dev/null & disown; echo "pid=$!"'

# Poll until the process exits (use the pid from the previous command)
ssh arch-lenovo 'while kill -0 <pid> 2>/dev/null; do sleep 10; done; tail -25 /tmp/yarn-install.log'

# Same pattern for the build
ssh arch-lenovo 'cd ~/Projects/oss/happier-dev && nohup yarn cli:build > /tmp/yarn-build.log 2>&1 < /dev/null & disown; echo "pid=$!"'
ssh arch-lenovo 'while kill -0 <pid> 2>/dev/null; do sleep 10; done; tail -25 /tmp/yarn-build.log'
```

**Why `--ignore-engines`:** some dependencies pin max Node versions (e.g. `@homebridge/node-pty-prebuilt-multiarch` refuses Node 25). Arch's system `node` tends to run ahead of what happier-dev declares as supported. The flag bypasses the check; if the build later fails for a real reason, install an older Node via pacman or nvm.

### Step 4: Restart the arch cloud daemon

```bash
ssh arch-lenovo 'systemctl --user restart happier-daemon.cloud'
ssh arch-lenovo 'systemctl --user is-active happier-daemon.cloud'
ssh arch-lenovo 'export PATH="$HOME/.npm-global/bin:$PATH"; happier daemon status | head -25'
```

If the user also runs the self-hosted relay daemon (`happier-daemon.arch-happier-relay-server.service`), ask whether to restart that too. Restarting picks up the new source build; leaving it alone means it keeps the old code in memory until the next restart. Usually you want to restart it for consistency unless the user explicitly asks otherwise.

### Step 5: Verify

```bash
# Mac
happier --version
happier auth status | head -10

# Arch
ssh arch-lenovo 'export PATH="$HOME/.npm-global/bin:$PATH"; happier --version; happier auth status | head -10'
```

Both should show ✓ Authenticated and ✓ Daemon running. Versions may differ slightly — arch is on the `preview` branch tip, Mac is on the prebuilt release channel — but both should be on the same minor (0.2.x, 0.3.x, etc.).

## Gotchas learned the hard way

- **SSH drops kill foreground commands.** Always use `nohup ... & disown` for `yarn install` and `yarn cli:build`. Both take 2–5 minutes each on arch.
- **Node engine pins break yarn install.** Use `--ignore-engines` as the first attempt; only downgrade Node if the actual build fails.
- **The mac installer location moved.** Older versions installed via npm global; newer versions use `~/.happier/cli/current/`. If both exist, PATH order decides which wins. Clean up the old one.
- **`npm uninstall -g` can silently no-op** when you're on a different Node than the one the package was installed under (homebrew vs nvm). Delete files directly if the npm command reports "up to date" instead of actually removing.
- **`happier --version` reports a long preview ID on the Mac** (`0.2.1-preview.<timestamp>.<hash>`) but a short semver on arch (`0.2.2`). They're on the same release line; don't panic about the format difference.
- **Stale v1 `happy-daemon.service` on arch.** Predates the Happier migration. If `systemctl --user list-units` shows it, offer to stop, disable, remove the unit file, and `npm uninstall -g happy-coder`.
- **Two happier daemons on arch is usually fine**, not a bug. One is cloud, one is for a self-hosted relay. Check the systemd unit file to see which is which before killing anything. Look at the `ExecStart` and `HAPPIER_SERVER_URL` environment variable.

## When something goes wrong

- **Build fails after the engine workaround:** read the actual error. If it's a real incompatibility, install a supported Node via `sudo pacman -S nodejs-lts-iron` or use nvm/fnm.
- **`happier auth status` shows not authenticated after restart:** re-run `happier auth login` on the affected machine. Each machine has its own keys; the relay treats them as separate devices.
- **Daemon fails to start:** check `journalctl --user -u happier-daemon.cloud -n 50` on arch or `~/.happier/logs/<latest>-daemon.log` on either. Common causes: port conflict, stale state file, auth token expired.
- **Sessions missing after upgrade:** they're in the relay, not local. Wait a few seconds for the daemon to reconnect, then `happier session list`. Old sessions from pre-relay days (v2 and earlier) may not show up — those are permanently local to whichever machine ran them.
