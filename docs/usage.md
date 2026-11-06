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
- [Write a note from a template](#write-a-note-from-a-template)

## Write a note from a template

`/note` turns your material into a note built from one of your vault templates. You can type the request, point it at a note in your inbox, or both. Like the rest of Tomo it only proposes: the note lands in your inbox with an instruction set, and nothing reaches its final folder until you apply the instruction set in Tomo Hashi.

### Modes

- `/note <request>` — for example `/note meeting with the design team`, or `/note meeting notes from 100 Inbox/Meeting raw.md`. Tomo picks the matching template (and asks you when several fit), shows which template points your material already covers, and asks about the open ones in at most two rounds. It then prints the full draft with the template, the final name and place, the points left empty and, for an inbox-note source, that the source is deleted when you apply the instruction set. You can change anything, including keeping the source instead of having it deleted on apply, then approve to deliver or abort. Questions about a list or the draft appear as a dialog with numbered options such as `1 Deliver · 2 Change something · 3 Abort`; the draft (or the list) shows in the dialog's preview box, and typing the number or the word still answers. If you cannot see the content, say "show me the draft" and Tomo prints it as text and asks in plain text. For the template list, type its number, or `0` to abort. If a delivery was interrupted earlier, `/note` offers to resume or drop that draft first. A draft you never approved or aborted (the session ended during the questions or at the approval question) is offered too: Continue takes you back to the approval question for a draft that was already shown, or to the questions otherwise; Discard removes it, and nothing of it was in the inbox. Only Abort removes a draft without asking.
- `/note --process <template>` — creates or changes the process file for one template (see below).

If a note with the chosen name already exists, Tomo overwrites nothing and offers to rename or abort.

### First run

The first time you use `/note`, Tomo lists your template folder, proposes which filename patterns count as note templates, and shows which templates match and which it leaves out. You confirm or correct the patterns, and nothing is saved until you confirm. Your request then continues in the same session. The template mapped as your daily note is never offered as a note kind.

### Process files

A process file remembers what you want for one template: the destination folder, the points that are required and the order of the questions. Tomo creates it in a dialogue — you never edit one by hand. After a delivery where you changed the destination, filled a skipped point through Change something before delivery or asked for a question order, Tomo asks once: save, not now, or never for this template. "Never" is remembered; `/note --process <template>` replaces it.

### Titles and destinations

- A title may not start with a dot and may not contain invisible characters. The zero-width joiner and zero-width non-joiner are allowed.
- A blank title, or one containing `{{` or `<%`, is refused and Tomo asks for another.
- A process destination must be a relative vault folder, for example `Atlas/Meetings`, not an absolute path.

### Discard a delivered note

If you decide against the result, it costs two deletions and one command:

1. Delete the note in Obsidian.
2. Delete the instruction set in Obsidian.
3. Run `/inbox --recover`. A source that `/note` marked is treated as fresh again.

If you abort during the dialogue, nothing reaches the vault.

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
| `/note` | Write a note from a vault template. See [Write a note from a template](#write-a-note-from-a-template). | A request in free text, or `--process <template>` to create or change a process file. |
| `/moc-propose` | Live vault scan for new MOC proposals. See [How Tomo proposes new MOCs](workflows/moc-propose.md). | Scope such as `tag:`, `folder:`, `class:`, `title:` or free text. |
| `/garden-audit` | Audit the vault for structural problems. See [Audit your vault](workflows/garden-audit.md). | `audit`, `configure`, `suggest`, `stats`. |
| `/hashi-hook` | Draft a Tomo Hashi hook. See [Author a Hashi hook](workflows/hashi-hooks.md). | Optional description of the behaviour you want. |
| `/tomo-help` | Context-aware help. | A topic keyword (e.g. `inbox`, `kado`, `docker`, `login`); empty for a topic menu. |

Each command has a fuller spec inside its own definition — see `tomo-instance/.claude/commands/<command>.md` for the latest behaviour and edge cases.
