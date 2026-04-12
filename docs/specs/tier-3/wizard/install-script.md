# Tier 3: Install Script (Phase 1)

> Parent: [Setup Wizard](../../tier-2/components/setup-wizard.md)
> Status: Implemented

---

## 1. Purpose

Define the Phase 1 setup that runs during `install-tomo.sh` on the host machine. No Kado required. Produces a starter `vault-config.yaml`, an initialized instance repo, and a generated `begin-tomo.sh` launcher sufficient to boot Tomo.

## 2. Environment

- **Runs on:** Host machine (macOS or Linux)
- **No AI involved:** Deterministic shell script, user-interactive
- **Filesystem access:** Can `ls` the vault directory directly (drill-down browser)
- **No Kado:** Kado may not be running yet
- **Output:** `vault-config.yaml`, instance directory, `tomo-home/`, generated `begin-tomo.sh` launcher, `tomo-install.json`

## 3. Script Flow

```
install-tomo.sh
       │
       ▼
  ┌────────────────────┐
  │  1. Welcome         │  ANSI logo + version banner
  │                     │  Check prerequisites (docker, git, jq)
  └──────────┬─────────┘
             │
             ▼
  ┌────────────────────┐
  │  2. Vault Path      │  "Where is your Obsidian vault?"
  │                     │  Validate directory, warn if no .obsidian/
  │                     │  List top-level folders (numbered)
  └──────────┬─────────┘
             │
             ▼
  ┌────────────────────┐
  │  3. Framework       │  "Which PKM framework?"
  │     Selection       │  Options: miyo | lyt | custom
  │                     │  Load profile defaults
  └──────────┬─────────┘
             │
             ▼
  ┌────────────────────┐
  │  4. Concept         │  For each concept (9 total):
  │     Mapping         │  Prompt d=default / b=browse / type path
  │                     │  Browser drills into vault subdirectories
  │                     │  After each concept: [Enter] next | [b] back
  │                     │  Final summary with last-chance back-nav
  └──────────┬─────────┘
             │
             ▼
  ┌────────────────────┐
  │  5. Lifecycle       │  "Tag prefix for Tomo states?"
  │     Prefix          │  Default: MiYo-Tomo
  └──────────┬─────────┘
             │
             ▼
  ┌────────────────────┐
  │  6. Kado            │  "Kado MCP connection:"
  │     Connection      │  Host (default: host.docker.internal)
  │                     │  Port (default: 23026)
  │                     │  Protocol: http (hardcoded, no prompt)
  │                     │  Bearer token (must start with kado_)
  └──────────┬─────────┘
             │
             ▼
  ┌────────────────────┐
  │  6b. Git User       │  Read host's global git config
  │     Configuration   │  Options: use host values (recommended)
  │                     │           / enter different / skip
  │                     │  Applies to tomo-home/.gitconfig and
  │                     │  instance repo local config
  └──────────┬─────────┘
             │
             ▼
  ┌────────────────────┐
  │  7. Generate        │  Write vault-config.yaml with:
  │     Config          │  - schema_version: 1
  │                     │  - profile + version
  │                     │  - concept paths (confirmed)
  │                     │  - lifecycle prefix
  │                     │  Profile defaults for everything else
  └──────────┬─────────┘
             │
             ▼
  ┌────────────────────┐
  │  8. Instance        │  Create instance dir + .claude subtree
  │     Setup           │  Copy managed files from tomo/
  │                     │  Render CLAUDE.md, vault-config rule,
  │                     │  kado-config rule from templates
  │                     │  Write .mcp.json (Kado bearer)
  │                     │  Set up tomo-home/ (auth, .gitconfig)
  └──────────┬─────────┘
             │
             ▼
  ┌────────────────────┐
  │  8b. Generate       │  sed-render scripts/begin-tomo.sh.template
  │      Launcher       │  → $INSTANCE_LOCATION/begin-tomo.sh
  │                     │  with {{INSTANCE_PATH}}, {{HOME_DIR}},
  │                     │  {{TOMO_REPO_ROOT}}, etc. substituted
  │                     │  chmod +x the result
  └──────────┬─────────┘
             │
             ▼
  ┌────────────────────┐
  │  9. Instance        │  Write instance .gitignore
  │     Git Init        │  (.mcp.json, runtime state, OS cruft)
  │                     │  git init + local user config
  │                     │  symbolic-ref HEAD → main
  │                     │  Initial commit (non-blocking on failure)
  │                     │  Skip if instance already has .git/
  └──────────┬─────────┘
             │
             ▼
  ┌────────────────────┐
  │  10. Done           │  "Run: bash <launcher path>"
  │                     │  Docker image is NOT built here —
  │                     │  the generated launcher builds it on
  │                     │  first run (or with --rebuild-image).
  │                     │  "First run: /explore-vault"
  └────────────────────┘
```

## 4. Concept Mapping UX

For each concept the script prints a styled header and three short options:

```
  ── Inbox ──
  Profile default: 100 Inbox/

  d=accept default  b=browse vault  or type a path
  >
```

**Three input modes:**

1. **`d` or Enter** — accept the profile default
2. **`b`** — launch the directory browser
3. **type a path** — direct entry, trailing slash added automatically

**Directory browser** (`b`): starts at the profile default's parent (or vault root if that fails). Shows numbered subdirectories:

```
  Browsing: Atlas/

    1. 200 Maps/
    2. 202 Notes/
    3. 290 Assets/

   0=↑ up  d=done (use current)  or type a path
  >
```

- **Number** (1, 2, ...) — drill into that subdirectory
- **`0`** — go up one level (disabled at vault root)
- **`d` or Enter** — confirm current path
- **direct path** — exit browser with that path

