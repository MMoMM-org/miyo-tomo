# Tomo Setup Guide

This guide walks through Tomo's interactive setup, the launcher, post-install configuration, and operational tasks like authentication and cleanup. For prerequisites and the bare install command, see [Installation](installation.md).

## Install Script Walkthrough

The install script guides you through setup step by step.

### Create new vs. update an existing instance

Tomo supports several self-contained instances side by side (typically one per vault). At the top of the run, the installer reads the instance registry (`~/.tomo/instances.json`):

- **No instances registered yet** — it goes straight to creating your first instance.
- **One or more registered** — it lists them by name and path and asks:

  ```
  Registered instances:
    privat  (/Users/you/MiYo/Tomo/privat)
    work    (/Users/you/MiYo/Tomo/work)

    n. Create a new instance
    Or type the name of an instance to update.
  Choice (n / <name>) [n]:
  ```

  Press `n` (or Enter) to create a new one; type an existing name to re-run setup against that instance. Registry entries whose directory has gone missing are flagged `[stale]` so you can spot them.

When creating a new instance you'll be asked for:

- **Instance directory name** (default `tomo-instance`) — must be unique; the installer re-prompts if the name is already registered.
- **Instance parent directory** (default `~/MiYo/Tomo`) — the parent that will hold `<name>/`. A leading `~` is expanded. If the parent doesn't exist, the installer creates it and notes that it did.

The instance is then created at `<parent>/<name>/`, holding `instance/`, `home/`, `tomo-install.json`, and `begin-tomo.sh`.

### 1. Vault Path

Point Tomo at your Obsidian vault directory. The script validates the path exists and checks for `.obsidian/`.

### 2. Framework Profile

Choose your PKM framework:
- **miyo** — Marcus's vault conventions (LYT-derived with customizations)
- **lyt** — Standard LYT/Ideaverse Pro conventions
- **custom** — Start from scratch

The profile provides default folder mappings, classification categories, and relationship markers. Everything can be overridden later.

### 3. Concept Mapping

For each concept (inbox, notes, maps, calendar, projects, areas, sources, templates, assets) you have three options at each prompt:

- **`d`** — accept the profile default
- **`b`** — launch the directory browser to drill into your vault structure
- **Type a path directly** — for quick manual entry

The directory browser lets you navigate: number keys descend into a subfolder, `0` goes back up, `d` confirms the current path. After each concept, `[b]` takes you back to re-do the previous one, and a final summary lets you jump back to any concept before confirming all.

### 4. Kado Connection

