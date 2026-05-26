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

For the launcher's other modes (`--rebuild-image`, `--bash`, `--auto`, `--yolo`, `-h`), see [Launcher flags and slash commands](#launcher-flags-and-slash-commands) below, or [Setup Guide → Launcher](setup.md#launcher-begin-tomosh) for the long-form description.

If this is your first session after install, run `/tomo-setup` — it walks the post-install wizards (vault discovery, user rules, templates, trackers, daily log) end to end. After that, day-to-day work centres on `/inbox`.

## Common workflows

### Process inbox items

This is the day-to-day loop. When new items have landed in your inbox folder (voice memos tagged `<lifecycle-prefix>/captured`, web clips, quick captures, anything ready for triage), run:

```
/inbox
```

`/inbox` runs the **2-pass workflow**:

1. **Pass 1 — Suggestions.** Analysts read each captured item and propose what should happen to it: classification, tags, MOC links, target folder. The result is a markdown suggestions document at `<inbox>/<YYYY-MM-DD_HHMM>_suggestions.md`. Nothing is moved or rewritten in the vault yet.
2. **You review and approve.** Open the suggestions doc. Each action has a tri-state checkbox (Approve / Skip / Delete source); flip the boxes you want, then check the top-level `[x] Approved` header when ready.
3. **Pass 2 — Instructions.** Tomo expands the approved suggestions into a concrete instruction set with file-level actions (write_file, link, tag, archive). It runs automatically when `/inbox` next sees an approved suggestions doc — or force it with `/inbox --pass2`.
4. **Apply the actions.** Tomo doesn't write outside the inbox; this step is yours. Two paths:
    - **Manually**: open the instruction set in Obsidian, perform each action yourself (write note, add link, set tag), tick `[x] Applied` per action.
    - **Via Tomo Hashi**: run the instruction-set executor in [Tomo Hashi](https://github.com/MMoMM-org/miyo-tomo-hashi) on the file. Choose preview mode — `Preview on` (approve each action), `Preview off` (visible apply), or `No confirmation` (background).
5. **Cleanup.** Re-run `/inbox`. When it sees an instruction set with all actions applied (whether by hand or by Hashi), `state-promoter.py` transitions source items from `<prefix>/captured` to `<prefix>/active` and `mark-captured.py` archives completed workflow docs per your vault-config rules.

`/inbox` is auto-resumable: it inspects checkbox state in existing suggestions and instruction docs to decide whether to run Pass 1, run Pass 2, run cleanup, or do nothing. Force a specific phase with `/inbox --pass1`, `/inbox --pass2`, or `/inbox --cleanup`.

### Refresh vault discovery

When you've reorganised folders, added new MOCs, or changed tag conventions, refresh the discovery cache:

```
/explore-vault            # silent rebuild (uses prior confirmations)
/explore-vault --confirm  # walk through every detection step again
```

Discovery writes `tomo-instance/config/discovery-cache.yaml` and may update `vault-config.yaml` for the sections it owns (tags, callouts, relationships, trackers). Each section asks for confirmation before writing. Your vault is never modified — only Tomo's config files. See [Configuration → Override mechanism](configuration.md#override-mechanism) for how the cache fits into the layer precedence.

### Re-run a setup wizard

Conventions evolve. Refresh just one part of the setup without re-running the full installer:

```
/tomo-setup            # full post-install wizard (recommended after every install)
/tomo-setup rules      # user-rules wizard only (Phase 3)
/tomo-setup templates  # template verification only (Phase 4)
/tomo-setup trackers   # tomo-trackers-wizard skill
/tomo-setup daily-log  # tomo-daily-log-wizard skill
```

Wizards write to `tomo-instance/config/` (sections of `vault-config.yaml` they own, or files under `user-rules/`). They never touch the vault.

### Get help in-session

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
  - The lifecycle tag on **inbox source items** flips from `<prefix>/captured` to `<prefix>/active` once you've applied their actions and `/inbox` cleanup runs.

### What Tomo never writes

- Atomic notes (`Atlas/202 Notes/` or wherever your `concepts.atomic_note` points).
- MOC notes, daily notes, project notes, source notes.
- Frontmatter or body of any existing note outside the inbox.
- Any vault file other than the suggestions and instructions documents Tomo itself produced inside the inbox.

When you approve a suggestions doc and Tomo runs Pass 2, the result is an **instruction set** — a markdown document with concrete `write_file`, `link`, `tag`, `archive` actions. You apply those actions one of two ways: by hand in Obsidian (write the new note, add the link, set the tag, tick `[x] Applied`) or via [Tomo Hashi](https://github.com/MMoMM-org/miyo-tomo-hashi)'s instruction-set executor with your chosen preview mode. Either way, the next `/inbox` run sees the fully-applied instruction set and runs cleanup: `state-promoter.py` transitions source-item lifecycle states and `mark-captured.py` archives completed workflow docs.

### Success markers per workflow

| Workflow | What "success" looks like |
|---|---|
| `bash begin-tomo.sh` | Claude Code starts in the container; the instance prompt appears; `/tomo-help` works. If Kado is unreachable you'll see a connection error from `kado-*` MCP calls. |
| `/explore-vault` | Each detection step prompts for confirmation; on accept, the corresponding section of `vault-config.yaml` updates. `discovery-cache.yaml` is rewritten at the end. |
| `/inbox` Pass 1 | A `_suggestions.md` file appears in your inbox folder. Per-item analyst counts and any failures are reported. |
| `/inbox` Pass 2 | A `_instructions.md` file appears in your inbox folder. The orchestrator reports an action count and a coverage audit. |
| You apply the instruction set | Each action is applied — manually in Obsidian (tick `[x] Applied` per action) or via Tomo Hashi's instruction-set executor. |
| `/inbox` cleanup | The next `/inbox` run runs cleanup: `state-promoter.py` transitions source items `<prefix>/captured` → `<prefix>/active`; `mark-captured.py` archives fully-applied workflow docs per your vault-config rules. |
| `/tomo-setup <section>` | The relevant `config/` files are updated. The wizard prints a per-phase summary so you can see what was written. |

### Lifecycle tag namespace

Tomo tracks every inbox source item's state via tags under your `lifecycle.tag_prefix` (default `MiYo-Tomo`):

| Tag | Meaning |
|---|---|
| `<prefix>/captured` | Item is in the inbox, waiting to be processed. |
| `<prefix>/active` | Item has been processed: its actions were applied and `/inbox` cleanup transitioned it. |

Source items carry exactly one of these tags at any time. Workflow documents (suggestions, instructions) **don't** carry lifecycle tags — their state is read from checkbox state (`[ ] Approved` on suggestions, `[ ] Applied` per action on instruction sets).

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

OAuth re-auth doesn't have a dedicated launcher flag. When your credentials expire, run `claude login` inside the container (the launcher always exposes port 10000 for the OAuth callback).

### Slash commands inside the session

Run from the Claude Code prompt once you're in a session.

| Command | Purpose | Arguments |
|---|---|---|
| `/inbox` | 2-pass workflow + cleanup; auto-detects which phase to run. | `--pass1`, `--pass2`, `--cleanup` to force a specific phase. |
| `/explore-vault` | Vault discovery; populates `vault-config.yaml` and `discovery-cache.yaml`. | `--confirm` re-runs every detection step with prompts. |
| `/tomo-setup` | Post-install wizard (recommended after every install). | `rules`, `templates`, `trackers`, `daily-log` to run a single phase. |
| `/tomo-help` | Context-aware help. | A topic keyword (e.g. `inbox`, `kado`, `docker`, `login`); empty for a topic menu. |

Each command has a fuller spec inside its own definition — see `tomo-instance/.claude/commands/<command>.md` for the latest behaviour and edge cases.
