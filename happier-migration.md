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

Happier uses a tool called `hstack` (Happier Stack) to manage the self-hosted infrastructure (servers, databases, daemon), while `happier` is the CLI used for actual AI interactions.

To ensure the Happier Relay Server and Daemon run persistently in the background:

```bash
cd ~/Projects/oss/happier-dev

# Install and enable the systemd service (runs in prod mode)
yarn service:install
yarn service:enable

# Enable Tailscale to securely expose the Web UI and Relay
yarn tailscale:enable
yarn tailscale:url
# -> Yields: https://arch.tailacf9ef.ts.net
```

## 4. Connecting and Authenticating

Once the server is running and exposed over Tailscale, you must connect your CLI to the new Relay Server and authenticate.

1. **Set the Default Server (CLI):**
   Link the `happier` CLI to your private Tailscale relay instead of the public cloud.
   ```bash
   happier server add --name "arch happier relay server" --server-url "https://arch.tailacf9ef.ts.net" --use
   ```

2. **Install the Background Daemon:**
   Install the systemd daemon so sessions stay alive remotely.
   ```bash
   happier daemon install
   ```

3. **Sign In (Interactive):**
   *Note: This command generates a QR code. It must be run manually in an interactive SSH session, otherwise it will hang background scripts.*
   ```bash
   happier auth login
   ```
   *Scan the resulting QR code with the Happier mobile app to pair your terminal.*

4. **Authenticate the AI (e.g., Claude):**
   To enable AI vendor usage:
   ```bash
   happier connect claude
   ```

## Architecture Summary

- **Relay Server:** Hosted locally on Arch (managed via `hstack`), handling sessions and state.
- **Web UI & App Routing:** Accessible at the local Tailscale URL (`https://arch.tailacf9ef.ts.net`).
- **Daemon:** Running as a systemd background service on Arch.
- **Mobile/Remote:** Traffic routes over Tailscale directly to the Arch server, entirely bypassing `api.happier.dev`.