- **Host** — where Kado runs (default: `host.docker.internal` for Docker)
- **Port** — Kado port (default: `23026`, matching Kado's desktop-only bind on `127.0.0.1:23026`)
- **Bearer token** — your Kado API key (must start with `kado_`)

### 5. Git User Configuration

Tomo sets up a git identity so commits made inside the Docker container are attributed correctly. The script reads your host's global git config and offers three options:

- **Use host values** (recommended) — reuses your `git config --global user.name/email`
- **Enter different values** — prompts for name and email
- **Skip** — no git config; you can set it manually later

The values are written to the instance's `home/.gitconfig` (global for the container user). The instance directory itself is **not** git-initialised.

### Tomo Context — live editor context (optional)

*Tomo Context* connects Claude Code inside the container to your live Obsidian editor through the [Tomo Hashi](https://github.com/MMoMM-org/miyo-tomo-hashi) plugin's IDE Bridge. When enabled, Claude can see your **active note, selection, and cursor position** in real time — so a request like "summarise the note I'm looking at" works without pasting a path.

The wizard step is labelled **Hashi IDE Bridge**. To enable it, grab two things from the Hashi plugin in Obsidian:

- **Auth token** — Hashi generates a `hashi_<uuid>` token; copy it from Hashi's settings. The wizard rejects anything not in `hashi_<uuid>` form.
- **Port** — must match the port Hashi listens on (Hashi's default is `23027`). If you change it on one side, change it on the other; a mismatch is the most common failure.

The wizard writes an IDE lock file to `tomo-home/.claude/ide/<port>.lock` and records the choice in `tomo-install.json`. On the next launch the container spawns a `socat` proxy (container `localhost:<port>` → `host.docker.internal:<port>`) and auto-connects Claude Code to the bridge — no manual `/ide` needed.

> **The green Hashi icon means *connected*, not *working*.** It confirms the socket handshake only — it does **not** verify that editor context is actually flowing or that the rest of Hashi is healthy. If the icon is green but context isn't reaching Claude, see [Troubleshooting → Tomo Context](troubleshooting.md#tomo-context-ide-bridge) and Hashi's own [context guide](https://github.com/MMoMM-org/miyo-tomo-hashi/blob/main/docs/context.md).

Change or disable Tomo Context anytime by re-running `install-tomo.sh` or `update-tomo.sh`.

### 6. Instance Creation

The script creates your instance under `<parent>/<name>/instance/` with agents, commands, skills, and config files copied from `tomo/` source. It writes an instance-level `.gitignore` (excluding `.mcp.json` with your Kado token, and runtime state) for users who later choose to `git init` the instance themselves.

The instance is **not** git-initialised by the installer — it is bind-mounted infrastructure, not a code project, and a nested `.git/` inside a gitignored directory has caused accidental wipes in the past. Versioning lives in the host source repo.

### 7. Docker Home Setup + Launcher Generation

Sets up `<parent>/<name>/home/` as the Docker `/home/coder` mount, including Claude Code auth from your host (if available) and the `.gitconfig` from step 5. Then renders `scripts/lib/begin-tomo.sh.template` into `<parent>/<name>/begin-tomo.sh` with all paths baked in — this is the launcher you run to start sessions for this instance.

### 8. Registry Update

Finally, the installer records the instance in `~/.tomo/instances.json` (name → path → source repo → version) so future install/update runs can find it. The registry is a rebuildable index: if it's lost, your instances still launch via their own `begin-tomo.sh`, and the next install re-creates the entry. A registry write failure does not abort an otherwise successful install.

## Launcher (begin-tomo.sh)

Each instance has its own launcher with hardcoded paths, generated at `<parent>/<name>/begin-tomo.sh` (default parent `~/MiYo/Tomo`). Run the launcher for the instance you want to start:

```bash
bash ~/MiYo/Tomo/<name>/begin-tomo.sh                 # start Claude Code in the container
bash ~/MiYo/Tomo/<name>/begin-tomo.sh --rebuild-image # force Docker image rebuild
bash ~/MiYo/Tomo/<name>/begin-tomo.sh --bash          # launch a bash shell (debugging)
bash ~/MiYo/Tomo/<name>/begin-tomo.sh --help          # show all options
```

**First run**: The launcher builds the Docker image from the source repo's `docker/` automatically. Subsequent runs reuse the existing image unless you pass `--rebuild-image`.

**Update check**: On every launch the launcher compares this instance's installed `tomoVersion` against the source repo's current version (via the source path baked in at install). If the instance is **behind**, it prints the installed and available versions and asks `Update now? [y/N]`:

- **`y`** — runs `update-tomo.sh --instance <name>` for you, then relaunches.
- **anything else** — launches the current version anyway.

The check is non-fatal: if the source repo or version info can't be read, it is skipped silently and never blocks launch.

**Re-auth**: When your Claude Code credentials expire or you want to switch accounts, run `claude login` inside the container. Port 10000 (the OAuth callback) is not exposed by default — normal operation runs off the mounted credentials. Expose it for the in-container login by passing `--auth-port` for a single launch, or set `"exposeAuthPort": true` in `tomo-install.json` to make it persistent; the login then completes without restarting Tomo.

**Regenerating**: The launcher is regenerated every time you run `install-tomo.sh` or `update-tomo.sh` for that instance — re-run either if paths change.

## Non-Interactive Mode

For automated setups, `--non-interactive` uses defaults for every prompt (and requires at least `--vault`). Name and place the instance with `--instance-name` and `--instance-location` (the parent dir):

```bash
bash scripts/install-tomo.sh \
  --vault /path/to/vault \
  --profile miyo \
  --kado-host host.docker.internal \
  --kado-port 23026 \
  --kado-token kado_your_token \
  --instance-name work \
  --instance-location ~/MiYo/Tomo \
  --non-interactive
```

By default a `--instance-name` that already exists in the registry is rejected as a duplicate. To re-run setup against an existing instance non-interactively, add `--update` (which requires `--instance-name`):

```bash
bash scripts/install-tomo.sh --update --instance-name work --vault /path/to/vault --non-interactive
```

## After Installation

### First Session — Explore Your Vault

Start Tomo and run the vault explorer:

```
/explore-vault
```

This scans your vault via Kado to discover:
- Folder structure and note counts
- Frontmatter field patterns
- Tag taxonomy
- Relationship markers (up::, related::)
- Callout usage (editable vs protected)
- MOC hierarchy and topics

You confirm each discovery step. Results are written to `vault-config.yaml` and `discovery-cache.yaml`.

### Processing Inbox

Once exploration is complete:

```
/inbox
```

Tomo auto-detects what to do next based on each item's `tomo.state` frontmatter.

## Authentication

### Existing Claude Code User

The install script extracts auth from `~/.claude.json` and `~/.claude/.credentials.json` automatically.

### First-Time User

1. Run your instance's launcher: `bash ~/MiYo/Tomo/<name>/begin-tomo.sh`
2. Claude Code prompts for authentication
3. Follow the browser login flow
4. See [Troubleshooting](troubleshooting.md) if the auth callback fails

## Updating an Instance

Update a single instance by name; the path is resolved through the registry:

```bash
bash scripts/update-tomo.sh --instance <name>   # update the named instance
bash scripts/update-tomo.sh --instance <name> --dry-run   # show the plan, write nothing
```

The update runs in two passes — a no-write pre-flight scan that shows what will change (current / update / create / retire), then a confirmation before any writes. It overwrites managed files whose `# version:` changed, skips your user files, re-renders that instance's launcher, refreshes its `tomoVersion`, and updates the registry entry.

You normally don't run this by hand: each instance's `begin-tomo.sh` offers to update itself when it detects the instance is behind the source (see [Launcher → Update check](#launcher-begin-tomosh)).

`--config-file <path>` targets a `tomo-install.json` directly instead of resolving by name (used mainly for test isolation); it is mutually exclusive with `--instance`.

## Instance Git Repository

The installer does **not** git-initialise the instance directory. It is bind-mounted infrastructure, not a code project, and versioning lives in the host source repo. A nested `.git/` inside a gitignored directory has caused accidental wipes, so install avoids it deliberately.

The installer still writes a `.gitignore` at the instance so that if you choose to `git init` the instance yourself, sensible defaults apply. It excludes:
- `.mcp.json` — contains your Kado bearer token, never commit this
- `.claude/settings.local.json`, `.claude/*.log`, `.claude/cache/` — Claude Code runtime state
- `tomo-tmp/` — pipeline scratch
- OS cruft (`.DS_Store`, `Thumbs.db`)

## Cleanup / Re-install

For a clean re-run (useful during testing or after config mistakes):

```bash
bash scripts/cleanup-tomo.sh              # interactive with confirmation
bash scripts/cleanup-tomo.sh --force      # skip confirmation
bash scripts/cleanup-tomo.sh --dry-run    # preview what would be removed
bash scripts/cleanup-tomo.sh --keep-home  # preserve Claude auth credentials
```

The cleanup script removes `tomo-instance/`, `tomo-home/`, and `tomo-install.json`. It refuses to delete anything outside the repo root as a safety check.
