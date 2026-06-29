---
title: "Tomo Companion Mode P1 — Framework Authoring Skills"
status: draft
version: "1.0"
---

# Product Requirements Document

## Validation Checklist

### CRITICAL GATES (Must Pass)

- [x] All required sections are complete
- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Problem statement is specific and measurable
- [x] Every feature has testable acceptance criteria (Gherkin format)
- [x] No contradictions between sections

### QUALITY CHECKS (Should Pass)

- [x] Problem is validated by evidence (not assumptions)
- [x] Context → Problem → Solution flow makes sense
- [x] Every persona has at least one user journey
- [x] All MoSCoW categories addressed (Must/Should/Could/Won't)
- [x] Every metric has corresponding tracking events
- [x] No feature redundancy (check for duplicates)
- [x] No technical implementation details included
- [x] A new team member could understand this PRD

---

## Output Schema

See the PRD Status Report at the end of this document.

---

## Product Overview

### Vision

Tomo becomes an **interactive PKM companion** that authors notes and artifacts on demand — and gets
the Obsidian format right every time — landing everything safely in the user's inbox.

### Problem Statement

Today Tomo has one primary mode: `/inbox`, an async, proposal-first pipeline that triages material
the user *already captured*. The complementary half — conversationally *producing* content (write me
a summary note, compile these daily notes, make a base view) — is unserved. When the existing
free-form path (`default-doc-writer`) is used, two gaps surface:

1. **Format incorrectness.** Claude produces Obsidian-Flavored Markdown (OFM) with recurring syntax
   errors (the wikilink/backtick bug class is the observed example), and has no grounded reference
   for `.base` (Bases) or `.canvas` (JSON Canvas) — both JSON-family formats it cannot reliably
   construct from memory.
2. **Scattered authoring knowledge.** The "how to write to the vault correctly" knowledge (which
   helper script, template resolution, stem sanitization, inbox placement) is spread across script
   internals, so neither the user nor Tomo can reuse it reliably.

The consequence: companion-authored artifacts are inconsistent, occasionally malformed, and the
capability is effectively undiscoverable.

### Value Proposition

P1 ships **framework knowledge the LLM lacks, as reusable skills**, and wires the existing authoring
path to use them. The result: every companion-authored artifact is syntactically correct OFM /
`.base` / `.canvas`, lands in the inbox via the existing safe write path, and the authoring
capability is invocable by both the user and Tomo. It does this with **zero new trust surface** —
inbox-only, the existing Kado key, no new agent, command, or persona.

**Terminology:** *OFM* = Obsidian-Flavored Markdown. *MOC* = Map of Content. *Kado* (門) = the MCP
gateway that mediates all vault access. *Companion* = the existing conversational Tomo session acting
in authoring mode (not a separate process). *Skill* = a Claude Code SKILL.md directory, auto-loaded
by description or user-invoked.

## User Personas

### Primary Persona: The Vault Author (human user)

- **Demographics:** Obsidian power-user running Tomo in its Docker container; comfortable with
  conversational AI; not necessarily fluent in OFM/`.base`/`.canvas` syntax details.
- **Goals:** Ask Tomo to compose a note, summary, compiled log, base view, or canvas and have it land
  in the inbox in correct format, ready to file or use directly. Optionally invoke a format-reference
  skill directly to author by hand.
- **Pain Points:** Malformed wikilinks/tables; no reliable way to get a valid `.base`/`.canvas`; not
  knowing which mechanism Tomo uses to write, so failures are opaque.

### Secondary Personas

**Tomo (the session itself)** — the non-human consumer. Tomo auto-loads these skills while satisfying
an authoring request, so its output is correct without the user naming a sub-skill.

- **Goals:** Select the right template, load the right format skill, write to the correct inbox path.
- **Pain Points:** Improvising format from memory; re-deriving write mechanics each time.

## User Journey Maps

### Primary User Journey: Compose-to-Inbox

1. **Awareness:** User wants a note/artifact produced ("compile my Elsass-trip daily notes", "make a
   reading-list base"). They ask Tomo in-session.
2. **Consideration:** No alternative inside Tomo today — `/inbox` only triages existing material;
   `default-doc-writer` covers only free-form `.md` without grounded format knowledge.
3. **Adoption:** User phrases the request conversationally; Tomo auto-loads the relevant authoring
   skills.
4. **Usage:** Tomo composes the artifact (guided by the format skills), resolves a template, validates
   structure, and writes it to the inbox via the existing helper. Tomo reports the vault path.
5. **Retention:** Artifacts are consistently correct and discoverable; the user trusts companion
   authoring for recurring tasks and invokes the reference skills directly when authoring by hand.

### Secondary User Journeys

**Direct skill reference (user-invocable):** User invokes `/obsidian-markdown`, `/obsidian-bases`,
`/obsidian-canvas`, or the Kado helper skill directly to get authoring guidance without composing a
full artifact.

**Tomo auto-authoring (no human in the sub-loop):** During any session task that produces vault
content, Tomo auto-loads the format skill matching the artifact type and the write-side helper skill.

## Feature Requirements

### Must Have Features

The five P1 deliverables. Each is a skill (framework knowledge the LLM lacks) or wiring of the
existing path. Boundary for all: writes target the **inbox folder only** via Kado; the Kado key stays
read-broad + write-inbox-only; no new agent, persona, or command.

#### Feature 1: obsidian-markdown skill (upgrade)

- **User Story:** As Tomo (and the user), I want a grounded, broadly-correct OFM authoring reference
  so that every markdown artifact I produce is Obsidian-compatible.
- **Acceptance Criteria:**
  - [ ] Given a Tomo session, When the user invokes `/obsidian-markdown`, Then the skill loads and
        returns OFM guidance (frontmatter `user-invocable: true`; no "not user-invocable" / "Lazy-loaded"
        text remains in the body).
  - [ ] Given an authoring task involving OFM syntax (wikilinks, callouts, embeds, frontmatter, tables,
        tags, headings), When the task matches the skill description, Then the skill auto-loads via its
        description without explicit `skills:` injection.
  - [ ] Given the `moc-architect` agent with `skills: [obsidian-markdown]`, When a moc task runs, Then
        the agent still loads the skill by name with no regression.
  - [ ] Given a callout task, When skills are matched, Then `obsidian-markdown` triggers on *syntax* and
        `obsidian-fields` does NOT co-load (descriptions differentiated: markdown = syntax, fields =
        classification).

#### Feature 2: obsidian-bases skill (new)

- **User Story:** As the user/Tomo, I want a complete `.base` (Bases) syntax reference so that base
  views I request or compose are structurally valid.
- **Acceptance Criteria:**
  - [ ] Given a request to author a `.base` artifact, When `obsidian-bases` auto-loads, Then the LLM
        produces well-formed Bases YAML using only valid property names, filters, formulas, and view
        types.
  - [ ] Given the `obsidian-bases` description, When a `.canvas` or plain-markdown task fires, Then
        `obsidian-bases` does NOT co-load (trigger surface anchored to `.base`).
  - [ ] Given the skill is access-agnostic, When its body is read, Then it contains zero Kado/write
        references (pure format knowledge).

#### Feature 3: obsidian-canvas skill (new)

- **User Story:** As the user/Tomo, I want a complete JSON Canvas (`.canvas`) reference so that canvas
  artifacts conform to the spec and render in Obsidian.
- **Acceptance Criteria:**
  - [ ] Given a request to author a `.canvas` artifact, When `obsidian-canvas` auto-loads, Then the LLM
        constructs JSON Canvas with valid node/edge structures per the JSON Canvas 1.0 spec.
  - [ ] Given the `obsidian-canvas` description, When a `.base` or plain-markdown task fires, Then
        `obsidian-canvas` does NOT co-load.
  - [ ] Given the skill is access-agnostic, When its body is read, Then it contains zero Kado/write
        references.

#### Feature 4: inbox-author skill (rename of default-doc-writer + extend)

- **User Story:** As the user/Tomo, I want one skill that composes any free-form artifact — markdown,
  `.base`, or `.canvas` — in correct format and lands it in the inbox, so that I can author on demand
  without managing write mechanics.
- **Acceptance Criteria:**
  - [ ] Given a free-form authoring request, When `inbox-author` runs, Then it composes the content
        referencing the matching format skill and writes the result to `concepts.inbox` with a
        sanitized stem; the three existing STRICT guards (built-in template fallback, `--tokens` file,
        `sanitize_stem`) are preserved.
  - [ ] Given a request naming a known note type, When template mapping runs, Then it resolves
        `templates.mapping.<key>` for the real schema keys (`atomic_note`, `map_note`, `daily`,
        `weekly`, `monthly`, `yearly`, `project`, `source`) plus the `default` convention, fetches the
        template body from the vault, and falls back to the built-in minimal default (telling the user)
        if the field is empty or the read fails.
  - [ ] Given a requested type outside the known set AND no matching vault template is found, When
        `inbox-author` resolves the template, Then it writes using the **default/inbox template** and
        **tells the user** no type-specific template was found (it does not silently mislabel or refuse).
  - [ ] Given a `.base`/`.canvas` artifact, When the JSON is composed, Then `inbox-author` runs the
        deterministic `validate-json.py` parse-check (exit 0 = valid) before writing; on invalid JSON
        it does NOT write and surfaces the error (structural/semantic validation is out of scope → #92).
  - [ ] Given an inbox file already exists with the same stem+extension, When `inbox-author` calls
        `kado-write-file.py --no-overwrite`, Then the write is refused with an "exists" signal and
        `inbox-author` warns the user and asks before overwriting (no silent overwrite).
  - [ ] Given the rename from `default-doc-writer`, When `scripts/update-tomo.sh` runs on an existing
        instance, Then the old skill directory is pruned (`RETIRED_SKILLS_DIRS`) and no runtime
        reference to the old name remains.

#### Feature 5: kado-write-patterns skill (new)

- **User Story:** As the user/Tomo, I want a catalog of write-side Kado helper invocations so that I
  perform vault writes, config reads, template fetches, and stem sanitization correctly on the first
  attempt.
- **Acceptance Criteria:**
  - [ ] Given a write/config/compose task, When `kado-write-patterns` loads, Then it provides exact
        invocations for `kado-write-file.py` (`.md` → note, non-`.md` → file, `--no-overwrite`),
        `read-config-field.py`, `token-render.py`, `validate-json.py`, and `sanitize_stem` — as
        invocations (HOW), not prose about what they do.
  - [ ] Given a read/query/discovery task, When the LLM considers `kado-write-patterns`, Then its
        description directs the LLM to `kado-discovery-patterns` instead (read/write boundary explicit
        in both descriptions).
  - [ ] Given the skill body, When read, Then it duplicates no read-side pattern already in
        `kado-discovery-patterns`.

### Should Have Features

- **JSON parse-check ergonomics:** a clear, user-readable error when `.base`/`.canvas` JSON fails the
  parse-check, naming the artifact and the parse failure.
- **obsidian-markdown content audit checklist:** explicitly add the OFM sections currently missing
  (tables, task lists, fenced code with language, footnotes, properties/frontmatter YAML, math,
  Mermaid, comments, highlight) vs. an open-ended "expand" directive.

### Could Have Features

- `obsidian-templater` / `obsidian-dataview` authoring knowledge skills — **research-gated (#91)**;
  fold into this deliverable set only if research confirms the need before sign-off.
- Structural/semantic validation for `.base`/`.canvas` beyond parseability — **#92**.

### Won't Have (This Phase)

- **Direct-write outside the inbox** — companion writes inbox-only; no broader Kado ACL, no cross-repo
  Kado change, no Kokoro ADR.
- **Analytics engine** / generic marker-query + vault-config marker-declaration schema — **P2**.
- **Tsukai-like guidance codeblock** in notes driving a later `/inbox` `replace_section` apply — **P2**.
- **`/inbox` triage of `.base`/`.canvas`** — they land in the inbox and are skipped by triage (stay in
  place for direct use) — **#93**.
- **External enrichment / defuddle** — deferred (separate network-policy evaluation).
- **`/ask` command, companion agent/persona, `obsidian-cli`** — dropped entirely.

## Detailed Feature Specifications

### Feature: inbox-author (the most complex deliverable)

**Description:** Composes a free-form artifact the user asked for, in correct format (guided by the
format skills), and writes it to the inbox via the existing helper chain. Extends the existing
`default-doc-writer` from markdown-only to markdown + `.base` + `.canvas`, adds grounded template
mapping, JSON parse-checking, and collision handling.

**User Flow:**
1. User requests an artifact (e.g. "compile my Elsass daily notes into a trip log"; "make a
   reading-list base").
2. Tomo determines artifact format (`.md` / `.base` / `.canvas`) and loads the matching format skill.
3. Tomo resolves the template: known type → `templates.mapping.<key>` from the vault, with built-in
   fallback; unknown type → vault search, else default template + user note.
4. Tomo composes the content; for `.base`/`.canvas` it runs a `json.loads()` parse-check.
5. Tomo checks for an existing inbox file with the same stem+extension; if found, warns and asks.
6. Tomo writes to `concepts.inbox/<sanitized-stem>.<ext>` and reports the vault path.

**Business Rules:**
- Rule 1: Writes target the inbox folder only. Never write outside the inbox; never create
  defined-type notes as `/inbox` Pass-2 would (those remain `/inbox`'s job).
- Rule 2: `sanitize_stem` is applied to the raw title/stem only; the extension is appended separately
  (never sanitized into the stem).
- Rule 3: Template fetch is from the vault via Kado; source-repo `t_*_tomo.md` are NOT reachable at
  runtime — the built-in minimal template is the only in-container fallback.
- Rule 4: `.base`/`.canvas` artifacts carry no frontmatter and no Tomo lifecycle state; they are
  finished artifacts outside the `/inbox` pipeline.
- Rule 5: Invalid JSON for `.base`/`.canvas` blocks the write and surfaces an error.

**Edge Cases:**
- Same stem+extension already in inbox → warn + ask before overwrite.
- `templates.mapping.<key>` empty or template missing in vault → built-in minimal default + user note.
- Unknown type, no vault template → default template + user note (do not refuse, do not mislabel).
- Malformed `.base`/`.canvas` JSON → no write, error surfaced.
- Kado server-side extension rejection → does not occur (verified against Kado source; non-`.md` via
  `operation=file` is accepted unconditionally). If a live test ever contradicts this, raise a Kado
  handoff.

## Success Metrics

### Key Performance Indicators

- **Adoption:** Companion authoring is used on real requests during dogfooding (target: the five
  skills load — auto or invoked — across ≥1 real Compose-to-Inbox session per format family
  md/base/canvas during P1 validation on the `tomo-privat` vault).
- **Engagement:** The format skills auto-trigger on matching tasks without the user naming them
  (target: correct skill auto-loads on each format family in validation; no cross-format co-load).
- **Quality:** Companion-authored artifacts are syntactically valid (target: 0 malformed artifacts
  written — `.md` correct OFM; `.base`/`.canvas` pass `json.loads()`); no `default-doc-writer`
  reference remains post-rename; `moc-architect` shows no regression.
- **Framework Impact:** Each shipped skill passes the skill test (encodes non-obvious knowledge) and
  the `/skill-author` audit; full test suite green.

### Tracking Requirements

(Tomo is a local-first dev tool; "tracking" = validation evidence captured during the P1 live walk,
not telemetry — per Constitution L1 no analytics.)

| Event | Properties | Purpose |
|-------|------------|---------|
| Compose-to-Inbox run | format family, skill(s) loaded, template key resolved, vault path | Confirm auto-trigger + correct template mapping |
| `.base`/`.canvas` parse-check | pass/fail, artifact path | Confirm the parse-gate blocks malformed JSON |
| Collision prompt | stem, user choice | Confirm warn-and-ask path fires |
| Rename sweep | `rg default-doc-writer` count | Confirm zero residual references |
| moc-architect run | load OK / regression | Confirm compatibility |

## Constraints and Assumptions

### Constraints
- **Inbox-only boundary** (Constitution L1/L2): all companion writes via Kado to the inbox; Kado key
  read-broad + write-inbox-only; no broader ACL.
- **Runtime authoring rules:** skills are directories; SKILL.md contains imperatives/invocations only
  (WHY → `docs/tomo/<mirror>.md`); `# version: X.Y.Z` number-only; all skills built/audited via
  `/skill-author`; kepano attribution in README (general) + docs/tomo mirror (optional), never in
  runtime SKILL.md.
- **Runtime reachability:** source-repo templates and host paths are not reachable inside the
  container; only vault-resident content (via Kado) and in-container scripts are.
- **No new runtime surface:** no new agent, persona, or slash command.

### Assumptions
- Kado accepts `.base`/`.canvas` via `operation=file` — **verified** against Kado source
  (`request-mapper.ts` Rule 3; `kado-write-file.py` already extension-agnostic). No handoff needed.
- kepano `obsidian-markdown`/`obsidian-bases`/`json-canvas` are pure, adoptable format knowledge under
  MIT (README attribution sufficient); they ship checklists, not validator scripts.
- The user (Marcus) manages Kado key rights; the inbox folder and `templates.mapping` are present in
  the target vault-config.

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Template key drift (`note`/`moc` vs real `atomic_note`/`map_note`) mislabels notes | Medium | Medium | PRD pins the real schema keys; SDD enumerates them; AC tests the resolution |
| Description over-broadening co-loads multiple format skills (token waste / wrong format) | Medium | Medium | Anchor each description to its artifact type; AC asserts no cross-format co-load |
| `moc-architect` regression from obsidian-markdown change | High | Low | Loads via `skills:` frontmatter (verified safe); AC asserts no regression |
| Malformed `.base`/`.canvas` reaches vault | Medium | Low | `json.loads()` parse-gate in P1; structural validation tracked in #92 |
| Rename leaves dangling `default-doc-writer` references | Medium | Medium | `rg default-doc-writer` sweep + `RETIRED_SKILLS_DIRS` update; AC asserts zero residuals |
| Silent overwrite destroys a prior inbox artifact | Medium | Medium | Warn-and-ask on stem+extension collision |

## Open Questions

- [x] OQ-1/OQ-4: write-side skill name + packaging — **resolved in SDD ADR-1: one skill
      `kado-write-patterns`** (symmetric to `kado-discovery-patterns`).
- [x] OQ-3: staging file path — **resolved in SDD ADR-2: `tomo-tmp/staged-artifact.<ext>`**.
- [ ] #91: whether `obsidian-templater` / `obsidian-dataview` skills are needed (research-gated;
      Could-have).

## Supporting Research

### Competitive Analysis

`kepano/obsidian-skills` (MIT, Steph Ango) is the adapted **source**, not a competitor: it bundles
portable format knowledge (adopt) and a Kado-incompatible CLI access half (reject). Its
`obsidian-markdown`/`obsidian-bases`/`json-canvas` skills are pure format references with no validator
scripts — adoptable wholesale with README attribution.

### User Research

Grounded in real `tomo-privat` session-log usage: vault analytics, thematic search→synthesis, direct
authoring/compilation, external enrichment. P1 targets the authoring/compilation slice; the
wikilink/backtick OFM-correctness friction is the concrete observed pain point (already partially
fixed via formatting-style + skill guidance; #62).

### Market Data

Not applicable (internal framework feature for a local-first PKM tool).

---

## PRD Status Report

| Field | Value |
|-------|-------|
| specId | 026-companion-p1-authoring-skills |
| title | Tomo Companion Mode P1 — Framework Authoring Skills |
| status | IN_REVIEW |
| clarificationsRemaining | 0 |
| acceptanceCriteria | 19 explicit Gherkin ACs (F1:4, F2:3, F3:3, F4:6, F5:3) + 2 Should-have behaviors covered in tasks |
| openQuestions | OQ-1/4 + OQ-3 resolved in SDD (kado-write-patterns; staging path). Remaining: #91 (templater/dataview need, Could-have). |
