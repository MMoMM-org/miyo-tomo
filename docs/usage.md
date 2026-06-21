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

### Process inbox items

This is the day-to-day loop. When new items have landed in your inbox folder (voice memos with `tomo.state: captured` in their frontmatter, web clips, quick captures, anything ready for triage), run:

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
5. **Cleanup.** Re-run `/inbox`. When it sees an instruction set with all actions applied (whether by hand or by Hashi), `state-promoter.py` transitions source items from `tomo.state: captured` to `tomo.state: active` and `mark-captured.py` archives completed workflow docs per your vault-config rules.

`/inbox` is auto-resumable: there is no state you have to track. Each run it re-reads the inbox from the vault, works out what changed, and does the next step — run Pass 1, run Pass 2, transcribe audio, run cleanup, or report idle. You just keep running `/inbox`.

#### What a re-run redoes (and what it leaves alone)

Each `/inbox` does **one step**, and prefers finishing in-flight work over new intake. The common situations:

- **New note dropped** → Pass 1 suggests it.
- **You approved a suggestions doc** → Pass 2 synthesises its instructions.
- **You re-run after applying** → Tomo sees the work is already done (an instruction set covers it, unchanged) and stays **idle** — it will *not* re-render a duplicate.
- **You edited an approved suggestions doc** after its instructions were generated → Tomo detects the change and re-synthesises just that one.
- **Approved work pending *and* a new note** → Pass 2 runs first (finish the batch); the new note is suggested on your next run. Want to intake the new note now instead? `/inbox --pass1`.

Tomo only treats a doc as "changed" when its **body** changes (your edits) — its own bookkeeping (marking a doc approved) never counts as a change.

#### Forcing a phase

| Command | Does |
|---------|------|
| `/inbox --pass1` | Suggest new sources now (even if Pass 2 work is pending) |
| `/inbox --pass2` | Synthesise only what's changed or not yet done |
| `/inbox --pass2 --force` | Re-synthesise **all** approved docs, ignoring "already done" |
| `/inbox --pass1 --force` | Re-suggest **everything**, including already-captured items |
| `/inbox --force` | Full rebuild — re-suggest, then re-synthesise everything |

`--force` is a modifier you add to a phase (or use alone for a full rebuild). For the decision logic in detail, see [Inbox Change Detection & Pass Routing](XDD/reference/tier-2/workflows/inbox-change-detection.md) (with flowchart).

### Refresh vault discovery

When you've reorganised folders, added new MOCs, or changed tag conventions, refresh the discovery cache:

```
/explore-vault            # silent rebuild (uses prior confirmations)
/explore-vault --confirm  # walk through every detection step again
```

Discovery writes `tomo-instance/config/discovery-cache.yaml` and may update `vault-config.yaml` for the sections it owns (tags, callouts, relationships, trackers). Each section asks for confirmation before writing. Your vault is never modified — only Tomo's config files. See [Configuration → Override mechanism](configuration.md#override-mechanism) for how the cache fits into the layer precedence.

### How Tomo proposes new MOCs (and why cache freshness matters)

