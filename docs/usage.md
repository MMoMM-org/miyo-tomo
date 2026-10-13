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
5. **Clean up when you're ready — nothing does it for you.** An applied instruction set and the suggestions doc it came from **stay in your inbox**, and so do abandoned ones you never approved. There is no automatic removal, and nothing re-processes them in the meantime: re-running `/inbox` reports `idle` with the reason *"All approved items already covered by existing instructions"*.

    **One thing to know if you do delete them: delete the pair, not just one half.** The leftover instruction set is what records that the work is done. Remove it while leaving its approved suggestions doc behind, and the next `/inbox` run sees an approved doc nothing covers — and builds the instruction set again. Deleting both, or neither, is always safe.

> **Two surfaces, one rule.** You can review and edit a run two ways: directly
> in the suggestions document, or in [Tomo Hashi](https://github.com/MMoMM-org/miyo-tomo-hashi)'s
> structured Suggestions Editor. Both work on the same run. Once you've saved
> that run in the editor, the editor's values are what Pass 2 uses for the
> whole run — not the markdown, even for fields you left untouched in the
> editor. Don't go back and edit the markdown for that run afterwards; the
> edit is dropped, not merged in. If a run produced a second suggestions
> document, Tomo needs both saved in the editor — otherwise it uses the
> markdown for the whole run instead, and Pass 2 says so when that happens.
> If you haven't opened the editor for a run at all, the suggestions document
> is what counts, which is why editing it directly and running `/inbox
> --pass2 --force` works the way the rest of this page describes.

`/inbox` is auto-resumable: there is no state you have to track. Each run it re-reads the inbox from the vault, works out what changed, and does the next step — run Pass 1, run Pass 2, transcribe audio, run cleanup, or report idle. You just keep running `/inbox`.

#### When an attachment's name is already taken

If an inbox note embeds a file — a scan, a photo, a PDF — Tomo files that file
into your attachments folder alongside the note. When a file of that name is
**already there**, Tomo does not guess. Pass 1 adds an **Attachment Conflicts**
section to the suggestions document, above the suggestions, and you decide.

Each entry names the file, the destination that is occupied, and which of your
notes embeds it. It also tells you whether the two files are actually the same:

| What it says | What it means |
|---|---|
| A different file already holds this name | Two unrelated files, one name. Renaming keeps both. |
| This is the same file already in the vault | You already have it. Renaming would leave you with two copies. |
| The files could not be compared | Tomo could not read one of them — look before you accept the rename. |

Three remedies, one per entry. **Rename is pre-ticked** — it is the only one
that files the attachment successfully in every case:

- **Rename** — files it under a computed free name (`karte (2).png`), and
  rewrites the embed in your note to match, so the note keeps working. Under
  the Rename line sits a **Folder** line, pre-filled with the folder the
  occupied name lives in. You can change either one before you apply:
    - **The name is yours to change**: type over the text between the
      backticks on the Rename line. Tomo files it under what you typed instead
      of the computed one. If Pass 1 couldn't find a free name at all, the
      backticks start out **empty** — type a name there yourself.
    - **The folder is yours to change**: type over the text between the
      backticks on the Folder line, for example to file the map into your maps
      folder where nothing is called `karte.png`. A folder that doesn't exist
      yet is fine; Pass 2 says it "will be created on apply". Leave the line
      alone and the folder stays as it is. The Folder line only counts while
      Rename is ticked.
    - A folder never goes into the Rename line. Typing `maps/karte.png` there
      is refused as a path — use the Folder line.
  (You can set the name and folder in Tomo Hashi's Suggestions Editor instead
  of the markdown, too — see "Two surfaces, one rule" above: if this run
  produced a second suggestions document, save that one in the editor too, or
  your typed values are dropped in favour of the markdown. In the editor you
  pick the folder from your existing folders — the inbox is not offered — so a
  folder that does not exist yet, or one Pass 2 refuses, can only come from
  the Folder line in the markdown.) [#185](https://github.com/MMoMM-org/miyo-tomo/issues/185)
- **Keep in inbox** — leaves the file where it is. The note is still filed; only
  the file stays behind.
- **Ignore** — sends the move anyway. It will be refused unless you free the
  name yourself before applying.

> **When the comparison says it is the same file**, the pre-ticked Rename gives
> you a second copy of something you already have. Tick **Keep in inbox**
> instead if you would rather not file it at all.

**Keep in inbox or Ignore still file the note.** They hold back the *file*,
not the note — so the filed note will point at a file that is still sitting in
your inbox. That reference still works; it just reaches backwards. Tomo says
so in the instruction set, both on the action and in its summary. **A typed
name that Pass 2 refuses is the one exception** — it holds back the note as
well; see below.

**A typed name or folder is checked, never corrected.** Tomo doesn't guess at
what you meant by swapping out a character — it either files exactly what you
typed, or refuses it outright. (Tomo Hashi's editor is different: when you
type something there that the markdown would refuse, the editor cleans the
name up for you, visibly, before it saves. Tomo itself never does.)

A typed **name** is refused when it is:

- **blank** — empty, or nothing but whitespace,
- **a path, not a plain filename** — it contains `/`,
- **padded** — it starts or ends with a space or other whitespace such as a tab,
- **unsafe** — it contains a control character, `{{` or `<%`,
- **carrying a character your vault forbids** — any of `\` `:` `*` `?` `"` `<` `>` `|`,
- **carrying a character that breaks links** — any of `#` `^` `[` `]`.

A typed **folder** is refused when it is:

- **blank**, or the line is damaged so it no longer holds exactly one folder in
  backticks,
- **leaving the vault** — it starts with `/`, `~` or `./`, uses `\`, starts
  with a drive letter such as `C:`, or contains a `.` or `..` segment,
- **holding an empty part** — it contains `//`,
- **padded** — a part of the path starts or ends with a space or other
  whitespace such as a tab,
- **ending in `/`**,
- **unsafe** — a control character, `{{` or `<%`,
- **carrying a forbidden character** — any of `:` `*` `?` `"` `<` `>` `|`,
- **carrying a link-breaking character** — any of `#` `^` `[` `]`,
- **the inbox itself, or inside it** — the next run would read the file as
  inbox material again. Upper/lower case and Unicode form are ignored in this
  check, so `100 inbox/x` is refused too when your inbox is `100 Inbox`.

"That name is already taken" is deliberately not one of these reasons — Tomo
checks that separately, against the vault, and reports it as described next.

**When a typed name or folder is refused, the attachment isn't filed — and
neither is any note in this run that embeds it.** Both stay behind in your
inbox: the instruction set lists them under "Attachments still in the inbox",
and Pass 2 reports them in your terminal too. To fix it, correct the name or
folder in the suggestions document, then:

- **before you apply:** run `/inbox --pass2 --force`;
- **after you applied:** run `/inbox --recover`. The attachment and its notes
  are still in the inbox, and the re-run proposes the default name or folder
  again. It offers your choice again only if the target is still taken; if the
  target is free, the attachment is simply filed there.

**What Pass 2 tells you about the target.** Pass 2 looks at the vault for the
final path before it writes the move. An occupied target is reported under
"Attachments still in the inbox", because no move is written for it; the other
findings sit in the block of the move that is written:

- **occupied** — something is already at that path (a file, a folder, or a
  file that differs only in upper/lower case). The attachment is not filed over
  it and stays in the inbox together with the note. Free the target in the
  vault, or pick another name or folder, and run `/inbox --pass2 --force`
  before you apply (`/inbox --recover` after).
- **not checked** — the vault did not answer for that path, so Tomo cannot say
  whether it is free. The move is still written, and you can apply it as it is;
  if it fails, the attachment and its note stay in the inbox. To be sure
  first, look in the vault for the path named in the message.
- **will be created on apply** — the folder you typed on the Folder line
  doesn't exist yet. Nothing to do.
- **Embed written with path** — another file in your vault has the same name,
  so the note links to the file by its full path instead of the bare name. The
  link works the same; the longer form is what keeps it pointing at the right
  file. [#185](https://github.com/MMoMM-org/miyo-tomo/issues/185)

To change your mind after Pass 2 has run but before you apply: tick a different
remedy in the suggestions document, then run `/inbox --pass2 --force`.

#### Tagged notes from MiYo tools

If you use [Tomo Tsukai](https://github.com/MMoMM-org/miyo-tomo-tsukai) or another MiYo tool that tags inbox notes with `MiYo/<Feature>/…`, and you have a matching handler registered, `/inbox` groups all such captures for the same target into **one** merged suggestion rather than surfacing them individually. You review and approve it the same way you would any other suggestion. No special command is needed — the grouping happens automatically during Pass 1.

To register or edit a handler, use **`/tomo-tag-handler-wizard`**. See [Configuration → Tag-handler framework](configuration.md#configtag-handlers--tag-handler-framework) for the full reference.

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
| `/inbox` | 2-pass workflow + cleanup; auto-detects which phase to run. | `--pass1`, `--pass2`, `--cleanup` to force a specific phase. |
| `/explore-vault` | Vault discovery; populates `vault-config.yaml` and `discovery-cache.yaml`. | `--confirm` re-runs every detection step with prompts. |
| `/tomo-setup` | Post-install wizard (recommended after every install). | `rules`, `templates`, `trackers`, `daily-log` to run a single phase. |
| `/tomo-help` | Context-aware help. | A topic keyword (e.g. `inbox`, `kado`, `docker`, `login`); empty for a topic menu. |

Each command has a fuller spec inside its own definition — see `tomo-instance/.claude/commands/<command>.md` for the latest behaviour and edge cases.
