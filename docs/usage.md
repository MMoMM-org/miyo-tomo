# Usage

Day-to-day Tomo: starting a session, common workflows, what Tomo writes versus what stays your responsibility, and the launcher and slash-command reference.

## Starting a session

Once installed, every Tomo session starts the same way:

```bash
bash begin-tomo.sh
```

The launcher builds the Docker image on first run, then drops you into a Claude Code session inside the container. Working directory is your instance path (`<repo-root>/tomo-instance/` for the default install); your vault is **not** bind-mounted — Tomo talks to your vault through Kado over `host.docker.internal:23026`, so Kado must be running before you launch.

Inside the session you steer Tomo two ways:

- **Slash commands** for structured workflows (`/inbox`, `/explore-vault`, `/tomo-setup`, `/tomo-help`).
- **Conversational chat** for ad-hoc requests; agents and the Kado MCP tools are available the whole time.

If you enabled **Tomo Context** at install (the Hashi IDE Bridge), Claude also receives live editor context from Obsidian — your active note, selection, and cursor — as long as Obsidian and the [Tomo Hashi](https://github.com/MMoMM-org/miyo-tomo-hashi) plugin are running. The container auto-connects on launch. Note: the green icon in Obsidian shows the connection is up, **not** that context is flowing — see [Troubleshooting → Tomo Context](troubleshooting.md#tomo-context-ide-bridge) if Claude doesn't see your editor.

For the launcher's other modes (`--rebuild-image`, `--bash`, `--auto`, `--yolo`, `-h`), see [Launcher flags and slash commands](#launcher-flags-and-slash-commands) below, or [Setup Guide → Launcher](setup.md#launcher-begin-tomosh) for the long-form description.

If this is your first session after install, run `/tomo-setup` — it walks the post-install wizards (vault discovery, user rules, templates, trackers, daily log) end to end. After that, day-to-day work centres on `/inbox`.

## Common workflows

Each job has its own page:

- [Process inbox items](workflows/inbox.md)
- [Refresh vault discovery](workflows/explore-vault.md)
- [How Tomo proposes new MOCs](workflows/moc-propose.md), including how to exclude notes
- [Audit your vault](workflows/garden-audit.md)
- [Author a Hashi hook](workflows/hashi-hooks.md)

## Re-run a setup wizard

Conventions evolve. Refresh just one part of the setup without re-running the full installer:

```
/tomo-setup            # full post-install wizard (recommended after every install)
/tomo-setup rules      # user-rules wizard only (Phase 3)
/tomo-setup templates  # template verification only (Phase 4)
/tomo-setup trackers   # tomo-trackers-wizard skill
/tomo-setup daily-log  # tomo-daily-log-wizard skill
```

Wizards write to `tomo-instance/config/` (sections of `vault-config.yaml` they own, or files under `user-rules/`). They never touch the vault.

To stop Tomo proposing a tracker, run `/tomo-setup trackers` and choose **Deactivate** on that field. Tomo keeps the definition and adds `active: false`. **Reactivate** in the same wizard turns it back on.

## Get help in-session

`/tomo-help` is context-aware. With no argument it shows a topic menu; with a keyword it routes to the most relevant section:

```
/tomo-help              # menu
/tomo-help inbox        # /inbox workflow
/tomo-help kado         # Kado connection / token issues
/tomo-help docker       # container / launcher
/tomo-help login        # OAuth re-auth
```

## What Tomo does and doesn't change

Tomo's contract is **proposal-first and write-bounded**: Tomo only writes to the inbox folder of your vault and to its own instance directory. Notes outside the inbox — atomic notes, MOCs, daily notes, projects, sources — are written by **you**, by hand in Obsidian, after reviewing Tomo's instruction set.

### What Tomo writes itself

- **Inside the instance** (`tomo-instance/`):
  - `config/vault-config.yaml`, `config/discovery-cache.yaml` — written by `/explore-vault` and `/tomo-setup` after you confirm each detection section.
  - `config/user-rules/*.md` — written by `/tomo-setup rules` (your `README.md` is preserved).
  - `tomo-tmp/` — scratch state used between Pass 1 and Pass 2 (per-item analysis JSON, fan-out reductions, render outputs).
  - `voice/config.json` — refreshed by the installer / `update-tomo.sh`.
- **Inside your vault, but only in the inbox folder**:
  - `<inbox>/<YYYY-MM-DD_HHMM>_suggestions.md` — Pass 1 output.
  - `<inbox>/<YYYY-MM-DD_HHMM>_instructions.md` — Pass 2 output.
  - The `tomo.state` frontmatter field on **inbox source items**, set to `captured` when Pass 1 dispatches them. `captured` is the final state for a source item — it never changes again, and applying the actions does not change it.

### What Tomo never writes

- Atomic notes (`Atlas/202 Notes/` or wherever your `concepts.atomic_note` points).
- MOC notes, daily notes, project notes, source notes.
- Frontmatter or body of any existing note outside the inbox.
- Any vault file other than the suggestions and instructions documents Tomo itself produced inside the inbox.

When you approve a suggestions doc and Tomo runs Pass 2, the result is an **instruction set** — a markdown document with concrete `write_file`, `link`, `tag`, `archive` actions. You apply those actions one of two ways: by hand in Obsidian (write the new note, add the link, set the tag, tick `[x] Applied`) or via [Tomo Hashi](https://github.com/MMoMM-org/miyo-tomo-hashi)'s instruction-set executor with your chosen preview mode. Either way, the applied set and its suggestions doc **stay where they are**. Tomo does not delete or archive them, and neither does Hashi today — removing them is yours to do, whenever you want to.

### Success markers per workflow

| Workflow | What "success" looks like |
|---|---|
| `bash begin-tomo.sh` | Claude Code starts in the container; the instance prompt appears; `/tomo-help` works. If Kado is unreachable you'll see a connection error from `kado-*` MCP calls. |
| `/explore-vault` | Each detection step prompts for confirmation; on accept, the corresponding section of `vault-config.yaml` updates. `discovery-cache.yaml` is rewritten at the end. |
| `/inbox` Pass 1 | A `_suggestions.md` file appears in your inbox folder. Per-item analyst counts and any failures are reported. |
| `/inbox` Pass 2 | A `_instructions.md` file appears in your inbox folder. The orchestrator reports an action count and a coverage audit. |
| You apply the instruction set | Each action is applied — manually in Obsidian (tick `[x] Applied` per action) or via Tomo Hashi's instruction-set executor. |
| The run after you applied | `/inbox` reports **`idle`**, naming *"All approved items already covered by existing instructions"*. That is the success marker: the work is recorded as done and will not be redone. Nothing is deleted or archived — the applied set and its suggestions doc stay in the inbox until you remove them. |
| `/tomo-setup <section>` | The relevant `config/` files are updated. The wizard prints a per-phase summary so you can see what was written. |

### Lifecycle state

Tomo tracks every inbox source item's state in a hidden `tomo.state` frontmatter field — not a tag. You never add or edit it by hand; Tomo writes it automatically. A source item has exactly **one** state:

| `tomo.state` | Meaning |
|---|---|
| `captured` | Pass 1 has picked the item up. This is the only state a source item ever has — it is set once and never changes, including after you apply the actions. |

Applying the actions does not advance it, because the item's own fate is already recorded in the instruction set: either an action moved it, or a `delete_source` removed it, or it was skipped and stays. The state field answers "has Pass 1 seen this", nothing more. Because the field is frontmatter rather than a tag, it stays out of your tag pane. The signals you *do* see are filename conventions, body checkboxes (`[ ] Approved` on suggestions, `[ ] Applied` per action on instruction sets), and the per-run `/inbox` summary. Workflow documents (suggestions, instructions) don't carry a `tomo.state` — their progress is read from those checkboxes.

## Launcher flags and slash commands

### `begin-tomo.sh` — host-side launcher

Run from your host shell. Default behaviour (no flag) is a standard interactive Claude Code session inside the container; every vault-touching action prompts for permission.

| Flag | Effect |
|---|---|
| *(none)* | Standard interactive session — Claude Code prompts for every permission. |
| `--rebuild-image` | Force a rebuild of the Tomo Docker image before launch. Use after editing `docker/` or pulling source updates. |
| `--auto` | Auto mode — Claude Code's AI classifier approves "safe" actions automatically (`--permission-mode auto`); the user is still prompted for risky ones. |
| `--yolo` | Skip all permission prompts (`--dangerously-skip-permissions`). Trusted use only. |
| `--bash` | Launch a bash shell inside the container instead of Claude Code. For debugging the runtime environment. |
| `--help`, `-h` | Print the launcher help and exit. |

You can set a persistent default mode in `tomo-install.json`'s `defaultMode` field — values: `default`, `auto`, `yolo`, `bash`. The CLI flag still wins for that invocation.

OAuth re-auth: when your credentials expire, run `claude login` inside the container. Port 10000 (the OAuth callback) is not exposed by default — normal operation runs off the mounted credentials. Pass `--auth-port` for a single launch, or set `"exposeAuthPort": true` in `tomo-install.json` persistently, so the in-container login can complete.

### Slash commands inside the session

Run from the Claude Code prompt once you're in a session.

| Command | Purpose | Arguments |
|---|---|---|
| `/inbox` | 2-pass workflow; auto-detects which phase to run. | `--pass1`, `--pass2` to force a phase; `--force`, `--recover`. See [Forcing a phase](workflows/inbox.md#forcing-a-phase). |
| `/explore-vault` | Vault discovery; populates `vault-config.yaml` and `discovery-cache.yaml`. | `--confirm` re-runs every detection step with prompts. |
| `/tomo-setup` | Post-install wizard (recommended after every install). | `rules`, `templates`, `trackers`, `daily-log` to run a single phase. |
| `/moc-propose` | Live vault scan for new MOC proposals. See [How Tomo proposes new MOCs](workflows/moc-propose.md). | Scope such as `tag:`, `folder:`, `class:`, `title:` or free text. |
| `/garden-audit` | Audit the vault for structural problems. See [Audit your vault](workflows/garden-audit.md). | `audit`, `configure`, `suggest`, `stats`. |
| `/hashi-hook` | Draft a Tomo Hashi hook. See [Author a Hashi hook](workflows/hashi-hooks.md). | Optional description of the behaviour you want. |
| `/tomo-help` | Context-aware help. | A topic keyword (e.g. `inbox`, `kado`, `docker`, `login`); empty for a topic menu. |

Each command has a fuller spec inside its own definition — see `tomo-instance/.claude/commands/<command>.md` for the latest behaviour and edge cases.
