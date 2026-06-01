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

# 2. Run the install script (prompts for instance name + parent dir)
bash scripts/install-tomo.sh

# 3. Start Tomo via the instance's generated launcher
#    (builds the Docker image on first run)
bash ~/MiYo/Tomo/<name>/begin-tomo.sh
```

The installer is interactive by default; it prompts you for an instance name, a parent directory, vault path, framework profile, Kado connection details, and more. See [Setup Guide → Install Script Walkthrough](setup.md#install-script-walkthrough) for what to expect at each step.

For unattended or CI installs, see [Setup Guide → Non-Interactive Mode](setup.md#non-interactive-mode).

### Instance layout

Each instance is **self-contained** in its own directory under a parent you choose (default `~/MiYo/Tomo/`):

```
~/MiYo/Tomo/<name>/
├── begin-tomo.sh        # the launcher you run to start this instance
├── tomo-install.json    # this instance's install state
├── instance/            # Docker workspace (agents, skills, configs)
└── home/                # Docker /home/coder (auth, .gitconfig)
```

The installer also records the instance in a small registry at `~/.tomo/instances.json` so later runs can find it. You run an instance by its own launcher — e.g. `bash ~/MiYo/Tomo/<name>/begin-tomo.sh`.

### Multiple instances

You can run several Tomo instances side by side — for example one per vault. Re-run `bash scripts/install-tomo.sh`: if any instances are already registered, the installer lists them and offers to **create a new instance** or **update an existing one** by name. See [Setup Guide → Install Script Walkthrough](setup.md#install-script-walkthrough).

## Verify the installation

After your instance's `begin-tomo.sh` completes its first image build, Claude Code launches inside the Tomo container. To confirm the install plus Kado connection are working, run the vault explorer in your first session:

```
/explore-vault
```

If the command starts scanning your vault and prompts you to confirm folder mappings, the install is healthy. See [Setup Guide → After Installation](setup.md#after-installation) for the full first-session flow.

If the launcher fails to start the container, or Claude Code can't reach Kado, see [Troubleshooting](troubleshooting.md).

## Updating

```bash
git pull                                  # Get latest source
bash scripts/update-tomo.sh --instance <name>   # Update a named instance
```

The update script overwrites managed files (agents, commands, hooks) if the version changed, but never touches user files (vault-config, kado-config). It resolves the instance by name through `~/.tomo/instances.json`, updates only that instance, re-renders its launcher, and refreshes its `tomoVersion`.

You don't have to remember to update manually: the next time you run an instance's `begin-tomo.sh`, the launcher compares the installed version against the source repo and — if the instance is behind — offers to run the update for you before launching.

For a clean re-install or full cleanup, see [Setup Guide → Cleanup / Re-install](setup.md#cleanup--re-install).
