# Migration to Happier (Self-Hosted)

This document outlines the transition from the standalone Claude Code CLI to the **Happier** environment, specifically detailing the self-hosted relay server setup on the Arch Linux machine.

## 1. System Node.js & NPM Fix (Arch Machine)

The system-wide `npm` installation on Arch Linux (Node v25.6.1) was broken due to a missing `semver` dependency. To ensure a stable JavaScript environment for Happier, we bypassed the system Node and installed `nvm`.

```bash
# Installed NVM
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash

# Set default Node version
nvm install 25.4.0
nvm alias default 25.4.0
```

*Note: The Arch machine uses a customized ZSH environment, so NVM environment variables were exported directly to `~/.config/zsh/.zshrc` to ensure `yarn` and `node` load interactively.*

## 2. Happier Self-Hosted Installation

Because the `@happier-dev/cli` package on the NPM registry was missing an internal dependency (`@happier-dev/release-runtime`), we opted to clone the monorepo and run the entire suite from source to enable self-hosting the API Relay.

```bash
# 1. Clone the repository
mkdir -p ~/Projects/oss
cd ~/Projects/oss
git clone https://github.com/happier-dev/happier happier-dev
cd happier-dev

# 2. Install dependencies & build the monorepo
yarn install
yarn build

# 3. Activate the CLI globally
yarn cli:activate

# Added the generated bin to PATH (~/.config/zsh/.zshrc)
export PATH="$HOME/.happier-stack/bin:$PATH"
```

## 3. Server & Service Configuration

To ensure the Happier Relay Server and Daemon run persistently in the background:

```bash
cd ~/Projects/oss/happier-dev

# Install and enable the systemd service (runs in prod mode)
yarn service:install
yarn service:enable

# Enable Tailscale to securely expose the Web UI
yarn tailscale:enable
yarn tailscale:url
```

## 4. Connecting and Authenticating

Once the server is running and exposed over Tailscale, the final steps require interactive authentication:

1. **Authenticate the stack** to pair the local daemon/CLI with the local relay server:
   ```bash
   hstack stack auth repo-happier-dev-1097aa2624 login
   ```
2. **Authenticate the CLI** to enable AI usage (e.g., Claude):
   ```bash
   happier connect claude
   ```

## Architecture Summary

- **Relay Server:** Hosted locally on Arch, handling sessions and state.
- **Web UI:** Accessible at the local Tailscale URL (`https://arch.tailacf9ef.ts.net`).
- **Daemon:** Running as a systemd background service on Arch.
- **Mobile/Remote:** Traffic routes over Tailscale directly to the Arch server, entirely bypassing `api.happier.dev`.
