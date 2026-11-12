# Privacy

MiYo Tomo is an AI-assisted PKM workflow toolkit for Obsidian. This document
describes Tomo's trust contract: what runs where, what vault data reaches the
LLM, and what is recorded. It complements the MiYo Constitution (Privacy &
Security, L1/L2) and Kado's own `PRIVACY.md`.

## Local-first by design

- Tomo runs inside a **Docker container** with sandbox isolation. It has no
  direct filesystem access to your Obsidian vault.
- **All** vault access (read, search, write) goes through the **Kado MCP
  gateway**, reached only over the loopback interface (`127.0.0.1`) on the
  host. Kado enforces its own default-deny, per-path and per-capability
  permission model — Tomo never bypasses it.
- No third-party telemetry, analytics, or crash reporting. No background
  network calls. Tomo only talks to (a) Kado on localhost and (b) the
  Anthropic API for the Claude model that drives the workflows — both only
  when you initiate a command.

## What vault content reaches the LLM

Tomo's workflows are **user-initiated**: vault content reaches the Claude model
only when you run a command such as `/inbox`. During `/inbox`:

- **Inbox note bodies** — the text of the notes you are processing is sent to
  the model so it can be summarised, classified, and linked.
- **MOC names** — the name (title, or vault path when two MOCs share a
  title) of every MOC Tomo may link to is sent with each inbox item, so the
  model can pick the MOCs that fit it.
- **MOC structural metadata** (per specs 022/023/040) — only for the MOCs the
  model picked for an item, it receives each MOC's topics, H2/H3 **heading
  text**, **editable-callout opener lines** and a `has_footer` flag, to decide
  *where inside the MOC* a link should go. This is real vault content. MOCs the
  model did not pick send their name only.
- **`MiYo/Tomo/exclude/moc`** removes a MOC from the MOCs `/inbox` considers,
  so neither its name nor its structure is sent for inbox items. It is **not an
  access control**: other workflows (`/moc-propose`, the garden audit,
  `/explore-vault`) still read the MOC. Keep sensitive MOCs behind Kado's deny
  rules instead.
- **Note paths and titles** — appear in the per-item result so links and
  placements can be surfaced for your review.

During **companion mode** — when you ask Tomo in conversation to compose or
compile an artifact (an overview, list, summary, comparison, a Bases view, or a
Canvas) and write it to your inbox:

- **Note content read for compilations** — when a companion skill gathers
  source notes to synthesise or compile, the bodies of those notes are sent
  to the model. Only notes you explicitly reference or that fall within the
  scope you confirm are included.
- **Template fetches** — when a companion skill retrieves a note template
  from the vault to fill or extend, that template's content reaches the
  model. Templates contain structural markup, not personal data.
- **No new network surface** — companion mode uses the same two surfaces as
  every other Tomo command: Kado on loopback and the Anthropic API. No
  additional endpoints are contacted.

During **`/review`** — when you ask Tomo to review a finished week or month:

- **Your daily notes of the period** — from every daily note dated in the
  period, the sections you named in the setup (for example the Daily Log, the
  end-of-day fields, your habits), the **tracker values** such as sleep, energy
  and sport, the tasks with their done state, and the notes those sections
  link or embed for the same day — in a journal-style vault that is the
  Dayplanner and the entry of the current year in the **5 Year Journal**. Only
  text that belongs to the period reaches the model; earlier years and "On
  This Day" sections do not.
- **Living task notes** you named in the setup (for example a `Next Todos`
  note), so the review can tell which tasks were done in the period.
- **Weekly notes** of the weeks that overlap the month, for a monthly review.
- **Vault growth** — the **paths** of the notes created in the period and of
  the MOCs changed in it, not their content.
- **The weekly or monthly note itself**, so the review section can be placed
  under the right heading, and during the setup its template.
- **The review document you edited** — in Pass 2 a script reads the edited
  document and tells the model only counts and ids: how many items you kept,
  unticked, deleted or added. The model then sees the preview of the review
  section as it will land in your weekly or monthly note — the items you kept
  and added, in your wording — with the note's path and the heading it goes
  under; when that heading cannot be found, the note's headings too, so you
  can pick one. The instruction set is written to your inbox by a script and is
  not shown to the model.

