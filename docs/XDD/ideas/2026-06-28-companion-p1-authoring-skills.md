# Tomo Companion Mode — P1: Framework Authoring Skills

> Brainstorm spec / charter for **Phase 1** of Tomo companion mode.
> Created: 2026-06-28. Status: **design approved (decision-first, no code)**. Next step: `/xdd` → PRD.
> Supersedes the execution-boundary decisions (§6.2/§7) of the older charter
> `docs/XDD/ideas/2026-06-24-tomo-companion-mode.md` — see "Reframe" below.
> Origin: brainstorm session 2026-06-28 (this file is the `/xdd` handoff contract).

---

## 1. Goal

Make Tomo usable as an **interactive PKM companion** that *authors* notes and artifacts on
demand, in-session, outside the `/inbox` batch pipeline — and gets the **format right** (valid
Obsidian-Flavored Markdown, `.base`, `.canvas`). P1 is the smallest shippable slice: ship the
**framework knowledge** the LLM lacks, and wire the **already-existing** authoring path to use it.

## 2. Reframe — what changed vs. the 2026-06-24 charter

The older charter's central tension (§6.2 execution-boundary, §7 cross-repo Kado/Kokoro work) is
**dissolved** by these decisions, which OVERRIDE it:

- **Inbox-only, no direct-write.** Everything the companion produces lands in the **inbox** via
  Kado, exactly like `/inbox` output. The user then edits / moves / processes it. Companion-written
  `.md` notes are **not excluded** from the `/inbox` pipeline.
- **Kado is just the tool.** The Kado API key stays **read-broad + write-inbox-only**; Marcus
  manages the key's rights. **No broader ACL, no cross-repo Kado change, no Kokoro ADR.**
- **No agent, no persona, no `/ask` command, no analytics engine.** The existing conversational
  Tomo session *is* the companion; it dispatches subagents itself when a task warrants it.
- **P1 = skills + wiring.** Skills encode framework knowledge the LLM does not have; they
  **auto-trigger via description**, are **user-invocable**, and are usable by **both** the user and
  Tomo.

### The skill test (design guard)

A capability earns a skill **only if it encodes knowledge the LLM does not already have.** A skill
that merely says "count the entries" is worthless — the LLM can do that. User-specific use cases
(specific markers, curated reports) live in the **user's Tomo instance config**, not in the shipped
framework. This is a framework, not a collection of Marcus's use cases.

## 3. Scope

### In-scope (P1) — five deliverables

