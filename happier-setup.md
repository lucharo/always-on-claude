# Happier Setup

Reference for Happier installation on both server and client, using Happier Cloud relay for cross-device session sync.

## Prerequisites

- Node.js & npm working on the server (Arch: `sudo pacman -S nodejs npm yarn node-gyp`)
- User-local npm prefix (no sudo for global installs):
  ```bash
  mkdir -p ~/.npm-global
  npm config set prefix ~/.npm-global
  # In ~/.config/zsh/.zshrc:
  export PATH="$HOME/.npm-global/bin:$PATH"
  ```

## Happier CLI

The npm package is currently broken ([#103](https://github.com/happier-dev/happier/issues/103)) and the install script binary requires AVX2 ([#117](https://github.com/happier-dev/happier/issues/117)). Build from source:

```bash
cd ~/Projects/oss/happier-dev
git checkout preview
git pull origin preview
yarn install
yarn cli:build
```

Create a direct wrapper (bypasses the `hstack` shim which breaks cloud auth — [#116](https://github.com/happier-dev/happier/issues/116)):

```bash
cat > ~/.npm-global/bin/happier << 'EOF'
#!/bin/bash
exec node ~/Projects/oss/happier-dev/apps/cli/bin/happier.mjs "$@"
EOF
chmod +x ~/.npm-global/bin/happier
```

> **Note:** The official and recommended install method is `curl -fsSL https://happier.dev/install | bash`. We build from source because our server has a quite old CPU (Sandy Bridge i5-2520M) that lacks AVX2, which the pre-compiled binary requires ([#117](https://github.com/happier-dev/happier/issues/117)).

### Updating

```bash
cd ~/Projects/oss/happier-dev
git pull origin preview
yarn install
yarn cli:build
# Wrapper script picks up the new build automatically
```

## Auth & Daemon

```bash
# Authenticate (interactive — scan QR with Happier mobile app)
happier auth login

# Install daemon (keeps sessions alive for phone access)
happier daemon install

# Verify
happier auth status
happier daemon status
```

## MacBook Setup

On the MacBook, the standard install works (no AVX2 issues):

```bash
curl -fsSL https://happier.dev/install | bash
happier auth login    # same account as server
happier daemon install
```

With Happier on both machines, all sessions are accessible from either device through the relay server. Use `happier session list` to see sessions or `happier resume` to continue one.

## Self-hosted relay (optional)

Happier supports running your own relay server via `hstack` — useful if you want conversations to never touch the Happier Cloud infrastructure. This setup doesn't use it: we run the default hosted relay at `https://api.happier.dev` because it's E2E encrypted and operationally simpler. If you want to self-host instead, see the [Happier stack docs](https://github.com/happier-dev/happier) and configure a second daemon with `HAPPIER_SERVER_URL=https://your-relay.example`.

## Other AI CLIs

| CLI | Install | Path |
|-----|---------|------|
| Claude Code | Native installer | `~/.local/bin/claude` |
| Gemini | `npm install -g @google/gemini-cli` | `~/.npm-global/bin/gemini` |
| OpenCode | `curl -fsSL https://opencode.ai/install \| bash` | `~/.opencode/bin/opencode` |

All are available as Happier backends: `happier`, `happier gemini`, `happier opencode`.

To connect vendors for phone-initiated sessions: `happier connect gemini`

## Known Issues

| Issue | Description |
|-------|-------------|
| [#103](https://github.com/happier-dev/happier/issues/103) | npm package missing `@happier-dev/release-runtime` |
| [#116](https://github.com/happier-dev/happier/issues/116) | hstack shim overrides server URL, breaks cloud auth |
| [#117](https://github.com/happier-dev/happier/issues/117) | Install script binary crashes on older CPUs (no AVX2) |
| [#118](https://github.com/happier-dev/happier/issues/118) | "CLI Not Detected" popups reappear after dismissal |
| [#119](https://github.com/happier-dev/happier/issues/119) | Working directory path lowercased in session picker |