A review reads your journal, so it reaches the most personal content a vault
holds. Folders you do not want reviewed — a therapy journal, client notes —
keep behind Kado **deny rules**: `/review` reads only what the Kado key
allows, and the run report says when a day could not be read. The setup
chooses which daily sections are read; sections it does not name stay out.

This is the intended design: you trigger the run, and the model needs your note
content and the target MOCs' structure to propose accurate placements. Tomo
proposes; you confirm before anything is applied.

## What Tomo records (metadata only)

Per MiYo Constitution L2, **Tomo's own records** — its logs, its error output
on **stderr** and its cost records — carry **metadata only**: paths, dates,
counts and states. They go nowhere but your machine, never to any external
service.

This scope is deliberate: "metadata only" is a promise about what Tomo writes
*about* a run, **not** a promise that no content rests on your machine. The
content Tomo reads also rests in places Tomo does not own; the section
[Where read content rests](#where-read-content-rests) names them.

The MOC-insertion resolution telemetry (`instruction-render.py`) emits a single
metadata-only line per run containing:

- per-tier resolution **counts** (heading / new_section / callout / line /
  unresolved / tier1_confident, plus the MOC count),
- numeric `fit_confidence` **values**, and
- MOC vault **paths**.

It **never** records heading text, callout text, note content, or frontmatter
values. The `/review` scripts follow the same rule: no daily-note text, journal
answer, tracker value or proposal text appears in their error output or in
the cost log — only paths, dates, counts and states (tested).

## Where read content rests

Everything the model reads has to pass through your machine, and some of it
stays there after the run. These are the places, named so that you can decide
what to do with them:

- **Claude Code's session transcripts in the container home.** Every Tomo
  session is a Claude Code session, and Claude Code keeps a transcript of each
  one — including every tool result the model saw, so the daily notes,
  journal entries, tracker values and proposals of a `/review` run, and the
  note bodies of an `/inbox` run, are in there in full. They live in the
  instance's Docker home under `home/.claude/projects/`. Tomo never reads,
  trims or deletes them. A backup made with `backup-tomo.sh` archives the
  Docker home, so it archives the transcripts too.
- **Tomo's working folder `tomo-tmp/`** in the instance workspace. A `/review`
  run keeps what it read in `tomo-tmp/review/<period>_review/read.json` and
  the model's proposals in `proposals.json`. Tomo deletes `read.json` and
  `proposals.json` once the review document is written to the inbox or the
  run is aborted; a session that ended without writing or aborting leaves
  `read.json` and `proposals.json` there until the next `/review` of that
  period. What stays afterwards (`meta.json`) is metadata only. Other
  commands keep their working files there too, for example the per-item
  results of `/inbox` and the draft of `/note`.
- **Your inbox.** The review document (`<period> Review.md`) holds the
  proposals built from your journal; the instruction set
  (`<period>_review_instructions.json` and `.md`) holds the items you
  approved, in your wording; a review of a week or month without a note yet
  adds that new note. They stay in the inbox after you applied them, like
  every other document Tomo delivers — removing them is yours to do.

Beyond those two working files, Tomo does not remove any of this; whether and
when to remove it is **your choice**. Because the transcripts and the working folder can hold your journal
as plainly as the vault does, protect the instance directory — both `instance/`
and `home/` — **like your vault**: keep it on an encrypted disk (for example a
FileVault-protected volume), give it the same backup and sync rules, and do not
share or commit it.

## Credentials

The Kado **bearer token** lives only in the instance's local `.mcp.json` and is
never committed to git. It authenticates Tomo to the local Kado gateway; it is
not transmitted anywhere else.

## Summary of network surfaces

| Destination | Transport | Purpose | When |
|-------------|-----------|---------|------|
| Kado gateway | `127.0.0.1` (loopback, MCP) | all vault read/search/write | on user-initiated commands |
| Anthropic API | HTTPS | Claude model that drives workflows | on user-initiated commands |

No other inbound or outbound network surfaces exist. Tomo accepts no inbound
traffic and opens no listening ports.