| # | Deliverable | Type | Summary |
|---|---|---|---|
| 1 | **obsidian-markdown** | upgrade existing | Flip `user-invocable: true`; broaden description for companion auto-trigger; remove the "not user-invocable" body line; audit/expand content vs kepano `obsidian-markdown`. |
| 2 | **obsidian-bases** | new | `.base` view syntax knowledge, adapted from kepano `obsidian-bases`. Pure, access-agnostic format knowledge. |
| 3 | **obsidian-canvas** | new | JSON Canvas / `.canvas` knowledge, adapted from kepano `json-canvas` (renamed). Pure format knowledge. |
| 4 | **inbox-author** | rename of `default-doc-writer` + extend | Compose free-form artifacts and write them to the inbox. Extensions: wire to the format skills; template mapping (#46); `.base`/`.canvas` write path. |
| 5 | **kado-toolkit** | new | Catalog of Kado **write-side** helper invocations. User + Tomo usable. |

**Research (tracked as #91):** whether to add `obsidian-templater` + `obsidian-dataview` authoring
support (same shape as the format skills). If research says yes, fold into this deliverable.

### Out-of-scope (parking lot — P2+)

- **Analytics engine** / generic marker-query + a vault-config marker-declaration schema → **P2**.
- **Tsukai-like guidance codeblock** embedded in companion notes that later drives an `/inbox`
  `replace_section` apply (e.g. "update die Notiz" → block in inbox → user says "apply" → replace
  in target) → **P2**.
- **inbox-triage for `.base`/`.canvas`** — currently `/inbox` triage handles `.md` + audio only;
  `.base`/`.canvas` inbox files are skipped (they stay in the folder, unprocessed, available for
  direct use). Teaching triage to handle them → **#93** (P2+).
- **External enrichment / defuddle** → deferred (separate evaluation incl. network policy).
- **Dropped entirely:** `/ask` command, companion agent/persona, `obsidian-cli`.


## 4. Design

### 4.1 Architecture

No new runtime surface. The companion is the normal Tomo session using these skills. Format skills
are **access-agnostic** (they never mention Kado — just "how to write valid X"). Only `inbox-author`
and `kado-toolkit` know about Kado. Writing always targets the **inbox folder** (`concepts.inbox`),
sanitized stem, inbox-only boundary preserved.

### 4.2 Deliverable 1 — obsidian-markdown (upgrade)

- `user-invocable: false → true`.
- Broaden `description` to action-oriented + companion trigger phrases (author/write valid OFM:
  wikilinks, callouts, embeds, frontmatter, tables, tags, headings) — **and differentiate its
  trigger surface from `obsidian-fields`** so both don't co-load on the word "callout" (markdown =
  *syntax*; fields = *classification*).
- Remove SKILL body line "Lazy-loaded … not user-invocable" (contradicts the flip).
- Audit/expand content vs kepano `obsidian-markdown` for **broader, more accurate OFM understanding**.
  The specific wikilink/backtick bug is **already fixed** (formatting-style + skill guidance to use
  backticks for notes; see #62) — this deliverable is about deepening Claude's general grasp of how
  Obsidian markdown works, not re-fixing that one bug.

- **Compatibility:** `moc-architect` loads this skill via explicit `skills:` frontmatter (not
  description auto-trigger), so broadening description / flipping user-invocable is **safe** —
  verified, no agent breakage.

### 4.3 Deliverables 2 & 3 — obsidian-bases, obsidian-canvas (new)

Pure format-knowledge skills, adapted from kepano `obsidian-bases` / `json-canvas`. Focused
auto-trigger descriptions (`.base` task → bases; `.canvas` task → canvas). They guide the LLM to
**construct the format directly** (`.base`/`.canvas` are JSON — there is no token-template renderer
for them; see 4.4). A JSON-validity check before write is tracked as **#92** (check what the kepano
source skills already provide first).

### 4.4 Deliverable 4 — inbox-author (rename `default-doc-writer` + extend)

Existing `default-doc-writer` already: composes content → resolves default template
(`templates.mapping.default` via `read-config-field.py`, built-in minimal fallback) → renders via
`token-render.py` → writes to inbox (`concepts.inbox`) via `kado-write-file.py` with `sanitize_stem`
→ inbox-only boundary. Extensions:

- **(a) Format correctness** — reference `obsidian-markdown` / `obsidian-bases` / `obsidian-canvas`
  via `skills:` frontmatter so companion output is valid (kills the wikilink/backtick bug class).
- **(b) Template mapping (#46) — LLM-driven, grounded.** The skill states the always-shipped
  templates (default/inbox, note/atomic, moc, project, source, daily → `t_*_tomo`) and **how to
  fetch one** (`read-config-field --field templates.mapping.<type>` → `kado-read` the body from the
  vault by stem, built-in fallback if missing). **Default = the inbox/default template.** For a type
  outside the shipped set, the LLM **searches the vault** for a matching format or **asks the user**.
  No silent inference at a hidden write point beyond the shipped, known types.
- **(c) `.base`/`.canvas` write path.** The `.md` path stays (token-render). For `.base`/`.canvas`,
  the LLM composes the JSON directly (guided by 2/3) → staged file → `kado-write-file.py`
  (`operation=file`, already extension-agnostic at script lines ~78–84, **no client change needed**)
  → inbox. **`sanitize_stem` applies to the `.base`/`.canvas` stem too.** These artifacts are
  **finished** — they land in the inbox folder for direct use and are **outside** the `/inbox`
  pipeline (no frontmatter/state; triage skips them — see parking lot).
- **(d) Rename fan-out** — update every reference to `default-doc-writer`: the docs/tomo WHY mirror
  (`docs/tomo/dot_claude/skills/default-doc-writer.md` → `inbox-author.md`, content updated for the
  new scope), `scripts/update-tomo.sh` `RETIRED_SKILLS_DIRS` (add `default-doc-writer` so old
  instance dirs are pruned), profiles/configs, and any agent/rule referencing the old name.

### 4.5 Deliverable 5 — kado-toolkit (new)

A catalog of **write-side** Kado helper **invocations** (HOW, not WHAT-prose): `kado-write-file.py`
(`.md` and `operation=file`), `kado_client` write methods (`write_file`, `write_frontmatter` +
optimistic-concurrency guard), `read-config-field.py`, `token-render.py`,
`lib/obsidian_filename.sanitize_stem`. **Boundary:** read/query side stays in the existing
`kado-discovery-patterns` skill; `kado-toolkit` is the **write/compose** side. Description must state
the split so the LLM loads only the side it needs. Narrow to write + config-read invocations — do
not re-catalog well-known read methods. (How best to slice this — one `kado-helper` skill vs.
several — is OQ-4 for `/xdd`.)


### 4.6 Conventions (all five)

- **All skills via `/skill-author`** (global rule) — do not hand-write SKILL.md.
- **Runtime files are imperatives/invocations only** — no explanatory prose; WHY lives in
  `docs/tomo/<mirror>.md`. Tell HOW (the invocation), not WHAT (don't describe what a script does).
- **kepano attribution** — a **general** MIT attribution + dependency note in the **README**; the
  per-skill `docs/tomo/<mirror>.md` WHY files **may** carry an explicit attribution. Never inside the
  runtime SKILL.md files.
- Skills are directories with `SKILL.md`; `# version: X.Y.Z` header (number only).

## 5. Verification items (P1)

- **Confirm Kado accepts `.base`/`.canvas` via `kado-write operation=file`.** The client
  (`kado-write-file.py`) is already extension-agnostic; the open question is Kado's **server-side**
  extension acceptance. **Verify FIRST.** If Kado rejects these extensions, the `.base`/`.canvas`
  write path (4.4c) triggers a Kado handoff which will be delivered during working on this and will be available for live testing at the end.

## 6. Approaches considered (and why this one)

- **Direct-write-anywhere + broader Kado ACL** (old charter §6.2) — *rejected*: reopens the trust
  boundary that makes Tomo safe, forces cross-repo Kado + Kokoro work. Inbox-only gives the same
  user value with zero boundary erosion.
- **Companion as a dispatched subagent or a new persona/mode** — *rejected*: a companion is
  conversational (multi-turn); dispatched subagents are one-shot and non-interactive, and we already
  have the conversational loop. No persona needed.
- **Build a new inbox-write skill** — *rejected*: `default-doc-writer` already is it; rename + extend
  instead of duplicate.
- **Analytics/marker-query engine in P1** — *deferred*: user-specific until a generic vault-config
  marker convention proves out; fails the skill test as curated reports. → P2.

## 7. Open questions for `/xdd` (PRD to resolve)

- OQ-1: Final name for `kado-toolkit` (working name; adjust at build time).
- OQ-2: Exact known-template list surfaced in `inbox-author` — confirm the `t_*_tomo` set maps 1:1
  to `templates.mapping` keys (`default`, `note`, `moc`, `project`, `source`, `daily`).
- OQ-3: Staging location + naming for the composed `.base`/`.canvas` file before upload.
- OQ-4: `kado-toolkit` packaging — one combined `kado-helper` skill vs. several focused skills
  (write vs. config vs. compose). Resolve alongside the `kado-discovery-patterns` read/write split.

## 8. References

- Older charter: `docs/XDD/ideas/2026-06-24-tomo-companion-mode.md` (this spec supersedes its
  §6.2/§7).
- kepano source: `github.com/kepano/obsidian-skills` (MIT) — `obsidian-markdown`, `obsidian-bases`,
  `json-canvas`. Attribution belongs in README.
- Existing skills: `tomo/dot_claude/skills/{obsidian-markdown,default-doc-writer,kado-discovery-patterns,obsidian-fields}/`.
- Helper scripts: `tomo/scripts/{kado-write-file.py,read-config-field.py,token-render.py}`,
  `tomo/scripts/lib/{kado_client.py,obsidian_filename.py}`.
- GH issue #46 (template mapping for custom created notes in the inbox).
- Templates: `tomo/config/templates/t_*_tomo.md`.
