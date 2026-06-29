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
- **MOC structural metadata** (per specs 022/023) — to resolve *where inside a
  target MOC* a link should be inserted, the model receives, via `shared-ctx`,
  a per-MOC inventory of structural vault content: H2/H3 **heading text**,
  **editable-callout opener lines**, and a `has_footer` flag. This heading and
  callout text is real vault content sent to the model for insertion-point
  resolution.
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

This is the intended design: you trigger the run, and the model needs your note
content and the target MOCs' structure to propose accurate placements. Tomo
proposes; you confirm before anything is applied.

## What is recorded (metadata only)

Per MiYo Constitution L2, Tomo's operation traces record **metadata only** and
go to **stderr** (local) — never to any external service.

The MOC-insertion resolution telemetry (`instruction-render.py`) emits a single
metadata-only line per run containing:

- per-tier resolution **counts** (heading / new_section / callout / line /
  unresolved / tier1_confident, plus the MOC count),
- numeric `fit_confidence` **values**, and
- MOC vault **paths**.

It **never** records heading text, callout text, note content, or frontmatter
values.

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
