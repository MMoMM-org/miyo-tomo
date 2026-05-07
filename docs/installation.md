# Installation

> Get Tomo running on your machine — prerequisites, install command, verification, and updates. For the interactive install walkthrough and post-install configuration, see the [Setup Guide](setup.md).

## Prerequisites

- Docker installed and running
- Git, jq
- Python 3
- [MiYo Kado](https://github.com/MMoMM-org/miyo-kado) v0.5.0+ running and accessible on `127.0.0.1:23026` (the Kado default)

## Install

```bash
# 1. Clone the repo
git clone https://github.com/MMoMM-org/miyo-tomo.git
cd miyo-tomo

# 2. Run the install script
bash scripts/install-tomo.sh

# 3. Start Tomo (generated launcher builds the Docker image on first run)
bash begin-tomo.sh
```

The installer is interactive by default; it prompts you for vault path, framework profile, Kado connection details, and more. See [Setup Guide → Install Script Walkthrough](setup.md#install-script-walkthrough) for what to expect at each step.

For unattended or CI installs, see [Setup Guide → Non-Interactive Mode](setup.md#non-interactive-mode).

The installer generates `begin-tomo.sh` at your chosen instance location. For the default install this lands at the repo root; if you pointed the installer at a custom location, the launcher lives next to your instance there.

## Verify the installation

After `bash begin-tomo.sh` completes its first image build, Claude Code launches inside the Tomo container. To confirm the install plus Kado connection are working, run the vault explorer in your first session:

```
/explore-vault
```

If the command starts scanning your vault and prompts you to confirm folder mappings, the install is healthy. See [Setup Guide → After Installation](setup.md#after-installation) for the full first-session flow.

If `begin-tomo.sh` fails to start the container, or Claude Code can't reach Kado, see [Troubleshooting](troubleshooting.md).

## Updating

```bash
git pull                        # Get latest source
bash scripts/update-tomo.sh     # Update managed files in instance
```

The update script overwrites managed files (agents, commands, hooks) if the version changed, but never touches user files (vault-config, kado-config).

For a clean re-install or full cleanup, see [Setup Guide → Cleanup / Re-install](setup.md#cleanup--re-install).