**Back-navigation between concepts:**

After each concept is set, the script shows:

```
  [Enter] next  |  [b] go back
```

`[b]` re-enters the previous concept so the user can fix mistakes without starting over. After the last concept, a summary is shown:

```
  ─── Configured so far ───
  ✓ Inbox                    100 Inbox/
  ✓ Atomic Notes             Atlas/202 Notes/
  ...
  [Enter] confirm  |  [b] go back to last concept
```

The user can keep pressing `[b]` to step backwards through all concepts until they're happy.

## 4b. Deferred Concept Details

One concept field is NOT prompted during install — it is taken from the profile as a starting point and refined later by `/explore-vault`:

| Field | Source during install | Refined by |
|-------|----------------------|------------|
| `map_note.tags[0]` | profile `map_note.tags[0]` | `/explore-vault` — reads actual MOC files to detect tag patterns |

This requires reading actual vault content via Kado, so it intentionally belongs to Phase 2.

One additional field is prompted interactively rather than deferred:

| Field | Prompt behavior |
|-------|----------------|
| `calendar.granularities.daily.path` | Asked as a follow-up after calendar base path, using the profile default as suggestion. |

## 5. Validation

The script validates at each step:

| Check | Failure behavior |
|-------|-----------------|
| Vault directory exists | Error, re-prompt |
| `.obsidian/` exists in vault | Warning (might not be an Obsidian vault), continue |
| Profile name is valid | Error, re-prompt |
| Concept path exists in vault | Warning (folder doesn't exist yet — OK for new setups), continue |
| Kado connection works | Warning (Kado may be offline — OK, Phase 2 will handle), continue |
| Bearer token format (`kado_*`) | Error, re-prompt |

## 6. Output: vault-config.yaml

The generated config contains only the fields the user confirmed. Everything else falls back to profile defaults at runtime.

```yaml
# Generated by install-tomo.sh on 2026-04-09
schema_version: 1

profile: miyo
profile_version: "1.0"

concepts:
  inbox: "+/"
  atomic_note:
    base_path: "Atlas/202 Notes/"
  map_note:
    paths:
      - "Atlas/200 Maps/"
    tags:
      - "type/others/moc"
  calendar:
    base_path: "Calendar/"
    granularities:
      daily: { enabled: true, path: "Calendar/Days/" }
  project: "Efforts/Projects/"
  area: "Efforts/Areas/"

lifecycle:
  tag_prefix: "MiYo-Tomo"

# Everything else (naming, templates, frontmatter, relationships, 
# callouts, tags) comes from the profile defaults.
# Run /explore-vault in Tomo to detect and configure these.
```

## 7. What Phase 1 Does NOT Do

- **No frontmatter detection** — requires reading note content (needs Kado)
- **No tag taxonomy detection** — requires `kado-search listTags`
- **No callout classification** — requires reading note bodies
- **No template configuration** — requires reading template files
- **No relationship marker detection** — requires reading inline fields
- **No discovery cache** — requires full vault scan via Kado

All of these happen in Phase 2 (`/explore-vault` on first Tomo session).

## 8. Re-Running the Install Script

`install-tomo.sh` can be re-run safely:
- **Existing `tomo-install.json`:** script offers to reuse the config (skips prompts for instance location, Kado, etc.)
- **Existing `vault-config.yaml`:** script asks "overwrite or cancel"
- **Existing instance `.git/`:** git init is skipped to preserve history
- **Existing launcher:** overwritten with freshly rendered values
- **Docker image:** NOT touched by install-tomo.sh — the generated launcher handles builds

`scripts/cleanup-tomo.sh` provides a clean-slate option for testing: removes instance, tomo-home, launcher, and install config.

## 9. Generated Launcher

After the install completes, the user runs `begin-tomo.sh` (generated at `$INSTANCE_LOCATION`). The launcher is a rendered copy of `scripts/begin-tomo.sh.template` with these placeholders substituted at install time:

| Placeholder | Value |
|-------------|-------|
| `{{INSTANCE_PATH}}` | Absolute path to instance dir |
| `{{INSTANCE_NAME}}` | Instance dir basename |
| `{{HOME_DIR}}` | Path to tomo-home/ |
| `{{TOMO_REPO_ROOT}}` | Path to this repo (for Docker build + version check) |
| `{{DEV_NOTIFY_PORT}}` | dev-notify-bridge port (default 9999) |

The launcher accepts:
- `--rebuild-image` — force `docker build` before launch
- `--login` — force OAuth re-auth (exposes port 10000)
- `--bash` — launch bash instead of claude (debugging)
- `--auto` — Auto mode — AI classifier approves safe actions (`--permission-mode auto`)
- `--yolo` — Skip all permission prompts (`--dangerously-skip-permissions`). Safe in Tomo's sandboxed Docker container.
- `--help` — show help

First-run builds the image automatically from `$TOMO_REPO_ROOT/docker/Dockerfile`. All subsequent runs reuse the cached image unless `--rebuild-image` is passed.

## 10. Non-Interactive Mode

For automation (CI, test harnesses), the script supports flags:

```bash
install-tomo.sh \
  --vault /path/to/vault \
  --profile miyo \
  --kado-host host.docker.internal \
  --kado-port 23026 \
  --kado-token kado_abc123 \
  --prefix MiYo-Tomo \
  --non-interactive
```

In non-interactive mode:
- All prompts use defaults from the profile + provided flags
- No user confirmation
- Git user config is taken from the host's `git config --global` (if set), otherwise skipped
- Instance location defaults to the Tomo repo root; instance name to `tomo-instance`
