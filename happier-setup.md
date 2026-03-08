# Happier Setup (Arch Server)

Reference for the Happier installation on `arch`, using Happier Cloud relay.

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

> **Note:** The official install method is `curl -fsSL https://happier.dev/install | bash`, but the pre-compiled binary requires AVX2 ([#117](https://github.com/happier-dev/happier/issues/117)), which older CPUs (e.g., Sandy Bridge) lack. Building from source is the workaround.

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