Tomo suggests creating a new Map of Content (MOC) when a topic has accumulated enough notes without one (LYT's "Mental Squeeze Point"). There are **two paths**, and they differ in *when* they run and *how fresh* their data is:

- **Passive — automatically during `/inbox`.** While analysing each inbox item, Tomo proposes a new MOC in two cases: (a) the item's topic doesn't match any existing MOC, so a thematic MOC is suggested for it; or (b) the item's topic matches a **placeholder MOC** you already linked but haven't created — a dead `[[… MOC]]` wikilink sitting in one of your MOC bodies. Both run against the discovery cache from your **last `/explore-vault`** — no live vault scan at inbox time.
- **Active — on demand with `/moc-propose`.** This command **scans the vault live** (whole-vault, or scoped with `tag:` / `folder:` / `class:` / `title:` / free text) and writes a reviewable MOC proposal-doc to your inbox. Use it when you want an up-to-the-minute answer independent of cache age.

**Practical consequence — the passive `/inbox` detection is only as current as your last `/explore-vault`:**

- A MOC or placeholder link you added since the last explore **won't be matched during `/inbox` until you re-run `/explore-vault`**.
- Conversely, notes you've *filed* under a MOC since the last explore may still look unparented in a stale cache, so a `/moc-propose` scan can mention notes you've already organised.

So: **re-run `/explore-vault` after you've added or reorganised notes or MOCs** to refresh what `/inbox` can detect — or reach for **`/moc-propose`** when you want a live scan right now. (A cache-staleness warning in `/inbox` is planned — backlog F-21.)

### Excluding notes or MOCs from proposals

You can tell Tomo to leave specific notes or MOCs out of its MOC suggestions by tagging them. Both tags go in the note's **frontmatter** `tags:` list:

- **`MiYo/Tomo/exclude/note`** — the note is never offered as a candidate for a new MOC (it's dropped from the `/moc-propose` scan). Use it for notes that are intentionally standalone and shouldn't be clustered.
- **`MiYo/Tomo/exclude/moc`** — the MOC is skipped by the "missing uplink" check (`/moc-propose check:moc-uplinks`). Use it for top-level maps (e.g. a root index) that correctly have no parent. The MOC stays in the cache and remains a valid link target — only the uplink nag is suppressed.

```yaml
---
tags: [MiYo/Tomo/exclude/note]
---
```

> **Frontmatter only.** These tags are read from the YAML frontmatter `tags:` list. An **inline** `#MiYo/Tomo/exclude/note` written in the note body is **not** recognised and the exclusion is silently ignored. (This differs from MOC discovery, which accepts inline tags — a known inconsistency.) After adding or removing an exclude tag, re-run **`/explore-vault`** so the rebuilt cache picks it up.

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

### Author a Hashi hook

[Tomo Hashi](https://github.com/MMoMM-org/miyo-tomo-hashi) runs user-authored `.cjs` hooks from `.tomo-hashi/hooks/` to customise what happens `before`/`after` each instruction-set action. `/hashi-hook` walks you through writing one:

```
/hashi-hook                          # full guided flow
/hashi-hook "stamp moved notes"      # seed the flow with the behaviour you want
```

It asks for the phase (`before`/`after`) and action kind, drafts the hook, then **risk-classifies the generated code** (🟢 Obsidian-API only · 🟡 filesystem/env · 🔴 shell/network/filesystem-writes) and flags hooks that could change many notes in one run. The hook and a handoff document are written **to your inbox** — Tomo never places code in `.tomo-hashi/hooks/` itself.

> ⚠️ Hashi hooks run **unsandboxed on your host** with full vault, filesystem, and network access. Tomo drafts the code; reviewing it, testing it, and all liability are yours. **Back up your vault** before moving a hook into place, and again before the next Hashi run. The handoff doc repeats these warnings and includes a review checklist and the exact target filename.

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
  - The `tomo.state` frontmatter field on **inbox source items** flips from `captured` to `active` once you've applied their actions and `/inbox` cleanup runs.

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
| `/inbox` cleanup | The next `/inbox` run runs cleanup: `state-promoter.py` transitions source items from `tomo.state: captured` to `tomo.state: active`; `mark-captured.py` archives fully-applied workflow docs per your vault-config rules. |
| `/tomo-setup <section>` | The relevant `config/` files are updated. The wizard prints a per-phase summary so you can see what was written. |

### Lifecycle state

Tomo tracks every inbox source item's state in a hidden `tomo.state` frontmatter field — not a tag. You never add or edit it by hand; Tomo writes and advances it automatically. The two states a source item moves through are:

| `tomo.state` | Meaning |
|---|---|
| `captured` | Item is in the inbox, waiting to be processed. |
| `active` | Item has been processed: its actions were applied and `/inbox` cleanup transitioned it. |

A source item carries exactly one state at any time. Because the field is frontmatter rather than a tag, it stays out of your tag pane. The signals you *do* see are filename conventions, body checkboxes (`[ ] Approved` on suggestions, `[ ] Applied` per action on instruction sets), and the per-run `/inbox` summary. Workflow documents (suggestions, instructions) don't carry a `tomo.state` — their progress is read from those checkboxes.

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
